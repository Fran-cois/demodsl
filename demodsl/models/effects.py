"""Effect type, parameter validation, and Effect model."""

from __future__ import annotations

import warnings
from typing import Any, Literal

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
    "keyboard_shortcut",
    # Advanced browser effects
    "zoom_focus",
    "depth_blur",
    "animated_annotation",
    "perspective_tilt",
    "glassmorphism_float",
    "morph_transition",
    "scroll_parallax",
    "dark_mode_toggle",
    "click_particles",
    # UI effects
    "skeleton_loading",
    "tooltip_pop",
    "magnifier",
    "drag_drop",
    "progress_ring",
    # Camera/layout effects
    "device_frame",
    "rotation_3d",
    "split_screen",
    "directional_blur",
    # Focus/narration effects
    "notification_toast",
    "dashboard_timelapse",
    # Interaction / Data-Viz / Transition / Post-prod effects
    "click_ripple",
    "connection_trace",
    "sticky_element",
    "chart_draw",
    "odometer",
    "heatmap",
    "zoom_through",
    "infinite_canvas",
    "tab_swipe",
    "xray_view",
    "glass_reflection",
    "paper_texture",
    "ui_shimmer",
    "app_switcher",
    # OS desktop interaction effects
    "menu_dropdown",
    "window_animation",
    "context_menu",
    "spotlight_search",
    "control_center",
    "notification_center",
    "mission_control",
    "launchpad",
    "system_settings",
]

# ── Plugin effect types (populated at runtime by engine._discover_effect_plugins) ──
_PLUGIN_EFFECT_TYPES: set[str] = set()


def register_plugin_effect_type(
    name: str, valid_params: set[str] | None = None
) -> None:
    """Opt-in a plugin-provided effect type so the Effect model accepts it.

    Plugins call this (usually via the ``demodsl.effects.browser`` entry-point
    loader) to whitelist their effect name. Pass *valid_params* to get the
    standard "unused parameter" warning for typos.
    """
    _PLUGIN_EFFECT_TYPES.add(name)
    if valid_params is not None:
        EFFECT_VALID_PARAMS[name] = valid_params


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
    "keyboard_shortcut": {"text", "color", "position"},
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
    # Advanced browser effects
    "zoom_focus": {"scale", "target_x", "target_y"},
    "depth_blur": {"intensity", "focus_position"},
    "animated_annotation": {"color", "target_x", "target_y", "radius", "text"},
    "perspective_tilt": {"angle", "direction"},
    "glassmorphism_float": {"color", "intensity", "position", "text"},
    "morph_transition": {
        "color",
        "scale",
        "target_x",
        "target_y",
        "from_x",
        "from_y",
        "text",
    },
    "scroll_parallax": {"intensity", "depth"},
    "dark_mode_toggle": {"color", "target_x", "target_y"},
    "click_particles": {"color", "intensity"},
    # UI effects
    "skeleton_loading": {"color", "intensity"},
    "tooltip_pop": {"color", "text"},
    "magnifier": {"color", "scale", "radius"},
    "drag_drop": {"color", "intensity"},
    "progress_ring": {"color", "scale"},
    # Camera/layout effects
    "device_frame": {"color", "text"},
    "rotation_3d": {"angle", "depth"},
    "split_screen": {"color", "direction", "text"},
    "directional_blur": {"intensity", "direction"},
    # Focus/narration effects
    "notification_toast": {"color", "position", "style"},
    "dashboard_timelapse": {"color", "speed"},
    # Interaction / Data-Viz / Transition / Post-prod effects
    "click_ripple": {"color", "intensity"},
    "connection_trace": {"color", "from_x", "from_y", "target_x", "target_y"},
    "sticky_element": {"color", "intensity"},
    "chart_draw": {"color", "intensity"},
    "odometer": {"color", "scale"},
    "heatmap": {"intensity"},
    "zoom_through": {"target_x", "target_y", "scale"},
    "infinite_canvas": {"color", "scale"},
    "tab_swipe": {"color", "direction"},
    "xray_view": {"color", "intensity"},
    "glass_reflection": {"intensity"},
    "paper_texture": {"intensity"},
    "ui_shimmer": {"color", "intensity"},
    "app_switcher": {"color", "style", "selected", "apps"},
    # OS desktop interaction effects
    "menu_dropdown": {"menu", "items", "highlight", "color"},
    "window_animation": {"animation", "target"},
    "context_menu": {
        "items",
        "highlight",
        "color",
        "target_x",
        "target_y",
    },
    "spotlight_search": {
        "query",
        "results",
        "typing_speed",
        "highlight",
        "color",
    },
    "control_center": {
        "wifi",
        "wifi_name",
        "bluetooth",
        "airdrop",
        "focus",
        "brightness",
        "volume",
        "color",
    },
    "notification_center": {
        "notifications",
        "show_widgets",
    },
    "mission_control": {
        "windows",
        "highlight",
    },
    "launchpad": {
        "apps",
        "highlight",
    },
    "system_settings": {
        "category",
        "items",
        "color",
    },
}


