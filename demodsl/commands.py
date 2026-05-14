"""Command pattern for browser actions."""

from __future__ import annotations

import difflib
import json
import logging
import re
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
        # json.dumps yields a properly-quoted JS string literal — safe
        # against quote/backslash/newline injection from scenario YAML.
        # ensure_ascii=False keeps Unicode (⌘, emoji…) human-readable.
        safe_label = json.dumps(label, ensure_ascii=False)
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
            const parts = {safe_label}.split(' ');
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


class HoverCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("HoverCommand requires 'locator'")
        browser.hover(step.locator)

    def describe(self, step: Step) -> str:
        loc = step.locator
        return f"Hover over [{loc.type}] {loc.value}" if loc else "Hover (no locator)"


class DragCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("DragCommand requires 'locator' (source)")
        browser.drag_and_drop(
            step.locator,
            target=step.target_locator,
            target_x=step.end_x,
            target_y=step.end_y,
        )

    def describe(self, step: Step) -> str:
        src = f"[{step.locator.type}]{step.locator.value}" if step.locator else "?"
        if step.target_locator:
            tgt = f"[{step.target_locator.type}]{step.target_locator.value}"
        elif step.end_x is not None and step.end_y is not None:
            tgt = f"({step.end_x},{step.end_y})"
        else:
            tgt = "?"
        return f"Drag {src} → {tgt}"


class PressKeyCommand(BrowserCommand):
    """Press a single key (Enter, Escape, Tab, ArrowDown, etc.)."""

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if not step.key:
            raise ValueError("PressKeyCommand requires 'key'")
        browser.press_keys(step.key)

    def describe(self, step: Step) -> str:
        return f"Press key '{step.key}'"


_COMMANDS: dict[str, type[BrowserCommand]] = {
    "navigate": NavigateCommand,
    "click": ClickCommand,
    "type": TypeCommand,
    "scroll": ScrollCommand,
    "pause": PauseCommand,
    "wait_for": WaitForCommand,
    "shortcut": ShortcutCommand,
    "hover": HoverCommand,
    "drag": DragCommand,
    "press_key": PressKeyCommand,
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
            f"Unknown browser action '{action}'. Valid browser actions: {', '.join(valid)}.{hint}"
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
            f"Unknown mobile action '{action}'. Valid mobile actions: {', '.join(valid)}.{hint}"
        )
    return cls()


# ── Terminal Command Pattern ─────────────────────────────────────────────────

# Playwright-bundled Chromium crashes (BUS_ADRALN) when rendering characters
# with Emoji_Presentation=Yes on macOS ARM.  Text-presentation symbols like
# ✓ (U+2713) are safe.  We target exactly the Unicode Emoji_Presentation=Yes
# BMP codepoints plus the entire SMP (U+10000+).
_EMOJI_RE = re.compile(
    "["
    # --- BMP chars with Emoji_Presentation=Yes (crash Chromium) ---
    "\u231a\u231b"  # watch, hourglass
    "\u23e9-\u23ec"  # fast-forward/rewind
    "\u23f0"  # alarm clock
    "\u23f3"  # hourglass flowing
    "\u25fd\u25fe"  # medium squares
    "\u2614\u2615"  # umbrella, hot beverage
    "\u2648-\u2653"  # zodiac signs
    "\u267f"  # wheelchair
    "\u2693"  # anchor
    "\u26a1"  # high voltage
    "\u26aa\u26ab"  # circles
    "\u26bd\u26be"  # soccer, baseball
    "\u26c4\u26c5"  # snowman, sun behind cloud
    "\u26ce"  # ophiuchus
    "\u26d4"  # no entry
    "\u26ea"  # church
    "\u26f2\u26f3"  # fountain, golf
    "\u26f5"  # sailboat
    "\u26fa"  # tent
    "\u26fd"  # fuel pump
    "\u2705"  # ✅ white heavy check mark
    "\u270a-\u270d"  # raised fist → writing hand
    "\u270f"  # pencil
    "\u2712"  # black nib
    "\u2714"  # heavy check mark (emoji)
    "\u2716"  # heavy multiplication
    "\u271d"  # latin cross
    "\u2721"  # star of david
    "\u2728"  # sparkles
    "\u2733\u2734"  # eight-spoked asterisks
    "\u2744"  # snowflake
    "\u2747"  # sparkle
    "\u274c"  # ❌ cross mark
    "\u274e"  # cross mark negative squared
    "\u2753-\u2755"  # question/exclamation ornaments
    "\u2757"  # heavy exclamation mark
    "\u2763\u2764"  # heart exclamation, red heart
    "\u2795-\u2797"  # heavy plus/minus/divide
    "\u27a1"  # right arrow
    "\u27b0"  # curly loop
    "\u27bf"  # double curly loop
    "\u2934\u2935"  # right arrow curving up/down
    "\u2b05-\u2b07"  # left/up/down arrows
    "\u2b1b\u2b1c"  # black/white large squares
    "\u2b50"  # star
    "\u2b55"  # heavy large circle
    "\u3030"  # wavy dash
    "\u303d"  # part alternation mark
    "\u3297"  # circled ideograph congratulation
    "\u3299"  # circled ideograph secret
    # --- SMP catch-all (all emoji/symbols above BMP) ---
    "\U00010000-\U0001ffff"
    # --- Modifiers / joiners ---
    "\ufe00-\ufe0f"  # variation selectors
    "\u200d"  # zero width joiner
    "]+",
)


