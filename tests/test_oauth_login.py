"""Tests for demodsl.oauth governance and the oauth_login command/state machine."""

from __future__ import annotations

import warnings

import pytest

from demodsl.commands import OAuthLoginCommand, get_command
from demodsl.models import Locator, OAuthPolicy, Step
from demodsl.oauth import (
    OAuthGovernanceError,
    check_scopes,
    resolve_provider_profile,
)


class TestProviderProfiles:
    def test_known_providers(self) -> None:
        for name in ("google", "microsoft", "github", "generic"):
            assert resolve_provider_profile(name).name == name

    def test_unknown_falls_back_to_generic(self) -> None:
        assert resolve_provider_profile("okta").name == "generic"
        assert resolve_provider_profile(None).name == "generic"


class TestCheckScopes:
    def test_no_policy_allows(self) -> None:
        v = check_scopes(["see your name"], "see your name", None, None)
        assert v.ok

    def test_denied_substring_in_page_text_vetoes(self) -> None:
        v = check_scopes([], "This app wants to access your Google Drive", None, ["Drive"])
        assert not v.ok
        assert "Drive" in v.reason

    def test_denied_substring_in_scope_row_vetoes(self) -> None:
        v = check_scopes(["Delete your account"], "", None, ["delete"])
        assert not v.ok

    def test_denied_case_insensitive(self) -> None:
        v = check_scopes([], "manage your CONTACTS", None, ["manage your contacts"])
        assert not v.ok

    def test_allowlist_passes_when_all_match(self) -> None:
        v = check_scopes(
            ["See your name", "See your email address"],
            "page",
            ["name", "email address"],
            None,
        )
        assert v.ok

    def test_allowlist_vetoes_unlisted_permission(self) -> None:
        v = check_scopes(
            ["See your name", "Read your calendar"],
            "page",
            ["name", "email"],
            None,
        )
        assert not v.ok
        assert "calendar" in v.reason.lower()

    def test_allowlist_fails_closed_when_no_scopes_read(self) -> None:
        v = check_scopes([], "opaque consent screen", ["name"], None)
        assert not v.ok
        assert "fail-closed" in v.reason

    def test_denied_takes_precedence_over_allowed(self) -> None:
        v = check_scopes(
            ["Drive access"],
            "Drive access",
            ["Drive access"],  # even if allowlisted...
            ["Drive"],  # ...deny wins
        )
        assert not v.ok


class TestStepModelValidation:
    def test_oauth_login_minimal_parses(self) -> None:
        step = Step(action="oauth_login")
        assert step.action == "oauth_login"
        assert step.oauth is None

    def test_oauth_login_with_policy(self) -> None:
        step = Step(
            action="oauth_login",
            locator=Locator(type="text", value="Continue with Google"),
            timeout=90,
            oauth=OAuthPolicy(
                provider="google",
                account_email="me@example.com",
                success_host="app.acme.com",
                denied_scopes=["Drive"],
            ),
        )
        assert step.oauth.provider == "google"
        assert step.oauth.denied_scopes == ["Drive"]

    def test_success_host_rejects_url(self) -> None:
        with pytest.raises(ValueError):
            OAuthPolicy(success_host="https://app.acme.com/login")

    def test_overlap_allow_deny_rejected(self) -> None:
        with pytest.raises(ValueError):
            Step(
                action="oauth_login",
                oauth=OAuthPolicy(allowed_scopes=["Drive"], denied_scopes=["drive"]),
            )

    def test_get_command_returns_oauth_command(self) -> None:
        assert isinstance(get_command("oauth_login"), OAuthLoginCommand)


class _FakeBrowser:
    """Scripts a sequence of probe results to drive the state machine."""

    def __init__(self, states: list[dict]) -> None:
        self._states = states
        self._i = 0
        self.clicks: list = []
        self.js_calls: list[str] = []
        self.hostname = "app.acme.com"

    def click(self, locator) -> None:  # noqa: ANN001
        self.clicks.append(locator)

    def evaluate_js(self, script: str):  # noqa: ANN001
        self.js_calls.append(script)
        # location.hostname capture
        if "location.hostname" in script and "function" not in script:
            return self.hostname
        # click helpers return a string label
        if "click()" in script and "state" not in script:
            return "clicked"
        # probe returns the next scripted state
        if self._i < len(self._states):
            st = self._states[self._i]
            self._i += 1
            return st
        return self._states[-1]


def _run(states: list[dict], policy: OAuthPolicy | None = None, locator=None):  # noqa: ANN001
    cmd = OAuthLoginCommand()
    step = Step(action="oauth_login", locator=locator, oauth=policy, timeout=10)
    browser = _FakeBrowser(states)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = cmd.execute(browser, step)
    return result, browser


class TestOAuthLoginStateMachine:
    def test_direct_success(self) -> None:
        states = [{"state": "success", "url": "https://app.acme.com/home", "host": "app.acme.com"}]
        result, _ = _run(states)
        assert result == "https://app.acme.com/home"

    def test_account_then_consent_then_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
        states = [
            {"state": "account", "url": "u", "host": "accounts.google.com"},
            {
                "state": "consent",
                "url": "u",
                "host": "accounts.google.com",
                "scopes": ["See your name"],
                "text": "see your name",
            },
            {"state": "success", "url": "https://app.acme.com/onboarding", "host": "app.acme.com"},
        ]
        policy = OAuthPolicy(success_host="app.acme.com")
        result, browser = _run(states, policy)
        assert result == "https://app.acme.com/onboarding"

    def test_consent_denied_scope_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
        states = [
            {
                "state": "consent",
                "url": "u",
                "host": "accounts.google.com",
                "scopes": ["Access your Google Drive"],
                "text": "access your google drive",
            },
        ]
        policy = OAuthPolicy(success_host="app.acme.com", denied_scopes=["Drive"])
        with pytest.raises(OAuthGovernanceError, match="Drive"):
            _run(states, policy)

    def test_credentials_abort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
        states = [{"state": "credentials", "url": "u", "host": "accounts.google.com"}]
        policy = OAuthPolicy(success_host="app.acme.com", on_credentials="abort")
        with pytest.raises(OAuthGovernanceError, match="setup-login"):
            _run(states, policy)

    def test_2fa_abort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
        states = [{"state": "challenge", "url": "u", "host": "accounts.google.com"}]
        policy = OAuthPolicy(success_host="app.acme.com", on_2fa="abort")
        with pytest.raises(OAuthGovernanceError, match="2FA"):
            _run(states, policy)

    def test_clicks_social_button_when_locator_given(self) -> None:
        states = [{"state": "success", "url": "https://app.acme.com/", "host": "app.acme.com"}]
        loc = Locator(type="text", value="Continue with Google")
        _result, browser = _run(states, OAuthPolicy(success_host="app.acme.com"), locator=loc)
        assert browser.clicks == [loc]
