"""Abstract base classes for DemoDSL providers (Abstract Factory pattern)."""

from __future__ import annotations

import functools
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

from demodsl.models import Locator, Viewport

logger = logging.getLogger(__name__)


# ── Retry decorator ──────────────────────────────────────────────────────────

F = TypeVar("F")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[BaseException], ...] | None = None,
):
    """Decorator: retry on transient errors with exponential backoff.

    By default retries on any Exception. Pass *retryable_exceptions* to
    restrict to specific types (e.g. timeout, HTTP 429/5xx).
    """
    exc_types = retryable_exceptions or (Exception,)

    def decorator(func):  # type: ignore[no-untyped-def]
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exc_types as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                            func.__qualname__,
                            attempt + 1,
                            max_retries + 1,
                            exc,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__qualname__,
                            max_retries + 1,
                            exc,
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ── Voice ─────────────────────────────────────────────────────────────────────


class VoiceProvider(ABC):
    @abstractmethod
    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        """Generate a TTS audio file. Returns path to the MP3.

        Args:
            reference_audio: Optional path to a .wav/.mp3 sample for voice cloning.
                             Supported by: elevenlabs, coqui, cosyvoice, custom.
        """

    def cache_extra(self) -> dict[str, str]:
        """Return provider-specific parameters that affect audio output.

        Override in subclasses to include model names, API endpoints, or
        other settings that change the generated audio.  The returned
        dict is folded into the TTS cache key so that a configuration
        change (e.g. switching Piper model) invalidates stale entries.
        """
        return {}

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
    def launch(
        self,
        browser_type: str,
        viewport: Viewport,
        video_dir: Path,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        """Launch browser with given viewport, recording video to *video_dir*."""

    @abstractmethod
    def launch_without_recording(
        self,
        browser_type: str,
        viewport: Viewport,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        """Launch browser without video recording (for pre_steps warmup)."""

    @abstractmethod
    def restart_with_recording(self, video_dir: Path) -> None:
        """Close current context and reopen with video recording on the same page."""

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
