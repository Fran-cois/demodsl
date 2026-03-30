"""Pydantic v2 models for the DemoDSL DSL."""

from __future__ import annotations

import os
import re
import warnings
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Strict base ──────────────────────────────────────────────────────────────


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Path safety ──────────────────────────────────────────────────────────────

_BLOCKED_PREFIXES = (
    "/etc",
    "/sys",
    "/proc",
    "/dev",
    "/var/run",
    "/tmp",
    "/root",
    "/home",
)

_BLOCKED_PREFIXES_WIN = (
    "c:\\windows",
    "c:\\system",
    "c:\\users",
    "c:\\programdata",
)


def _validate_safe_path(v: str) -> str:
    """Reject paths with directory traversal or pointing to sensitive system dirs."""
    if "\x00" in v:
        raise ValueError(f"Null byte in path is not allowed: {v!r}")

    # Normalize to resolve sequences like tmp/../etc/passwd
    normalized = os.path.normpath(v).replace("\\", "/")
    if ".." in normalized.split("/"):
        raise ValueError(f"Path traversal ('..') is not allowed: {v}")

    lower = normalized.lower()
    for prefix in _BLOCKED_PREFIXES:
        if lower.startswith(prefix):
            raise ValueError(f"Path points to a restricted system directory: {v}")
    win_lower = v.lower().replace("/", "\\")
    for prefix in _BLOCKED_PREFIXES_WIN:
        if win_lower.startswith(prefix):
            raise ValueError(f"Path points to a restricted system directory: {v}")
    return v


# ── URL safety ────────────────────────────────────────────────────────────────

_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


def _validate_url(v: str) -> str:
    """Reject URLs with dangerous schemes (file://, javascript:, data:, etc.)."""
    parsed = urlparse(v)
    if parsed.scheme and parsed.scheme not in _ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' is not allowed. "
            f"Only {sorted(_ALLOWED_URL_SCHEMES)} are accepted: {v}"
        )
    return v


# ── Color validation ─────────────────────────────────────────────────────────

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RGBA = re.compile(
    r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)$"
)
_HSL_HSLA = re.compile(
    r"^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%\s*(?:,\s*[\d.]+\s*)?\)$"
)
_CSS_COLOR_NAMES = frozenset(
    {
        "aliceblue",
        "antiquewhite",
        "aqua",
        "aquamarine",
        "azure",
        "beige",
        "bisque",
        "black",
        "blanchedalmond",
        "blue",
        "blueviolet",
        "brown",
        "burlywood",
        "cadetblue",
        "chartreuse",
        "chocolate",
        "coral",
        "cornflowerblue",
        "cornsilk",
        "crimson",
        "cyan",
        "darkblue",
        "darkcyan",
        "darkgoldenrod",
        "darkgray",
        "darkgreen",
        "darkkhaki",
        "darkmagenta",
        "darkolivegreen",
        "darkorange",
        "darkorchid",
        "darkred",
        "darksalmon",
        "darkseagreen",
        "darkslateblue",
        "darkslategray",
        "darkturquoise",
        "darkviolet",
        "deeppink",
        "deepskyblue",
        "dimgray",
        "dodgerblue",
        "firebrick",
        "floralwhite",
        "forestgreen",
        "fuchsia",
        "gainsboro",
        "ghostwhite",
        "gold",
        "goldenrod",
        "gray",
        "green",
        "greenyellow",
        "honeydew",
        "hotpink",
        "indianred",
        "indigo",
        "ivory",
        "khaki",
        "lavender",
        "lavenderblush",
        "lawngreen",
        "lemonchiffon",
        "lightblue",
        "lightcoral",
        "lightcyan",
        "lightgoldenrodyellow",
        "lightgray",
        "lightgreen",
        "lightpink",
        "lightsalmon",
        "lightseagreen",
        "lightskyblue",
        "lightslategray",
        "lightsteelblue",
        "lightyellow",
        "lime",
        "limegreen",
        "linen",
        "magenta",
        "maroon",
        "mediumaquamarine",
        "mediumblue",
        "mediumorchid",
        "mediumpurple",
        "mediumseagreen",
        "mediumslateblue",
        "mediumspringgreen",
        "mediumturquoise",
        "mediumvioletred",
        "midnightblue",
        "mintcream",
        "mistyrose",
        "moccasin",
        "navajowhite",
        "navy",
        "oldlace",
        "olive",
        "olivedrab",
        "orange",
        "orangered",
        "orchid",
        "palegoldenrod",
        "palegreen",
        "paleturquoise",
        "palevioletred",
        "papayawhip",
        "peachpuff",
        "peru",
        "pink",
        "plum",
        "powderblue",
        "purple",
        "rebeccapurple",
        "red",
        "rosybrown",
        "royalblue",
        "saddlebrown",
        "salmon",
        "sandybrown",
        "seagreen",
        "seashell",
        "sienna",
        "silver",
        "skyblue",
        "slateblue",
        "slategray",
        "snow",
        "springgreen",
        "steelblue",
        "tan",
        "teal",
        "thistle",
        "tomato",
        "turquoise",
        "violet",
        "wheat",
        "white",
        "whitesmoke",
        "yellow",
        "yellowgreen",
        "transparent",
        "inherit",
        "currentcolor",
    }
)


