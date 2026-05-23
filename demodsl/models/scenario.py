"""Scenario, Step, and related models."""

from __future__ import annotations

import warnings
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from demodsl.models._base import _StrictBase
from demodsl.models.effects import Effect
from demodsl.models.mobile import MobileConfig
from demodsl.models.overlays import (
    AvatarConfig,
    BackgroundConfig,
    CursorConfig,
    GlowSelectConfig,
    PopupCardConfig,
    SubtitleConfig,
)
from demodsl.models.terminal import TerminalConfig
from demodsl.models.timeline import Timeline
from demodsl.models.video import SpeedRamp
from demodsl.validators import _validate_url


class Viewport(_StrictBase):
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)


class Locator(_StrictBase):
    type: Literal[
        "css",
        "id",
        "xpath",
        "text",
        # Mobile-specific locator strategies
        "accessibility_id",
        "class_name",
        "android_uiautomator",
        "ios_predicate",
        "ios_class_chain",
    ] = "css"
    value: str


class CardContent(_StrictBase):
    """Content for a popup card displayed during a step."""

    title: str | None = None
    body: str | None = None
    items: list[str] | None = None
    icon: str | None = None  # emoji or short text


class StopCondition(_StrictBase):
    """Condition that aborts the demo when met after a step executes."""

    selector: str | None = None
    js: str | None = Field(
        default=None,
        max_length=4096,
        description=(
            "Arbitrary JS expression evaluated in the browser. "
            "Trusted: the YAML author controls this value just as they "
            "control all Playwright actions. Never accept from untrusted input. "
            "Capped at 4096 chars; set env DEMODSL_DISABLE_STOP_JS=1 to "
            "refuse evaluation entirely (recommended in shared CI / template "
            "marketplaces)."
        ),
    )
    url_contains: str | None = None
    message: str = "Demo stopped: condition met"

    @model_validator(mode="after")
    def _at_least_one(self) -> StopCondition:
        if not self.selector and not self.js and not self.url_contains:
            raise ValueError(
                "StopCondition requires at least one of: 'selector', 'js', 'url_contains'"
            )
        return self


class DemoStoppedError(RuntimeError):
    """Raised when a stop_if condition matches during demo execution."""


class ZoomInputConfig(_StrictBase):
    """Configuration for zooming into an input element during organic typing."""

    scale: float = Field(
        default=1.5,
        gt=1.0,
        le=4.0,
        description="Zoom scale factor applied to the viewport around the input.",
    )
    padding: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Pixel padding around the input element when zooming.",
    )


class CameraMove(_StrictBase):
    """Virtual camera move applied to the recorded page.

    Implemented as an animated CSS ``transform`` on ``<html>`` so the move
    is captured by the browser's video recording (no post-processing
    required). Stacks cleanly with browser/post effects.

    Provide either *target* (a locator the camera centers/zooms onto),
    explicit normalized *target_x*/*target_y* (0..1 of the viewport), or
    pixel-precise *pan_x*/*pan_y*. *zoom*=1 with *reset*=True animates
    back to the identity transform.
    """

    zoom: float | None = Field(
        default=None,
        gt=0,
        le=10.0,
        description="Zoom scale factor (1.0 = no zoom, 2.0 = 2x in, 0.5 = 2x out).",
    )
    target: Locator | None = Field(
        default=None,
        description="Locator the camera centers on. Resolved at runtime.",
    )
    target_x: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized X focus point in the viewport (0=left, 1=right). "
        "Ignored if 'target' is set.",
    )
    target_y: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized Y focus point in the viewport (0=top, 1=bottom). "
        "Ignored if 'target' is set.",
    )
    pan_x: float | None = Field(
        default=None,
        description="Extra horizontal pan in CSS pixels (positive = right).",
    )
    pan_y: float | None = Field(
        default=None,
        description="Extra vertical pan in CSS pixels (positive = down).",
    )
    rotation: float | None = Field(
        default=None,
        ge=-360.0,
        le=360.0,
        description="Rotation in degrees applied around the focus point.",
    )
    duration: float = Field(
        default=0.6,
        ge=0.0,
        le=10.0,
        description="Animation duration in seconds (0 = snap).",
    )
    ease: Literal[
        "linear",
        "ease",
        "ease-in",
        "ease-out",
        "ease-in-out",
        "spring",
    ] = Field(
        default="ease-in-out",
        description="Easing function for the camera tween.",
    )
    hold: float = Field(
        default=0.0,
        ge=0.0,
        le=30.0,
        description="Seconds to hold the camera at the destination after the move.",
    )
    reset: bool = Field(
        default=False,
        description="Animate back to the identity transform (cancels any prior move). "
        "When True, other fields are ignored except 'duration' and 'ease'.",
    )

    @model_validator(mode="after")
    def _at_least_one_action(self) -> CameraMove:
        if self.reset:
            return self
        if (
            self.zoom is None
            and self.target is None
            and self.target_x is None
            and self.target_y is None
            and self.pan_x is None
            and self.pan_y is None
            and self.rotation is None
        ):
            raise ValueError(
                "CameraMove requires at least one of: 'zoom', 'target', "
                "'target_x'/'target_y', 'pan_x'/'pan_y', 'rotation', or 'reset: true'."
            )
        return self