def _strip_emoji(text: str) -> str:
    """Remove emoji characters that crash headless Chromium."""
    return _EMOJI_RE.sub("", text)


class TerminalCommand(ABC):
    """Base class for terminal action commands."""

    @abstractmethod
    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        """Execute the terminal action via Playwright JS calls."""

    @abstractmethod
    def describe(self, step: Step) -> str:
        """Human-readable description."""


class TerminalRunCommand(TerminalCommand):
    """Type a command in the terminal and optionally display output."""

    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        import json
        import time

        if not step.command:
            raise ValueError("TerminalRunCommand requires 'command'")

        # Type the command character-by-character
        # Use JSON encoding to safely pass Unicode (emojis, special chars)
        safe_cmd = json.dumps(_strip_emoji(step.command))
        # Use void() to fire-and-forget the async typeCommand — avoids
        # blocking Playwright's CDP connection for the full animation
        # duration, which would conflict with the CDP screen recorder.
        browser.evaluate_js(f"void(typeCommand({safe_cmd}, {typing_speed}))")

        # Wait for typing to finish (approximate)
        typing_duration = len(step.command) / typing_speed
        time.sleep(typing_duration + 0.2)

        # Show output if provided
        if step.output is not None:
            time.sleep(output_delay)
            if isinstance(step.output, list):
                output_text = "\n".join(step.output)
            else:
                output_text = step.output
            safe_output = json.dumps(_strip_emoji(output_text))
            browser.evaluate_js(f"showOutput({safe_output})")
            time.sleep(0.1)

        # Show a new prompt
        browser.evaluate_js("showPrompt()")

    def describe(self, step: Step) -> str:
        out = " (with output)" if step.output else ""
        return f"Terminal: $ {step.command}{out}"


class TerminalClearCommand(TerminalCommand):
    """Clear the terminal screen."""

    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        browser.evaluate_js("clearTerminal()")

    def describe(self, step: Step) -> str:
        return "Terminal: clear"


class TerminalZoomCommand(TerminalCommand):
    """Zoom in or out on the terminal content."""

    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        import time

        scale = step.zoom_level if step.zoom_level is not None else 1.5
        duration_s = step.zoom_duration if step.zoom_duration is not None else 0.8
        duration_ms = int(duration_s * 1000)
        browser.evaluate_js(f"void(zoomTerminal({scale}, {duration_ms}))")
        time.sleep(duration_s + 0.1)

    def describe(self, step: Step) -> str:
        scale = step.zoom_level if step.zoom_level is not None else 1.5
        return f"Terminal: zoom {scale}x"


_TERMINAL_COMMANDS: dict[str, type[TerminalCommand]] = {
    "terminal_run": TerminalRunCommand,
    "terminal_clear": TerminalClearCommand,
    "terminal_zoom": TerminalZoomCommand,
}


def get_terminal_command(action: str) -> TerminalCommand:
    """Instantiate the appropriate terminal command for *action*."""
    cls = _TERMINAL_COMMANDS.get(action)
    if cls is None:
        valid = sorted(_TERMINAL_COMMANDS.keys())
        close = difflib.get_close_matches(action, valid, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(
            f"Unknown terminal action '{action}'. Valid terminal actions: {', '.join(valid)}.{hint}"
        )
    return cls()