def _validate_css_color(v: str) -> str:
    """Validate a CSS color string, raise ValueError on invalid."""
    stripped = v.strip()
    if stripped.lower() in _CSS_COLOR_NAMES:
        return stripped
    if _HEX_COLOR.match(stripped):
        return stripped
    if _RGB_RGBA.match(stripped):
        return stripped
    if _HSL_HSLA.match(stripped):
        return stripped
    raise ValueError(
        f"Invalid CSS color: {v!r}. "
        f"Accepted formats: hex (#abc, #aabbcc), rgb(), rgba(), hsl(), hsla(), named colors."
    )


def _validate_css_color_list(v: list[str]) -> list[str]:
    """Validate each color in a list."""
    return [_validate_css_color(c) for c in v]


# ── Metadata ──────────────────────────────────────────────────────────────────


class Metadata(_StrictBase):
    title: str
    description: str | None = None
    author: str | None = None
    version: str | None = None


# ── Voice (TTS) ──────────────────────────────────────────────────────────────


class VoiceConfig(_StrictBase):
    engine: Literal[
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
    ] = "elevenlabs"
    voice_id: str = Field(default="josh", description="ElevenLabs voice preset name")
    speed: float = Field(default=1.0, gt=0, le=10.0)
    pitch: int = Field(default=0, ge=-100, le=100)
    reference_audio: str | None = None  # path to .wav/.mp3 for voice cloning
    narration_gap: float = Field(
        default=0.3,
        ge=0.0,
        le=10.0,
        description="Minimum gap in seconds between narration clips to prevent overlap.",
    )
    collision_strategy: Literal["warn", "shift", "truncate"] = Field(
        default="warn",
        description=(
            "How to handle narration collisions: "
            "'warn' logs only, 'shift' delays the next clip, "
            "'truncate' fades out the previous clip."
        ),
    )

    @field_validator("reference_audio")
    @classmethod
    def _safe_reference_audio(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_safe_path(v)
        return v


# ── Audio ─────────────────────────────────────────────────────────────────────


class BackgroundMusic(_StrictBase):
    file: str
    volume: float = Field(default=0.3, ge=0.0, le=1.0)
    ducking_mode: Literal["none", "light", "moderate", "heavy"] = "moderate"
    loop: bool = True

    @field_validator("file")
    @classmethod
    def _safe_file(cls, v: str) -> str:
        return _validate_safe_path(v)


class VoiceProcessing(_StrictBase):
    normalize: bool = True
    target_dbfs: int = -20
    remove_silence: bool = True
    silence_threshold: int = -40
    enhance_clarity: bool = False
    enhance_warmth: bool = False
    noise_reduction: bool = False


class Compression(_StrictBase):
    threshold: int = -20
    ratio: float = Field(default=3.0, gt=0)
    attack: int = Field(default=5, ge=0)
    release: int = Field(default=50, ge=0)


class AudioEffects(_StrictBase):
    eq_preset: str | None = None
    reverb_preset: str | None = None
    compression: Compression | None = None


class AudioConfig(_StrictBase):
    background_music: BackgroundMusic | None = None
    voice_processing: VoiceProcessing | None = None
    effects: AudioEffects | None = None


# ── Device Rendering ──────────────────────────────────────────────────────────


class DeviceRendering(_StrictBase):
    device: str = "iphone_15_pro"
    orientation: Literal["portrait", "landscape"] = "portrait"
    quality: Literal["low", "medium", "high"] = "high"
    render_engine: Literal["eevee", "cycles"] = "eevee"
    camera_animation: str = "orbit_smooth"
    lighting: str = "studio"


# ── Video ─────────────────────────────────────────────────────────────────────


class Intro(_StrictBase):
    duration: float = Field(default=3.0, ge=0)
    type: str = "fade_in"
    text: str | None = None
    subtitle: str | None = None
    font_size: int = Field(default=60, gt=0)
    font_color: str = "#FFFFFF"
    background_color: str = "#1a1a1a"

    @field_validator("font_color", "background_color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)


class Transitions(_StrictBase):
    type: Literal["crossfade", "slide", "zoom", "dissolve"] = "crossfade"
    duration: float = Field(default=0.5, ge=0, le=10.0)


class Watermark(_StrictBase):
    image: str
    position: Literal[
        "top_left", "top_right", "bottom_left", "bottom_right", "center"
    ] = "bottom_right"
    opacity: float = Field(default=0.7, ge=0.0, le=1.0)
    size: int = Field(default=100, gt=0, le=2000)

    @field_validator("image")
    @classmethod
    def _safe_image(cls, v: str) -> str:
        return _validate_safe_path(v)


class Outro(_StrictBase):
    duration: float = Field(default=4.0, ge=0)
    type: str = "fade_out"
    text: str | None = None
    subtitle: str | None = None
    cta: str | None = None


class VideoOptimization(_StrictBase):
    target_size_mb: int | None = None
    web_optimized: bool = True
    compression_level: Literal["low", "balanced", "high"] = "balanced"


class VideoConfig(_StrictBase):
    intro: Intro | None = None
    transitions: Transitions | None = None
    watermark: Watermark | None = None
    outro: Outro | None = None
    optimization: VideoOptimization | None = None


# ── Scenarios ─────────────────────────────────────────────────────────────────


class Viewport(_StrictBase):
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)


class Locator(_StrictBase):
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


# ── Effect parameter validation mapping ───────────────────────────────────────

EFFECT_VALID_PARAMS: dict[str, set[str]] = {
    # Browser effects
    "spotlight": {"intensity"},
    "highlight": {"color", "intensity"},
    "confetti": set(),
    "typewriter": set(),
    "glow": {"color"},
    "shockwave": set(),
    "sparkle": set(),
    "cursor_trail": set(),
    "cursor_trail_rainbow": set(),
    "cursor_trail_comet": set(),
    "cursor_trail_glow": {"color"},
    "cursor_trail_line": set(),
    "cursor_trail_particles": set(),
    "cursor_trail_fire": set(),
    "ripple": set(),
    "neon_glow": {"color"},
    "success_checkmark": set(),
    "emoji_rain": set(),
    "fireworks": set(),
    "bubbles": set(),
    "snow": set(),
    "star_burst": set(),
    "party_popper": set(),
    "text_highlight": {"color"},
    "text_scramble": {"speed"},
    "magnetic_hover": {"intensity"},
    "tooltip_annotation": {"text", "color"},
    "morphing_background": {"colors"},
    "matrix_rain": {"color", "density", "speed"},
    "frosted_glass": {"intensity"},
    "progress_bar": {"color", "position", "intensity"},
    "countdown_timer": {"duration", "color", "position"},
    "callout_arrow": {"text", "color", "target_x", "target_y"},
    # Post effects
    "parallax": {"depth"},
    "zoom_pulse": {"scale"},
    "fade_in": {"duration"},
    "fade_out": {"duration"},
    "vignette": {"intensity"},
    "glitch": {"intensity"},
    "slide_in": {"duration"},
    "drone_zoom": {"scale", "target_x", "target_y"},
    "ken_burns": {"scale", "direction"},
    "zoom_to": {"scale", "target_x", "target_y"},
    "dolly_zoom": {"intensity"},
    "elastic_zoom": {"scale"},
    "camera_shake": {"intensity", "speed"},
    "whip_pan": {"direction"},
    "rotate": {"angle", "speed"},
    "letterbox": {"ratio"},
    "film_grain": {"intensity"},
    "color_grade": {"preset"},
    "focus_pull": {"direction", "intensity"},
    "tilt_shift": {"intensity", "focus_position"},
    "crt_scanlines": {"intensity", "line_spacing"},
    "chromatic_aberration": {"offset"},
    "vhs_distortion": {"intensity"},
    "pixel_sort": {"threshold", "direction"},
    "bloom": {"threshold", "radius", "intensity"},
    "bokeh_blur": {"focus_area", "radius"},
    "light_leak": {"color", "intensity", "speed"},
    "wipe": {"direction", "style"},
    "iris": {"direction"},
    "dissolve_noise": {"grain_size"},
}


class Effect(_StrictBase):
    type: EffectType
    duration: float | None = Field(default=None, ge=0)
    intensity: float | None = Field(default=None, ge=0, le=1.0)
    color: str | None = None
    speed: float | None = Field(default=None, gt=0)
    scale: float | None = Field(default=None, gt=0)
    depth: int | None = Field(default=None, ge=0)
    direction: str | None = None
    target_x: float | None = None
    target_y: float | None = None
    angle: float | None = None
    ratio: float | None = Field(default=None, gt=0)
    preset: str | None = None
    focus_position: float | None = Field(default=None, ge=0, le=1.0)
    threshold: float | None = None
    line_spacing: int | None = Field(default=None, gt=0)
    offset: int | None = None
    grain_size: int | None = Field(default=None, gt=0)
    focus_area: float | None = Field(default=None, ge=0, le=1.0)
    radius: float | None = Field(default=None, gt=0)
    text: str | None = None
    position: str | None = None
    style: str | None = None
    density: float | None = Field(default=None, gt=0)
    colors: list[str] | None = None

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_css_color(v)
        return v

    @field_validator("colors")
    @classmethod
    def _valid_colors(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return _validate_css_color_list(v)
        return v

    @model_validator(mode="after")
    def _warn_irrelevant_params(self) -> Effect:
        valid = EFFECT_VALID_PARAMS.get(self.type)
        if valid is None:
            return self
        # "duration" is always allowed (even if not in valid set) — it controls wait time
        allowed = valid | {"duration"}
        set_fields = {
            name
            for name in type(self).model_fields
            if name != "type" and getattr(self, name) is not None
        }
        extra = set_fields - allowed
        if extra:
            warnings.warn(
                f"Effect '{self.type}': parameters {sorted(extra)} are not used "
                f"by this effect type and will be ignored.",
                UserWarning,
                stacklevel=1,
            )
        return self


class CardContent(_StrictBase):
    """Content for a popup card displayed during a step."""

    title: str | None = None
    body: str | None = None
    items: list[str] | None = None
    icon: str | None = None  # emoji or short text


class Step(_StrictBase):
    action: Literal["navigate", "click", "type", "scroll", "wait_for", "screenshot"]

    # navigate
    url: str | None = None

    # click / type / wait_for
    locator: Locator | None = None

    # type
    value: str | None = None

    # scroll
    direction: Literal["up", "down", "left", "right"] | None = None
    pixels: int | None = Field(default=None, gt=0)

    # wait_for
    timeout: float | None = Field(default=None, gt=0)

    # screenshot
    filename: str | None = None

    # common optional
    narration: str | None = None
    wait: float | None = Field(default=None, ge=0)
    effects: list[Effect] | None = None
    card: CardContent | None = None

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_url(v)
        return v

    @model_validator(mode="after")
    def _validate_action_fields(self) -> Step:
        """Ensure each action has the fields it requires at parse time."""
        a = self.action
        if a == "navigate" and not self.url:
            raise ValueError("'navigate' requires 'url'")
        if a in ("click", "wait_for") and not self.locator:
            raise ValueError(f"'{a}' requires 'locator'")
        if a == "type" and (not self.locator or self.value is None):
            raise ValueError("'type' requires 'locator' and 'value'")
        # Warn on irrelevant fields for an action
        _STEP_RELEVANT: dict[str, set[str]] = {
            "navigate": {"url"},
            "click": {"locator"},
            "type": {"locator", "value"},
            "scroll": {"direction", "pixels"},
            "wait_for": {"locator", "timeout"},
            "screenshot": {"filename"},
        }
        _COMMON = {"narration", "wait", "effects", "card", "action"}
        relevant = _STEP_RELEVANT.get(a, set()) | _COMMON
        set_fields = {
            name for name in type(self).model_fields if getattr(self, name) is not None
        }
        extra = set_fields - relevant
        if extra:
            warnings.warn(
                f"Step '{a}': fields {sorted(extra)} are not relevant "
                f"for this action and will be ignored.",
                UserWarning,
                stacklevel=1,
            )
        return self


class CursorConfig(_StrictBase):
    visible: bool = True
    style: Literal["dot", "pointer"] = "dot"
    color: str = "#ef4444"
    size: int = Field(default=20, gt=0, le=500)
    click_effect: Literal["ripple", "pulse", "none"] = "ripple"
    smooth: float = Field(
        default=0.4,
        ge=0,
        le=1.0,
        description="Cursor movement smoothing factor (0=instant, 1=max smooth)",
    )

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)


class GlowSelectConfig(_StrictBase):
    enabled: bool = True
    colors: list[str] = Field(
        default_factory=lambda: ["#a855f7", "#6366f1", "#ec4899", "#a855f7"]
    )
    duration: float = Field(default=0.8, gt=0)
    padding: int = Field(default=8, ge=0)
    border_radius: int = Field(default=12, ge=0)
    intensity: float = Field(default=0.9, ge=0, le=1.0)

    @field_validator("colors")
    @classmethod
    def _valid_colors(cls, v: list[str]) -> list[str]:
        return _validate_css_color_list(v)


# ── Avatar style registry ────────────────────────────────────────────────────

AVATAR_STYLES: frozenset[str] = frozenset(
    {
        "ai_hallucinated",
        "battery_low",
        "bit",
        "bluetooth",
        "bounce",
        "bsod",
        "bugdroid",
        "captcha",
        "chrome_dino",
        "clippy",
        "cloud",
        "cookie",
        "cursor_hand",
        "distracted_bf",
        "doge",
        "equalizer",
        "error_404",
        "esc_key",
        "expanding_brain",
        "fail_whale",
        "firewire",
        "floppy_disk",
        "google_blob",
        "gpu_sweat",
        "high_ping",
        "hourglass",
        "incognito",
        "kermit",
        "lasso_tool",
        "mac128k",
        "mario_block",
        "marvin",
        "matrix",
        "modem56k",
        "no_idea_dog",
        "nokia3310",
        "nyan_cat",
        "pacman",
        "pc_fan",
        "pickle_rick",
        "pulse",
        "qr_code",
        "rainbow_wheel",
        "registry_key",
        "rubber_duck",
        "sad_mac",
        "scratched_cd",
        "server_rack",
        "space_invader",
        "success_kid",
        "surprised_pikachu",
        "tamagotchi",
        "this_is_fine",
        "trollface",
        "usb_cable",
        "vhs_tape",
        "visualizer",
        "waveform",
        "wifi_low",
        "wiki_globe",
        "xp_bliss",
    }
)


class AvatarConfig(_StrictBase):
    enabled: bool = True
    provider: Literal["animated", "d-id", "heygen", "sadtalker"] = "animated"
    image: str | None = None  # path or preset name: "default", "robot", "circle"
    position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = (
        "bottom-right"
    )
    size: int = Field(default=120, gt=0, le=2000, description="Avatar size in pixels")
    style: str = "bounce"
    shape: Literal["circle", "rounded", "square"] = "circle"
    background: str = "rgba(0,0,0,0.5)"
    background_shape: Literal["square", "circle", "rounded"] = "square"
    api_key: str | None = Field(
        default=None,
        repr=False,
    )  # for paid providers, supports ${ENV_VAR}
    show_subtitle: bool = False  # render narration text below avatar box
    subtitle_font_size: int = Field(default=18, gt=0)
    subtitle_font_color: str = "#FFFFFF"
    subtitle_bg_color: str = "rgba(0,0,0,0.7)"

    @field_validator("image")
    @classmethod
    def _safe_image(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_safe_path(v)
        return v

    @field_validator("background", "subtitle_font_color", "subtitle_bg_color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)

    @model_validator(mode="after")
    def _validate_style(self) -> AvatarConfig:
        if self.style not in AVATAR_STYLES:
            raise ValueError(
                f"Unknown avatar style '{self.style}'. "
                f"Valid styles: {sorted(AVATAR_STYLES)[:5]}... ({len(AVATAR_STYLES)} total)"
            )
        return self


class SubtitleConfig(_StrictBase):
    enabled: bool = True
    style: Literal[
        "classic",
        "tiktok",
        "color",
        "word_by_word",
        "typewriter",
        "karaoke",
        "bounce",
        "cinema",
        "highlight_line",
        "fade_word",
        "emoji_react",
    ] = "classic"
    speed: Literal["slow", "normal", "fast", "tiktok"] = "normal"
    font_size: int = Field(default=48, gt=0)
    font_family: str = "Arial"
    font_color: str = "#FFFFFF"
    background_color: str = "rgba(0,0,0,0.6)"
    position: Literal["bottom", "center", "top"] = "bottom"
    highlight_color: str = "#FFD700"
    max_words_per_line: int = Field(default=8, gt=0)
    animation: Literal["none", "fade", "pop", "slide"] = "none"

    @field_validator("font_color", "background_color", "highlight_color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)


class PopupCardConfig(_StrictBase):
    enabled: bool = True
    position: Literal[
        "bottom-right",
        "bottom-left",
        "top-right",
        "top-left",
        "bottom-center",
        "top-center",
    ] = "bottom-right"
    theme: Literal["glass", "dark", "light", "gradient"] = "glass"
    max_width: int = Field(default=420, gt=0)
    animation: Literal["slide", "fade", "scale"] = "slide"
    accent_color: str = "#818cf8"
    show_icon: bool = True
    show_progress: bool = True

    @field_validator("accent_color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)


class Scenario(_StrictBase):
    name: str
    # Base URL for the scenario. The first step should typically be
    # action: "navigate" pointing to this URL.
    url: str
    browser: Literal["chrome", "firefox", "webkit"] = "chrome"
    viewport: Viewport = Field(default_factory=Viewport)
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    locale: str | None = None
    cursor: CursorConfig | None = None
    glow_select: GlowSelectConfig | None = None
    popup_card: PopupCardConfig | None = None
    avatar: AvatarConfig | None = None
    subtitle: SubtitleConfig | None = None
    pre_steps: list[Step] | None = None
    steps: list[Step] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: str) -> str:
        return _validate_url(v)


# ── Pipeline ──────────────────────────────────────────────────────────────────


class PipelineStage(_StrictBase):
    """A single pipeline stage parsed from a one-key dict in the YAML list."""

    model_config = ConfigDict(extra="allow")  # params are free-form by design

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
            return {
                "stage_type": key,
                "params": value if isinstance(value, dict) else {},
            }
        return data


# ── Output ────────────────────────────────────────────────────────────────────


class Thumbnail(_StrictBase):
    timestamp: float = Field(ge=0)


class SocialExport(_StrictBase):
    platform: str
    resolution: str | None = None
    bitrate: str | None = None
    aspect_ratio: str | None = None
    max_duration: int | None = Field(default=None, gt=0)
    max_size_mb: int | None = Field(default=None, gt=0)


class DeployConfig(_StrictBase):
    """Cloud deployment configuration for uploading output videos."""

    provider: Literal["s3", "gcs", "azure_blob", "r2", "custom"]
    bucket: str
    region: str | None = None
    prefix: str = ""
    acl: str | None = None
    content_type: str = "video/mp4"
    endpoint_url: str | None = None  # custom S3-compatible endpoint (R2, MinIO, etc.)
    # Credentials resolve via env vars — supports ${ENV_VAR} syntax
    access_key: str | None = Field(default=None, repr=False)  # ${AWS_ACCESS_KEY_ID}
    secret_key: str | None = Field(default=None, repr=False)  # ${AWS_SECRET_ACCESS_KEY}
    # GCS
    project: str | None = None
    credentials_file: str | None = None  # path to service account JSON
    # Azure
    connection_string: str | None = Field(
        default=None,
        repr=False,
    )  # ${AZURE_STORAGE_CONNECTION_STRING}
    container: str | None = None  # alias for bucket in Azure terminology


class OutputConfig(_StrictBase):
    filename: str = "output.mp4"
    directory: str = "output/"
    formats: list[str] = Field(default_factory=lambda: ["mp4"])
    thumbnails: list[Thumbnail] | None = None
    social: list[SocialExport] | None = None
    deploy: DeployConfig | None = None


# ── Analytics ─────────────────────────────────────────────────────────────────


class Analytics(_StrictBase):
    track_engagement: bool = False
    heatmap: bool = False
    click_tracking: bool = False


# ── Root config ───────────────────────────────────────────────────────────────


class DemoConfig(_StrictBase):
    metadata: Metadata
    voice: VoiceConfig | None = None
    audio: AudioConfig | None = None
    device_rendering: DeviceRendering | None = None
    video: VideoConfig | None = None
    # Root-level subtitle config. Takes priority over per-scenario subtitle.
    # Resolution order: root (if enabled) > first scenario (if enabled) > disabled.
    # See orchestrators/post_processing.py get_subtitle_config().
    subtitle: SubtitleConfig | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    pipeline: list[PipelineStage] = Field(default_factory=list)
    output: OutputConfig | None = None
    analytics: Analytics | None = None


# ── Public API ───────────────────────────────────────────────────────────────

__all__ = [
    "Analytics",
    "AudioConfig",
    "AudioEffects",
    "AvatarConfig",
    "AVATAR_STYLES",
    "BackgroundMusic",
    "CardContent",
    "Compression",
    "CursorConfig",
    "DemoConfig",
    "DeployConfig",
    "DeviceRendering",
    "Effect",
    "EFFECT_VALID_PARAMS",
    "EffectType",
    "GlowSelectConfig",
    "Intro",
    "Locator",
    "Metadata",
    "OutputConfig",
    "Outro",
    "PipelineStage",
    "PopupCardConfig",
    "Scenario",
    "SocialExport",
    "Step",
    "SubtitleConfig",
    "Thumbnail",
    "Transitions",
    "VideoConfig",
    "VideoOptimization",
    "Viewport",
    "VoiceConfig",
    "VoiceProcessing",
    "Watermark",
]
