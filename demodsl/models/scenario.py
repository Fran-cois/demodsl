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
from demodsl.models.theme import ThemeConfig, discover_theme_presets
from demodsl.models.timeline import Timeline
from demodsl.models.video import SpeedRamp
from demodsl.validators import _validate_safe_path, _validate_url


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


# ── Locator capability matrix (issue #28) ────────────────────────────────────
#
# ``Locator.type`` is the union of every strategy the DSL knows about, but no
# single provider resolves all of them: the web providers only implement
# ``css | id | xpath | text``. Advertising the union in the schema means a web
# scenario could carry ``accessibility_id`` through validation and only fail
# mid-render, after the browser recording and the TTS work. This table is the
# single source of truth used by both the validator below and the providers.

WEB_LOCATOR_TYPES: frozenset[str] = frozenset({"css", "id", "xpath", "text"})
MOBILE_LOCATOR_TYPES: frozenset[str] = frozenset(
    {
        "css",
        "id",
        "xpath",
        "text",
        "accessibility_id",
        "class_name",
        "android_uiautomator",
        "ios_predicate",
        "ios_class_chain",
    }
)

#: Which locator strategies each subsystem can actually resolve.
LOCATOR_SUPPORT: dict[str, frozenset[str]] = {
    "web": WEB_LOCATOR_TYPES,
    "mobile": MOBILE_LOCATOR_TYPES,
    "terminal": frozenset(),
}

#: Strategies that only exist on the mobile side — the ones that used to crash
#: a web render with ``Unsupported locator type``.
MOBILE_ONLY_LOCATOR_TYPES: frozenset[str] = MOBILE_LOCATOR_TYPES - WEB_LOCATOR_TYPES


def supported_locator_types(subsystem: str) -> frozenset[str]:
    """Locator strategies resolvable by *subsystem* (``web``/``mobile``/``terminal``)."""
    return LOCATOR_SUPPORT.get(subsystem, WEB_LOCATOR_TYPES)


class LocatorNotSupportedError(ValueError):
    """A scenario declares a locator strategy its provider cannot resolve.

    Carried through pydantic's ``ctx['error']`` so
    :func:`demodsl.diagnostics.diagnose_raw` can emit the stable
    ``step.locator_unsupported`` code instead of regex-parsing the message.
    """

    def __init__(self, locator_type: str, subsystem: str, where: str) -> None:
        self.locator_type = locator_type
        self.subsystem = subsystem
        self.where = where
        self.supported = sorted(supported_locator_types(subsystem))
        hint = ""
        if locator_type in MOBILE_ONLY_LOCATOR_TYPES and subsystem != "mobile":
            hint = (
                f" '{locator_type}' is a mobile-only strategy: set a 'mobile' config "
                f"on the scenario, or target the element with css/text instead."
            )
        super().__init__(
            f"{where}: locator type '{locator_type}' is not supported by "
            f"{subsystem} scenarios. Supported: {self.supported}.{hint}"
        )


# ── Per-step failure policy (issue #22) ──────────────────────────────────────

OnErrorPolicy = Literal["skip", "fail", "scroll_into_view_only"]

#: Actions whose failure invalidates everything that follows, so they keep
#: failing hard even under the default graceful policy. Everything else
#: (hover, click on a decorative element, screenshot…) degrades to a warning.
FATAL_ACTIONS: frozenset[str] = frozenset({"navigate", "oauth_login", "await_email"})


def resolve_on_error(step: Step, scenario_default: OnErrorPolicy | None = None) -> OnErrorPolicy:
    """Resolve the effective failure policy for *step*.

    Order: explicit ``step.on_error`` > ``scenario.on_error`` > graceful
    default (``skip``, except for the actions in :data:`FATAL_ACTIONS`
    where losing the step makes the rest of the tour meaningless).
    """
    if step.on_error is not None:
        return step.on_error
    if scenario_default is not None:
        return scenario_default
    return "fail" if step.action in FATAL_ACTIONS else "skip"


class CardContent(_StrictBase):
    """Content for a popup card displayed during a step."""

    title: str | None = None
    body: str | None = None
    items: list[str] | None = None
    icon: str | None = None  # emoji or short text


