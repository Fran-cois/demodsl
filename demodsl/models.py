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
    engine: Literal["elevenlabs", "google", "azure", "aws_polly", "openai", "cosyvoice", "coqui", "piper", "local_openai", "espeak", "gtts", "custom"] = "elevenlabs"
    voice_id: str = "josh"
    speed: float = 1.0
    pitch: int = 0
    reference_audio: str | None = None  # path to .wav/.mp3 for voice cloning


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
    "cursor_trail_rainbow",
    "cursor_trail_comet",
    "cursor_trail_glow",
    "cursor_trail_line",
    "cursor_trail_particles",
    "cursor_trail_fire",
    "zoom_pulse",
    "ripple",
    "fade_in",
    "fade_out",
    "glitch",
    "neon_glow",
    "slide_in",
    "success_checkmark",
    "vignette",
    # Fun / celebration effects
    "emoji_rain",
    "fireworks",
    "bubbles",
    "snow",
    "star_burst",
    "party_popper",
    # Camera movement effects
    "drone_zoom",
    "ken_burns",
    "zoom_to",
    "dolly_zoom",
    "elastic_zoom",
    "camera_shake",
    "whip_pan",
    "rotate",
    # Cinematic effects
    "letterbox",
    "film_grain",
    "color_grade",
    "focus_pull",
    "tilt_shift",
    # New browser effects — text / interaction / visual
    "text_highlight",
    "text_scramble",
    "magnetic_hover",
    "tooltip_annotation",
    "morphing_background",
    "matrix_rain",
    "frosted_glass",
    # New post-effects — retro / stylised
    "crt_scanlines",
    "chromatic_aberration",
    "vhs_distortion",
    "pixel_sort",
    # New post-effects — depth & light
    "bloom",
    "bokeh_blur",
    "light_leak",
    # New post-effects — transitions
    "wipe",
    "iris",
    "dissolve_noise",
    # New overlays — utility
    "progress_bar",
    "countdown_timer",
    "callout_arrow",
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
    target_x: float | None = None
    target_y: float | None = None
    angle: float | None = None
    ratio: float | None = None
    preset: str | None = None
    focus_position: float | None = None
    # New fields for added effects
    threshold: float | None = None
    line_spacing: int | None = None
    offset: int | None = None
    grain_size: int | None = None
    focus_area: float | None = None
    radius: float | None = None
    text: str | None = None
    position: str | None = None
    style: str | None = None
    density: float | None = None
    colors: list[str] | None = None


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
    card: CardContent | None = None


class CursorConfig(BaseModel):
    visible: bool = True
    style: Literal["dot", "pointer"] = "dot"
    color: str = "#ef4444"
    size: int = 20
    click_effect: Literal["ripple", "pulse", "none"] = "ripple"
    smooth: float = 0.4


class GlowSelectConfig(BaseModel):
    enabled: bool = True
    colors: list[str] = Field(
        default_factory=lambda: ["#a855f7", "#6366f1", "#ec4899", "#a855f7"]
    )
    duration: float = 0.8
    padding: int = 8
    border_radius: int = 12
    intensity: float = 0.9


class AvatarConfig(BaseModel):
    enabled: bool = True
    provider: Literal["animated", "d-id", "heygen", "sadtalker"] = "animated"
    image: str | None = None  # path or preset name: "default", "robot", "circle"
    position: Literal[
        "bottom-right", "bottom-left", "top-right", "top-left"
    ] = "bottom-right"
    size: int = 120
    style: Literal["bounce", "waveform", "pulse", "equalizer", "xp_bliss", "clippy", "visualizer", "pacman", "space_invader", "mario_block", "nyan_cat", "matrix", "pickle_rick", "chrome_dino", "marvin", "mac128k", "floppy_disk", "bsod", "bugdroid", "qr_code", "gpu_sweat", "rubber_duck", "fail_whale", "server_rack", "cursor_hand", "vhs_tape", "cloud", "wifi_low", "nokia3310", "cookie", "modem56k", "esc_key", "sad_mac", "usb_cable", "hourglass", "firewire", "ai_hallucinated", "tamagotchi", "lasso_tool", "battery_low", "incognito"] = "bounce"
    shape: Literal["circle", "rounded", "square"] = "circle"
    background: str = "rgba(0,0,0,0.5)"
    api_key: str | None = None  # for paid providers, supports ${ENV_VAR}
    show_subtitle: bool = False  # render narration text below avatar box
    subtitle_font_size: int = 18
    subtitle_font_color: str = "#FFFFFF"
    subtitle_bg_color: str = "rgba(0,0,0,0.7)"


