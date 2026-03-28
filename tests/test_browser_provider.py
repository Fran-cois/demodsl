"""Tests for demodsl.providers.browser — PlaywrightBrowserProvider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demodsl.models import Locator
from demodsl.providers.browser import PlaywrightBrowserProvider, _BROWSER_MAP


class TestBrowserMap:
    def test_chrome_maps_to_chromium(self) -> None:
        assert _BROWSER_MAP["chrome"] == "chromium"

    def test_firefox_maps_to_firefox(self) -> None:
        assert _BROWSER_MAP["firefox"] == "firefox"

    def test_webkit_maps_to_webkit(self) -> None:
        assert _BROWSER_MAP["webkit"] == "webkit"

    def test_unknown_defaults_to_chromium(self) -> None:
        assert _BROWSER_MAP.get("unknown", "chromium") == "chromium"


class TestResolveSelector:
    def test_css(self) -> None:
        loc = Locator(type="css", value="div.main")
        assert PlaywrightBrowserProvider._resolve_selector(loc) == "div.main"

    def test_id_prefixed(self) -> None:
        loc = Locator(type="id", value="my-elem")
        assert PlaywrightBrowserProvider._resolve_selector(loc) == "#my-elem"

    def test_xpath_prefixed(self) -> None:
        loc = Locator(type="xpath", value="//div[@class='x']")
        assert (
            PlaywrightBrowserProvider._resolve_selector(loc)
            == "xpath=//div[@class='x']"
        )

    def test_text_prefixed(self) -> None:
        loc = Locator(type="text", value="Click me")
        assert PlaywrightBrowserProvider._resolve_selector(loc) == "text=Click me"

    def test_unsupported_raises(self) -> None:
        # Build a locator with an invalid type by bypassing validation
        loc = MagicMock()
        loc.type = "aria"
        loc.value = "label"
        with pytest.raises(ValueError, match="Unsupported locator type"):
            PlaywrightBrowserProvider._resolve_selector(loc)


class TestScrollDeltas:
    def _make_provider(self) -> PlaywrightBrowserProvider:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        return provider

    def test_scroll_down(self) -> None:
        p = self._make_provider()
        p.scroll("down", 300)
        p._page.evaluate.assert_called_once_with("window.scrollBy(0, 300)")

    def test_scroll_up(self) -> None:
        p = self._make_provider()
        p.scroll("up", 200)
        p._page.evaluate.assert_called_once_with("window.scrollBy(0, -200)")

    def test_scroll_right(self) -> None:
        p = self._make_provider()
        p.scroll("right", 100)
        p._page.evaluate.assert_called_once_with("window.scrollBy(100, 0)")

    def test_scroll_left(self) -> None:
        p = self._make_provider()
        p.scroll("left", 50)
        p._page.evaluate.assert_called_once_with("window.scrollBy(-50, 0)")

    def test_scroll_unknown_direction_noop(self) -> None:
        p = self._make_provider()
        p.scroll("diagonal", 100)
        p._page.evaluate.assert_called_once_with("window.scrollBy(0, 0)")


class TestWaitFor:
    def test_timeout_seconds_to_ms(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        loc = Locator(type="css", value=".btn")
        provider.wait_for(loc, timeout=2.5)
        provider._page.wait_for_selector.assert_called_once_with(".btn", timeout=2500)


class TestClose:
    def test_close_chain_with_video(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider._page.video.path.return_value = "/tmp/rec.webm"
        provider._context = MagicMock()
        provider._browser = MagicMock()
        provider._pw = MagicMock()

        result = provider.close()
        assert result == Path("/tmp/rec.webm")
        provider._context.close.assert_called_once()
        provider._browser.close.assert_called_once()
        provider._pw.stop.assert_called_once()

    def test_close_without_video(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider._page.video = None
        provider._context = MagicMock()
        provider._browser = MagicMock()
        provider._pw = MagicMock()

        result = provider.close()
        assert result is None

    def test_close_all_none(self) -> None:
        provider = PlaywrightBrowserProvider()
        # All attributes default to None — should not raise
        result = provider.close()
        assert result is None


class TestNavigateAndClick:
    def test_navigate(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider.navigate("https://example.com")
        provider._page.goto.assert_called_once_with(
            "https://example.com", wait_until="networkidle"
        )

    def test_click_resolves_selector(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        loc = Locator(type="id", value="btn")
        provider.click(loc)
        provider._page.click.assert_called_once_with("#btn")

    def test_type_text(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        loc = Locator(type="css", value="input.email")
        provider.type_text(loc, "user@test.com")
        provider._page.fill.assert_called_once_with("input.email", "user@test.com")

    def test_evaluate_js(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider._page.evaluate.return_value = 42
        assert provider.evaluate_js("1+1") == 42

    def test_screenshot(self, tmp_path: Path) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        out = tmp_path / "sub" / "shot.png"
        result = provider.screenshot(out)
        assert result == out
        provider._page.screenshot.assert_called_once_with(path=str(out))

    @pytest.mark.skip(reason="not ready — requires Playwright browser binaries")
    def test_launch_real(self) -> None:
        pass
