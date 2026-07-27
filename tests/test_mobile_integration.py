"""Live end-to-end integration test for the mobile (Appium) framework.

These tests exercise the *real* stack: a running Appium server driving a booted
local iOS simulator via the XCUITest driver. They are intentionally gated so the
fast unit suite and CI runners (where no simulator/Appium exist) skip them
cleanly instead of failing.

Run locally with:

    # 1. start Appium:      appium --port 4723
    # 2. boot a simulator:  xcrun simctl boot "iPhone 17" && open -a Simulator
    # 3. run:               pytest tests/test_mobile_integration.py -m integration -v

The target app is Apple's Settings (``com.apple.Preferences``), which is present
on every iOS simulator, so no app bundle needs to be installed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_APPIUM_URL = os.environ.get("DEMODSL_APPIUM_URL", "http://127.0.0.1:4723")


def _appium_ready(url: str) -> bool:
    """Return True if an Appium server answers /status."""
    try:
        with urllib.request.urlopen(f"{url}/status", timeout=3) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return bool(data.get("value", {}).get("ready"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _booted_ios_udid() -> str | None:
    """Return the UDID of a booted iOS simulator, or None."""
    from demodsl.providers.simulators import detect_booted_ios

    dev = detect_booted_ios()
    return dev.udid if dev else None


def _appium_client_installed() -> bool:
    try:
        import appium  # noqa: F401

        return True
    except ImportError:
        return False


# A single guard reused by every test in the module.
_SKIP_REASON: str | None = None
if not _appium_client_installed():
    _SKIP_REASON = "Appium-Python-Client not installed (pip install 'demodsl[mobile]')"
elif not _appium_ready(_APPIUM_URL):
    _SKIP_REASON = f"no Appium server reachable at {_APPIUM_URL}"
elif _booted_ios_udid() is None:
    _SKIP_REASON = "no booted iOS simulator (xcrun simctl boot <name>)"

pytestmark.append(pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or ""))


@pytest.fixture()
def settings_config():
    """MobileConfig launching the Settings app on the booted simulator."""
    from demodsl.models import MobileConfig

    return MobileConfig(
        platform="ios",
        device_name="auto",
        bundle_id="com.apple.Preferences",
        appium_server=_APPIUM_URL,
        auto_boot=False,
        orientation="portrait",
    )


@pytest.fixture()
def live_provider(settings_config):
    """A launched (non-recording) Appium session, torn down after the test."""
    from demodsl.providers.mobile import AppiumMobileProvider

    provider = AppiumMobileProvider()
    try:
        provider.launch_without_recording(settings_config)
    except Exception as exc:  # noqa: BLE001 - device/server dropped between gate and run
        pytest.skip(f"could not open a live Appium session: {exc}")
    try:
        yield provider
    finally:
        try:
            provider.close()
        except Exception:  # noqa: BLE001
            pass


def test_session_reports_window_size(live_provider) -> None:
    size = live_provider.get_window_size()
    assert size["width"] > 0
    assert size["height"] > 0


def test_page_source_contains_settings_app(live_provider) -> None:
    source = live_provider.page_source()
    assert source.startswith("<")
    assert "XCUIElementType" in source


def test_screenshot_is_written(live_provider, tmp_path) -> None:
    out = tmp_path / "settings.png"
    result = live_provider.screenshot(out)
    assert result == out
    assert out.exists()
    # PNG magic number
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_wait_for_navigation_bar(live_provider) -> None:
    """The Settings root screen always has a navigation bar — waiting must not raise."""
    from demodsl.models import Locator

    live_provider.wait_for(
        Locator(type="ios_predicate", value="type == 'XCUIElementTypeNavigationBar'"),
        timeout=15.0,
    )


def test_swipe_does_not_crash_session(live_provider) -> None:
    """A coordinate swipe should scroll the list and leave the session usable."""
    size = live_provider.get_window_size()
    cx = size["width"] // 2
    live_provider.swipe(cx, int(size["height"] * 0.7), cx, int(size["height"] * 0.3), 600)
    # Session still responsive after the gesture.
    assert live_provider.get_window_size()["width"] == size["width"]


def test_os_setting_command_drives_real_session(live_provider) -> None:
    """OsSettingCommand runs end-to-end against a live session.

    Uses a temporary taxonomy entry whose control targets the Settings search
    field (``XCUIElementTypeSearchField`` — a locale- and version-independent
    element type) so the smoke test does not depend on localized cell labels.
    """
    from demodsl.commands import OsSettingCommand
    from demodsl.models import Step
    from demodsl.os_taxonomy import OS_TAXONOMY, Control, OsSetting, Recipe

    OS_TAXONOMY["_test.search"] = OsSetting(
        key="_test.search",
        title="Search (test)",
        kind="open",
        ios=Recipe(
            path=(),
            control=Control(
                kind="open",
                locator={"type": "xpath", "value": "//XCUIElementTypeSearchField"},
            ),
        ),
    )
    try:
        OsSettingCommand().execute(live_provider, Step(action="os_setting", setting="_test.search"))
        # Session is still alive and responsive after the command.
        assert live_provider.get_window_size()["width"] > 0
    finally:
        del OS_TAXONOMY["_test.search"]
