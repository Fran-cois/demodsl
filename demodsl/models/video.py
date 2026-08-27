"""Video configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase, _validate_css_color
from demodsl.validators import _validate_safe_path


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
    """Segment-to-segment transition.

    Currently inert: the Remotion composition butt-joins segments and never
    reads this block. Kept so existing configs keep validating, and flagged
    at validation time so nobody sizes a demo around a crossfade that will
    not happen.
    """

    type: Literal["crossfade", "slide", "zoom", "dissolve"] = "crossfade"
    duration: float = Field(default=0.5, ge=0, le=10.0)


class Watermark(_StrictBase):
    image: str
    position: Literal["top_left", "top_right", "bottom_left", "bottom_right", "center"] = (
        "bottom_right"
    )
    opacity: float = Field(default=0.7, ge=0.0, le=1.0)
    size: int = Field(default=100, gt=0, le=2000)

    @field_validator("image")
    @classmethod
    def _safe_image(cls, v: str) -> str:
        return _validate_safe_path(v)


class ReviewerBadge(_StrictBase):
    """Persistent on-video reviewer identity — the human behind the voice.

    Composited at the video level (like the watermark) so it never zooms or
    scrolls with the recorded page. ``image`` is optional: without it the
    renderer uses the built-in flat-vector reviewer portrait.
    """

    enabled: bool = True
    name: str = "Alex Rivera"
    title: str = "Senior CRO Reviewer"
    company: str = "DemoBro"
    image: str | None = None
    accent: str = "#6366F1"
    position: Literal["bottom-left", "bottom-right", "top-left", "top-right"] = "bottom-left"
    size: int = Field(default=88, gt=32, le=400, description="Portrait bubble diameter (px)")

    @field_validator("image")
    @classmethod
    def _safe_image(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_safe_path(v)
        return v

    @field_validator("accent")
    @classmethod
    def _valid_accent(cls, v: str) -> str:
        return _validate_css_color(v)


class LiveAvatarBadge(_StrictBase):
    """Audio-reactive stylized presenter bubble (no photorealism, no uncanny
    valley): a flat-vector character whose mouth follows the narration's
    amplitude envelope. Composited at the video level, like the watermark."""

    enabled: bool = True
    accent: str = "#6366F1"
    position: Literal["bottom-left", "bottom-right", "top-left", "top-right"] = "bottom-right"
    size: int = Field(default=168, gt=48, le=600, description="Bubble diameter (px)")

    @field_validator("accent")
    @classmethod
    def _valid_accent(cls, v: str) -> str:
        return _validate_css_color(v)


class ProgressBarOverlay(_StrictBase):
    """Slim accent progress line over the content (intro/outro excluded)."""

    enabled: bool = True
    accent: str = "#6366F1"
    position: Literal["top", "bottom"] = "top"
    height: int = Field(default=6, gt=1, le=40)

    @field_validator("accent")
    @classmethod
    def _valid_accent(cls, v: str) -> str:
        return _validate_css_color(v)


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


class ColorCorrection(_StrictBase):
    """Manual color correction controls."""

    brightness: float = Field(default=0.0, ge=-1.0, le=1.0)
    contrast: float = Field(default=0.0, ge=-1.0, le=1.0)
    saturation: float = Field(default=1.0, ge=0.0, le=3.0)
    gamma: float = Field(default=1.0, ge=0.1, le=3.0)
    white_balance: Literal["auto", "daylight", "tungsten", "fluorescent", "cloudy"] | None = None
    temperature: int | None = Field(
        default=None,
        ge=2000,
        le=10000,
        description="Color temperature in Kelvin (overrides white_balance).",
    )


class SpeedRamp(_StrictBase):
    """Speed ramp configuration for a step."""

    start_speed: float = Field(default=1.0, gt=0, le=10.0)
    end_speed: float = Field(default=1.0, gt=0, le=10.0)
    ease: Literal["linear", "ease-in", "ease-out", "ease-in-out"] = "ease-in-out"


class PictureInPicture(_StrictBase):
    """Picture-in-Picture overlay configuration."""

    source: str  # path to video file
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "bottom-right"
    size: float = Field(
        default=0.25,
        gt=0,
        le=1.0,
        description="Size as fraction of main video width.",
    )
    shape: Literal["rectangle", "circle", "rounded"] = "rounded"
    border_color: str = "#FFFFFF"
    border_width: int = Field(default=2, ge=0, le=20)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("source")
    @classmethod
    def _safe_source(cls, v: str) -> str:
        return _validate_safe_path(v)

    @field_validator("border_color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)


class ChapterMarker(_StrictBase):
    """Manual chapter marker for video."""

    title: str
    timestamp: float = Field(ge=0)


class VideoConfig(_StrictBase):
    intro: Intro | None = None
    transitions: Transitions | None = None
    watermark: Watermark | None = None
    reviewer: ReviewerBadge | None = None
    live_avatar: LiveAvatarBadge | None = None
    progress_bar: ProgressBarOverlay | None = None
    outro: Outro | None = None
    optimization: VideoOptimization | None = None
    color_correction: ColorCorrection | None = None
    pip: PictureInPicture | None = None
    frame_rate: int | None = Field(
        default=None,
        gt=0,
        le=120,
        description="Target frame rate (24, 30, 60).",
    )
    chapters: list[ChapterMarker] | None = None
    speed: float | None = Field(
        default=None,
        gt=0,
        le=10.0,
        description="Global playback speed multiplier.",
    )
