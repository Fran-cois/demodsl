"""Command pattern for browser actions."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from demodsl.models import Step
from demodsl.providers.base import BrowserProvider

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
        browser.type_text(step.locator, step.value)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Type '{step.value}' into {target}"


class ScrollCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        direction = step.direction or "down"
        pixels = step.pixels or 300
        browser.scroll(direction, pixels)

    def describe(self, step: Step) -> str:
        return f"Scroll {step.direction or 'down'} {step.pixels or 300}px"


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
