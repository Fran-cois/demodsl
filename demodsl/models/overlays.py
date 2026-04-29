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
    style: Literal["dot", "pointer", "xp"] = "dot"
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
    colors: list[str] = Field(default_factory=lambda: ["#a855f7", "#6366f1", "#ec4899", "#a855f7"])
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
    position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = "bottom-right"
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


class OsApp(_StrictBase):
    """An application entry shown in the dock/taskbar and app switcher."""

    name: str = Field(description="Display name of the application.")
    color: str = Field(default="#6366f1", description="Accent color for the app icon.")
    icon: str = Field(
        default="M12 2a10 10 0 100 20 10 10 0 000-20z",
        description="SVG path data (d attribute) for the app icon.",
    )
    url: str | None = Field(
        default=None,
        description="URL to navigate to when this app is 'opened' (optional).",
    )
    bounce: bool = Field(
        default=False,
        description="If true, the dock icon performs a bounce animation "
        "shortly after launch (simulates app opening).",
    )

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)


class WindowFrame(_StrictBase):
    """Position and size of the real browser window inside the OS overlay."""

    x: int = Field(default=0, ge=0, description="X position in pixels from left edge of viewport.")
    y: int = Field(
        default=0,
        ge=0,
        description="Y position in pixels from top edge of viewport (below menu bar).",
    )
    width: int | None = Field(
        default=None,
        gt=0,
        description="Window width in pixels. If unset, the window takes the full available width.",
    )
    height: int | None = Field(
        default=None,
        gt=0,
        description="Window height in pixels. If unset, the window takes the full available height.",
    )


class SecondaryWindow(_StrictBase):
    """Static window mockup rendered as an overlay beside the real browser window."""

    title: str = Field(default="Window", description="Title shown in the fake window's title bar.")
    x: int = Field(default=0, ge=0, description="X position in pixels.")
    y: int = Field(default=0, ge=0, description="Y position in pixels.")
    width: int = Field(default=600, gt=0, description="Window width in pixels.")
    height: int = Field(default=400, gt=0, description="Window height in pixels.")
    background_color: str = Field(
        default="#1a1a2e",
        description="Background color of the window's content area.",
    )
    screenshot: str | None = Field(
        default=None,
        description="URL or path of an image to display inside the window (optional).",
    )
    url: str | None = Field(
        default=None,
        description="URL to load inside the window as a live iframe (optional). "
        "Takes precedence over `screenshot`. Note: sites with X-Frame-Options "
        "or frame-ancestors CSP cannot be embedded.",
    )
    app_color: str = Field(
        default="#6366f1",
        description="Accent color shown in the window title bar.",
    )

    @field_validator("background_color", "app_color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)

    @field_validator("screenshot")
    @classmethod
    def _safe_screenshot(cls, v: str | None) -> str | None:
        if v is None or v.startswith(("http://", "https://", "data:")):
            return v
        return _validate_safe_path(v)


class BackgroundConfig(_StrictBase):
    """Simulate an OS desktop background around the webapp window."""

    enabled: bool = True
    os: Literal["macos", "windows"] = "macos"
    theme: Literal["dark", "light", "xp"] = "dark"
    wallpaper_color: str = Field(
        default="#1a1a2e",
        description="Solid or gradient base color for the desktop wallpaper.",
    )
    window_title: str = Field(
        default="Demo App",
        description="Title shown in the app window title bar.",
    )
    show_dock: bool = Field(default=True, description="Show dock (macOS) or taskbar (Windows).")
    show_menu_bar: bool = Field(default=True, description="Show top menu bar.")
    apps: list[OsApp] | None = Field(
        default=None,
        description="List of apps shown in the dock/taskbar and available for "
        "the app_switcher effect. If unset, a default set is used.",
    )
    window: WindowFrame | None = Field(
        default=None,
        description="Position/size of the real browser window. If unset, the browser "
        "fills the full area between menu bar and dock.",
    )
    secondary_windows: list[SecondaryWindow] | None = Field(
        default=None,
        description="Static window mockups rendered beside the real browser window, "
        "useful for showing multiple apps side-by-side.",
    )

    @field_validator("wallpaper_color")
    @classmethod
    def _valid_wallpaper(cls, v: str) -> str:
        return _validate_css_color(v)