class Effect(_StrictBase):
    # Allow plugin-provided extra params (e.g. from demodsl.effects.browser
    # entry-points). Core fields below remain strongly typed; unknown keys
    # are preserved and forwarded to the plugin's inject().
    model_config = {"extra": "allow"}

    type: str  # core EffectType literal OR any plugin-registered name
    duration: float | None = Field(default=None, ge=0)
    intensity: float | None = Field(default=None, ge=0, le=1.0)
    color: str | None = None
    speed: float | None = Field(default=None, gt=0)
    scale: float | None = Field(default=None, gt=0)
    depth: int | None = Field(default=None, ge=0)
    direction: str | None = None
    target_x: float | None = None
    target_y: float | None = None
    from_x: float | None = None
    from_y: float | None = None
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
    # App switcher effect params
    selected: int | None = Field(
        default=None,
        ge=0,
        le=20,
        description="0-based index of the app to highlight in the app switcher.",
    )
    apps: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of {name, color, icon} dicts for the app switcher. "
        "Inherited from background.apps if not set.",
    )
    # Menu / window / context menu effect params
    menu: str | None = Field(
        default=None,
        description="Name of the menu bar item for the menu_dropdown effect "
        "(e.g. 'File', 'Edit', 'View', 'Window', 'Help', 'app').",
    )
    items: list[str] | None = Field(
        default=None,
        description="Custom list of menu or context-menu items. Use '---' "
        "for separators.",
    )
    highlight: int | None = Field(
        default=None,
        ge=-1,
        le=50,
        description="0-based index of the item to highlight (menu_dropdown / "
        "context_menu).  -1 disables highlighting.",
    )
    animation: str | None = Field(
        default=None,
        description="Window animation type: 'open', 'close', 'minimize', "
        "'maximize', 'restore'.",
    )
    target: str | int | None = Field(
        default=None,
        description="Target for window_animation: 'main' (default) or a "
        "secondary_window index.",
    )
    # Spotlight search params
    query: str | None = Field(
        default=None,
        description="Text typed into Spotlight search bar.",
    )
    results: list[dict[str, Any]] | None = Field(
        default=None,
        description="Spotlight result list ({icon, name, subtitle} dicts).",
    )
    typing_speed: float | None = Field(
        default=None,
        gt=0,
        le=1.0,
        description="Seconds between characters during Spotlight typing animation.",
    )
    # Control Center params
    wifi: bool | None = None
    wifi_name: str | None = None
    bluetooth: bool | None = None
    airdrop: bool | None = None
    focus: bool | None = None
    brightness: float | None = Field(default=None, ge=0.0, le=1.0)
    volume: float | None = Field(default=None, ge=0.0, le=1.0)
    # Notification Center params
    notifications: list[dict[str, Any]] | None = Field(
        default=None,
        description="Notification list ({app, icon, title, body, time} dicts).",
    )
    show_widgets: bool | None = None
    # Mission control / system_settings params
    windows: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of {title, color} dicts for mission_control.",
    )
    category: str | None = Field(
        default=None,
        description="Active category name for system_settings.",
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

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        from typing import get_args

        known = set(get_args(EffectType)) | _PLUGIN_EFFECT_TYPES
        if v not in known:
            raise ValueError(
                f"Unknown effect type '{v}'. "
                f"Known: {sorted(known)[:10]}... (plus plugins)."
            )
        return v

    @model_validator(mode="after")
    def _warn_irrelevant_params(self) -> Effect:
        valid = EFFECT_VALID_PARAMS.get(self.type)
        if valid is None:
            return self
        # "duration" is always allowed (even if not in valid set) — it controls wait time
        allowed = valid | {"duration"}
        declared = {
            name
            for name in type(self).model_fields
            if name != "type" and getattr(self, name) is not None
        }
        extras = set((self.model_extra or {}).keys())
        set_fields = declared | extras
        extra = set_fields - allowed
        if extra:
            warnings.warn(
                f"Effect '{self.type}': parameters {sorted(extra)} are not used "
                f"by this effect type and will be ignored.",
                UserWarning,
                stacklevel=1,
            )
        return self