# ── Semantic beat (issue #20) ────────────────────────────────────────────────

#: Editorial roles a beat can play in a walkthrough. The role — not the
#: author — decides the camera framing and the pointing gesture.
BeatRole = Literal["hero", "argument", "proof", "metric", "social_proof", "cta"]
BeatSentiment = Literal["good", "neutral", "bad"]


class BeatSpec(_StrictBase):
    """A step described by *intent* instead of mechanics.

    ``beat: cta`` (or the expanded mapping form) says *what the step means*;
    demodsl's house recipe fills in the camera move, the pointing effects and
    the pacing. Explicit ``camera``/``effects``/``wait``/``action`` on the same
    step always win, so a beat is a default, never a straitjacket.
    """

    role: BeatRole = "argument"
    sentiment: BeatSentiment | None = None
    note: str | None = Field(
        default=None,
        max_length=28,
        description="Optional 2-4 word on-screen label drawn next to the mark.",
    )


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


class ZoomOnClick(_StrictBase):
    """Automatically zoom the virtual camera onto a ``click`` step's own target.

    Unlike a manual ``camera`` step there is no ``target`` field here: the
    click's own locator IS the focus point, so the selector is never written
    twice. Zooms in, performs the click, holds, then zooms back out — all in
    one step.
    """

    zoom: float = Field(
        default=1.6,
        gt=1.0,
        le=10.0,
        description="Zoom scale factor while the click happens.",
    )
    duration: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Zoom-in / zoom-out animation duration in seconds.",
    )
    hold: float = Field(
        default=0.6,
        ge=0.0,
        le=10.0,
        description="Seconds to hold the zoomed-in view before zooming back out.",
    )
    ease: Literal[
        "linear",
        "ease",
        "ease-in",
        "ease-out",
        "ease-in-out",
        "spring",
    ] = Field(default="ease-in-out")


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


#: Subsystems the operator drives, each dialable on its own.
HumanizeChannel = Literal["cursor", "keyboard", "scroll", "camera", "video", "voice", "timing"]


class HumanizeConfig(_StrictBase):
    """Simulated human operator — imperfection that is coherent, not random.

    Where ``natural`` adds cosmetic smoothing, ``humanize`` models *who* is
    driving: a persona whose precision, tempo and confidence drive cursor
    overshoot, typos, uneven scrolling and hesitation — all derived from one
    seed, and rationed by ``max_imperfections`` so the demo reads as
    hand-recorded rather than amateur.

    Plugs in at three levels: on the config (every scenario inherits it), on
    a scenario (wins over the config), and on a single step (see
    :class:`StepHumanize`). ``channels`` dials individual subsystems, so a
    demo can be humanised at the keyboard but locked-off at the camera.
    """

    enabled: bool = True
    persona: Literal[
        "expert_confident",
        "first_time_user",
        "tired_operator",
        "presenter",
    ] = Field(
        default="presenter",
        description="Operator archetype driving precision, tempo and confidence.",
    )
    intensity: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="How much imperfection to apply. 0 = identical to a "
        "scripted robot run, 1 = maximum human drift.",
    )
    seed: int | None = Field(
        default=None,
        description="Seed for the operator's noise streams. None inherits the "
        "config-level 'seed', keeping runs reproducible.",
    )
    fatigue_ramp: bool = Field(
        default=True,
        description="Let precision and tempo degrade as the recording goes on.",
    )
    max_imperfections: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Hard cap on visible mistakes (mistyped keys, misclicks) "
        "per scenario. Never two on consecutive steps.",
    )
    keyboard_layout: Literal["qwerty", "azerty"] = Field(
        default="qwerty",
        description="Physical layout used to pick a plausible wrong key when simulating a typo.",
    )
    handheld: bool = Field(
        default=True,
        description="Add a sub-hertz camera drift, as if the recording were "
        "framed by a person rather than locked to the pixel grid.",
    )
    film_look: bool = Field(
        default=False,
        description="Add animated grain and a soft vignette. A deliberate "
        "stylistic choice, so off by default.",
    )
    channels: dict[HumanizeChannel, float] | None = Field(
        default=None,
        description="Per-subsystem intensity, overriding the global one. "
        "0 switches a subsystem off entirely: {'camera': 0, 'keyboard': 1.0} "
        "keeps a locked-off camera while the typing stays fully human. "
        "Subsystems left out follow 'intensity'.",
    )

    @field_validator("channels")
    @classmethod
    def _channel_range(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        for name, value in (v or {}).items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"humanize.channels['{name}'] must be between 0 and 1, got {value}"
                )
        return v


