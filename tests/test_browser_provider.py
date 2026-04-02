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
        calls = [c.args[0] for c in p._page.evaluate.call_args_list]
        assert "window.scrollBy(100, 0)" in calls

    def test_scroll_left(self) -> None:
        p = self._make_provider()
        p.scroll("left", 50)
        calls = [c.args[0] for c in p._page.evaluate.call_args_list]
        assert "window.scrollBy(-50, 0)" in calls

    def test_scroll_unknown_direction_noop(self) -> None:
        p = self._make_provider()
        p.scroll("diagonal", 100)
        # No horizontal delta, so no unlock/lock — just scrollBy
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


class TestLockHorizontalScroll:
    def test_lock_injects_style_tag(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider._lock_horizontal_scroll()
        provider._page.evaluate.assert_called_once()
        js = provider._page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js
        assert "overflow-x" in js
        assert "clip" in js

    def test_unlock_removes_style_tag(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider._unlock_horizontal_scroll()
        provider._page.evaluate.assert_called_once()
        js = provider._page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js
        assert "remove" in js

    def test_navigate_calls_lock(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider.navigate("https://example.com")
        # evaluate is called once for the horizontal-scroll lock
        provider._page.evaluate.assert_called_once()
        js = provider._page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js

    def test_restart_with_recording_calls_lock(self) -> None:
        provider = PlaywrightBrowserProvider()
        mock_browser = MagicMock()
        new_context = MagicMock()
        new_page = MagicMock()
        mock_browser.new_context.return_value = new_context
        new_context.new_page.return_value = new_page

        provider._browser = mock_browser
        provider._context = MagicMock()
        provider._page = MagicMock(url="about:blank")
        provider._viewport = {"width": 1280, "height": 720}
        provider._color_scheme = None
        provider._locale = None

        provider.restart_with_recording(Path("/tmp/video"))

        # The new page should have the style tag injected
        new_page.evaluate.assert_called_once()
        js = new_page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js
        assert "clip" in js

    def test_restart_locks_after_goto(self) -> None:
        """When restart navigates to a URL, the lock is applied after goto."""
        provider = PlaywrightBrowserProvider()
        mock_browser = MagicMock()
        new_context = MagicMock()
        new_page = MagicMock()
        mock_browser.new_context.return_value = new_context
        new_context.new_page.return_value = new_page

        provider._browser = mock_browser
        provider._context = MagicMock()
        provider._page = MagicMock(url="https://example.com/page")
        provider._viewport = {"width": 1280, "height": 720}
        provider._color_scheme = None
        provider._locale = None

        provider.restart_with_recording(Path("/tmp/video"))

        # goto called first, then evaluate for lock
        new_page.goto.assert_called_once()
        new_page.evaluate.assert_called_once()
        js = new_page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js

    def test_scroll_right_unlocks_then_relocks(self) -> None:
        """Horizontal scroll temporarily removes the lock."""
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider.scroll("right", 200)
        calls = provider._page.evaluate.call_args_list
        assert len(calls) == 3  # unlock, scrollBy, lock
        assert "remove" in calls[0].args[0]
        assert "scrollBy" in calls[1].args[0]
        assert "__demodsl_hscroll_lock" in calls[2].args[0]

    def test_scroll_left_unlocks_then_relocks(self) -> None:
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider.scroll("left", 100)
        calls = provider._page.evaluate.call_args_list
        assert len(calls) == 3
        assert "remove" in calls[0].args[0]
        assert "scrollBy" in calls[1].args[0]

    def test_scroll_down_no_unlock(self) -> None:
        """Vertical scroll should not unlock horizontal."""
        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider.scroll("down", 300)
        calls = provider._page.evaluate.call_args_list
        assert len(calls) == 1  # only scrollBy
        assert "scrollBy" in calls[0].args[0]


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


class TestLaunchContextOptions:
    """Verify color_scheme and locale are forwarded to new_context."""

    def _launch_with(self, *, color_scheme=None, locale=None):
        from unittest.mock import patch

        provider = PlaywrightBrowserProvider()
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            from demodsl.models import Viewport

            provider.launch(
                "chrome",
                Viewport(width=1280, height=720),
                Path("/tmp/vid"),
                color_scheme=color_scheme,
                locale=locale,
            )
        return mock_browser.new_context.call_args

    def test_no_color_scheme_no_locale(self) -> None:
        call = self._launch_with()
        kwargs = call.kwargs
        assert "color_scheme" not in kwargs
        assert "locale" not in kwargs

    def test_color_scheme_light(self) -> None:
        call = self._launch_with(color_scheme="light")
        assert call.kwargs["color_scheme"] == "light"

    def test_color_scheme_dark(self) -> None:
        call = self._launch_with(color_scheme="dark")
        assert call.kwargs["color_scheme"] == "dark"

    def test_locale_set(self) -> None:
        call = self._launch_with(locale="fr-FR")
        assert call.kwargs["locale"] == "fr-FR"

    def test_both_set(self) -> None:
        call = self._launch_with(color_scheme="light", locale="en-US")
        assert call.kwargs["color_scheme"] == "light"
        assert call.kwargs["locale"] == "en-US"

    def test_launch_calls_lock(self) -> None:
        """launch() should call _lock_horizontal_scroll on the new page."""
        from unittest.mock import patch

        provider = PlaywrightBrowserProvider()
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value.new_page.return_value = mock_page

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            from demodsl.models import Viewport

            provider.launch(
                "chrome", Viewport(width=1280, height=720), Path("/tmp/vid")
            )

        mock_page.evaluate.assert_called_once()
        js = mock_page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js


class TestLaunchWithoutRecording:
    """Verify launch_without_recording does not pass record_video_dir."""

    def _launch_no_rec(self, *, color_scheme=None, locale=None):
        from unittest.mock import patch

        provider = PlaywrightBrowserProvider()
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            from demodsl.models import Viewport

            provider.launch_without_recording(
                "chrome",
                Viewport(width=1280, height=720),
                color_scheme=color_scheme,
                locale=locale,
            )
        return provider, mock_browser

    def test_no_record_video_dir(self) -> None:
        _, mock_browser = self._launch_no_rec()
        ctx_kwargs = mock_browser.new_context.call_args.kwargs
        assert "record_video_dir" not in ctx_kwargs
        assert "record_video_size" not in ctx_kwargs

    def test_viewport_is_set(self) -> None:
        _, mock_browser = self._launch_no_rec()
        ctx_kwargs = mock_browser.new_context.call_args.kwargs
        assert ctx_kwargs["viewport"] == {"width": 1280, "height": 720}

    def test_color_scheme_forwarded(self) -> None:
        _, mock_browser = self._launch_no_rec(color_scheme="dark")
        ctx_kwargs = mock_browser.new_context.call_args.kwargs
        assert ctx_kwargs["color_scheme"] == "dark"

    def test_locale_forwarded(self) -> None:
        _, mock_browser = self._launch_no_rec(locale="ja-JP")
        ctx_kwargs = mock_browser.new_context.call_args.kwargs
        assert ctx_kwargs["locale"] == "ja-JP"

    def test_launch_without_recording_calls_lock(self) -> None:
        """launch_without_recording() should also lock horizontal scroll."""
        provider, mock_browser = self._launch_no_rec()
        mock_page = mock_browser.new_context.return_value.new_page.return_value
        mock_page.evaluate.assert_called_once()
        js = mock_page.evaluate.call_args.args[0]
        assert "__demodsl_hscroll_lock" in js

    def test_stores_viewport_for_restart(self) -> None:
        provider, _ = self._launch_no_rec()
        assert provider._viewport == {"width": 1280, "height": 720}


class TestRestartWithRecording:
    """Verify restart_with_recording opens a new context with recording."""

    def test_restart_enables_recording(self) -> None:
        provider = PlaywrightBrowserProvider()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.url = "https://example.com/page"
        mock_browser = MagicMock()
        new_context = MagicMock()
        new_page = MagicMock()
        mock_browser.new_context.return_value = new_context
        new_context.new_page.return_value = new_page

        provider._browser = mock_browser
        provider._context = mock_context
        provider._page = mock_page
        provider._viewport = {"width": 1280, "height": 720}
        provider._color_scheme = None
        provider._locale = None

        provider.restart_with_recording(Path("/tmp/video"))

        # Old context closed
        mock_context.close.assert_called_once()
        # New context has recording
        ctx_kwargs = mock_browser.new_context.call_args.kwargs
        assert ctx_kwargs["record_video_dir"] == "/tmp/video"
        assert ctx_kwargs["record_video_size"] == {"width": 1280, "height": 720}
        # Navigated to current URL
        new_page.goto.assert_called_once_with(
            "https://example.com/page", wait_until="networkidle"
        )
        assert provider._page is new_page
        assert provider._context is new_context

    def test_restart_preserves_color_scheme_and_locale(self) -> None:
        provider = PlaywrightBrowserProvider()
        mock_browser = MagicMock()
        new_context = MagicMock()
        new_context.new_page.return_value = MagicMock(url="about:blank")
        mock_browser.new_context.return_value = new_context

        provider._browser = mock_browser
        provider._context = MagicMock()
        provider._page = MagicMock(url="about:blank")
        provider._viewport = {"width": 800, "height": 600}
        provider._color_scheme = "dark"
        provider._locale = "fr-FR"

        provider.restart_with_recording(Path("/tmp/video"))

        ctx_kwargs = mock_browser.new_context.call_args.kwargs
        assert ctx_kwargs["color_scheme"] == "dark"
        assert ctx_kwargs["locale"] == "fr-FR"

    def test_restart_skips_goto_for_about_blank(self) -> None:
        provider = PlaywrightBrowserProvider()
        mock_browser = MagicMock()
        new_context = MagicMock()
        new_page = MagicMock()
        mock_browser.new_context.return_value = new_context
        new_context.new_page.return_value = new_page

        provider._browser = mock_browser
        provider._context = MagicMock()
        provider._page = MagicMock(url="about:blank")
        provider._viewport = {"width": 1280, "height": 720}
        provider._color_scheme = None
        provider._locale = None

        provider.restart_with_recording(Path("/tmp/video"))

        # Should NOT navigate since page is about:blank
        new_page.goto.assert_not_called()

    def test_restart_skips_goto_when_no_page(self) -> None:
        provider = PlaywrightBrowserProvider()
        mock_browser = MagicMock()
        new_context = MagicMock()
        new_page = MagicMock()
        mock_browser.new_context.return_value = new_context
        new_context.new_page.return_value = new_page

        provider._browser = mock_browser
        provider._context = MagicMock()
        provider._page = None
        provider._viewport = {"width": 1280, "height": 720}
        provider._color_scheme = None
        provider._locale = None

        provider.restart_with_recording(Path("/tmp/video"))

        new_page.goto.assert_not_called()
