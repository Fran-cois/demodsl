"""UI overlay configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from demodsl.models._base import (
    _StrictBase,
    _validate_css_color,
    _validate_css_color_list,
)
from demodsl.validators import _validate_safe_path


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
    bezier: bool = Field(
        default=True,
        description="Use Bézier curves for natural mouse movement (False=straight line).",
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
