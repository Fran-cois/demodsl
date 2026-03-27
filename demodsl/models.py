"""Pydantic v2 models for the DemoDSL DSL."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ── Metadata ──────────────────────────────────────────────────────────────────

class Metadata(BaseModel):
    title: str
    description: str | None = None
    author: str | None = None
    version: str | None = None


# ── Voice (TTS) ──────────────────────────────────────────────────────────────

class VoiceConfig(BaseModel):
    engine: Literal["elevenlabs", "google", "azure", "aws_polly", "openai", "cosyvoice", "coqui", "piper", "local_openai"] = "elevenlabs"
    voice_id: str = "josh"
    speed: float = 1.0
    pitch: int = 0


# ── Audio ─────────────────────────────────────────────────────────────────────

class BackgroundMusic(BaseModel):
    file: str
    volume: float = 0.3
    ducking_mode: Literal["none", "light", "moderate", "heavy"] = "moderate"
    loop: bool = True


class VoiceProcessing(BaseModel):
    normalize: bool = True
    target_dbfs: int = -20
    remove_silence: bool = True
    silence_threshold: int = -40
    enhance_clarity: bool = False
    enhance_warmth: bool = False
    noise_reduction: bool = False


class Compression(BaseModel):
    threshold: int = -20
    ratio: float = 3.0
    attack: int = 5
    release: int = 50


class AudioEffects(BaseModel):
    eq_preset: str | None = None
    reverb_preset: str | None = None
    compression: Compression | None = None


class AudioConfig(BaseModel):
    background_music: BackgroundMusic | None = None
    voice_processing: VoiceProcessing | None = None
    effects: AudioEffects | None = None


# ── Device Rendering ──────────────────────────────────────────────────────────

class DeviceRendering(BaseModel):
    device: str = "iphone_15_pro"
    orientation: Literal["portrait", "landscape"] = "portrait"
    quality: Literal["low", "medium", "high"] = "high"
    render_engine: Literal["eevee", "cycles"] = "eevee"
    camera_animation: str = "orbit_smooth"
    lighting: str = "studio"


# ── Video ─────────────────────────────────────────────────────────────────────

class Intro(BaseModel):
    duration: float = 3.0
    type: str = "fade_in"
    text: str | None = None
    subtitle: str | None = None
    font_size: int = 60
    font_color: str = "#FFFFFF"
    background_color: str = "#1a1a1a"


class Transitions(BaseModel):
    type: Literal["crossfade", "slide", "zoom", "dissolve"] = "crossfade"
    duration: float = 0.5


class Watermark(BaseModel):
    image: str
    position: Literal[
        "top_left", "top_right", "bottom_left", "bottom_right", "center"
    ] = "bottom_right"
    opacity: float = 0.7
    size: int = 100


class Outro(BaseModel):
    duration: float = 4.0
    type: str = "fade_out"
    text: str | None = None
    subtitle: str | None = None
    cta: str | None = None


class VideoOptimization(BaseModel):
    target_size_mb: int | None = None
    web_optimized: bool = True
    compression_level: Literal["low", "balanced", "high"] = "balanced"


class VideoConfig(BaseModel):
    intro: Intro | None = None
    transitions: Transitions | None = None
    watermark: Watermark | None = None
    outro: Outro | None = None
    optimization: VideoOptimization | None = None


# ── Scenarios ─────────────────────────────────────────────────────────────────

class Viewport(BaseModel):
    width: int = 1920
    height: int = 1080


class Locator(BaseModel):
    type: Literal["css", "id", "xpath", "text"] = "css"
    value: str


EffectType = Literal[
    "spotlight",
    "highlight",
    "confetti",
    "typewriter",
    "glow",
    "shockwave",
    "sparkle",
    "parallax",
    "cursor_trail",
    "zoom_pulse",
    "ripple",
    "fade_in",
    "fade_out",
    "glitch",
    "neon_glow",
    "slide_in",
    "success_checkmark",
    "vignette",
]


class Effect(BaseModel):
    type: EffectType
    duration: float | None = None
    intensity: float | None = None
    color: str | None = None
    speed: float | None = None
    scale: float | None = None
    depth: int | None = None
    direction: str | None = None


class Step(BaseModel):
    action: Literal["navigate", "click", "type", "scroll", "wait_for", "screenshot"]

    # navigate
    url: str | None = None

    # click / type / wait_for
    locator: Locator | None = None

    # type
    value: str | None = None

    # scroll
    direction: Literal["up", "down", "left", "right"] | None = None
    pixels: int | None = None

    # wait_for
    timeout: float | None = None

    # screenshot
    filename: str | None = None

    # common optional
    narration: str | None = None
    wait: float | None = None
    effects: list[Effect] | None = None


class Scenario(BaseModel):
    name: str
    url: str
    browser: Literal["chrome", "firefox", "webkit"] = "chrome"
    viewport: Viewport = Field(default_factory=Viewport)
    steps: list[Step] = Field(default_factory=list)


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineStage(BaseModel):
    """A single pipeline stage parsed from a one-key dict in the YAML list."""

    stage_type: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _parse_from_dict(cls, data: Any) -> Any:
        """Accept ``{"restore_audio": {"denoise": true}}`` shorthand."""
        if isinstance(data, dict) and "stage_type" not in data:
            if len(data) != 1:
                raise ValueError(
                    f"Pipeline stage dict must have exactly 1 key, got {list(data.keys())}"
                )
            key, value = next(iter(data.items()))
            return {"stage_type": key, "params": value if isinstance(value, dict) else {}}
        return data


# ── Output ────────────────────────────────────────────────────────────────────

class Thumbnail(BaseModel):
    timestamp: float


class SocialExport(BaseModel):
    platform: str
    resolution: str | None = None
    bitrate: str | None = None
    aspect_ratio: str | None = None
    max_duration: int | None = None
    max_size_mb: int | None = None


class OutputConfig(BaseModel):
    filename: str = "output.mp4"
    directory: str = "output/"
    formats: list[str] = Field(default_factory=lambda: ["mp4"])
    thumbnails: list[Thumbnail] | None = None
    social: list[SocialExport] | None = None


# ── Analytics ─────────────────────────────────────────────────────────────────

class Analytics(BaseModel):
    track_engagement: bool = False
    heatmap: bool = False
    click_tracking: bool = False


# ── Root config ───────────────────────────────────────────────────────────────

class DemoConfig(BaseModel):
    metadata: Metadata
    voice: VoiceConfig | None = None
    audio: AudioConfig | None = None
    device_rendering: DeviceRendering | None = None
    video: VideoConfig | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    pipeline: list[PipelineStage] = Field(default_factory=list)
    output: OutputConfig | None = None
    analytics: Analytics | None = None