class NaturalConfig(_StrictBase):
    """Scenario-level defaults for natural/human-like demo behaviour."""

    enabled: bool = True
    hover_delay: float = Field(
        default=0.2,
        ge=0,
        le=5.0,
        description="Seconds to pause between cursor arrival and click.",
    )
    smooth_scroll: bool = Field(
        default=True,
        description="Use smooth CSS scroll instead of instant scrollBy.",
    )
    jitter: float = Field(
        default=0.1,
        ge=0,
        le=0.5,
        description="Random timing variance fraction (±10% by default).",
    )
    typing_variance: float = Field(
        default=0.3,
        ge=0,
        le=1.0,
        description="Per-character delay variance for organic typing (0=uniform).",
    )
    bezier_cursor: bool = Field(
        default=True,
        description="Use Bézier curves for mouse movement instead of straight lines.",
    )


class Step(_StrictBase):
    action: Literal[
        "navigate",
        "click",
        "type",
        "scroll",
        "pause",
        "wait_for",
        "screenshot",
        "shortcut",
        # New browser actions
        "hover",
        "drag",
        "press_key",
        # Virtual camera
        "camera",
        "camera_reset",
        # Mobile-specific actions
        "tap",
        "swipe",
        "pinch",
        "long_press",
        "back",
        "home",
        "notification",
        "app_switch",
        "rotate_device",
        "shake",
        # Terminal actions
        "terminal_run",
        "terminal_clear",
        "terminal_zoom",
    ]

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

    # shortcut (e.g. "Meta+f", "Control+Shift+p")
    keys: str | None = Field(
        default=None,
        description="Keyboard shortcut to press, e.g. 'Meta+f', 'Control+c'.",
    )

    # drag: target element
    target_locator: Locator | None = Field(
        default=None,
        description="Target element locator for drag action.",
    )

    # press_key: single key name (e.g. 'Enter', 'Escape', 'ArrowDown')
    key: str | None = Field(
        default=None,
        description="Single key name for press_key action.",
    )

    # mobile: swipe / pinch / tap coordinates
    # x / y are accepted as aliases of start_x / start_y for tap convenience.
    start_x: float | None = Field(default=None, ge=0)
    start_y: float | None = Field(default=None, ge=0)
    end_x: float | None = Field(default=None, ge=0)
    end_y: float | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(
        default=None,
        gt=0,
        description="Duration of the gesture in milliseconds.",
    )
    # mobile: pinch
    pinch_scale: float | None = Field(
        default=None,
        gt=0,
        description="Pinch scale factor (>1 zoom in, <1 zoom out).",
    )
    # mobile: rotate_device
    orientation: Literal["portrait", "landscape"] | None = None

    # terminal: terminal_run
    command: str | None = Field(
        default=None,
        description="Shell command to type in the terminal (for terminal_run).",
    )
    output: str | list[str] | None = Field(
        default=None,
        description="Simulated command output. String or list of lines (for terminal_run).",
    )
    zoom_level: float | None = Field(
        default=None,
        description="Zoom scale for terminal_zoom (>1 zoom in, <1 zoom out, 1=reset).",
    )
    zoom_duration: float | None = Field(
        default=None,
        description="Duration in seconds for the zoom animation (default 0.8).",
    )

    # common optional
    narration: str | None = None
    narrations: dict[str, str] | None = Field(
        default=None,
        description=(
            "Per-language narration translations: {lang_code: text}. "
            "Used in multi-language rendering. The base 'narration' field "
            "is treated as the source language (LanguagesConfig.default)."
        ),
    )
    wait: float | None = Field(default=None, ge=0)
    effects: list[Effect] | None = None
    card: CardContent | None = None
    speed: float | None = Field(
        default=None,
        gt=0,
        le=10.0,
        description="Playback speed for this step (0.25=slow-mo, 2.0=fast).",
    )
    speed_ramp: SpeedRamp | None = None
    freeze_duration: float | None = Field(
        default=None,
        ge=0,
        le=30.0,
        description="Freeze the last frame of this step for N seconds.",
    )
    audio_offset: float | None = Field(
        default=None,
        ge=-10.0,
        le=10.0,
        description="Audio offset: negative=J-cut (audio early), positive=L-cut (audio late).",
    )
    stop_if: list[StopCondition] | None = None

    # click – natural interaction
    hover_delay: float | None = Field(
        default=None,
        ge=0,
        le=5.0,
        description="Seconds to wait between cursor arrival and click (simulates hover).",
    )

    # scroll – smoothing
    smooth_scroll: bool | None = Field(
        default=None,
        description="Use smooth CSS scrolling instead of instant jump. "
        "None = use scenario natural config or False.",
    )

    # type – organic typing
    char_rate: float | None = Field(
        default=None,
        gt=0,
        le=100,
        description="Characters per second for organic (char-by-char) typing. "
        "None = instant fill (default behaviour).",
    )
    zoom_input: bool | ZoomInputConfig | None = Field(
        default=None,
        description="Zoom into the target input during typing. "
        "True uses defaults (scale=1.5, padding=50). "
        "Pass a ZoomInputConfig object for custom values.",
    )
    typing_variance: float | None = Field(
        default=None,
        ge=0,
        le=1.0,
        description="Per-character delay variance for organic typing "
        "(0=uniform, 0.3=±30% natural). Requires char_rate.",
    )

    # virtual camera – applied alongside any action (or standalone via
    # action: 'camera' / 'camera_reset').
    camera: CameraMove | None = Field(
        default=None,
        description="Animated virtual camera move (zoom/pan/rotate) applied "
        "to the recorded page before/with the action. See CameraMove.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalise_coordinate_aliases(cls, data: Any) -> Any:
        """Accept ``x``/``y`` as aliases of ``start_x``/``start_y`` for tap."""
        if isinstance(data, dict):
            if "x" in data and "start_x" not in data:
                data["start_x"] = data.pop("x")
            elif "x" in data:
                data.pop("x")  # start_x takes precedence
            if "y" in data and "start_y" not in data:
                data["start_y"] = data.pop("y")
            elif "y" in data:
                data.pop("y")  # start_y takes precedence
        return data

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
        if a == "swipe" and (
            self.start_x is None or self.start_y is None or self.end_x is None or self.end_y is None
        ):
            raise ValueError("'swipe' requires 'start_x', 'start_y', 'end_x', 'end_y'")
        if a == "pinch" and self.pinch_scale is None:
            raise ValueError("'pinch' requires 'pinch_scale'")
        if a == "rotate_device" and self.orientation is None:
            raise ValueError("'rotate_device' requires 'orientation'")
        if a == "shortcut" and not self.keys:
            raise ValueError("'shortcut' requires 'keys'")
        if a == "hover" and not self.locator:
            raise ValueError("'hover' requires 'locator'")
        if a == "drag" and not self.locator:
            raise ValueError("'drag' requires 'locator' (source)")
        if a == "press_key" and not self.key:
            raise ValueError("'press_key' requires 'key'")
        if a == "terminal_run" and not self.command:
            raise ValueError("'terminal_run' requires 'command'")
        if a == "camera" and self.camera is None:
            raise ValueError("'camera' requires a 'camera:' block (CameraMove)")
        # Warn on irrelevant fields for an action
        _STEP_RELEVANT: dict[str, set[str]] = {
            "navigate": {"url"},
            "click": {"locator", "hover_delay"},
            "type": {"locator", "value", "char_rate", "zoom_input", "typing_variance"},
            "scroll": {"direction", "pixels", "smooth_scroll"},
            "pause": set(),
            "wait_for": {"locator", "timeout"},
            "screenshot": {"filename"},
            "shortcut": {"keys"},
            "hover": {"locator", "hover_delay"},
            "drag": {"locator", "target_locator", "end_x", "end_y", "duration_ms"},
            "press_key": {"key"},
            # Mobile actions
            "tap": {"locator", "start_x", "start_y", "duration_ms"},
            "swipe": {"start_x", "start_y", "end_x", "end_y", "duration_ms"},
            "pinch": {"locator", "pinch_scale", "duration_ms"},
            "long_press": {"locator", "start_x", "start_y", "duration_ms"},
            "back": set(),
            "home": set(),
            "notification": set(),
            "app_switch": set(),
            "rotate_device": {"orientation"},
            "shake": set(),
            # Terminal actions
            "terminal_run": {"command", "output"},
            "terminal_clear": set(),
            "terminal_zoom": {"zoom_level", "zoom_duration"},
            # Virtual camera actions
            "camera": {"camera"},
            "camera_reset": set(),
        }
        _COMMON = {
            "narration",
            "narrations",
            "wait",
            "effects",
            "card",
            "action",
            "speed",
            "speed_ramp",
            "freeze_duration",
            "audio_offset",
            "stop_if",
            "camera",
        }
        relevant = _STEP_RELEVANT.get(a, set()) | _COMMON
        set_fields = {name for name in type(self).model_fields if getattr(self, name) is not None}
        extra = set_fields - relevant
        if extra:
            warnings.warn(
                f"Step '{a}': fields {sorted(extra)} are not relevant "
                f"for this action and will be ignored.",
                UserWarning,
                stacklevel=1,
            )
        return self


# Browser-only actions that must not appear in mobile scenarios
_BROWSER_ONLY_ACTIONS: frozenset[str] = frozenset(
    {"navigate", "shortcut", "hover", "drag", "press_key", "camera", "camera_reset"}
)

_TERMINAL_ONLY_ACTIONS: frozenset[str] = frozenset(
    {"terminal_run", "terminal_clear", "terminal_zoom"}
)


class Scenario(_StrictBase):
    name: str
    # Base URL for the scenario. The first step should typically be
    # action: "navigate" pointing to this URL.
    url: str | None = None
    browser: Literal["chrome", "firefox", "webkit"] = "chrome"
    fallback_browser: Literal["chrome", "firefox", "webkit"] | None = None
    provider: Literal["playwright", "selenium"] = "playwright"
    viewport: Viewport = Field(default_factory=Viewport)
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    locale: str | None = None
    cursor: CursorConfig | None = None
    glow_select: GlowSelectConfig | None = None
    popup_card: PopupCardConfig | None = None
    avatar: AvatarConfig | None = None
    subtitle: SubtitleConfig | None = None
    natural: bool | NaturalConfig | None = Field(
        default=None,
        description="Enable natural/human-like demo behaviour. "
        "True uses defaults; pass NaturalConfig for custom values. "
        "Step-level fields (hover_delay, smooth_scroll, etc.) override.",
    )
    background: BackgroundConfig | None = None
    mobile: MobileConfig | None = None
    terminal: TerminalConfig | None = None
    pre_steps: list[Step] | None = None
    steps: list[Step] = Field(default_factory=list)
    timeline: Timeline | None = Field(
        default=None,
        description="After-Effects-style overlay timeline composited on top "
        "of the captured browser video (text/shape/image layers with "
        "keyframed transforms).",
    )

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_url(v)

    @model_validator(mode="after")
    def _validate_mobile_or_browser(self) -> Scenario:
        """Mobile and terminal scenarios don't require a URL."""
        if not self.mobile and not self.terminal and not self.url:
            raise ValueError(
                "Browser scenarios require 'url'. Set 'mobile' config for native app demos "
                "or 'terminal' config for terminal demos."
            )
        # Validate no browser-only actions in mobile scenarios
        if self.mobile:
            for i, step in enumerate(self.steps):
                if step.action in _BROWSER_ONLY_ACTIONS:
                    raise ValueError(
                        f"Step {i + 1}: '{step.action}' is a browser-only action "
                        f"and is not valid in mobile scenarios. "
                        f"Mobile scenarios launch the app automatically via "
                        f"bundle_id/app_package — no 'navigate' step is needed."
                    )
            for i, step in enumerate(self.pre_steps or []):
                if step.action in _BROWSER_ONLY_ACTIONS:
                    raise ValueError(
                        f"Pre-step {i + 1}: '{step.action}' is a browser-only "
                        f"action and is not valid in mobile scenarios. "
                        f"Mobile scenarios launch the app automatically via "
                        f"bundle_id/app_package — no 'navigate' step is needed."
                    )
        # Validate terminal scenarios
        if self.terminal:
            for i, step in enumerate(self.steps):
                if step.action in _BROWSER_ONLY_ACTIONS:
                    raise ValueError(
                        f"Step {i + 1}: '{step.action}' is a browser-only action "
                        f"and is not valid in terminal scenarios."
                    )
        # Validate terminal-only actions not used outside terminal scenarios
        if not self.terminal:
            for i, step in enumerate(self.steps):
                if step.action in _TERMINAL_ONLY_ACTIONS:
                    raise ValueError(
                        f"Step {i + 1}: '{step.action}' is a terminal-only action. "
                        f"Set 'terminal' config on the scenario to use it."
                    )
        return self
