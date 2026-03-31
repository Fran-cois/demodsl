"""Tests for demodsl.providers.base — Provider factories (Voice, Browser, Render)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from demodsl.models import Locator, Viewport
from demodsl.providers.base import (
    BrowserProvider,
    BrowserProviderFactory,
    RenderProvider,
    RenderProviderFactory,
    VoiceProvider,
    VoiceProviderFactory,
)


# ── Concrete stubs for testing ────────────────────────────────────────────────


class _StubVoice(VoiceProvider):
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def generate(
        self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0
    ) -> Path:
        return Path("stub.mp3")

    def close(self) -> None:
        pass


class _StubBrowser(BrowserProvider):
    def launch(self, browser_type: str, viewport: Viewport, video_dir: Path) -> None:
        pass

    def launch_without_recording(
        self, browser_type: str, viewport: Viewport, **kw: Any
    ) -> None:
        pass

    def restart_with_recording(self, video_dir: Path) -> None:
        pass

    def navigate(self, url: str) -> None:
        pass

    def click(self, locator: Locator) -> None:
        pass

    def type_text(self, locator: Locator, value: str) -> None:
        pass

    def type_text_organic(
        self, locator: Locator, value: str, char_rate: float, variance: float = 0.0
    ) -> None:
        pass

    def scroll(self, direction: str, pixels: int, *, smooth: bool = False) -> None:
        pass

    def wait_for(self, locator: Locator, timeout: float) -> None:
        pass

    def screenshot(self, path: Path) -> Path:
        return path

    def evaluate_js(self, script: str) -> Any:
        return None

    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        return None

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        return None

    def close(self) -> Path | None:
        return None


class _StubRender(RenderProvider):
    def compose(self, segments: list[Path], output: Path) -> Path:
        return output

    def add_intro(self, video: Path, intro_config: dict[str, Any]) -> Path:
        return video

    def add_outro(self, video: Path, outro_config: dict[str, Any]) -> Path:
        return video

    def apply_watermark(self, video: Path, watermark_config: dict[str, Any]) -> Path:
        return video

    def export(self, video: Path, fmt: str, output_dir: Path, **kwargs: Any) -> Path:
        return output_dir / f"{video.stem}.{fmt}"


# ── VoiceProviderFactory ─────────────────────────────────────────────────────


class TestVoiceProviderFactory:
    def test_register_and_create(self) -> None:
        VoiceProviderFactory.register("_test_stub", _StubVoice)
        provider = VoiceProviderFactory.create("_test_stub", output_dir=Path("/tmp"))
        assert isinstance(provider, _StubVoice)
        assert provider.kwargs == {"output_dir": Path("/tmp")}

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown voice provider"):
            VoiceProviderFactory.create("__nonexistent_voice__")

    def test_default_providers_registered(self) -> None:
        # Trigger registration by importing voice module
        import demodsl.providers.voice  # noqa: F401

        expected = {
            "elevenlabs",
            "google",
            "azure",
            "aws_polly",
            "openai",
            "cosyvoice",
            "coqui",
            "piper",
            "local_openai",
            "espeak",
            "gtts",
            "custom",
            "dummy",
        }
        registered = set(VoiceProviderFactory._registry.keys())
        assert expected.issubset(registered)


# ── BrowserProviderFactory ────────────────────────────────────────────────────


class TestBrowserProviderFactory:
    def test_register_and_create(self) -> None:
        BrowserProviderFactory.register("_test_stub_b", _StubBrowser)
        provider = BrowserProviderFactory.create("_test_stub_b")
        assert isinstance(provider, _StubBrowser)

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown browser provider"):
            BrowserProviderFactory.create("__nonexistent_browser__")

    def test_playwright_registered(self) -> None:
        import demodsl.providers.browser  # noqa: F401

        assert "playwright" in BrowserProviderFactory._registry


# ── RenderProviderFactory ─────────────────────────────────────────────────────


class TestRenderProviderFactory:
    def test_register_and_create(self) -> None:
        RenderProviderFactory.register("_test_stub_r", _StubRender)
        provider = RenderProviderFactory.create("_test_stub_r")
        assert isinstance(provider, _StubRender)

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown render provider"):
            RenderProviderFactory.create("__nonexistent_render__")

    def test_moviepy_registered(self) -> None:
        import demodsl.providers.render  # noqa: F401

        assert "moviepy" in RenderProviderFactory._registry
