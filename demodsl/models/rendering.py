"""Device rendering (3D Blender) configuration model."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase, _validate_css_color
from demodsl.validators import _validate_safe_path

_BACKGROUND_PRESETS = (
    "solid",
    "gradient",
    "studio_floor",
    "spotlight",
    "warm_gradient",
    "cool_gradient",
    "sunset",
    "abstract_noise",
    "space",
    "space_dark",
)


class DeviceRendering(_StrictBase):
    device: str = "iphone_15_pro"
    orientation: Literal["portrait", "landscape"] = "portrait"
    quality: Literal["low", "medium", "high", "cinematic"] = "high"
    render_engine: Literal["eevee", "cycles"] = "eevee"
    camera_animation: str = "orbit_smooth"
    lighting: str = "studio"
    background_preset: str = "space"
    background_color: str = "#1a1a1a"
    background_gradient_color: str | None = None
    background_hdri: str | None = None
    camera_distance: float = Field(default=1.5, gt=0, le=10.0)
    camera_height: float = Field(default=0.0, ge=-5.0, le=5.0)
    rotation_speed: float = Field(default=1.0, gt=0, le=5.0)
    shadow: bool = True
    depth_of_field: bool = False
    dof_aperture: float = Field(default=2.8, gt=0, le=22.0)
    motion_blur: bool = False
    bloom: bool = False
    film_grain: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("background_preset")
    @classmethod
    def _valid_bg_preset(cls, v: str) -> str:
        if v not in _BACKGROUND_PRESETS:
            raise ValueError(
                f"Invalid background_preset '{v}'. Must be one of: {', '.join(_BACKGROUND_PRESETS)}"
            )
        return v

    @field_validator("background_color", "background_gradient_color")
    @classmethod
    def _valid_bg_color(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_css_color(v)
        return v

    @field_validator("background_hdri")
    @classmethod
    def _safe_hdri(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_safe_path(v)
        return v