class SubtitleConfig(BaseModel):
    enabled: bool = True
    style: Literal[
        "classic", "tiktok", "color", "word_by_word", "typewriter", "karaoke",
        "bounce", "cinema", "highlight_line", "fade_word", "emoji_react",
    ] = "classic"
    speed: Literal["slow", "normal", "fast", "tiktok"] = "normal"
    font_size: int = 48
    font_family: str = "Arial"
    font_color: str = "#FFFFFF"
    background_color: str = "rgba(0,0,0,0.6)"
    position: Literal["bottom", "center", "top"] = "bottom"
    highlight_color: str = "#FFD700"
    max_words_per_line: int = 8
    animation: Literal["none", "fade", "pop", "slide"] = "none"


class PopupCardConfig(BaseModel):
    enabled: bool = True
    position: Literal[
        "bottom-right", "bottom-left", "top-right", "top-left", "bottom-center", "top-center"
    ] = "bottom-right"
    theme: Literal["glass", "dark", "light", "gradient"] = "glass"
    max_width: int = 420
    animation: Literal["slide", "fade", "scale"] = "slide"
    accent_color: str = "#818cf8"
    show_icon: bool = True
    show_progress: bool = True


class CardContent(BaseModel):
    """Content for a popup card displayed during a step."""
    title: str | None = None
    body: str | None = None
    items: list[str] | None = None
    icon: str | None = None  # emoji or short text


class Scenario(BaseModel):
    name: str
    url: str
    browser: Literal["chrome", "firefox", "webkit"] = "chrome"
    viewport: Viewport = Field(default_factory=Viewport)
    cursor: CursorConfig | None = None
    glow_select: GlowSelectConfig | None = None
    popup_card: PopupCardConfig | None = None
    avatar: AvatarConfig | None = None
    subtitle: SubtitleConfig | None = None
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


class DeployConfig(BaseModel):
    """Cloud deployment configuration for uploading output videos."""
    provider: Literal["s3", "gcs", "azure_blob", "r2", "custom"]
    bucket: str
    region: str | None = None
    prefix: str = ""
    acl: str | None = None
    content_type: str = "video/mp4"
    endpoint_url: str | None = None  # custom S3-compatible endpoint (R2, MinIO, etc.)
    # Credentials resolve via env vars — supports ${ENV_VAR} syntax
    access_key: str | None = None  # ${AWS_ACCESS_KEY_ID}
    secret_key: str | None = None  # ${AWS_SECRET_ACCESS_KEY}
    # GCS
    project: str | None = None
    credentials_file: str | None = None  # path to service account JSON
    # Azure
    connection_string: str | None = None  # ${AZURE_STORAGE_CONNECTION_STRING}
    container: str | None = None  # alias for bucket in Azure terminology


class OutputConfig(BaseModel):
    filename: str = "output.mp4"
    directory: str = "output/"
    formats: list[str] = Field(default_factory=lambda: ["mp4"])
    thumbnails: list[Thumbnail] | None = None
    social: list[SocialExport] | None = None
    deploy: DeployConfig | None = None


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
    subtitle: SubtitleConfig | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    pipeline: list[PipelineStage] = Field(default_factory=list)
    output: OutputConfig | None = None
    analytics: Analytics | None = None
