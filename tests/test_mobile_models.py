"""Tests for MobileConfig model, mobile locators, and mobile step actions."""

from __future__ import annotations

import pytest

from demodsl.models import (
    DemoConfig,
    Locator,
    MobileConfig,
    Scenario,
    Step,
)


# ── MobileConfig ──────────────────────────────────────────────────────────────


class TestMobileConfig:
    def test_android_minimal(self) -> None:
        cfg = MobileConfig(
            platform="android",
            device_name="Pixel 7",
            app_package="com.example.app",
        )
        assert cfg.platform == "android"
        assert cfg.automation_name is None
        assert cfg.appium_server == "http://127.0.0.1:4723"

    def test_ios_minimal(self) -> None:
        cfg = MobileConfig(
            platform="ios",
            device_name="iPhone 15 Pro",
            bundle_id="com.example.app",
        )
        assert cfg.platform == "ios"

    def test_android_requires_app_or_package(self) -> None:
        with pytest.raises(ValueError, match="Android requires"):
            MobileConfig(platform="android", device_name="Pixel 7")

    def test_ios_requires_app_or_bundle(self) -> None:
        with pytest.raises(ValueError, match="iOS requires"):
            MobileConfig(platform="ios", device_name="iPhone 15")

    def test_android_with_app_path(self) -> None:
        cfg = MobileConfig(
            platform="android",
            device_name="Pixel 7",
            app="app/build/outputs/apk/debug/app-debug.apk",
        )
        assert cfg.app is not None

    def test_ios_with_app_url(self) -> None:
        cfg = MobileConfig(
            platform="ios",
            device_name="iPhone 15 Pro",
            app="https://example.com/app.ipa",
        )
        assert cfg.app.startswith("http")

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            MobileConfig(
                platform="android",
                device_name="Pixel 7",
                app="../../../etc/passwd",
            )

    def test_full_config(self) -> None:
        cfg = MobileConfig(
            platform="android",
            device_name="Pixel 7",
            app_package="com.example.app",
            app_activity=".MainActivity",
            udid="emulator-5554",
            automation_name="UiAutomator2",
            no_reset=True,
            full_reset=False,
            orientation="landscape",
        )
        assert cfg.orientation == "landscape"
        assert cfg.automation_name == "UiAutomator2"


# ── Mobile Locators ───────────────────────────────────────────────────────────


class TestMobileLocators:
    def test_accessibility_id(self) -> None:
        loc = Locator(type="accessibility_id", value="login_button")
        assert loc.type == "accessibility_id"

    def test_android_uiautomator(self) -> None:
        loc = Locator(
            type="android_uiautomator",
            value='new UiSelector().text("Login")',
        )
        assert loc.type == "android_uiautomator"

    def test_ios_predicate(self) -> None:
        loc = Locator(
            type="ios_predicate",
            value="type == 'XCUIElementTypeButton' AND name == 'Login'",
        )
        assert loc.type == "ios_predicate"

    def test_ios_class_chain(self) -> None:
        loc = Locator(
            type="ios_class_chain",
            value="**/XCUIElementTypeButton[`name == 'Login'`]",
        )
        assert loc.type == "ios_class_chain"

    def test_class_name(self) -> None:
        loc = Locator(type="class_name", value="android.widget.Button")
        assert loc.type == "class_name"


# ── Mobile Step Actions ───────────────────────────────────────────────────────


class TestMobileStepActions:
    def test_tap_with_locator(self) -> None:
        step = Step(
            action="tap",
            locator=Locator(type="accessibility_id", value="btn"),
        )
        assert step.action == "tap"

    def test_tap_with_coordinates(self) -> None:
        step = Step(action="tap", start_x=100, start_y=200)
        assert step.start_x == 100
        assert step.start_y == 200

    def test_swipe_requires_coords(self) -> None:
        with pytest.raises(ValueError, match="'swipe' requires"):
            Step(action="swipe", start_x=100, start_y=200)

    def test_swipe_valid(self) -> None:
        step = Step(
            action="swipe",
            start_x=100,
            start_y=200,
            end_x=500,
            end_y=200,
            duration_ms=800,
        )
        assert step.action == "swipe"
        assert step.end_x == 500

    def test_pinch_requires_scale(self) -> None:
        with pytest.raises(ValueError, match="'pinch' requires"):
            Step(action="pinch")

    def test_pinch_valid(self) -> None:
        step = Step(action="pinch", pinch_scale=2.0)
        assert step.pinch_scale == 2.0

    def test_long_press(self) -> None:
        step = Step(
            action="long_press",
            locator=Locator(type="accessibility_id", value="item"),
            duration_ms=1500,
        )
        assert step.action == "long_press"

    def test_back(self) -> None:
        step = Step(action="back")
        assert step.action == "back"

    def test_home(self) -> None:
        step = Step(action="home")
        assert step.action == "home"

    def test_notification(self) -> None:
        step = Step(action="notification")
        assert step.action == "notification"

    def test_app_switch(self) -> None:
        step = Step(action="app_switch")
        assert step.action == "app_switch"

    def test_rotate_device_requires_orientation(self) -> None:
        with pytest.raises(ValueError, match="'rotate_device' requires"):
            Step(action="rotate_device")

    def test_rotate_device_valid(self) -> None:
        step = Step(action="rotate_device", orientation="landscape")
        assert step.orientation == "landscape"

    def test_shake(self) -> None:
        step = Step(action="shake")
        assert step.action == "shake"


# ── Scenario with mobile config ──────────────────────────────────────────────


class TestMobileScenario:
    def test_mobile_scenario_no_url_required(self) -> None:
        s = Scenario(
            name="Mobile Test",
            mobile=MobileConfig(
                platform="android",
                device_name="Pixel 7",
                app_package="com.example.app",
            ),
            steps=[Step(action="tap", locator=Locator(type="id", value="btn"))],
        )
        assert s.url is None
        assert s.mobile is not None

    def test_browser_scenario_requires_url(self) -> None:
        with pytest.raises(ValueError, match="Browser scenarios require"):
            Scenario(
                name="Browser Test",
                steps=[
                    Step(action="navigate", url="https://example.com"),
                ],
            )

    def test_full_mobile_config_in_demo(self) -> None:
        cfg = DemoConfig(
            metadata={"title": "Mobile Demo"},
            scenarios=[
                {
                    "name": "Android",
                    "mobile": {
                        "platform": "android",
                        "device_name": "Pixel 7",
                        "app_package": "com.example.app",
                    },
                    "steps": [{"action": "back"}],
                }
            ],
        )
        assert cfg.scenarios[0].mobile is not None
        assert cfg.scenarios[0].mobile.platform == "android"


# ── Step narration with mobile actions ────────────────────────────────────────


class TestMobileStepNarration:
    def test_tap_with_narration(self) -> None:
        step = Step(
            action="tap",
            locator=Locator(type="accessibility_id", value="btn"),
            narration="Tap the login button.",
            wait=1.5,
        )
        assert step.narration == "Tap the login button."
        assert step.wait == 1.5

    def test_swipe_with_effects(self) -> None:
        step = Step(
            action="swipe",
            start_x=100,
            start_y=500,
            end_x=900,
            end_y=500,
            narration="Swipe to reveal the menu.",
            effects=[{"type": "fade_in", "duration": 0.5}],
        )
        assert len(step.effects) == 1
