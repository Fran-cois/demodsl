"""Tests for AppiumMobileProvider with mocked Appium driver."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import Locator, MobileConfig
from demodsl.providers.base import MobileProviderFactory

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_mock_appium_modules() -> dict[str, types.ModuleType]:
    """Create mock appium modules so we can import mobile.py without Appium."""
    appium_mod = types.ModuleType("appium")
    webdriver_mod = types.ModuleType("appium.webdriver")
    options_mod = types.ModuleType("appium.options")
    android_opts = types.ModuleType("appium.options.android")
    ios_opts = types.ModuleType("appium.options.ios")

    android_opts.UiAutomator2Options = MagicMock  # type: ignore[attr-defined]
    ios_opts.XCUITestOptions = MagicMock  # type: ignore[attr-defined]
    webdriver_mod.Remote = MagicMock  # type: ignore[attr-defined]

    appium_mod.webdriver = webdriver_mod  # type: ignore[attr-defined]
    appium_mod.options = options_mod  # type: ignore[attr-defined]

    return {
        "appium": appium_mod,
        "appium.webdriver": webdriver_mod,
        "appium.options": options_mod,
        "appium.options.android": android_opts,
        "appium.options.ios": ios_opts,
    }


@pytest.fixture()
def _patch_appium():
    """Patch appium modules into sys.modules for the duration of a test."""
    mocks = _make_mock_appium_modules()
    with patch.dict(sys.modules, mocks):
        yield


# ── _build_locator_args / _xpath_quote ────────────────────────────────────────


class TestBuildLocatorArgs:
    """Test locator strategy mapping and XPath safety."""

    def _import_build(self):
        from demodsl.providers.mobile import _build_locator_args

        return _build_locator_args

    def test_accessibility_id(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="accessibility_id", value="loginBtn"))
        assert by == "accessibility id"
        assert value == "loginBtn"

    def test_xpath_passthrough(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="xpath", value="//android.widget.Button"))
        assert by == "xpath"
        assert value == "//android.widget.Button"

    def test_text_no_quotes(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="text", value="Sign In"))
        assert by == "xpath"
        assert "'Sign In'" in value
        assert "contains(@text" in value
        assert "contains(@content-desc" in value

    def test_text_with_single_quote(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="text", value="it's here"))
        assert by == "xpath"
        # Must use concat or double-quotes — never bare backslash-escaped
        assert "\\'" not in value
        # Value should contain the text in some quoted form
        assert "it" in value and "here" in value

    def test_text_with_double_quote(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="text", value='say "hello"'))
        assert by == "xpath"
        # Uses single-quote wrapping since no single-quotes present
        assert "'say \"hello\"'" in value

    def test_text_with_both_quotes(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="text", value="""it's "fancy" """))
        assert by == "xpath"
        # Must use concat()
        assert "concat(" in value
        assert "\\'" not in value

    def test_unsupported_locator_type(self) -> None:
        build = self._import_build()
        # Create a locator with a valid type then force an unsupported one
        loc = Locator(type="id", value="x")
        object.__setattr__(loc, "type", "name")
        with pytest.raises(ValueError, match="Unsupported"):
            build(loc)

    def test_android_uiautomator(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="android_uiautomator", value='new UiSelector().text("OK")'))
        assert by == "-android uiautomator"

    def test_ios_predicate(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="ios_predicate", value="label == 'Done'"))
        assert by == "-ios predicate string"

    def test_ios_class_chain(self) -> None:
        build = self._import_build()
        by, value = build(Locator(type="ios_class_chain", value="**/XCUIElementTypeButton"))
        assert by == "-ios class chain"


# ── XPath quote function ─────────────────────────────────────────────────────


class TestXPathQuote:
    def _import_quote(self):
        from demodsl.providers.mobile import _xpath_quote

        return _xpath_quote

    def test_simple_string(self) -> None:
        q = self._import_quote()
        assert q("hello") == "'hello'"

    def test_string_with_single_quote(self) -> None:
        q = self._import_quote()
        result = q("it's")
        assert result == '"it\'s"'

    def test_string_with_double_quote(self) -> None:
        q = self._import_quote()
        result = q('say "hi"')
        assert result == "'say \"hi\"'"

    def test_string_with_both_quotes(self) -> None:
        q = self._import_quote()
        result = q("""it's "fancy" """)
        assert result.startswith("concat(")
        assert "'" not in result.split("concat(")[0]  # no bare quotes outside


