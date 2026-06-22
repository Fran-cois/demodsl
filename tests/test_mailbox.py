"""Tests for demodsl.mailbox and the await_email command."""

from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from demodsl.commands import EmailVerifyCommand, get_command
from demodsl.mailbox import (
    extract_code,
    extract_link,
    message_text,
    resolve_mailbox_config,
)
from demodsl.models import Locator, Step


class TestResolveMailboxConfig:
    def test_scenario_values_win_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEMODSL_IMAP_HOST", "env.example.com")
        cfg = resolve_mailbox_config(
            {
                "imap_host": "imap.acme.com",
                "username": "bot@acme.com",
                "password": "secret",
            }
        )
        assert cfg["imap_host"] == "imap.acme.com"
        assert cfg["imap_port"] == 993
        assert cfg["use_ssl"] is True
        assert cfg["folder"] == "INBOX"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEMODSL_IMAP_HOST", "imap.gmail.com")
        monkeypatch.setenv("DEMODSL_IMAP_USER", "bot@gmail.com")
        monkeypatch.setenv("DEMODSL_IMAP_PASSWORD", "app-password")
        monkeypatch.setenv("DEMODSL_IMAP_PORT", "1993")
        cfg = resolve_mailbox_config(None)
        assert cfg["imap_host"] == "imap.gmail.com"
        assert cfg["username"] == "bot@gmail.com"
        assert cfg["password"] == "app-password"
        assert cfg["imap_port"] == 1993

    def test_missing_credentials_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("DEMODSL_IMAP_HOST", "DEMODSL_IMAP_USER", "DEMODSL_IMAP_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError, match="missing mailbox credentials"):
            resolve_mailbox_config({"imap_host": "imap.acme.com"})

    def test_ssl_disabled_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEMODSL_IMAP_SSL", "false")
        cfg = resolve_mailbox_config({"imap_host": "h", "username": "u", "password": "p"})
        assert cfg["use_ssl"] is False


class TestExtractors:
    def test_extract_link_first(self) -> None:
        text = "Welcome! Visit https://app.acme.com/home for more."
        assert extract_link(text) == "https://app.acme.com/home"

    def test_extract_link_filtered_by_contains(self) -> None:
        text = (
            "Unsubscribe: https://acme.com/unsub\n"
            "Confirm here: https://acme.com/verify?token=abc123\n"
        )
        assert extract_link(text, contains="verify") == "https://acme.com/verify?token=abc123"

    def test_extract_link_strips_trailing_punctuation(self) -> None:
        text = "Go to https://acme.com/confirm/xyz."
        assert extract_link(text) == "https://acme.com/confirm/xyz"

    def test_extract_link_none(self) -> None:
        assert extract_link("no links here") is None

    def test_extract_code_default(self) -> None:
        assert extract_code("Your code is 482915 — enjoy") == "482915"

    def test_extract_code_custom_pattern(self) -> None:
        assert extract_code("PIN: AB-7788", pattern=r"AB-(\d{4})") == "7788"

    def test_extract_code_none(self) -> None:
        assert extract_code("no digits at all") is None


class TestMessageText:
    def test_plain_message(self) -> None:
        msg = EmailMessage()
        msg["Subject"] = "Confirm your account"
        msg.set_content("Click https://acme.com/verify?t=1 to confirm.")
        body = message_text(msg)
        assert "https://acme.com/verify?t=1" in body

    def test_multipart_keeps_html_href(self) -> None:
        msg = EmailMessage()
        msg["Subject"] = "Verify"
        msg.set_content("plain fallback")
        msg.add_alternative(
            '<a href="https://acme.com/verify?token=zzz">Confirm</a>', subtype="html"
        )
        body = message_text(msg)
        assert "https://acme.com/verify?token=zzz" in body


def _make_email(subject: str, sender: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg.set_content(body)
    return msg


class TestEmailVerifyCommand:
    def test_get_command_returns_email_verify(self) -> None:
        cmd = get_command("await_email", mailbox={"imap_host": "h"})
        assert isinstance(cmd, EmailVerifyCommand)

    def test_link_extraction_navigates(self) -> None:
        msg = _make_email(
            "Confirm your account",
            "noreply@acme.com",
            "Welcome! Confirm: https://acme.com/verify?token=abc",
        )
        step = Step(
            action="await_email",
            email_subject="Confirm",
            email_link_contains="verify",
            timeout=5,
        )
        cmd = EmailVerifyCommand(mailbox={"imap_host": "h", "username": "u", "password": "p"})
        browser = MagicMock()

        with patch("demodsl.mailbox.MailboxClient") as MockClient:
            inst = MockClient.return_value.__enter__.return_value
            inst.wait_for_message.return_value = msg
            result = cmd.execute(browser, step)

        assert result == "https://acme.com/verify?token=abc"
        browser.navigate.assert_called_once_with("https://acme.com/verify?token=abc")

    def test_code_extraction_fills_field(self) -> None:
        msg = _make_email("Your code", "noreply@acme.com", "Code: 246810")
        step = Step(
            action="await_email",
            email_extract="code",
            locator=Locator(type="css", value="#otp"),
            timeout=5,
        )
        cmd = EmailVerifyCommand(mailbox={"imap_host": "h", "username": "u", "password": "p"})
        browser = MagicMock()

        with patch("demodsl.mailbox.MailboxClient") as MockClient:
            inst = MockClient.return_value.__enter__.return_value
            inst.wait_for_message.return_value = msg
            result = cmd.execute(browser, step)

        assert result == "246810"
        browser.type_text.assert_called_once()
        args = browser.type_text.call_args.args
        assert args[1] == "246810"

    def test_missing_credentials_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("DEMODSL_IMAP_HOST", "DEMODSL_IMAP_USER", "DEMODSL_IMAP_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        step = Step(action="await_email", timeout=5)
        cmd = EmailVerifyCommand(mailbox=None)
        with pytest.raises(RuntimeError, match="missing mailbox credentials"):
            cmd.execute(MagicMock(), step)

    def test_no_link_found_raises(self) -> None:
        msg = _make_email("Confirm", "noreply@acme.com", "no links in this body")
        step = Step(action="await_email", timeout=5)
        cmd = EmailVerifyCommand(mailbox={"imap_host": "h", "username": "u", "password": "p"})
        with patch("demodsl.mailbox.MailboxClient") as MockClient:
            inst = MockClient.return_value.__enter__.return_value
            inst.wait_for_message.return_value = msg
            with pytest.raises(RuntimeError, match="no confirmation link"):
                cmd.execute(MagicMock(), step)


class TestStepModelValidation:
    def test_code_without_locator_rejected(self) -> None:
        with pytest.raises(ValueError, match="requires 'locator'"):
            Step(action="await_email", email_extract="code")

    def test_link_mode_needs_no_locator(self) -> None:
        step = Step(action="await_email", email_subject="Confirm")
        assert step.action == "await_email"

    def test_await_email_rejected_in_mobile_scenario(self) -> None:
        from demodsl.models import Scenario
        from demodsl.models.mobile import MobileConfig

        with pytest.raises(ValueError, match="browser-only action"):
            Scenario(
                name="m",
                mobile=MobileConfig(
                    platform="ios", device_name="iPhone 15", bundle_id="com.acme.app"
                ),
                steps=[Step(action="await_email")],
            )
