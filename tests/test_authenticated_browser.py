"""Tests for demodsl.providers.authenticated_browser.

Covers the two providers backed by an already-authenticated browser
session: CDP attach (``playwright-cdp``) and persistent profile
(``playwright-persistent``).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import Viewport
from demodsl.providers.authenticated_browser import (
    CDPConnectBrowserProvider,
    PersistentProfileBrowserProvider,
    _env_flag,
)
from demodsl.providers.base import BrowserProviderFactory


class TestFactoryRegistration:
    def test_cdp_registered(self) -> None:
        provider = BrowserProviderFactory.create("playwright-cdp")
        assert isinstance(provider, CDPConnectBrowserProvider)

    def test_persistent_registered(self) -> None:
        provider = BrowserProviderFactory.create("playwright-persistent")
        assert isinstance(provider, PersistentProfileBrowserProvider)


class TestEnvFlag:
    @pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy(self, val: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("X", val)
        assert _env_flag("X") is True

    @pytest.mark.parametrize("val", ["0", "false", "no", "off", ""])
    def test_falsey(self, val: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("X", val)
        assert _env_flag("X") is False

    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("X", raising=False)
        assert _env_flag("X", default=True) is True


class TestCDPConnect:
    def _attach(self, monkeypatch: pytest.MonkeyPatch, cdp_url: str | None = None):
        if cdp_url is not None:
            monkeypatch.setenv("DEMODSL_CDP_URL", cdp_url)
        else:
            monkeypatch.delenv("DEMODSL_CDP_URL", raising=False)

        provider = CDPConnectBrowserProvider()
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_browser.contexts = [mock_context]
        mock_context.pages = [mock_page]
        mock_pw.chromium.connect_over_cdp.return_value = mock_browser

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))
        return provider, mock_pw, mock_browser, mock_context, mock_page

    def test_does_not_own_browser(self) -> None:
        assert CDPConnectBrowserProvider._owns_browser is False

    def test_default_cdp_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, mock_pw, *_ = self._attach(monkeypatch, cdp_url=None)
        mock_pw.chromium.connect_over_cdp.assert_called_once_with("http://127.0.0.1:9222")
        assert provider._debug_port == 9222

    def test_custom_cdp_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, mock_pw, *_ = self._attach(monkeypatch, cdp_url="http://127.0.0.1:9333")
        mock_pw.chromium.connect_over_cdp.assert_called_once_with("http://127.0.0.1:9333")
        assert provider._debug_port == 9333

    def test_reuses_existing_context_and_page(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _, mock_context, mock_page = self._attach(monkeypatch)
        assert provider._context is mock_context
        assert provider._page is mock_page
        mock_context.new_page.assert_not_called()

    def test_close_does_not_close_user_browser(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, mock_pw, mock_browser, mock_context, _ = self._attach(monkeypatch)
        provider._cdp_recorder = None
        provider.close()
        mock_context.close.assert_not_called()
        mock_browser.close.assert_not_called()
        mock_pw.stop.assert_called_once()

    def test_connect_failure_stops_playwright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEMODSL_CDP_URL", raising=False)
        provider = CDPConnectBrowserProvider()
        mock_pw = MagicMock()
        mock_pw.chromium.connect_over_cdp.side_effect = RuntimeError("refused")

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            with pytest.raises(RuntimeError, match="Could not attach"):
                provider.launch_without_recording("chrome", Viewport(width=1280, height=720))
        mock_pw.stop.assert_called_once()


class TestPersistentProfile:
    def test_owns_browser(self) -> None:
        assert PersistentProfileBrowserProvider._owns_browser is True

    def test_requires_user_data_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEMODSL_USER_DATA_DIR", raising=False)
        provider = PersistentProfileBrowserProvider()
        with pytest.raises(RuntimeError, match="DEMODSL_USER_DATA_DIR"):
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))

    def test_launch_uses_persistent_context(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("DEMODSL_USER_DATA_DIR", str(tmp_path / "profile"))
        monkeypatch.delenv("DEMODSL_BROWSER_HEADLESS", raising=False)
        provider = PersistentProfileBrowserProvider()
        mock_pw = MagicMock()
        mock_context = MagicMock()
        mock_context.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_context

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))

        mock_pw.chromium.launch_persistent_context.assert_called_once()
        call = mock_pw.chromium.launch_persistent_context.call_args
        # First positional arg is the profile dir.
        assert call.args[0] == str(tmp_path / "profile")
        # Default channel is real Chrome.
        assert call.kwargs.get("channel") == "chrome"
        # Headed by default (no --headless=new flag).
        assert "--headless=new" not in call.kwargs["args"]

    def test_headless_flag_adds_arg(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("DEMODSL_USER_DATA_DIR", str(tmp_path / "profile"))
        monkeypatch.setenv("DEMODSL_BROWSER_HEADLESS", "1")
        provider = PersistentProfileBrowserProvider()
        mock_pw = MagicMock()
        mock_context = MagicMock()
        mock_context.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_context

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))

        call = mock_pw.chromium.launch_persistent_context.call_args
        assert "--headless=new" in call.kwargs["args"]

    def test_channel_override_empty_uses_chromium(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("DEMODSL_USER_DATA_DIR", str(tmp_path / "profile"))
        monkeypatch.setenv("DEMODSL_CHROME_CHANNEL", "")
        provider = PersistentProfileBrowserProvider()
        mock_pw = MagicMock()
        mock_context = MagicMock()
        mock_context.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_context

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))

        call = mock_pw.chromium.launch_persistent_context.call_args
        assert "channel" not in call.kwargs


class TestRestartWithRecordingInPlace:
    def test_sets_warm_url_without_recreating_context(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        provider = CDPConnectBrowserProvider()
        mock_page = MagicMock()
        mock_page.url = "https://app.example.com/login"
        mock_context = MagicMock()
        provider._page = mock_page
        provider._context = mock_context
        provider._viewport = {"width": 1280, "height": 720}
        provider._debug_port = 9222

        with patch.object(provider, "_start_cdp_recording", return_value=True) as rec:
            provider.restart_with_recording(tmp_path / "video")

        rec.assert_called_once()
        assert provider._warm_url == "https://app.example.com/login"
        # Existing context must be reused — never recreated.
        mock_context.close.assert_not_called()


class TestPerScenarioAuthConfig:
    """scenario.auth overrides DEMODSL_* env vars (enables multi-browser)."""

    def test_cdp_url_from_auth_config_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEMODSL_CDP_URL", "http://127.0.0.1:9222")
        provider = CDPConnectBrowserProvider()
        provider.set_auth_config({"cdp_url": "http://127.0.0.1:9444"})
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_ctx = MagicMock()
        mock_browser.contexts = [mock_ctx]
        mock_ctx.pages = [MagicMock()]
        mock_pw.chromium.connect_over_cdp.return_value = mock_browser

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=800, height=600))

        mock_pw.chromium.connect_over_cdp.assert_called_once_with("http://127.0.0.1:9444")
        assert provider._debug_port == 9444

    def test_persistent_user_data_dir_from_auth(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # No env var — config must come from auth alone.
        monkeypatch.delenv("DEMODSL_USER_DATA_DIR", raising=False)
        prof = tmp_path / "acct_b"
        provider = PersistentProfileBrowserProvider()
        provider.set_auth_config(
            {"user_data_dir": str(prof), "channel": "msedge", "headless": True}
        )
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_ctx

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=800, height=600))

        call = mock_pw.chromium.launch_persistent_context.call_args
        assert call.args[0] == str(prof)
        assert call.kwargs.get("channel") == "msedge"  # Edge engine
        assert "--headless=new" in call.kwargs["args"]

    def test_none_values_in_auth_fall_back_to_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("DEMODSL_USER_DATA_DIR", str(tmp_path / "envdir"))
        provider = PersistentProfileBrowserProvider()
        # Mirrors model_dump() of a partial auth block.
        provider.set_auth_config({"user_data_dir": None, "channel": None})
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_ctx

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=800, height=600))

        call = mock_pw.chromium.launch_persistent_context.call_args
        assert call.args[0] == str(tmp_path / "envdir")

    def test_isolate_clones_profile(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        src = tmp_path / "real_profile"
        src.mkdir()
        (src / "Cookies").write_text("session", encoding="utf-8")
        provider = PersistentProfileBrowserProvider()
        provider.set_auth_config({"user_data_dir": str(src), "isolate": True})
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_ctx

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=800, height=600))

        used_dir = Path(mock_pw.chromium.launch_persistent_context.call_args.args[0])
        assert used_dir != src  # a clone, not the original
        assert provider._cloned_profile == used_dir
        assert (used_dir / "Cookies").read_text() == "session"  # session preserved


class TestMakeBrowserAppliesAuth:
    """The orchestrator helper wires scenario.auth into the provider."""

    def test_make_browser_sets_auth_config(self) -> None:
        from demodsl.models import Scenario
        from demodsl.orchestrators.scenario import ScenarioOrchestrator

        scenario = Scenario(
            name="s",
            url="https://app.example.com",
            provider="playwright-cdp",
            auth={"cdp_url": "http://127.0.0.1:9555"},
        )
        browser = ScenarioOrchestrator._make_browser(scenario)
        assert isinstance(browser, CDPConnectBrowserProvider)
        assert browser._auth.get("cdp_url") == "http://127.0.0.1:9555"

    def test_make_browser_without_auth_is_noop(self) -> None:
        from demodsl.models import Scenario
        from demodsl.orchestrators.scenario import ScenarioOrchestrator

        scenario = Scenario(name="s", url="https://app.example.com", provider="playwright-cdp")
        browser = ScenarioOrchestrator._make_browser(scenario)
        assert browser._auth == {}
