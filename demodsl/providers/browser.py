"""Playwright-based browser provider."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.models import Locator, Viewport
from demodsl.providers.base import BrowserProvider, BrowserProviderFactory

logger = logging.getLogger(__name__)

_BROWSER_MAP = {"chrome": "chromium", "firefox": "firefox", "webkit": "webkit"}


class PlaywrightBrowserProvider(BrowserProvider):
    def __init__(self) -> None:
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def launch(
        self,
        browser_type: str,
        viewport: Viewport,
        video_dir: Path,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        engine_name = _BROWSER_MAP.get(browser_type, "chromium")
        launcher = getattr(self._pw, engine_name)
        self._browser = launcher.launch(headless=True)
        ctx_kwargs: dict[str, Any] = {
            "viewport": {"width": viewport.width, "height": viewport.height},
            "record_video_dir": str(video_dir),
            "record_video_size": {"width": viewport.width, "height": viewport.height},
        }
        if color_scheme is not None:
            ctx_kwargs["color_scheme"] = color_scheme
        if locale is not None:
            ctx_kwargs["locale"] = locale
        self._context = self._browser.new_context(**ctx_kwargs)
        self._page = self._context.new_page()
        logger.info(
            "Browser launched: %s %dx%d", engine_name, viewport.width, viewport.height
        )

    def navigate(self, url: str) -> None:
        self._page.goto(url, wait_until="networkidle")

    def click(self, locator: Locator) -> None:
        selector = self._resolve_selector(locator)
        self._page.click(selector)

    def type_text(self, locator: Locator, value: str) -> None:
        selector = self._resolve_selector(locator)
        self._page.fill(selector, value)

    def scroll(self, direction: str, pixels: int) -> None:
        delta_x, delta_y = 0, 0
        if direction == "down":
            delta_y = pixels
        elif direction == "up":
            delta_y = -pixels
        elif direction == "right":
            delta_x = pixels
        elif direction == "left":
            delta_x = -pixels
        self._page.evaluate(f"window.scrollBy({delta_x}, {delta_y})")

    def wait_for(self, locator: Locator, timeout: float) -> None:
        selector = self._resolve_selector(locator)
        self._page.wait_for_selector(selector, timeout=int(timeout * 1000))

    def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(path))
        return path

    def evaluate_js(self, script: str) -> Any:
        return self._page.evaluate(script)

    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        selector = self._resolve_selector(locator)
        try:
            box = self._page.locator(selector).first.bounding_box(timeout=3000)
        except Exception:
            return None
        if box is None:
            return None
        return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        selector = self._resolve_selector(locator)
        try:
            box = self._page.locator(selector).first.bounding_box(timeout=3000)
        except Exception:
            return None
        return box

    def close(self) -> Path | None:
        video_path: Path | None = None
        if self._page and self._page.video:
            video_path = Path(self._page.video.path())
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        return video_path

    @staticmethod
    def _resolve_selector(locator: Locator) -> str:
        if locator.type == "css":
            return locator.value
        if locator.type == "id":
            return f"#{locator.value}"
        if locator.type == "xpath":
            return f"xpath={locator.value}"
        if locator.type == "text":
            return f"text={locator.value}"
        raise ValueError(f"Unsupported locator type: {locator.type}")


# Register with factory
BrowserProviderFactory.register("playwright", PlaywrightBrowserProvider)
