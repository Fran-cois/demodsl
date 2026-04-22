"""Effect type, parameter validation, and Effect model."""

from __future__ import annotations

import warnings
from typing import Literal

from pydantic import Field, field_validator, model_validator

from demodsl.models._base import (
    _StrictBase,
    _validate_css_color,
    _validate_css_color_list,
)


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
    # Speed / timing effects
    "speed_ramp",
    "freeze_frame",
    "reverse",
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
    "confetti": {"duration"},
    "typewriter": set(),
    "glow": {"color"},
    "shockwave": set(),
    "sparkle": {"duration"},
    "cursor_trail": {"simulate_mouse"},
    "cursor_trail_rainbow": {"simulate_mouse"},
    "cursor_trail_comet": {"simulate_mouse"},
    "cursor_trail_glow": {"color", "simulate_mouse"},
    "cursor_trail_line": {"simulate_mouse"},
    "cursor_trail_particles": {"simulate_mouse"},
    "cursor_trail_fire": {"simulate_mouse"},
    "ripple": set(),
    "neon_glow": {"color"},
    "success_checkmark": set(),
    "emoji_rain": {"duration"},
    "fireworks": {"duration"},
    "bubbles": {"duration"},
    "snow": {"duration"},
    "star_burst": {"duration"},
    "party_popper": {"duration"},
    "text_highlight": {"color"},
    "text_scramble": {"speed"},
    "magnetic_hover": {"intensity"},
    "tooltip_annotation": {"text", "color"},
    "morphing_background": {"colors"},
    "matrix_rain": {"color", "density", "speed", "duration"},
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
    "speed_ramp": {"start_speed", "end_speed", "ease"},
    "freeze_frame": {"freeze_duration"},
    "reverse": set(),
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
    # Speed/timing effect params
    start_speed: float | None = Field(default=None, gt=0, le=10.0)
    end_speed: float | None = Field(default=None, gt=0, le=10.0)
    ease: str | None = None
    freeze_duration: float | None = Field(default=None, ge=0, le=30.0)
    # Cursor trail: auto-dispatch mousemove events for demo/debug
    simulate_mouse: bool | None = Field(
        default=None,
        description="Auto-dispatch mousemove events along a sinusoidal path "
        "(useful for cursor trail demos without real user input).",
    )

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
