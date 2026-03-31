"""Command pattern for browser actions."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from demodsl.models import Step
from demodsl.providers.base import BrowserProvider, MobileProvider

logger = logging.getLogger(__name__)

_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


class BrowserCommand(ABC):
    """Base class for all browser action commands."""

    @abstractmethod
    def execute(self, browser: BrowserProvider, step: Step) -> Any:
        """Execute the action against the browser."""

    @abstractmethod
    def describe(self, step: Step) -> str:
        """Human-readable description (used for dry-run logging)."""


class NavigateCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.url is None:
            raise ValueError("NavigateCommand requires 'url'")
        parsed = urlparse(step.url)
        if parsed.scheme and parsed.scheme not in _ALLOWED_URL_SCHEMES:
            raise ValueError(
                f"Unsafe URL scheme '{parsed.scheme}'. "
                f"Only {sorted(_ALLOWED_URL_SCHEMES)} are allowed."
            )
        browser.navigate(step.url)

    def describe(self, step: Step) -> str:
        return f"Navigate to {step.url}"


class ClickCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("ClickCommand requires 'locator'")
        browser.click(step.locator)

    def describe(self, step: Step) -> str:
        loc = step.locator
        return f"Click on [{loc.type}] {loc.value}" if loc else "Click (no locator)"


class TypeCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None or step.value is None:
            raise ValueError("TypeCommand requires 'locator' and 'value'")
        if step.char_rate is not None:
            browser.type_text_organic(
                step.locator,
                step.value,
                step.char_rate,
                variance=step.typing_variance or 0.0,
            )
        else:
            browser.type_text(step.locator, step.value)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        rate = f" @{step.char_rate}ch/s" if step.char_rate else ""
        return f"Type '{step.value}' into {target}{rate}"


class ScrollCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        direction = step.direction or "down"
        pixels = step.pixels or 300
        browser.scroll(direction, pixels, smooth=bool(step.smooth_scroll))

    def describe(self, step: Step) -> str:
        smooth = " (smooth)" if step.smooth_scroll else ""
        return f"Scroll {step.direction or 'down'} {step.pixels or 300}px{smooth}"


class WaitForCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("WaitForCommand requires 'locator'")
        timeout = step.timeout or 5.0
        browser.wait_for(step.locator, timeout)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Wait for {target} (timeout={step.timeout or 5.0}s)"


class ScreenshotCommand(BrowserCommand):
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def execute(self, browser: BrowserProvider, step: Step) -> Path:
        filename = step.filename or "screenshot.png"
        path = self._output_dir / filename
        return browser.screenshot(path)

    def describe(self, step: Step) -> str:
        return f"Screenshot → {step.filename or 'screenshot.png'}"


# ── Command Registry ─────────────────────────────────────────────────────────

_COMMANDS: dict[str, type[BrowserCommand]] = {
    "navigate": NavigateCommand,
    "click": ClickCommand,
    "type": TypeCommand,
    "scroll": ScrollCommand,
    "wait_for": WaitForCommand,
    # "screenshot" handled separately because it needs output_dir
}


def get_command(action: str, **kwargs: Any) -> BrowserCommand:
    """Instantiate the appropriate command for *action*."""
    if action == "screenshot":
        output_dir = kwargs.get("output_dir", Path("."))
        return ScreenshotCommand(output_dir=output_dir)
    cls = _COMMANDS.get(action)
    if cls is None:
        raise ValueError(f"Unknown browser action '{action}'")
    return cls()


# ── Mobile Command Pattern ───────────────────────────────────────────────────


class MobileCommand(ABC):
    """Base class for all mobile action commands."""

    @abstractmethod
    def execute(self, mobile: MobileProvider, step: Step) -> Any:
        """Execute the action against the mobile provider."""

    @abstractmethod
    def describe(self, step: Step) -> str:
        """Human-readable description (used for dry-run logging)."""


class TapCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.tap(
            locator=step.locator,
            x=step.start_x,
            y=step.start_y,
            duration_ms=step.duration_ms,
        )

    def describe(self, step: Step) -> str:
        if step.locator:
            return f"Tap [{step.locator.type}] {step.locator.value}"
        return f"Tap at ({step.start_x}, {step.start_y})"


class SwipeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.swipe(
            start_x=step.start_x or 0,
            start_y=step.start_y or 0,
            end_x=step.end_x or 0,
            end_y=step.end_y or 0,
            duration_ms=step.duration_ms or 800,
        )

    def describe(self, step: Step) -> str:
        return f"Swipe ({step.start_x}, {step.start_y}) → ({step.end_x}, {step.end_y})"


class PinchCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.pinch(
            locator=step.locator,
            scale=step.pinch_scale or 0.5,
            duration_ms=step.duration_ms or 500,
        )

    def describe(self, step: Step) -> str:
        return f"Pinch scale={step.pinch_scale}"


class LongPressCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.long_press(
            locator=step.locator,
            x=step.start_x,
            y=step.start_y,
            duration_ms=step.duration_ms or 1000,
        )

    def describe(self, step: Step) -> str:
        if step.locator:
            return f"Long press [{step.locator.type}] {step.locator.value}"
        return f"Long press at ({step.start_x}, {step.start_y})"


class BackCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.back()

    def describe(self, step: Step) -> str:
        return "Press back button"


class HomeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.home()

    def describe(self, step: Step) -> str:
        return "Press home button"


class NotificationCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.open_notifications()

    def describe(self, step: Step) -> str:
        return "Open notifications"


class AppSwitchCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.app_switch()

    def describe(self, step: Step) -> str:
        return "Open app switcher"


class RotateDeviceCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.rotate(step.orientation or "portrait")

    def describe(self, step: Step) -> str:
        return f"Rotate to {step.orientation}"


class ShakeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.shake()

    def describe(self, step: Step) -> str:
        return "Shake device"


class MobileScrollCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        direction = step.direction or "down"
        pixels = step.pixels or 300
        mobile.scroll(direction, pixels)

    def describe(self, step: Step) -> str:
        return f"Scroll {step.direction or 'down'} {step.pixels or 300}px"


class MobileTypeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        if step.locator is None or step.value is None:
            raise ValueError("MobileTypeCommand requires 'locator' and 'value'")
        mobile.type_text(step.locator, step.value)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Type '{step.value}' into {target}"


class MobileClickCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("MobileClickCommand requires 'locator'")
        mobile.click(step.locator)

    def describe(self, step: Step) -> str:
        loc = step.locator
        return f"Tap [{loc.type}] {loc.value}" if loc else "Tap (no locator)"


class MobileWaitForCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("MobileWaitForCommand requires 'locator'")
        timeout = step.timeout or 5.0
        mobile.wait_for(step.locator, timeout)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Wait for {target} (timeout={step.timeout or 5.0}s)"


class MobileScreenshotCommand(MobileCommand):
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def execute(self, mobile: MobileProvider, step: Step) -> Path:
        filename = step.filename or "mobile_screenshot.png"
        path = self._output_dir / filename
        return mobile.screenshot(path)

    def describe(self, step: Step) -> str:
        return f"Screenshot → {step.filename or 'mobile_screenshot.png'}"


# ── Mobile Command Registry ──────────────────────────────────────────────────

_MOBILE_COMMANDS: dict[str, type[MobileCommand]] = {
    "tap": TapCommand,
    "swipe": SwipeCommand,
    "pinch": PinchCommand,
    "long_press": LongPressCommand,
    "back": BackCommand,
    "home": HomeCommand,
    "notification": NotificationCommand,
    "app_switch": AppSwitchCommand,
    "rotate_device": RotateDeviceCommand,
    "shake": ShakeCommand,
    # Shared actions mapped to mobile variants
    "scroll": MobileScrollCommand,
    "type": MobileTypeCommand,
    "click": MobileClickCommand,
    "wait_for": MobileWaitForCommand,
}


def get_mobile_command(action: str, **kwargs: Any) -> MobileCommand:
    """Instantiate the appropriate mobile command for *action*."""
    if action == "screenshot":
        output_dir = kwargs.get("output_dir", Path("."))
        return MobileScreenshotCommand(output_dir=output_dir)
    cls = _MOBILE_COMMANDS.get(action)
    if cls is None:
        raise ValueError(f"Unknown mobile action '{action}'")
    return cls()
