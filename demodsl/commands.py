"""Command pattern for browser actions."""

from __future__ import annotations

import difflib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from demodsl.models import Step
from demodsl.providers.base import BrowserProvider, MobileProvider
from demodsl.validators import _validate_url

logger = logging.getLogger(__name__)


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
        _validate_url(step.url)
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


class PauseCommand(BrowserCommand):
    """No-op action — holds the current page without scrolling."""

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        pass  # intentionally does nothing

    def describe(self, step: Step) -> str:
        return "Pause (no action)"


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


class ShortcutCommand(BrowserCommand):
    """Execute a keyboard shortcut and display an overlay badge."""

    # Display duration for the shortcut badge (seconds)
    _DISPLAY_SECONDS = 1.5

    @staticmethod
    def _format_label(keys: str) -> str:
        """Convert Playwright-style keys ('Meta+f') to display label ('⌘ F')."""
        _SYMBOLS = {
            "Meta": "⌘",
            "Command": "⌘",
            "Control": "Ctrl",
            "Shift": "⇧",
            "Alt": "⌥",
            "Option": "⌥",
            "Enter": "↵",
            "Escape": "Esc",
            "Backspace": "⌫",
            "Delete": "⌦",
            "Tab": "⇥",
            "ArrowUp": "↑",
            "ArrowDown": "↓",
            "ArrowLeft": "←",
            "ArrowRight": "→",
        }
        parts = keys.split("+")
        return " ".join(_SYMBOLS.get(p, p.upper()) for p in parts)

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if not step.keys:
            raise ValueError("ShortcutCommand requires 'keys'")
        label = self._format_label(step.keys)
        # Inject the visual overlay *before* pressing so it's visible on camera
        browser.evaluate_js(self._overlay_js(label, self._DISPLAY_SECONDS))
        import time

        time.sleep(0.15)  # brief pause so overlay is rendered before key press
        browser.press_keys(step.keys)

    def describe(self, step: Step) -> str:
        return f"Shortcut {step.keys}"

    @staticmethod
    def _overlay_js(label: str, duration: float) -> str:
        safe_label = label.replace("'", "\\'")
        ms = int(duration * 1000)
        return f"""
        (() => {{
            const existing = document.getElementById('__demodsl_shortcut');
            if (existing) existing.remove();
            const badge = document.createElement('div');
            badge.id = '__demodsl_shortcut';
            badge.style.cssText = `
                position: fixed;
                bottom: 48px;
                left: 50%;
                transform: translateX(-50%) scale(0.85);
                display: inline-flex;
                gap: 6px;
                padding: 10px 22px;
                background: rgba(24, 24, 27, 0.88);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.35);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 18px;
                font-weight: 600;
                letter-spacing: 0.04em;
                color: #f4f4f5;
                z-index: 999999;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.25s ease, transform 0.25s ease;
            `;
            const parts = '{safe_label}'.split(' ');
            parts.forEach((part, i) => {{
                const key = document.createElement('span');
                key.textContent = part;
                key.style.cssText = `
                    display: inline-block;
                    padding: 4px 10px;
                    background: rgba(255,255,255,0.10);
                    border: 1px solid rgba(255,255,255,0.18);
                    border-radius: 7px;
                    font-size: 16px;
                    line-height: 1.3;
                    min-width: 28px;
                    text-align: center;
                `;
                badge.appendChild(key);
            }});
            document.body.appendChild(badge);
            requestAnimationFrame(() => {{
                badge.style.opacity = '1';
                badge.style.transform = 'translateX(-50%) scale(1)';
            }});
            setTimeout(() => {{
                badge.style.opacity = '0';
                badge.style.transform = 'translateX(-50%) scale(0.85)';
                setTimeout(() => badge.remove(), 350);
            }}, {ms});
        }})()
        """


# ── Command Registry ─────────────────────────────────────────────────────────

_COMMANDS: dict[str, type[BrowserCommand]] = {
    "navigate": NavigateCommand,
    "click": ClickCommand,
    "type": TypeCommand,
    "scroll": ScrollCommand,
    "pause": PauseCommand,
    "wait_for": WaitForCommand,
    "shortcut": ShortcutCommand,
    # "screenshot" handled separately because it needs output_dir
}


def get_command(action: str, **kwargs: Any) -> BrowserCommand:
    """Instantiate the appropriate command for *action*."""
    if action == "screenshot":
        output_dir = kwargs.get("output_dir", Path("."))
        return ScreenshotCommand(output_dir=output_dir)
    cls = _COMMANDS.get(action)
    if cls is None:
        valid = sorted(list(_COMMANDS.keys()) + ["screenshot"])
        close = difflib.get_close_matches(action, valid, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(
            f"Unknown browser action '{action}'. "
            f"Valid browser actions: {', '.join(valid)}.{hint}"
        )
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
        valid = sorted(list(_MOBILE_COMMANDS.keys()) + ["screenshot"])
        if action == "navigate":
            raise ValueError(
                "Unknown mobile action 'navigate'. "
                "Mobile scenarios launch the app automatically via "
                "bundle_id/app_package — no 'navigate' step is needed. "
                "Did you mean to use a browser scenario (with 'url' instead of 'mobile')?"
            )
        # fuzzy suggestion
        close = difflib.get_close_matches(action, valid, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(
            f"Unknown mobile action '{action}'. "
            f"Valid mobile actions: {', '.join(valid)}.{hint}"
        )
    return cls()
