"""Abstract base classes for DemoDSL providers (Abstract Factory pattern)."""

from __future__ import annotations

import functools
import importlib.util
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from demodsl.models import Locator, MobileConfig, Viewport

logger = logging.getLogger(__name__)


# ── Errors ───────────────────────────────────────────────────────────────────


class MissingVoiceDependencyError(RuntimeError):
    """A voice engine was selected without its third-party package (issue #35).

    ``voice.engine`` is a ``Literal``, so a config naming an engine whose
    package is not installed passes validation and only blows up deep inside
    ``providers/voice.py`` with an opaque ``ModuleNotFoundError`` — after the
    run has started. Raising this at provider construction fails fast and,
    crucially, says what to install.

    Deliberately **not** an ``OSError``/``ValueError``: the narration
    orchestrator falls back to the silent ``dummy`` provider on those, which
    would ship a mute video instead of reporting a fixable environment gap.
    """

    def __init__(self, engine: str, module: str, install: str) -> None:
        self.engine = engine
        self.module = module
        self.install = install
        super().__init__(
            f"voice.engine {engine!r} requires the {module.split('.')[0]!r} package, "
            f"which is not installed: {install}"
        )


class UnsupportedLocatorError(ValueError):
    """A provider was handed a locator strategy it cannot resolve (issue #28).

    Subclasses :class:`ValueError` so existing ``except ValueError`` handlers
    keep working, but is a distinct type so the engine can treat it exactly
    like "element not found" — i.e. subject to the step's ``on_error`` policy
    rather than a hard render abort.

    Normally unreachable: ``Scenario`` rejects unsupported strategies at load
    time. This stays as the runtime backstop for configs built in code.
    """

    def __init__(self, locator_type: str, subsystem: str = "web") -> None:
        from demodsl.models.scenario import supported_locator_types

        self.locator_type = locator_type
        self.subsystem = subsystem
        supported = sorted(supported_locator_types(subsystem))
        super().__init__(
            f"Unsupported locator type: {locator_type!r} is not resolvable by "
            f"{subsystem} providers. Supported: {supported}."
        )


# ── Retry decorator ──────────────────────────────────────────────────────────

F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[BaseException], ...] | None = None,
) -> Callable[[F], F]:
    """Decorator: retry on transient errors with exponential backoff.

    By default retries on any Exception. Pass *retryable_exceptions* to
    restrict to specific types (e.g. timeout, HTTP 429/5xx).

    .. warning::
       This implementation uses :func:`time.sleep` and is **synchronous
       only**. Do not wrap ``async`` callables or call from inside an
       asyncio event loop or it will block the loop.
    """
    exc_types = retryable_exceptions or (Exception,)

    def decorator(func: F) -> F:
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

        return wrapper  # type: ignore[return-value]

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


#: Third-party package each voice engine imports at generation time, with the
#: command that installs it (issue #35). Engines absent from this map need
#: nothing beyond the base install, or only an external binary the provider
#: itself looks up (``espeak``, ``piper``).
#:
#: Keep in sync with the ``VoiceConfig.engine`` literal — ``tests/test_issue_35``
#: asserts every key is a registered engine.
VOICE_ENGINE_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "gtts": ("gtts", "pip install 'demodsl[gtts]'"),
    "google": ("google.cloud.texttospeech", "pip install google-cloud-texttospeech"),
    "aws_polly": ("boto3", "pip install boto3"),
    "coqui": ("TTS", "pip install TTS"),
    "voxtral": ("mlx_audio", "pip install mlx-audio soundfile"),
}


def missing_voice_dependency(engine: str) -> tuple[str, str] | None:
    """Return ``(module, install_command)`` if *engine* cannot import, else None.

    Uses :func:`importlib.util.find_spec` so nothing is imported (importing
    ``TTS`` alone costs seconds and pulls torch).
    """
    requirement = VOICE_ENGINE_REQUIREMENTS.get(engine)
    if requirement is None:
        return None
    module, install = requirement
    try:
        found = importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        # Namespace parent missing (``google`` without ``google.cloud``) or a
        # half-installed distribution: treat as absent, the hint still applies.
        found = False
    return None if found else (module, install)


