"""Appium-based mobile provider for native Android/iOS app demos."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.models import Locator, MobileConfig
from demodsl.providers.base import MobileProvider, MobileProviderFactory

logger = logging.getLogger(__name__)

# Android keycode constants
_KEYCODE_HOME = 3
_KEYCODE_APP_SWITCH = 187

# Locator strategy mapping: DSL type → Appium MobileBy constant string
_LOCATOR_MAP: dict[str, str] = {
    "accessibility_id": "accessibility id",
    "id": "id",
    "xpath": "xpath",
    "class_name": "class name",
    "css": "css selector",
    "text": "xpath",  # converted to XPath contains()
    "android_uiautomator": "-android uiautomator",
    "ios_predicate": "-ios predicate string",
    "ios_class_chain": "-ios class chain",
}


def _xpath_quote(s: str) -> str:
    """Safely quote a string for XPath 1.0, handling embedded quotes.

    Uses concat() to handle strings containing both single and double quotes.
    """
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    # String contains both quote types — use concat()
    parts: list[str] = []
    for segment in s.split("'"):
        parts.append(f"'{segment}'")
    return "concat(" + ', "\'", '.join(parts) + ")"


def _build_locator_args(locator: Locator) -> tuple[str, str]:
    """Convert a DSL Locator to Appium (by, value) tuple."""
    strategy = _LOCATOR_MAP.get(locator.type)
    if strategy is None:
        raise ValueError(f"Unsupported mobile locator type: {locator.type}")
    value = locator.value
    if locator.type == "text":
        # Convert text locator to XPath contains() with safe quoting
        value = (
            "//*[contains(@text, " + _xpath_quote(value) + ") "
            "or contains(@content-desc, " + _xpath_quote(value) + ")]"
        )
    return strategy, value


class AppiumMobileProvider(MobileProvider):
    """Appium WebDriver-based mobile automation provider."""

    def __init__(self) -> None:
        self._driver: Any = None
        self._video_dir: Path | None = None
        self._recording: bool = False
        self._config: MobileConfig | None = None

    def launch(self, config: MobileConfig, video_dir: Path) -> None:
        try:
            from appium import webdriver as appium_webdriver
            from appium.options.android import UiAutomator2Options
            from appium.options.ios import XCUITestOptions
        except ImportError as exc:
            raise ImportError(
                "Appium-Python-Client is required for mobile demos. "
                "Install it with: pip install 'demodsl[mobile]'"
            ) from exc

        self._config = config
        self._video_dir = video_dir
        video_dir.mkdir(parents=True, exist_ok=True)

        if config.platform == "android":
            options = UiAutomator2Options()
            options.device_name = config.device_name
            if config.app:
                options.app = config.app
            if config.app_package:
                options.app_package = config.app_package
            if config.app_activity:
                options.app_activity = config.app_activity
            if config.udid:
                options.udid = config.udid
            options.no_reset = config.no_reset
            options.full_reset = config.full_reset
            if config.automation_name:
                options.automation_name = config.automation_name
            else:
                options.automation_name = "UiAutomator2"
        else:
            options = XCUITestOptions()
            options.device_name = config.device_name
            if config.app:
                options.app = config.app
            if config.bundle_id:
                options.bundle_id = config.bundle_id
            if config.udid:
                options.udid = config.udid
            options.no_reset = config.no_reset
            options.full_reset = config.full_reset
            if config.automation_name:
                options.automation_name = config.automation_name
            else:
                options.automation_name = "XCUITest"

        self._driver = appium_webdriver.Remote(
            command_executor=config.appium_server,
            options=options,
        )

        # Set orientation
        if config.orientation == "landscape":
            self._driver.orientation = "LANDSCAPE"
        else:
            self._driver.orientation = "PORTRAIT"

        # Start screen recording
        self._driver.start_recording_screen()
        self._recording = True
        logger.info(
            "Mobile session started: %s on %s",
            config.platform,
            config.device_name,
        )

    def _find_element(self, locator: Locator) -> Any:
        """Find a single element using the locator."""
        by, value = _build_locator_args(locator)
        return self._driver.find_element(by, value)

    def tap(
        self,
        locator: Locator | None = None,
        x: float | None = None,
        y: float | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if locator:
            el = self._find_element(locator)
            el.click()
        elif x is not None and y is not None:
            self._driver.tap([(int(x), int(y))], duration_ms)
        else:
            raise ValueError("tap requires a locator or (x, y) coordinates")

    def swipe(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        duration_ms: int = 800,
    ) -> None:
        self._driver.swipe(
            int(start_x), int(start_y), int(end_x), int(end_y), duration_ms
        )

    def pinch(
        self,
        locator: Locator | None = None,
        scale: float = 0.5,
        duration_ms: int = 500,
    ) -> None:
        if locator:
            el = self._find_element(locator)
        else:
            # Use the root element
            el = self._driver.find_element("xpath", "//*")

        # Use Appium mobile: gesture commands (public API, stable)
        if scale > 1:
            self._driver.execute_script(
                "mobile: pinchOpen",
                {
                    "elementId": el.id,
                    "percent": min(scale - 1.0, 1.0),
                    "speed": max(500, duration_ms),
                },
            )
        else:
            self._driver.execute_script(
                "mobile: pinchClose",
                {
                    "elementId": el.id,
                    "percent": min(1.0 - scale, 1.0),
                    "speed": max(500, duration_ms),
                },
            )

    def long_press(
        self,
        locator: Locator | None = None,
        x: float | None = None,
        y: float | None = None,
        duration_ms: int = 1000,
    ) -> None:
        if locator:
            el = self._find_element(locator)
            loc = el.location
            size = el.size
            cx = loc["x"] + size["width"] // 2
            cy = loc["y"] + size["height"] // 2
        elif x is not None and y is not None:
            cx, cy = int(x), int(y)
        else:
            raise ValueError("long_press requires a locator or (x, y) coordinates")
        # Use tap with long duration for long press
        self._driver.tap([(cx, cy)], duration_ms)

    def scroll(self, direction: str, pixels: int) -> None:
        window = self._driver.get_window_size()
        w, h = window["width"], window["height"]
        cx, cy = w // 2, h // 2
        dist = min(pixels, h // 3)
        swipe_map = {
            "down": (cx, cy, cx, cy - dist),
            "up": (cx, cy, cx, cy + dist),
            "right": (cx, cy, cx - dist, cy),
            "left": (cx, cy, cx + dist, cy),
        }
        coords = swipe_map.get(direction)
        if coords:
            self._driver.swipe(*coords, 600)

    def type_text(self, locator: Locator, value: str) -> None:
        el = self._find_element(locator)
        el.click()
        el.send_keys(value)

    def click(self, locator: Locator) -> None:
        self.tap(locator=locator)

    def back(self) -> None:
        self._driver.back()

    def home(self) -> None:
        if self._config and self._config.platform == "android":
            self._driver.press_keycode(_KEYCODE_HOME)
        else:
            # iOS: use execute_script
            self._driver.execute_script("mobile: pressButton", {"name": "home"})

    def open_notifications(self) -> None:
        if self._config and self._config.platform == "android":
            self._driver.open_notifications()
        else:
            # iOS: swipe down from top
            window = self._driver.get_window_size()
            self._driver.swipe(
                window["width"] // 2,
                0,
                window["width"] // 2,
                window["height"] // 2,
                500,
            )

    def app_switch(self) -> None:
        if self._config and self._config.platform == "android":
            self._driver.press_keycode(_KEYCODE_APP_SWITCH)
        else:
            # iOS: double-tap home or swipe up and pause
            self._driver.execute_script(
                "mobile: pressButton", {"name": "home", "duration": 0.3}
            )

    def rotate(self, orientation: str) -> None:
        self._driver.orientation = orientation.upper()

    def shake(self) -> None:
        self._driver.shake()

    def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._driver.save_screenshot(str(path))
        logger.info("Mobile screenshot saved: %s", path)
        return path

    def wait_for(self, locator: Locator, timeout: float) -> None:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        by, value = _build_locator_args(locator)
        WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def close(self) -> Path | None:
        video_path: Path | None = None
        if self._driver:
            try:
                if self._recording:
                    import base64

                    raw = self._driver.stop_recording_screen()
                    self._recording = False
                    if raw and self._video_dir:
                        video_path = self._video_dir / "mobile_recording.mp4"
                        video_path.write_bytes(base64.b64decode(raw))
                        logger.info("Mobile recording saved: %s", video_path)
            finally:
                self._driver.quit()
                self._driver = None
        return video_path


# ── Register with factory ────────────────────────────────────────────────────

MobileProviderFactory.register("appium", AppiumMobileProvider)
