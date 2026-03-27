"""Abstract base classes for DemoDSL providers (Abstract Factory pattern)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from demodsl.models import Locator, Viewport

logger = logging.getLogger(__name__)


# ── Voice ─────────────────────────────────────────────────────────────────────

class VoiceProvider(ABC):
    @abstractmethod
    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        """Generate a TTS audio file. Returns path to the MP3."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


class VoiceProviderFactory:
    _registry: dict[str, type[VoiceProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[VoiceProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> VoiceProvider:
        if name not in cls._registry:
            raise ValueError(
                f"Unknown voice provider '{name}'. Available: {list(cls._registry)}"
            )
        return cls._registry[name](**kwargs)


# ── Browser ───────────────────────────────────────────────────────────────────

class BrowserProvider(ABC):
    @abstractmethod
    def launch(self, browser_type: str, viewport: Viewport, video_dir: Path) -> None:
        """Launch browser with given viewport, recording video to *video_dir*."""

    @abstractmethod
    def navigate(self, url: str) -> None:
        """Navigate to a URL."""

    @abstractmethod
    def click(self, locator: Locator) -> None:
        """Click an element."""

    @abstractmethod
    def type_text(self, locator: Locator, value: str) -> None:
        """Type text into an element."""

    @abstractmethod
    def scroll(self, direction: str, pixels: int) -> None:
        """Scroll the page."""

    @abstractmethod
    def wait_for(self, locator: Locator, timeout: float) -> None:
        """Wait for an element to appear."""

    @abstractmethod
    def screenshot(self, path: Path) -> Path:
        """Take a screenshot, return path."""

    @abstractmethod
    def evaluate_js(self, script: str) -> Any:
        """Execute JavaScript in the page context."""

    @abstractmethod
    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        """Return (x, y) center of the element, or None if not found."""

    @abstractmethod
    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        """Return {x, y, width, height} of the element, or None if not found."""

    @abstractmethod
    def close(self) -> Path | None:
        """Close browser, return path to recorded video if any."""


class BrowserProviderFactory:
    _registry: dict[str, type[BrowserProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[BrowserProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> BrowserProvider:
        if name not in cls._registry:
            raise ValueError(
                f"Unknown browser provider '{name}'. Available: {list(cls._registry)}"
            )
        return cls._registry[name](**kwargs)


# ── Render ────────────────────────────────────────────────────────────────────

class RenderProvider(ABC):
    @abstractmethod
    def compose(self, segments: list[Path], output: Path) -> Path:
        """Concatenate video segments into one file."""

    @abstractmethod
    def add_intro(self, video: Path, intro_config: dict[str, Any]) -> Path:
        """Prepend an intro sequence."""

    @abstractmethod
    def add_outro(self, video: Path, outro_config: dict[str, Any]) -> Path:
        """Append an outro sequence."""

    @abstractmethod
    def apply_watermark(self, video: Path, watermark_config: dict[str, Any]) -> Path:
        """Overlay a watermark."""

    @abstractmethod
    def export(self, video: Path, fmt: str, output_dir: Path, **kwargs: Any) -> Path:
        """Export video in a specific format."""


class RenderProviderFactory:
    _registry: dict[str, type[RenderProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[RenderProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> RenderProvider:
        if name not in cls._registry:
            raise ValueError(
                f"Unknown render provider '{name}'. Available: {list(cls._registry)}"
            )
        return cls._registry[name](**kwargs)


# ── Avatar ────────────────────────────────────────────────────────────────────

class AvatarProvider(ABC):
    """Generates a video clip of an avatar synchronized to narration audio."""

    @abstractmethod
    def generate(
        self,
        audio_path: Path,
        *,
        image: str | None = None,
        size: int = 120,
        style: str = "bounce",
        shape: str = "circle",
        narration_text: str | None = None,
    ) -> Path:
        """Generate avatar video clip synced to *audio_path*. Returns path to MP4 with alpha."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


class AvatarProviderFactory:
    _registry: dict[str, type[AvatarProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[AvatarProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> AvatarProvider:
        if name not in cls._registry:
            raise ValueError(
                f"Unknown avatar provider '{name}'. Available: {list(cls._registry)}"
            )
        return cls._registry[name](**kwargs)