class StepHumanize(_StrictBase):
    """Per-step tweak of the scenario's operator.

    Only the dials are overridable: the imperfection budget stays owned by the
    scenario, so a step cannot buy itself extra mistakes.
    """

    enabled: bool = True
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    channels: dict[HumanizeChannel, float] | None = Field(
        default=None,
        description="Per-subsystem intensity for this step only.",
    )

    @field_validator("channels")
    @classmethod
    def _channel_range(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        return HumanizeConfig._channel_range(v)


class OAuthPolicy(_StrictBase):
    """Governance policy for the ``oauth_login`` social-signup action.

    Drives a robust state machine through the *"Sign in with Google/Microsoft/
    GitHub"* consent flow (account chooser, credentials, 2FA, consent) and —
    crucially — makes the **permission grant** an explicit, auditable decision
    instead of a blind click.

    Security model:
        * Passwords are NEVER typed by the automation. The saved browser
          session (created once via ``demodsl setup-login``) supplies the
          identity. If a credentials screen appears, ``on_credentials`` decides
          whether to abort or wait for a human.
        * The consent screen is vetted against ``allowed_scopes`` /
          ``denied_scopes`` before the approve button is clicked. The denylist
          is a hard veto; the allowlist fails closed (if the requested
          permissions can't be read, consent is refused).
    """

    provider: Literal["google", "microsoft", "github", "generic"] = Field(
        default="google",
        description="Identity provider — tunes screen detection and the "
        "consent-button label. Use 'generic' for any other provider.",
    )
    account_email: str | None = Field(
        default=None,
        description="When an account chooser appears, pick the entry whose "
        "email/identifier contains this substring. If unset, the first "
        "account is used.",
    )
    success_host: str | None = Field(
        default=None,
        description="Hostname (or suffix) that signals a successful login, "
        "i.e. the SaaS host you are redirected back to. If unset, the host of "
        "the page where the flow started is used.",
    )
    auto_consent: bool = Field(
        default=True,
        description="Automatically click the approve button once the consent "
        "screen passes the scope policy. Set False to require a human click.",
    )
    allowed_scopes: list[str] | None = Field(
        default=None,
        description="Allowlist of permission substrings. When set, every "
        "permission read from the consent screen must match one of these, "
        "otherwise the flow aborts (fails closed if none can be read).",
    )
    denied_scopes: list[str] | None = Field(
        default=None,
        description="Denylist of permission substrings. If any appears on the "
        "consent screen, the flow aborts. Reliable hard veto, e.g. "
        "['delete', 'Drive', 'manage your contacts'].",
    )
    on_credentials: Literal["abort", "wait"] = Field(
        default="abort",
        description="What to do if an email/password screen appears (the saved "
        "session isn't signed in): 'abort' fails fast, 'wait' lets a human "
        "complete it within the timeout. Passwords are never auto-typed.",
    )
    on_2fa: Literal["abort", "wait"] = Field(
        default="wait",
        description="What to do on a 2FA/verification challenge: 'wait' (default) "
        "lets a human finish it within the timeout; 'abort' fails fast.",
    )
    poll: float = Field(
        default=1.0,
        gt=0,
        le=10.0,
        description="Seconds between screen probes.",
    )

    @field_validator("success_host")
    @classmethod
    def _clean_success_host(cls, v: str | None) -> str | None:
        if v is None:
            return v
        host = v.strip()
        if not host or "/" in host or " " in host or "\x00" in host or "://" in host:
            raise ValueError(f"success_host must be a bare hostname, got {v!r}")
        return host


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
        # Social / OAuth signup with consent governance
        "oauth_login",
        # Email validation (register + confirm flows)
        "await_email",
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
        # OS usage taxonomy (native settings setup)
        "os_setting",
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

    # mobile: os_setting — OS usage taxonomy (see demodsl.os_taxonomy)
    setting: str | None = Field(
        default=None,
        description="Dotted OS setting key from the taxonomy, e.g. "
        "'network.airplane_mode'. The value (on/off) goes in 'value'.",
    )
    os: str | None = Field(
        default=None,
        description="Compact OS setting intent, e.g. 'network.airplane_mode=on'. "
        "Shorthand that expands to action='os_setting' + setting + value.",
    )
    labels: dict[str, dict[str, str]] | None = Field(
        default=None,
        description="Localised label overrides for an 'os_setting' step, keyed by "
        "the canonical English label, e.g. {'General': {'type': 'text', "
        "'value': 'Général'}}. Lets localised devices reuse the taxonomy.",
    )

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
    humanize: bool | StepHumanize | None = Field(
        default=None,
        description="Per-step override of the operator. False protects a "
        "critical beat (CTA, form submit) from any simulated mistake while "
        "keeping the rest of the human motion; a StepHumanize block dials "
        "intensity or individual subsystems for this step only.",
    )
    zoom_on_click: bool | ZoomOnClick | None = Field(
        default=None,
        description="Automatically zoom the camera onto this click step's own "
        "locator, perform the click, hold, then zoom back out — no separate "
        "'camera' step needed. True uses sensible defaults; a ZoomOnClick "
        "block tunes zoom/duration/hold/ease. Only applies to 'click' steps.",
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

    # await_email: read a registration/validation email over IMAP and either
    # follow the confirmation link or fill in the verification code.
    email_subject: str | None = Field(
        default=None,
        description="Only match emails whose Subject contains this substring "
        "(case-insensitive). For action 'await_email'.",
    )
    email_from: str | None = Field(
        default=None,
        description="Only match emails whose From contains this substring "
        "(case-insensitive), e.g. 'noreply@acme.com'. For 'await_email'.",
    )
    email_extract: Literal["link", "code"] | None = Field(
        default=None,
        description="What to pull from the validation email: 'link' (default) "
        "navigates to the confirmation URL; 'code' fills the code into "
        "'locator'. For action 'await_email'.",
    )
    email_link_contains: str | None = Field(
        default=None,
        description="When email_extract='link', pick the first link whose URL "
        "contains this substring (e.g. 'verify', 'confirm'). For 'await_email'.",
    )
    email_code_pattern: str | None = Field(
        default=None,
        description="When email_extract='code', regex with one capture group "
        r"for the code (default '\b(\d{4,8})\b'). For 'await_email'.",
    )

    # oauth_login: governance policy for the social-signup consent flow.
    oauth: OAuthPolicy | None = Field(
        default=None,
        description="Governance policy for the 'oauth_login' action: which "
        "account to pick, which permissions are acceptable (allow/deny), and "
        "how to react to password/2FA screens. See OAuthPolicy.",
    )

    # action: 'camera' / 'camera_reset').
    camera: CameraMove | None = Field(
        default=None,
        description="Animated virtual camera move (zoom/pan/rotate) applied "
        "to the recorded page before/with the action. See CameraMove.",
    )

    # failure policy (issue #22)
    on_error: OnErrorPolicy | None = Field(
        default=None,
        description="What to do when this step fails: 'skip' logs a warning and "
        "keeps the wait + narration so the audio stays in sync; "
        "'scroll_into_view_only' falls back to scrolling the element into view; "
        "'fail' aborts the render. Default: 'skip', except for navigate / "
        "oauth_login / await_email which stay fatal.",
    )

    # semantic authoring (issue #20)
    beat: BeatSpec | None = Field(
        default=None,
        description="Semantic intent of this step (role + sentiment + note). "
        "Expands to the house camera move, pointing effects and pacing; "
        "explicit action/camera/effects/wait always override the expansion.",
    )

    @model_validator(mode="before")
    @classmethod
    def _expand_beat(cls, data: Any) -> Any:
        """Expand the semantic ``beat:`` shorthand into concrete fields."""
        if isinstance(data, dict) and data.get("beat") is not None:
            from demodsl.recipe import expand_beat

            return expand_beat(data)
        return data

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

    @model_validator(mode="before")
    @classmethod
    def _expand_os_shorthand(cls, data: Any) -> Any:
        """Expand the compact ``os: "key=value"`` shorthand into fields."""
        if isinstance(data, dict) and isinstance(data.get("os"), str):
            from demodsl.os_taxonomy import parse_setting_expr

            key, value = parse_setting_expr(data["os"])
            data.setdefault("action", "os_setting")
            data.setdefault("setting", key)
            if value is not None:
                data.setdefault("value", value)
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
        if a == "os_setting" and not self.setting:
            raise ValueError(
                "'os_setting' requires 'setting' (a taxonomy key like "
                "'network.airplane_mode') or the 'os:' shorthand."
            )
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
        if a == "await_email" and self.email_extract == "code" and not self.locator:
            raise ValueError(
                "'await_email' with email_extract='code' requires 'locator' "
                "(the field to fill with the verification code)."
            )
        if (
            a == "oauth_login"
            and self.oauth is not None
            and self.oauth.allowed_scopes
            and self.oauth.denied_scopes
        ):
            overlap = {s.lower() for s in self.oauth.allowed_scopes} & {
                s.lower() for s in self.oauth.denied_scopes
            }
            if overlap:
                raise ValueError(
                    f"'oauth_login' policy lists the same scope(s) in both "
                    f"allowed_scopes and denied_scopes: {sorted(overlap)}"
                )
        # Warn on irrelevant fields for an action
        relevant = STEP_RELEVANT_FIELDS.get(a, set()) | STEP_COMMON_FIELDS
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


#: Per-action fields that carry meaning (anything else set on the step is
#: warned about at validation time). Also the source of truth for the
#: machine-readable capability manifest (issue #15).
STEP_RELEVANT_FIELDS: dict[str, set[str]] = {
    "navigate": {"url"},
    "click": {"locator", "hover_delay", "zoom_on_click"},
    "type": {"locator", "value", "char_rate", "zoom_input", "typing_variance"},
    "scroll": {"direction", "pixels", "smooth_scroll"},
    "pause": set(),
    "wait_for": {"locator", "timeout"},
    "screenshot": {"filename"},
    "shortcut": {"keys"},
    "hover": {"locator", "hover_delay"},
    "drag": {"locator", "target_locator", "end_x", "end_y", "duration_ms"},
    "press_key": {"key"},
    "await_email": {
        "locator",
        "timeout",
        "email_subject",
        "email_from",
        "email_extract",
        "email_link_contains",
        "email_code_pattern",
    },
    "oauth_login": {"locator", "timeout", "oauth"},
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
    "os_setting": {"setting", "os", "value", "labels"},
    # Terminal actions
    "terminal_run": {"command", "output"},
    "terminal_clear": set(),
    "terminal_zoom": {"zoom_level", "zoom_duration"},
    # Virtual camera actions
    "camera": {"camera"},
    "camera_reset": set(),
}

#: Fields meaningful for every action.
STEP_COMMON_FIELDS: frozenset[str] = frozenset(
    {
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
        "on_error",
        "beat",
        "humanize",
    }
)

#: Fields an action cannot be built without (mirrors ``_validate_action_fields``).
STEP_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "navigate": ("url",),
    "click": ("locator",),
    "wait_for": ("locator",),
    "type": ("locator", "value"),
    "hover": ("locator",),
    "drag": ("locator",),
    "press_key": ("key",),
    "shortcut": ("keys",),
    "swipe": ("start_x", "start_y", "end_x", "end_y"),
    "pinch": ("pinch_scale",),
    "rotate_device": ("orientation",),
    "os_setting": ("setting",),
    "terminal_run": ("command",),
    "camera": ("camera",),
}


# Browser-only actions that must not appear in mobile scenarios
_BROWSER_ONLY_ACTIONS: frozenset[str] = frozenset(
    {
        "navigate",
        "shortcut",
        "hover",
        "drag",
        "press_key",
        "camera",
        "camera_reset",
        "await_email",
        "oauth_login",
    }
)

_TERMINAL_ONLY_ACTIONS: frozenset[str] = frozenset(
    {"terminal_run", "terminal_clear", "terminal_zoom"}
)


class BrowserAuthConfig(_StrictBase):
    """Per-scenario configuration for the authenticated-browser providers.

    Lets several scenarios in one config each drive their own
    already-authenticated browser session (e.g. different Google accounts,
    or a CDP attach in one scenario and a persistent profile in another).
    Overrides the global ``DEMODSL_*`` environment variables.

    Fields:
        user_data_dir: Chrome profile directory (provider 'playwright-persistent').
        cdp_url:       DevTools endpoint to attach to (provider 'playwright-cdp').
        channel:       Browser channel — 'chrome', 'msedge', 'chrome-beta', or
                       '' for bundled Chromium (persistent only).
        headless:      Run headless=new (persistent only; default headed).
        isolate:       Clone the profile to a throwaway dir before launch so the
                       SAME profile can back multiple scenarios running in
                       parallel without Chrome's single-instance lock clashing.
        record:        Recording backend — 'cdp' (default) uses periodic CDP
                       screenshots (works everywhere but can be choppy on slow
                       captures); 'playwright' uses Playwright's native video
                       recorder for smooth, full-frame-rate output.  Native
                       video requires a HEADED browser (``headless: false``):
                       headless Chromium records a blank track, so it
                       automatically falls back to the CDP recorder.
    """

    user_data_dir: str | None = None
    cdp_url: str | None = None
    channel: str | None = None
    headless: bool | None = None
    isolate: bool = False
    record: Literal["cdp", "playwright"] | None = None

    @field_validator("user_data_dir")
    @classmethod
    def _safe_dir(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_safe_path(v)

    @field_validator("cdp_url")
    @classmethod
    def _safe_cdp(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_url(v)


class MailboxConfig(_StrictBase):
    """IMAP mailbox used to automate register + email-validation flows.

    The ``await_email`` step connects here, waits for the validation email
    sent by the SaaS, and either follows the confirmation link or fills in
    the verification code.

    Every field falls back to a ``DEMODSL_IMAP_*`` environment variable when
    left unset, so secrets never have to live in the YAML:
        imap_host -> DEMODSL_IMAP_HOST
        username  -> DEMODSL_IMAP_USER
        password  -> DEMODSL_IMAP_PASSWORD   (RECOMMENDED to set via env only)
        imap_port -> DEMODSL_IMAP_PORT

    Security: do NOT commit a password in YAML — prefer the env var, and use
    a provider app-password (e.g. Gmail app password) rather than your main
    account password.
    """

    imap_host: str | None = Field(
        default=None,
        description="IMAP server hostname, e.g. 'imap.gmail.com'.",
    )
    imap_port: int = Field(
        default=993,
        gt=0,
        le=65535,
        description="IMAP port (993 for IMAPS/SSL).",
    )
    username: str | None = Field(
        default=None,
        description="Mailbox login (often the full email address).",
    )
    password: str | None = Field(
        default=None,
        description="Mailbox password / app-password. Prefer DEMODSL_IMAP_PASSWORD.",
    )
    use_ssl: bool = Field(
        default=True,
        description="Connect with implicit TLS (IMAPS). Disable only for STARTTLS/plain.",
    )
    folder: str = Field(
        default="INBOX",
        description="Mailbox folder to search.",
    )

    @field_validator("imap_host")
    @classmethod
    def _clean_host(cls, v: str | None) -> str | None:
        if v is None:
            return v
        host = v.strip()
        if not host or "/" in host or " " in host or "\x00" in host:
            raise ValueError(f"Invalid IMAP host: {v!r}")
        # Reject an accidental scheme/port suffix — host only.
        if "://" in host:
            raise ValueError(f"IMAP host must be a hostname, not a URL: {v!r}")
        return host


class Scenario(_StrictBase):
    name: str
    # Base URL for the scenario. The first step should typically be
    # action: "navigate" pointing to this URL.
    url: str | None = None
    browser: Literal["chrome", "firefox", "webkit"] = "chrome"
    fallback_browser: Literal["chrome", "firefox", "webkit"] | None = None
    provider: Literal[
        "playwright",
        "selenium",
        "playwright-cdp",
        "playwright-persistent",
    ] = "playwright"
    auth: BrowserAuthConfig | None = None
    viewport: Viewport = Field(default_factory=Viewport)
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    locale: str | None = None
    cursor: CursorConfig | None = None
    glow_select: GlowSelectConfig | None = None
    popup_card: PopupCardConfig | None = None
    avatar: AvatarConfig | None = None
    subtitle: SubtitleConfig | None = None
    mailbox: MailboxConfig | None = None
    natural: bool | NaturalConfig | None = Field(
        default=None,
        description="Enable natural/human-like demo behaviour. "
        "True uses defaults; pass NaturalConfig for custom values. "
        "Step-level fields (hover_delay, smooth_scroll, etc.) override.",
    )
    humanize: bool | HumanizeConfig | None = Field(
        default=None,
        description="Simulate a human operator (cursor overshoot, typos, "
        "uneven scrolling, hesitation) from a seeded persona. True uses the "
        "'presenter' defaults; pass HumanizeConfig to tune.",
    )
    background: BackgroundConfig | None = None
    mobile: MobileConfig | None = None
    terminal: TerminalConfig | None = None
    on_error: OnErrorPolicy | None = Field(
        default=None,
        description="Default failure policy for every step of this scenario. "
        "Per-step 'on_error' wins. See Step.on_error.",
    )
    pre_steps: list[Step] | None = None
    steps: list[Step] = Field(default_factory=list)
    timeline: Timeline | None = Field(
        default=None,
        description="After-Effects-style overlay timeline composited on top "
        "of the captured browser video (text/shape/image layers with "
        "keyframed transforms).",
    )
    theme: ThemeConfig | None = Field(
        default=None,
        description="Per-scenario theme override — lets one video showcase "
        "several visual identities back to back (e.g. a light theme for one "
        "scenario, a dark brand theme for the next). Accepts a preset name "
        "or an inline object, same as the top-level 'theme'. Falls back to "
        "the top-level theme when unset; explicit per-field overlay values "
        "still win over either.",
    )

    @field_validator("theme", mode="before")
    @classmethod
    def _resolve_theme_preset(cls, v: Any) -> Any:
        """Accept ``theme: dark-dev`` (a preset name) as well as an object."""
        if isinstance(v, str):
            presets = discover_theme_presets()
            preset = presets.get(v)
            if preset is None:
                raise ValueError(f"Unknown theme preset {v!r}. Available: {sorted(presets)}")
            return dict(preset)
        return v

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

    @property
    def subsystem(self) -> str:
        """Which provider family drives this scenario: web / mobile / terminal."""
        if self.mobile:
            return "mobile"
        if self.terminal:
            return "terminal"
        return "web"

    @model_validator(mode="after")
    def _validate_locator_strategies(self) -> Scenario:
        """Reject locator strategies the provider cannot resolve (issue #28).

        ``Locator.type`` is the union of every strategy the DSL knows about, so
        a web scenario used to accept ``accessibility_id``, pass
        ``demodsl validate``, and then die mid-render with ``Unsupported
        locator type`` — after the browser recording and the TTS work. Failing
        at load time instead costs nothing and names the strategies that would
        have worked.
        """
        allowed = supported_locator_types(self.subsystem)
        if not allowed:
            return self

        def check(step: Step, label: str) -> None:
            for field in ("locator", "target_locator"):
                locator = getattr(step, field, None)
                if locator is None or locator.type in allowed:
                    continue
                raise LocatorNotSupportedError(locator.type, self.subsystem, label)

        for i, step in enumerate(self.pre_steps or []):
            check(step, f"Pre-step {i + 1}")
        for i, step in enumerate(self.steps):
            check(step, f"Step {i + 1}")
        return self

    @model_validator(mode="after")
    def _check_camera_coherence(self) -> Scenario:
        """Replay the camera state machine and warn on incoherent choreography.

        Warnings only — authoring pipelines that want hard failures call
        :func:`demodsl.camera_check.check_camera_flow` themselves and treat
        ``error``-severity issues as rejections.
        """
        if any(
            s.camera is not None or s.action in ("camera", "camera_reset") for s in self.steps or []
        ):
            from demodsl.camera_check import check_camera_flow

            for issue in check_camera_flow(self):
                warnings.warn(f"Scenario '{self.name}': {issue}", UserWarning, stacklevel=1)
        return self