# ── AppiumMobileProvider ─────────────────────────────────────────────────────


class TestAppiumMobileProvider:
    @pytest.fixture()
    def provider(self, _patch_appium):
        from demodsl.providers.mobile import AppiumMobileProvider

        return AppiumMobileProvider()

    @pytest.fixture()
    def launched_provider(self, provider, tmp_path):
        """Provider with a mocked driver ready to use."""
        cfg = MobileConfig(
            platform="android",
            device_name="Pixel 7",
            app_package="com.example.app",
        )
        provider.launch(cfg, video_dir=tmp_path)
        return provider

    def test_instantiation(self, provider) -> None:
        assert provider._driver is None
        assert provider._recording is False

    def test_launch_sets_driver(self, launched_provider) -> None:
        assert launched_provider._driver is not None
        assert launched_provider._recording is True

    def test_close_calls_quit(self, launched_provider) -> None:
        driver = launched_provider._driver
        driver.stop_recording_screen.return_value = ""
        launched_provider.close()
        driver.quit.assert_called_once()
        assert launched_provider._driver is None

    def test_close_without_launch(self, provider) -> None:
        result = provider.close()
        assert result is None

    def test_back_delegates(self, launched_provider) -> None:
        launched_provider.back()
        launched_provider._driver.back.assert_called_once()

    def test_home_android_uses_keycode(self, launched_provider) -> None:
        launched_provider.home()
        launched_provider._driver.press_keycode.assert_called_once_with(3)

    def test_home_ios_uses_script(self, _patch_appium, tmp_path) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        p = AppiumMobileProvider()
        cfg = MobileConfig(
            platform="ios",
            device_name="iPhone 15",
            bundle_id="com.example.app",
        )
        p.launch(cfg, video_dir=tmp_path)
        p.home()
        p._driver.execute_script.assert_called_with("mobile: pressButton", {"name": "home"})

    def test_app_switch_android_uses_keycode(self, launched_provider) -> None:
        launched_provider.app_switch()
        launched_provider._driver.press_keycode.assert_called_once_with(187)

    def test_shake_delegates(self, launched_provider) -> None:
        launched_provider.shake()
        launched_provider._driver.shake.assert_called_once()

    def test_rotate_portrait(self, launched_provider) -> None:
        launched_provider.rotate("portrait")
        assert launched_provider._driver.orientation == "PORTRAIT"

    def test_rotate_landscape(self, launched_provider) -> None:
        launched_provider.rotate("landscape")
        assert launched_provider._driver.orientation == "LANDSCAPE"

    def test_screenshot_creates_file(self, launched_provider, tmp_path) -> None:
        out = tmp_path / "screens" / "shot.png"
        launched_provider.screenshot(out)
        launched_provider._driver.save_screenshot.assert_called_once_with(str(out))

    def test_pinch_zoom_in_uses_public_api(self, launched_provider) -> None:
        el = MagicMock()
        el.id = "el-123"
        launched_provider._driver.find_element.return_value = el
        launched_provider.pinch(scale=2.0)
        launched_provider._driver.execute_script.assert_called_once()
        call_args = launched_provider._driver.execute_script.call_args
        assert call_args[0][0] == "mobile: pinchOpen"
        assert call_args[0][1]["elementId"] == "el-123"

    def test_pinch_zoom_out_uses_public_api(self, launched_provider) -> None:
        el = MagicMock()
        el.id = "el-456"
        launched_provider._driver.find_element.return_value = el
        launched_provider.pinch(scale=0.5)
        launched_provider._driver.execute_script.assert_called_once()
        call_args = launched_provider._driver.execute_script.call_args
        assert call_args[0][0] == "mobile: pinchClose"

    def test_tap_with_coordinates(self, launched_provider) -> None:
        launched_provider.tap(x=100, y=200, duration_ms=300)
        launched_provider._driver.tap.assert_called_once_with([(100, 200)], 300)

    def test_swipe_delegates(self, launched_provider) -> None:
        launched_provider.swipe(0, 0, 100, 200, 500)
        launched_provider._driver.swipe.assert_called_once_with(0, 0, 100, 200, 500)

    def test_tap_with_locator(self, launched_provider) -> None:
        el = MagicMock()
        launched_provider._driver.find_element.return_value = el
        launched_provider.tap(locator=Locator(type="id", value="ok"))
        launched_provider._driver.find_element.assert_called_once_with("id", "ok")
        el.click.assert_called_once()

    def test_tap_without_locator_or_coords_raises(self, launched_provider) -> None:
        with pytest.raises(ValueError, match="requires a locator"):
            launched_provider.tap()

    def test_click_delegates_to_tap(self, launched_provider) -> None:
        el = MagicMock()
        launched_provider._driver.find_element.return_value = el
        launched_provider.click(Locator(type="accessibility_id", value="btn"))
        el.click.assert_called_once()

    def test_type_text_clicks_then_sends_keys(self, launched_provider) -> None:
        el = MagicMock()
        launched_provider._driver.find_element.return_value = el
        launched_provider.type_text(Locator(type="id", value="field"), "hello")
        el.click.assert_called_once()
        el.send_keys.assert_called_once_with("hello")

    @pytest.mark.parametrize(
        ("direction", "expected"),
        [
            ("up", lambda cx, cy, d: (cx, cy, cx, cy + d)),
            ("down", lambda cx, cy, d: (cx, cy, cx, cy - d)),
            ("left", lambda cx, cy, d: (cx, cy, cx + d, cy)),
            ("right", lambda cx, cy, d: (cx, cy, cx - d, cy)),
        ],
    )
    def test_scroll_direction_mapping(self, launched_provider, direction, expected) -> None:
        launched_provider._driver.get_window_size.return_value = {"width": 400, "height": 900}
        launched_provider.scroll(direction, 1000)
        cx, cy = 200, 450
        dist = min(1000, 900 // 3)  # clamped to a third of the screen height
        exp = (*expected(cx, cy, dist), 600)
        launched_provider._driver.swipe.assert_called_once_with(*exp)

    def test_scroll_unknown_direction_is_noop(self, launched_provider) -> None:
        launched_provider._driver.get_window_size.return_value = {"width": 400, "height": 900}
        launched_provider.scroll("sideways", 300)
        launched_provider._driver.swipe.assert_not_called()

    def test_long_press_with_coordinates(self, launched_provider) -> None:
        launched_provider.long_press(x=50, y=60, duration_ms=1500)
        launched_provider._driver.tap.assert_called_once_with([(50, 60)], 1500)

    def test_long_press_with_locator_uses_center(self, launched_provider) -> None:
        el = MagicMock()
        el.location = {"x": 10, "y": 20}
        el.size = {"width": 40, "height": 60}
        launched_provider._driver.find_element.return_value = el
        launched_provider.long_press(locator=Locator(type="id", value="tile"), duration_ms=1200)
        # center = (10 + 40//2, 20 + 60//2) = (30, 50)
        launched_provider._driver.tap.assert_called_once_with([(30, 50)], 1200)

    def test_long_press_without_target_raises(self, launched_provider) -> None:
        with pytest.raises(ValueError, match="requires a locator"):
            launched_provider.long_press()

    def test_open_notifications_android(self, launched_provider) -> None:
        launched_provider.open_notifications()
        launched_provider._driver.open_notifications.assert_called_once()

    def test_open_notifications_ios_swipes(self, _patch_appium, tmp_path) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        p = AppiumMobileProvider()
        cfg = MobileConfig(platform="ios", device_name="iPhone 15", bundle_id="com.example.app")
        p.launch(cfg, video_dir=tmp_path)
        p._driver.get_window_size.return_value = {"width": 400, "height": 900}
        p.open_notifications()
        p._driver.swipe.assert_called_once_with(200, 0, 200, 450, 500)

    def test_app_switch_ios_uses_press_button(self, _patch_appium, tmp_path) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        p = AppiumMobileProvider()
        cfg = MobileConfig(platform="ios", device_name="iPhone 15", bundle_id="com.example.app")
        p.launch(cfg, video_dir=tmp_path)
        p.app_switch()
        p._driver.execute_script.assert_called_with(
            "mobile: pressButton", {"name": "home", "duration": 0.3}
        )

    def test_wait_for_delegates_to_webdriverwait(self, launched_provider) -> None:
        # Patch the selenium wait so we can assert it is driven with the mapped locator.
        with patch("selenium.webdriver.support.ui.WebDriverWait") as mock_wait:
            launched_provider.wait_for(Locator(type="accessibility_id", value="done"), timeout=3.0)
            mock_wait.assert_called_once()
            # timeout forwarded
            assert mock_wait.call_args[0][1] == 3.0

    def test_close_saves_recording_video(self, launched_provider, tmp_path) -> None:
        import base64

        launched_provider._video_dir = tmp_path
        launched_provider._driver.stop_recording_screen.return_value = base64.b64encode(
            b"fakevideo"
        ).decode()
        video = launched_provider.close()
        assert video is not None
        assert video.exists()
        assert video.read_bytes() == b"fakevideo"


# ── Factory registration ─────────────────────────────────────────────────────


class TestMobileProviderFactory:
    def test_appium_registered(self, _patch_appium) -> None:
        import demodsl.providers.mobile  # noqa: F401 — triggers registration

        provider = MobileProviderFactory.create("appium")
        assert provider is not None

    def test_unknown_raises(self) -> None:
        with pytest.raises((KeyError, ValueError)):
            MobileProviderFactory.create("nonexistent_provider")


# ── Import safety ─────────────────────────────────────────────────────────────


class TestImportSafety:
    """Ensure the module can be imported even when Appium is not installed,
    and gives a clear error when trying to launch."""

    def test_module_imports_without_appium(self, _patch_appium) -> None:
        """Provider module can be imported with mocked appium."""
        import demodsl.providers.mobile

        assert hasattr(demodsl.providers.mobile, "AppiumMobileProvider")


# ── page_source / get_window_size ─────────────────────────────────────────────


class TestAppiumMobileProviderMethods:
    """Tests for new diagnostic methods on AppiumMobileProvider."""

    def test_page_source_returns_xml(self, _patch_appium) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        provider = AppiumMobileProvider()
        provider._driver = MagicMock()
        provider._driver.page_source = "<AppiumAUT />"
        assert provider.page_source() == "<AppiumAUT />"

    def test_page_source_without_session_raises(self, _patch_appium) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        provider = AppiumMobileProvider()
        with pytest.raises(RuntimeError, match="No active Appium session"):
            provider.page_source()

    def test_get_window_size(self, _patch_appium) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        provider = AppiumMobileProvider()
        provider._driver = MagicMock()
        provider._driver.get_window_size.return_value = {"width": 390, "height": 844}
        assert provider.get_window_size() == {"width": 390, "height": 844}

    def test_get_window_size_without_session_raises(self, _patch_appium) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        provider = AppiumMobileProvider()
        with pytest.raises(RuntimeError, match="No active Appium session"):
            provider.get_window_size()

    def test_stop_recording_only(self, _patch_appium) -> None:
        from demodsl.providers.mobile import AppiumMobileProvider

        provider = AppiumMobileProvider()
        provider._driver = MagicMock()
        provider._recording = True
        provider._stop_recording_only()
        provider._driver.stop_recording_screen.assert_called_once()
        assert provider._recording is False


# ── iOS auto-detect ────────────────────────────────────────────────────────────


class TestIOSDetect:
    """Tests for demodsl.providers.ios_detect."""

    @patch("subprocess.run")
    def test_detect_booted_sim(self, mock_run: MagicMock) -> None:
        import json

        from demodsl.providers.ios_detect import detect_booted_simulator

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "devices": {
                        "com.apple.CoreSimulator.SimRuntime.iOS-17-4": [
                            {
                                "name": "iPhone 15 Pro",
                                "udid": "ABCD-1234",
                                "state": "Booted",
                            }
                        ]
                    }
                }
            ),
        )
        result = detect_booted_simulator()
        assert result == {"device_name": "iPhone 15 Pro", "udid": "ABCD-1234"}

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_no_xcrun(self, _mock: MagicMock) -> None:
        from demodsl.providers.ios_detect import detect_booted_simulator

        assert detect_booted_simulator() is None

    @patch("subprocess.run")
    def test_no_booted_sim(self, mock_run: MagicMock) -> None:
        import json

        from demodsl.providers.ios_detect import detect_booted_simulator

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"devices": {}}),
        )
        assert detect_booted_simulator() is None
