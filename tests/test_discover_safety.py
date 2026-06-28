"""Tests for the authenticated-session safety guard (``demodsl.discover.safety``).

Fully offline and deterministic: no browser, API key or network. They pin the
guarantee that discovery against a signed-in session never fires a destructive
action unless the caller explicitly opts in with ``allow_writes``.
"""

from __future__ import annotations

import pytest

from demodsl.discover.actions import AgentAction
from demodsl.discover.observation import ElementRef, PageObservation
from demodsl.discover.safety import ActionGuard, is_risky_label
from demodsl.discover.search import execute_action
from demodsl.models import Locator

# ── helpers ───────────────────────────────────────────────────────────────────


def _el(
    mark: int, name: str, *, role: str = "button", attrs: str = "", editable: bool = False
) -> ElementRef:
    return ElementRef(
        mark=mark,
        role=role,
        name=name,
        locator=Locator(type="css", value=f"#el{mark}"),
        attrs=attrs,
        editable=editable,
    )


def _obs(*elements: ElementRef) -> PageObservation:
    return PageObservation(
        url="https://app.example.com/dashboard",
        title="Dashboard",
        strategy="axtree",
        elements=list(elements),
    )


# ── is_risky_label (deny-list, EN + FR) ────────────────────────────────────────


@pytest.mark.parametrize(
    "label",
    [
        "Delete account",
        "Delete",
        "Supprimer le compte",
        "Pay now",
        "Checkout",
        "Payer",
        "Buy now",
        "Send message",
        "Envoyer",
        "Submit",
        "Publish post",
        "Log out",
        "Sign out",
        "Déconnexion",
        "Cancel subscription",
        "Annuler",
        "Deactivate account",
        "Désactiver",
        "Wire transfer",
        "Withdraw funds",
        "Confirm",
    ],
)
def test_is_risky_label_true(label: str) -> None:
    assert is_risky_label(label) is True


@pytest.mark.parametrize(
    "label",
    [
        "Pricing",
        "Dashboard",
        "Open menu",
        "Tarifs",
        "Settings",
        "Wireframe",  # must NOT match "wire transfer"
        "Search",
        "Read more",
        "",
    ],
)
def test_is_risky_label_false(label: str) -> None:
    assert is_risky_label(label) is False


# ── ActionGuard.active ─────────────────────────────────────────────────────────


def test_guard_inactive_without_auth() -> None:
    guard = ActionGuard(authenticated=False, allow_writes=False)
    assert guard.active is False
    obs = _obs(_el(0, "Delete account"))
    action = AgentAction(kind="click", mark=0, locator=Locator(type="css", value="#el0"))
    assert guard.evaluate(action, obs) is None


def test_guard_inactive_with_allow_writes() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=True)
    assert guard.active is False
    obs = _obs(_el(0, "Delete account"))
    action = AgentAction(kind="click", mark=0)
    assert guard.evaluate(action, obs) is None


# ── ActionGuard.evaluate on an authenticated session ───────────────────────────


def test_guard_blocks_type_on_auth() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=False)
    obs = _obs(_el(0, "Email", role="textbox", editable=True))
    action = AgentAction(kind="type", mark=0, value="demo")
    reason = guard.evaluate(action, obs)
    assert reason is not None
    assert "write" in reason


def test_guard_blocks_risky_click_on_auth() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=False)
    obs = _obs(_el(0, "Delete account"))
    action = AgentAction(kind="click", mark=0)
    reason = guard.evaluate(action, obs)
    assert reason is not None
    assert "risky" in reason


def test_guard_allows_benign_click_on_auth() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=False)
    obs = _obs(_el(0, "Pricing", role="link"))
    action = AgentAction(kind="click", mark=0)
    assert guard.evaluate(action, obs) is None


def test_guard_matches_risky_attrs_not_just_name() -> None:
    # Visible name is an icon glyph, but the flattened attrs reveal the intent.
    guard = ActionGuard(authenticated=True, allow_writes=False)
    obs = _obs(_el(0, "\U0001f5d1", attrs="aria-label delete item trash"))
    action = AgentAction(kind="click", mark=0)
    assert guard.evaluate(action, obs) is not None


def test_guard_blocks_submit_key_but_allows_navigation_keys() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=False)
    assert guard.evaluate(AgentAction(kind="press_key", key="Enter")) is not None
    assert guard.evaluate(AgentAction(kind="press_key", key="Escape")) is None


def test_guard_allows_readonly_actions_on_auth() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=False)
    assert guard.evaluate(AgentAction(kind="navigate", url="https://app.example.com/x")) is None
    assert guard.evaluate(AgentAction(kind="scroll", direction="down", pixels=720)) is None
    assert guard.evaluate(AgentAction(kind="hover", mark=0)) is None
    assert guard.evaluate(AgentAction(kind="done")) is None


# ── execute_action gate (the actual loop integration point) ────────────────────


class _BoomEnv:
    """A WebEnvironment whose mutating methods must never be called."""

    def current_url(self) -> str:
        return "https://app.example.com/dashboard"

    def click(self, locator: Locator) -> None:
        raise AssertionError("guard must block the click before touching the browser")

    def type_text(self, locator: Locator, value: str) -> None:
        raise AssertionError("guard must block the type before touching the browser")


def test_execute_action_blocked_never_touches_browser() -> None:
    guard = ActionGuard(authenticated=True, allow_writes=False)
    obs = _obs(_el(0, "Delete account"))
    action = AgentAction(kind="click", mark=0, locator=Locator(type="css", value="#el0"))
    result = execute_action(
        _BoomEnv(), action, obs.url, observation=obs, allow_external=True, guard=guard
    )
    assert result.ok is False
    assert "risky" in (result.error or "")


def test_execute_action_without_guard_executes_on_public_site() -> None:
    # Sanity: the same risky click runs when there is no guard (public web).
    calls: list[str] = []

    class _RecEnv:
        def current_url(self) -> str:
            return "https://shop.example.com/"

        def click(self, locator: Locator) -> None:
            calls.append("click")

    obs = _obs(_el(0, "Delete account"))
    action = AgentAction(kind="click", mark=0, locator=Locator(type="css", value="#el0"))
    result = execute_action(_RecEnv(), action, obs.url, observation=obs)
    assert result.ok is True
    assert calls == ["click"]