class VoiceProviderFactory:
    _registry: dict[str, type[VoiceProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[VoiceProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> VoiceProvider:
        if name not in cls._registry:
            raise ValueError(f"Unknown voice provider '{name}'. Available: {list(cls._registry)}")
        missing = missing_voice_dependency(name)
        if missing is not None:
            raise MissingVoiceDependencyError(name, *missing)
        return cls._registry[name](**kwargs)


# ── Browser ───────────────────────────────────────────────────────────────────


class BrowserProvider(ABC):
    #: Simulated human operator, injected by the orchestrator before the
    #: first step. ``None`` keeps the deterministic robot behaviour, so
    #: providers that ignore it (Selenium) simply stay literal.
    humanize: Any | None = None

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
    def navigate(self, url: str, *, timeout: int = 30_000) -> None:
        """Navigate to a URL."""

    def reload(self) -> None:
        """Reload the current page (drops all JS state and DOM)."""
        # Default: re-navigate to current URL.  Subclasses may override.
        pass

    @abstractmethod
    def click(self, locator: Locator) -> None:
        """Click an element."""

    @abstractmethod
    def type_text(self, locator: Locator, value: str) -> None:
        """Type text into an element."""

    @abstractmethod
    def type_text_organic(
        self, locator: Locator, value: str, char_rate: float, variance: float = 0.0
    ) -> None:
        """Type text character-by-character at *char_rate* chars/second.

        *variance* (0–1) adds per-character delay randomisation.
        """

    @abstractmethod
    def scroll(self, direction: str, pixels: int, *, smooth: bool = False) -> None:
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

    def press_keys(self, keys: str) -> None:
        """Press a keyboard shortcut (e.g. 'Meta+f', 'Control+Shift+p').

        Default implementation dispatches ``KeyboardEvent`` via JS.
        Provider subclasses should override with native keyboard APIs.
        """
        parts = keys.split("+")
        key = parts[-1]
        ctrl = "true" if "Control" in parts else "false"
        meta = "true" if "Meta" in parts else "false"
        shift = "true" if "Shift" in parts else "false"
        alt = "true" if "Alt" in parts else "false"
        self.evaluate_js(f"""
        (() => {{
            const ev = new KeyboardEvent('keydown', {{
                key: '{key}',
                ctrlKey: {ctrl},
                metaKey: {meta},
                shiftKey: {shift},
                altKey: {alt},
                bubbles: true,
            }});
            document.activeElement.dispatchEvent(ev);
        }})()
        """)

    def hover(self, locator: Locator) -> None:
        """Hover an element.  Default is a no-op; browser providers override."""
        pass

    def move_mouse(self, x: float, y: float) -> None:
        """Move the real pointer to (x, y).

        Synthetic ``mouseenter``/``mouseover`` events do **not** apply CSS
        ``:hover`` — only a real input event does. Default is a no-op so
        providers without pointer control stay usable.
        """
        pass

    def scroll_into_view(self, locator: Locator) -> bool:
        """Best-effort scroll of the element into view. ``False`` when unsupported."""
        return False

    def drag_and_drop(
        self,
        source: Locator,
        target: Locator | None = None,
        *,
        target_x: float | None = None,
        target_y: float | None = None,
    ) -> None:
        """Drag the source element to target element or coordinates."""
        raise NotImplementedError("drag_and_drop is not supported by this provider")

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
            raise ValueError(f"Unknown browser provider '{name}'. Available: {list(cls._registry)}")
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
            raise ValueError(f"Unknown render provider '{name}'. Available: {list(cls._registry)}")
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
        background_shape: str = "square",
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
            raise ValueError(f"Unknown avatar provider '{name}'. Available: {list(cls._registry)}")
        return cls._registry[name](**kwargs)


# ── Mobile ────────────────────────────────────────────────────────────────────


class MobileProvider(ABC):
    """Abstract base for native mobile app automation providers."""

    @abstractmethod
    def launch(self, config: MobileConfig, video_dir: Path) -> None:
        """Start a mobile session and begin screen recording."""

    @abstractmethod
    def tap(
        self,
        locator: Locator | None = None,
        x: float | None = None,
        y: float | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Tap on an element or coordinates."""

    @abstractmethod
    def swipe(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        duration_ms: int = 800,
    ) -> None:
        """Swipe gesture from (start_x, start_y) to (end_x, end_y)."""

    @abstractmethod
    def pinch(
        self,
        locator: Locator | None = None,
        scale: float = 0.5,
        duration_ms: int = 500,
    ) -> None:
        """Pinch gesture on an element or screen center."""

    @abstractmethod
    def long_press(
        self,
        locator: Locator | None = None,
        x: float | None = None,
        y: float | None = None,
        duration_ms: int = 1000,
    ) -> None:
        """Long press on an element or coordinates."""

    @abstractmethod
    def scroll(self, direction: str, pixels: int) -> None:
        """Scroll the screen in a direction."""

    @abstractmethod
    def type_text(self, locator: Locator, value: str) -> None:
        """Type text into an element."""

    @abstractmethod
    def click(self, locator: Locator) -> None:
        """Tap an element (alias for tap with locator)."""

    @abstractmethod
    def back(self) -> None:
        """Press the back button."""

    @abstractmethod
    def home(self) -> None:
        """Press the home button."""

    @abstractmethod
    def open_notifications(self) -> None:
        """Open the notification shade / control center."""

    @abstractmethod
    def app_switch(self) -> None:
        """Open the app switcher / recent apps."""

    @abstractmethod
    def rotate(self, orientation: str) -> None:
        """Rotate the device to portrait or landscape."""

    @abstractmethod
    def shake(self) -> None:
        """Shake the device."""

    @abstractmethod
    def screenshot(self, path: Path) -> Path:
        """Take a screenshot, return path."""

    @abstractmethod
    def wait_for(self, locator: Locator, timeout: float) -> None:
        """Wait for an element to appear."""

    @abstractmethod
    def close(self) -> Path | None:
        """Stop recording and close the session. Returns path to recorded video."""

    def launch_without_recording(self, config: MobileConfig) -> None:
        """Start a mobile session *without* screen recording.

        Used by diagnostic commands (``test-connection``, ``inspect``).
        Default implementation delegates to :meth:`launch` with a temp dir.
        """
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="demodsl_probe_"))
        self.launch(config, tmp)
        # Immediately stop recording so the session is lightweight
        try:
            self._stop_recording_only()
        except Exception:  # noqa: BLE001
            pass

    def _stop_recording_only(self) -> None:
        """Stop recording without closing the session. Override if needed."""

    def page_source(self) -> str:
        """Return the page source (XML accessibility tree) of the current screen."""
        raise NotImplementedError("page_source not supported by this provider")

    def get_window_size(self) -> dict[str, int]:
        """Return {'width': …, 'height': …} of the device screen."""
        raise NotImplementedError("get_window_size not supported by this provider")

    @property
    def platform(self) -> str | None:
        """Platform of the active session ('ios' / 'android'), or None."""
        return None

    def get_attribute(self, locator: Locator, name: str) -> str | None:
        """Return an element attribute (e.g. a switch's on/off state)."""
        raise NotImplementedError("get_attribute not supported by this provider")


class MobileProviderFactory:
    _registry: dict[str, type[MobileProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[MobileProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> MobileProvider:
        if name not in cls._registry:
            raise ValueError(f"Unknown mobile provider '{name}'. Available: {list(cls._registry)}")
        return cls._registry[name](**kwargs)


# ── Blender 3D ────────────────────────────────────────────────────────────────


class BlenderProvider(ABC):
    """Renders a recorded video inside a 3D device mockup via Blender."""

    @abstractmethod
    def render(
        self,
        video_path: Path,
        config: Any,
        output_path: Path,
        *,
        scroll_positions: list[tuple[float, int]] | None = None,
    ) -> Path:
        """Render *video_path* inside a 3D device and write the result to
        *output_path*.  Returns the path to the rendered video."""

    @abstractmethod
    def check_available(self) -> bool:
        """Return True if the Blender backend is ready to use."""


class BlenderProviderFactory:
    _registry: dict[str, type[BlenderProvider]] = {}
    _plugins_loaded: bool = False

    @classmethod
    def register(cls, name: str, provider_cls: type[BlenderProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def _load_plugins(cls) -> None:
        """Discover blender providers from installed plugins via entry_points."""
        if cls._plugins_loaded:
            return
        cls._plugins_loaded = True
        from importlib.metadata import entry_points

        for ep in entry_points(group="demodsl.providers.blender"):
            if ep.name not in cls._registry:
                try:
                    provider_cls = ep.load()
                    cls.register(ep.name, provider_cls)
                    logger.info(
                        "Discovered blender provider '%s' from %s",
                        ep.name,
                        ep.value,
                    )
                except Exception:
                    logger.warning(
                        "Failed to load blender provider '%s'",
                        ep.name,
                        exc_info=True,
                    )

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> BlenderProvider:
        cls._load_plugins()
        if name not in cls._registry:
            raise ValueError(f"Unknown blender provider '{name}'. Available: {list(cls._registry)}")
        return cls._registry[name](**kwargs)
