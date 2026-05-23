"""Timeline / keyframes / layers — After-Effects-style compositing.

Phase 1 (MVP): Timeline + Keyframes + three layer types (text, shape, image).
A timeline is rendered as an overlay on top of the captured browser video
by the ``composite_timeline`` pipeline stage.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from demodsl.models._base import _StrictBase, _validate_css_color

# ── Keyframes & easing ───────────────────────────────────────────────────────

Easing = Literal["linear", "ease", "ease-in", "ease-out", "ease-in-out", "spring", "hold"]


class Keyframe(_StrictBase):
    """A single keyframe: at time ``t`` the property has value ``v``."""

    t: float = Field(ge=0.0, description="Time in seconds (layer-local).")
    v: float | list[float] = Field(
        description="Scalar or vector value (list for position [x,y], color, ...)."
    )
    ease: Easing = Field(
        default="ease-in-out",
        description="Easing applied between THIS keyframe and the NEXT one. "
        "'hold' freezes the value until the next keyframe.",
    )


# ── Transform ────────────────────────────────────────────────────────────────


class Transform(_StrictBase):
    """Static transform values. Use ``animators`` for time-varying ones."""

    position: list[float] = Field(
        default_factory=lambda: [960.0, 540.0],
        description="[x, y] in pixels, in the final video coordinate space.",
    )
    position_z: float = Field(
        default=0.0,
        description="Z depth in world units (Phase 8). Positive = farther from "
        "the camera. Ignored when no ``camera_3d`` is defined.",
    )
    anchor: list[float] = Field(
        default_factory=lambda: [0.5, 0.5],
        description="Anchor point (0–1 normalised) used for scale/rotation.",
    )
    scale: float = Field(default=1.0, gt=0.0)
    rotation: float = Field(default=0.0, description="Degrees.")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


# ── Animators (per-property keyframe tracks) ─────────────────────────────────


AnimatableProperty = Literal[
    "position",
    "scale",
    "rotation",
    "opacity",
    "position_x",
    "position_y",
    "position_z",
]


class PropertyTrack(_StrictBase):
    """A keyframed track for one property."""

    property: AnimatableProperty
    keyframes: list[Keyframe] = Field(min_length=1)

    @field_validator("keyframes")
    @classmethod
    def _sorted(cls, v: list[Keyframe]) -> list[Keyframe]:
        times = [kf.t for kf in v]
        if times != sorted(times):
            raise ValueError("keyframes must be sorted by 't' (ascending).")
        return v


# ── Layers ───────────────────────────────────────────────────────────────────


BlendMode = Literal[
    "normal",
    "multiply",
    "screen",
    "overlay",
    "add",
    "subtract",
    "darken",
    "lighten",
    "difference",
    "color-dodge",
    "color-burn",
]


MaskMode = Literal["add", "subtract", "intersect"]
MaskShape = Literal["rectangle", "ellipse"]


class Mask(_StrictBase):
    """Sprite-local mask. Applied AFTER the sprite is rendered, BEFORE
    transform. Coordinates are normalised 0–1 inside the sprite bounding box.
    """

    shape: MaskShape = "rectangle"
    bounds: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 1.0, 1.0],
        description="[x0, y0, x1, y1] in 0–1 sprite-local coordinates.",
    )
    feather: float = Field(default=0.0, ge=0.0, description="Edge blur (px).")
    inverted: bool = False
    mode: MaskMode = "add"

    @field_validator("bounds")
    @classmethod
    def _check_bounds(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError("bounds must be [x0, y0, x1, y1].")
        return v


TrackMatteMode = Literal["alpha", "alpha-inverted", "luma", "luma-inverted"]


class TrackMatte(_StrictBase):
    """Use another layer's alpha (or luma) as this layer's mask."""

    source: str = Field(description="Layer id whose alpha/luma is the matte.")
    mode: TrackMatteMode = "alpha"


# ── Time remapping & motion blur (Phase 5) ───────────────────────────────────


class TimeRemap(_StrictBase):
    """Remap layer-local time to a different internal time.

    Each keyframe is ``[t_out, t_in]``: at output time ``t_out`` (seconds since
    ``layer.start``), the layer is sampled at internal time ``t_in``. Between
    keyframes the mapping is linear; outside the first/last keyframe the value
    is clamped (freeze frames). This affects animators, expressions AND, for
    a ``PrecompLayer``, which inner-precomp frame is rendered.
    """

    keyframes: list[list[float]] = Field(
        min_length=2,
        description="List of [t_out, t_in] pairs (seconds), sorted by t_out.",
    )

    @field_validator("keyframes")
    @classmethod
    def _check(cls, v: list[list[float]]) -> list[list[float]]:
        outs: list[float] = []
        for kf in v:
            if len(kf) != 2:
                raise ValueError("TimeRemap keyframe must be [t_out, t_in].")
            outs.append(float(kf[0]))
        if outs != sorted(outs):
            raise ValueError("TimeRemap keyframes must be sorted by t_out.")
        return v


class MotionBlur(_StrictBase):
    """Cinematic motion blur — N sub-samples averaged across a shutter window.

    ``shutter_angle`` follows the film convention: 180° means each output
    frame integrates the first half of the inter-frame interval (the classic
    cinema look). 360° integrates the full interval (more blur).
    """

    shutter_angle: float = Field(
        default=180.0,
        gt=0.0,
        le=720.0,
        description="Shutter angle in degrees (180° = standard cinema).",
    )
    samples: int = Field(
        default=8,
        ge=2,
        le=32,
        description="Number of sub-frames sampled per output frame.",
    )


# ── SaaS B2B toolkit ─────────────────────────────────────────────────────────


class DropShadow(_StrictBase):
    """Soft drop shadow rendered behind any layer. Use it to detach UI
    elements (cards, buttons, dropdowns) from the page background."""

    color: str = Field(default="#000000")
    opacity: float = Field(default=0.45, ge=0.0, le=1.0)
    offset_x: float = Field(default=0.0)
    offset_y: float = Field(default=12.0)
    blur: float = Field(
        default=24.0,
        ge=0.0,
        description="Gaussian blur radius in pixels.",
    )
    spread: float = Field(
        default=0.0,
        ge=0.0,
        description="Dilate the shadow silhouette by this many pixels "
        "before blurring (CSS-style spread).",
    )

    @field_validator("color")
    @classmethod
    def _color(cls, v: str) -> str:
        return _validate_css_color(v)


class Counter(_StrictBase):
    """Animated numeric counter on a ``TextLayer``. The layer's
    ``content`` is REPLACED every frame by ``format.format(value=...)``,
    where ``value`` ticks from ``from_value`` to ``to_value`` between
    ``start`` and ``start + duration`` (layer-local seconds).

    Common formats:
      • ``"{value:,.0f}"`` — rounded with thousands separator (default)
      • ``"${value:,.2f}"`` — currency with two decimals
      • ``"+{value:.1f}%"`` — percentage with sign
    """

    from_value: float = Field(default=0.0)
    to_value: float
    start: float = Field(
        default=0.0,
        ge=0.0,
        description="Counter start in layer-local seconds.",
    )
    duration: float = Field(gt=0.0)
    ease: Easing = "ease-out"
    format: str = Field(default="{value:,.0f}")


class TextAnimator(_StrictBase):
    """Per-character text animator (After Effects-style).

    Each character is rendered as its own mini-sprite. The animator's
    keyframes describe a curve that is replayed for EVERY character, but the
    per-character clock is shifted by ``char_delay * char_index`` (sequential
    activation). Use ``reverse_order`` to animate from the last char first.

    All offsets are in pixels (post-rasterisation, pre-transform), so they
    integrate naturally with the layer's existing transform / motion-blur /
    time-remap pipeline.
    """

    char_delay: float = Field(
        default=0.05,
        ge=0.0,
        description="Seconds between consecutive char activations.",
    )
    reverse_order: bool = Field(
        default=False,
        description="If True, the LAST char activates first.",
    )
    letter_spacing: float = Field(
        default=0.0,
        description="Extra horizontal spacing between chars (pixels).",
    )
    offset_x: list[Keyframe] | None = Field(
        default=None,
        description="Per-char horizontal offset over time (pixels).",
    )
    offset_y: list[Keyframe] | None = Field(
        default=None,
        description="Per-char vertical offset over time (pixels).",
    )
    scale: list[Keyframe] | None = Field(
        default=None,
        description="Per-char scale over time (1.0 = normal).",
    )
    rotation: list[Keyframe] | None = Field(
        default=None,
        description="Per-char rotation over time (degrees).",
    )
    opacity: list[Keyframe] | None = Field(
        default=None,
        description="Per-char opacity over time (0..1).",
    )

    @field_validator("offset_x", "offset_y", "scale", "rotation", "opacity")
    @classmethod
    def _sorted_kfs(cls, v: list[Keyframe] | None) -> list[Keyframe] | None:
        if v is None:
            return v
        if len(v) < 1:
            raise ValueError("Animator track must have at least one keyframe.")
        times = [kf.t for kf in v]
        if times != sorted(times):
            raise ValueError("Animator keyframes must be sorted by ``t``.")
        return v


# ── Phase 9: Tracking & data-driven ──────────────────────────────────────────


class TrackPoint(_StrictBase):
    """One sampled position (and optional scale/rotation) at a given time."""

    t: float = Field(ge=0.0, description="Sample time in seconds.")
    x: float
    y: float
    scale: float | None = Field(default=None, gt=0.0)
    rotation: float | None = None


class Tracker(_StrictBase):
    """Attach a layer to a path of tracked points (e.g. a DOM element's
    bounding box sampled per-frame, or hand-authored samples).

    When set, the tracker's interpolated position overrides the layer's
    resolved ``transform.position``. With ``attach: "transform"`` the
    optional per-point scale/rotation override those properties too.
    """

    points: list[TrackPoint] = Field(min_length=1)
    offset: list[float] = Field(
        default_factory=lambda: [0.0, 0.0],
        description="[dx, dy] in pixels, added on top of each interpolated "
        "point. Use it to pin a label next to a tracked target.",
    )
    attach: Literal["position", "transform"] = Field(
        default="position",
        description="``position`` overrides only x/y. ``transform`` also "
        "overrides scale and rotation when those are provided on points.",
    )

    @field_validator("offset")
    @classmethod
    def _offset_len2(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("Tracker.offset must be [dx, dy].")
        return v

    @field_validator("points")
    @classmethod
    def _sorted(cls, v: list[TrackPoint]) -> list[TrackPoint]:
        if [p.t for p in v] != sorted(p.t for p in v):
            raise ValueError("Tracker.points must be sorted by ``t``.")
        return v


DataTarget = Literal[
    "content",
    "position_x",
    "position_y",
    "position_z",
    "scale",
    "rotation",
    "opacity",
]


class DataBinding(_StrictBase):
    """Bind a layer property to a value (or time-series) read from a JSON
    file at composition time.

    Two modes:
      • **Scalar** — ``path`` resolves to a number/string. For text layers
        with ``target: content`` the value is formatted via ``format`` and
        substituted into ``content``. For numeric targets the value is
        applied as a static override on the resolved Transform.
      • **Time-series** — ``path`` resolves to a list of items. With
        ``time_key`` + ``value_key`` set, items become keyframes
        ``(item[time_key], item[value_key])`` and are appended as an
        animator on the target property.
    """

    source: str = Field(
        min_length=1,
        description="Path to a JSON file, resolved against the YAML's directory if relative.",
    )
    path: str = Field(
        min_length=1,
        description="Dot-and-index path into the JSON, e.g. ``metrics.users`` or ``points[0].v``.",
    )
    target: DataTarget = Field(
        description="Layer property to drive. ``content`` is only valid on text layers.",
    )
    format: str = Field(
        default="{value}",
        description="Python format string, e.g. ``'{value:,.0f}'``. "
        "Available placeholder: ``{value}``.",
    )
    time_key: str | None = Field(
        default=None,
        description="When set, treat the resolved data as a list and read "
        "``item[time_key]`` for each keyframe time.",
    )
    value_key: str | None = Field(
        default=None,
        description="When ``time_key`` is set, also read ``item[value_key]``"
        " for the keyframe value.",
    )


class _LayerBase(_StrictBase):
    id: str = Field(min_length=1)
    start: float = Field(default=0.0, ge=0.0, description="In-point (seconds).")
    duration: float | None = Field(
        default=None,
        gt=0.0,
        description="Layer duration. ``None`` means until end of video.",
    )
    transform: Transform = Field(default_factory=Transform)
    animators: list[PropertyTrack] = Field(default_factory=list)
    parent: str | None = Field(
        default=None,
        description="Parent layer id. The parent's transform is applied "
        "BEFORE this layer's transform (composed in order).",
    )
    expressions: dict[AnimatableProperty, str] = Field(
        default_factory=dict,
        description="Per-property DSL expressions (e.g. "
        "'wiggle(freq=2, amp=20)'). Evaluated per-frame, OVERRIDE keyframed "
        "animators for the same property.",
    )
    masks: list[Mask] = Field(
        default_factory=list,
        description="Sprite-local masks (combined in order).",
    )
    track_matte: TrackMatte | None = Field(
        default=None,
        description="Use another layer as alpha/luma matte for this one. "
        "The matte source is NOT rendered on its own.",
    )
    blend_mode: BlendMode = Field(
        default="normal",
        description="How this layer blends with the layers below.",
    )
    time_remap: TimeRemap | None = Field(
        default=None,
        description="Per-layer time remapping (slow-mo, freeze, reverse).",
    )
    motion_blur: MotionBlur | None = Field(
        default=None,
        description="Enable cinematic motion blur on this layer.",
    )
    drop_shadow: DropShadow | None = Field(
        default=None,
        description="Optional soft drop shadow rendered behind this layer.",
    )
    tracker: Tracker | None = Field(
        default=None,
        description="Phase 9: attach this layer's position (and optionally "
        "scale/rotation) to a series of tracked points.",
    )
    data_bindings: list[DataBinding] = Field(
        default_factory=list,
        description="Phase 9: bind layer properties (or text content) to "
        "values loaded from a JSON file at composition time.",
    )

    @field_validator("animators")
    @classmethod
    def _unique_properties(cls, v: list[PropertyTrack]) -> list[PropertyTrack]:
        seen: set[str] = set()
        for tr in v:
            if tr.property in seen:
                raise ValueError(
                    f"Duplicate animator for property '{tr.property}' — "
                    "merge keyframes into a single track."
                )
            seen.add(tr.property)
        return v


class TextLayer(_LayerBase):
    type: Literal["text"]
    content: str = Field(min_length=1)
    font_family: str = Field(default="Inter")
    font_size: int = Field(default=64, gt=0)
    font_weight: Literal["normal", "bold", "black"] = "bold"
    color: str = Field(default="#FFFFFF")
    stroke_color: str | None = None
    stroke_width: int = Field(default=0, ge=0)
    align: Literal["left", "center", "right"] = "center"
    animator: TextAnimator | None = Field(
        default=None,
        description="Per-character animator (typewriter, wave, fly-in, …). "
        "When set, the text is rasterised char-by-char per frame.",
    )
    counter: Counter | None = Field(
        default=None,
        description="Animated numeric counter — overrides ``content`` per "
        "frame with a formatted interpolated number.",
    )

    @field_validator("color", "stroke_color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_css_color(v) if v else v


class ShapeLayer(_LayerBase):
    type: Literal["shape"]
    shape: Literal["rectangle", "ellipse"]
    width: float = Field(default=200.0, gt=0.0)
    height: float = Field(default=200.0, gt=0.0)
    fill: str | None = Field(default="#6366F1")
    stroke: str | None = None
    stroke_width: float = Field(default=0.0, ge=0.0)
    corner_radius: float = Field(default=0.0, ge=0.0)

    @field_validator("fill", "stroke")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_css_color(v) if v else v


class ImageLayer(_LayerBase):
    type: Literal["image"]
    src: str = Field(description="Path to PNG/JPG/GIF/SVG (relative to YAML or absolute).")
    width: float | None = Field(default=None, gt=0.0)
    height: float | None = Field(default=None, gt=0.0)


class NullLayer(_LayerBase):
    """Invisible pivot layer. Useful as a parent: animate the null, all its
    children inherit the move (camera-rig pattern)."""

    type: Literal["null"]


class SpotlightLayer(_LayerBase):
    """SaaS-grade focus effect: blurs and darkens the *captured frame*
    everywhere EXCEPT inside a soft-feathered shape centred on
    ``transform.position``. The composited overlay layers above are not
    affected — only the page underneath. Lifetime is controlled by
    ``start`` + ``duration`` like any layer.
    """

    type: Literal["spotlight"]
    shape: Literal["rectangle", "ellipse"] = "ellipse"
    width: float = Field(default=600.0, gt=0.0)
    height: float = Field(default=400.0, gt=0.0)
    feather: float = Field(
        default=80.0,
        ge=0.0,
        description="Gaussian falloff (in pixels) on the mask edges.",
    )
    darken: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="0 = no darkening outside the cut-out; 1 = pitch black.",
    )
    blur: float = Field(
        default=12.0,
        ge=0.0,
        description="Gaussian blur applied to the page outside the cut-out.",
    )
    corner_radius: float = Field(default=0.0, ge=0.0)


class PolylineLayer(_LayerBase):
    """A polyline / line-chart layer. Renders an open or closed polyline
    along ``points`` with a stroke (and optional underlying fill). The
    visible portion is controlled by ``trim_start`` / ``trim_end`` in
    parametric arc-length [0..1], which can be animated via the dedicated
    keyframe lists ``trim_start_kfs`` / ``trim_end_kfs`` (perfect for
    "drawing-in" KPI sparklines).
    """

    type: Literal["polyline"]
    points: list[list[float]] = Field(
        min_length=2,
        description="List of [x, y] points in canvas coordinates.",
    )
    stroke: str = Field(default="#22D3EE")
    stroke_width: float = Field(default=4.0, ge=0.0)
    closed: bool = Field(default=False)
    fill: str | None = Field(
        default=None,
        description="Optional fill under the line (e.g. for area charts). "
        "Requires ``fill_baseline_y``.",
    )
    fill_baseline_y: float | None = Field(
        default=None,
        description="When ``fill`` is set, close the polygon down to this y.",
    )
    trim_start: float = Field(default=0.0, ge=0.0, le=1.0)
    trim_end: float = Field(default=1.0, ge=0.0, le=1.0)
    trim_start_kfs: list[Keyframe] | None = None
    trim_end_kfs: list[Keyframe] | None = None
    line_cap: Literal["butt", "round", "square"] = "round"

    @field_validator("stroke", "fill")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_css_color(v) if v else v

    @field_validator("points")
    @classmethod
    def _len2(cls, v: list[list[float]]) -> list[list[float]]:
        for p in v:
            if len(p) != 2:
                raise ValueError("Each polyline point must be [x, y].")
        return v

    @field_validator("trim_start_kfs", "trim_end_kfs")
    @classmethod
    def _sorted_kfs(cls, v: list[Keyframe] | None) -> list[Keyframe] | None:
        if v is None:
            return v
        if [k.t for k in v] != sorted(k.t for k in v):
            raise ValueError("Trim keyframes must be sorted by ``t``.")
        return v


class ParticleEmitter(_LayerBase):
    """A particle system. Emits up to ``rate × emit_duration`` particles
    over its emission window, each with a randomised lifetime, position,
    velocity and visual style. The simulation is deterministic for a given
    ``seed`` and analytic per-particle (no inter-particle forces), so each
    output frame is computed independently — perfect for video pipelines.

    ``transform.position`` defines the emitter ORIGIN in canvas pixels
    (parenting + animators apply, so emitters can travel). All other
    transform fields (rotation, scale, anchor) are ignored for particles.

    Emission window: from layer ``start`` to ``start + emit_duration``
    (or until layer end if ``emit_duration`` is None). Particles continue
    living after emission stops, up to their individual lifetime.
    """

    type: Literal["particles"]

    rate: float = Field(
        default=60.0,
        gt=0.0,
        le=2000.0,
        description="Particles per second emitted (averaged).",
    )
    emit_duration: float | None = Field(
        default=None,
        gt=0.0,
        description="Emission window length (seconds). None = whole layer.",
    )
    lifetime: tuple[float, float] = Field(
        default=(0.8, 1.6),
        description="Per-particle lifetime range (seconds, [min, max]).",
    )
    emitter_shape: Literal["point", "circle", "rectangle"] = Field(
        default="point",
        description="Shape of the spawn region.",
    )
    emitter_width: float = Field(
        default=0.0,
        ge=0.0,
        description="Spawn region width (px). Used for circle/rectangle.",
    )
    emitter_height: float = Field(
        default=0.0,
        ge=0.0,
        description="Spawn region height (px). Rectangle only.",
    )
    direction: float = Field(
        default=-90.0,
        description="Mean emission direction in degrees (0 = right, -90 = up, 90 = down).",
    )
    spread: float = Field(
        default=30.0,
        ge=0.0,
        le=180.0,
        description="Cone half-angle around ``direction`` (degrees).",
    )
    speed: tuple[float, float] = Field(
        default=(200.0, 400.0),
        description="Initial speed range (px/s, [min, max]).",
    )
    gravity: tuple[float, float] = Field(
        default=(0.0, 0.0),
        description="Constant acceleration applied each frame (px/s²).",
    )
    particle_size: tuple[float, float] = Field(
        default=(4.0, 10.0),
        description="Initial size range (px, [min, max]). Used as the "
        "diameter/side for the chosen ``particle_shape``.",
    )
    particle_shape: Literal["circle", "square", "star"] = Field(
        default="circle",
        description="Per-particle sprite shape.",
    )
    color_start: str = Field(
        default="#FFFFFF",
        description="Particle colour at birth (hex / CSS).",
    )
    color_end: str | None = Field(
        default=None,
        description="Particle colour at death — interpolated over life. None = constant colour.",
    )
    opacity_start: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Opacity at birth.",
    )
    opacity_end: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Opacity at death.",
    )
    scale_end: float = Field(
        default=1.0,
        gt=0.0,
        description="Size multiplier at death (1.0 = constant).",
    )
    rotation_speed: tuple[float, float] = Field(
        default=(0.0, 0.0),
        description="Per-particle angular velocity range (deg/s).",
    )
    seed: int = Field(
        default=42,
        ge=0,
        description="RNG seed for deterministic emission.",
    )

    @field_validator("color_start", "color_end")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_css_color(v) if v else v

    @field_validator("lifetime", "speed", "particle_size", "rotation_speed")
    @classmethod
    def _range(cls, v: tuple[float, float]) -> tuple[float, float]:
        if v[0] > v[1]:
            raise ValueError(f"Range min > max: {v}")
        return v


class PrecompLayer(_LayerBase):
    """Reference to a pre-composition (a named ``Precomp`` defined at the
    timeline level). The precomp is rendered into its own RGBA canvas at
    each parent frame, then placed as a sprite on the parent timeline.
    The parent ``transform`` / ``animators`` apply to the WHOLE precomp
    as a single unit (rotate, scale, move groups of layers at once)."""

    type: Literal["precomp"]
    source: str = Field(
        min_length=1,
        description="Precomp id (key in ``Timeline.precomps``).",
    )
    width: float | None = Field(
        default=None,
        gt=0.0,
        description="Display width (px). Defaults to the precomp's native width.",
    )
    height: float | None = Field(
        default=None,
        gt=0.0,
        description="Display height (px). Defaults to the precomp's native height.",
    )
    time_offset: float = Field(
        default=0.0,
        description="Shift the precomp's internal clock (seconds). At parent "
        "time ``t``, the precomp is sampled at ``(t - start) + time_offset``.",
    )


Layer = Annotated[
    TextLayer
    | ShapeLayer
    | ImageLayer
    | NullLayer
    | PrecompLayer
    | ParticleEmitter
    | SpotlightLayer
    | PolylineLayer,
    Field(discriminator="type"),
]


# ── Precomp (nested composition) ─────────────────────────────────────────────


class Precomp(_StrictBase):
    """A named sub-composition rendered into its own RGBA canvas, then used
    as a sprite by ``PrecompLayer``. Layers inside a precomp can parent to
    each other but NOT to layers outside the precomp."""

    width: int = Field(default=1920, gt=0, le=8192)
    height: int = Field(default=1080, gt=0, le=8192)
    duration: float = Field(
        default=10.0,
        gt=0.0,
        description="Internal duration (seconds). When the parent samples "
        "beyond this, the precomp is held on its last visible frame.",
    )
    fps: int = Field(default=30, gt=0, le=120)
    layers: list[Layer] = Field(default_factory=list)

    @field_validator("layers")
    @classmethod
    def _validate_inner(cls, v: list[Any]) -> list[Any]:
        ids = [layer.id for layer in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Precomp layer ids must be unique within the precomp.")
        id_set = set(ids)
        for layer in v:
            if layer.parent and layer.parent not in id_set:
                raise ValueError(
                    f"Precomp layer '{layer.id}' has unknown parent "
                    f"'{layer.parent}' (parents must live in the same precomp)."
                )
        return v


# ── Timeline ─────────────────────────────────────────────────────────────────


class Camera3D(_StrictBase):
    """AE-style perspective camera (Phase 8).

    The camera is a pin-hole at ``position``. ``focal_length`` controls how
    strongly perspective compresses depth. With the default
    ``position = [960, 540, -1000]`` and ``focal_length = 1000``, a layer at
    ``position_z = 0`` is rendered identically to a 2D layer (scale 1, no
    parallax). Layers with smaller ``z`` appear closer (bigger); larger ``z``
    farther (smaller).
    """

    position: list[float] = Field(
        default_factory=lambda: [960.0, 540.0, -1000.0],
        description="[x, y, z] world position of the camera.",
    )
    focal_length: float = Field(
        default=1000.0,
        gt=0.0,
        description="Pin-hole focal length in pixels. Larger = flatter view.",
    )
    animate_position_x: list[Keyframe] | None = None
    animate_position_y: list[Keyframe] | None = None
    animate_position_z: list[Keyframe] | None = None
    animate_focal_length: list[Keyframe] | None = None

    @field_validator(
        "animate_position_x",
        "animate_position_y",
        "animate_position_z",
        "animate_focal_length",
    )
    @classmethod
    def _sorted_kfs(cls, v: list[Any] | None) -> list[Any] | None:
        if v is None:
            return v
        return sorted(v, key=lambda k: k.t)

    @field_validator("position")
    @classmethod
    def _len3(cls, v: list[float]) -> list[float]:
        if len(v) != 3:
            raise ValueError("Camera3D.position must be [x, y, z].")
        return v


class Timeline(_StrictBase):
    """An After-Effects-style overlay timeline composited on top of the
    captured browser video."""

    fps: int = Field(
        default=30,
        gt=0,
        le=120,
        description="Sampling rate for animator interpolation. Independent of "
        "the underlying video FPS (which is preserved by the compositor).",
    )
    layers: list[Layer] = Field(default_factory=list)
    camera_3d: Camera3D | None = Field(
        default=None,
        description="Optional perspective camera (Phase 8). When defined, "
        "layers with non-zero ``position_z`` are projected and z-sorted.",
    )
    precomps: dict[str, Precomp] = Field(
        default_factory=dict,
        description="Named pre-compositions referenceable by ``PrecompLayer``. "
        "Precomps may nest other precomps as long as there is no cycle.",
    )

    @field_validator("layers")
    @classmethod
    def _unique_ids(cls, v: list[Any]) -> list[Any]:
        ids = [layer.id for layer in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Layer ids must be unique within a timeline.")
        # Validate parent references and no cycles
        id_set = set(ids)
        for layer in v:
            if layer.parent and layer.parent not in id_set:
                raise ValueError(f"Layer '{layer.id}' has unknown parent '{layer.parent}'.")
        # Cycle detection
        parents = {layer.id: layer.parent for layer in v}
        for start_id in ids:
            seen: set[str] = set()
            cur: str | None = start_id
            while cur is not None:
                if cur in seen:
                    raise ValueError(f"Parent cycle detected involving layer '{cur}'.")
                seen.add(cur)
                cur = parents.get(cur)
        # Track-matte references must point to other existing layers
        for layer in v:
            if layer.track_matte is not None:
                if layer.track_matte.source == layer.id:
                    raise ValueError(f"Layer '{layer.id}' cannot use itself as track matte.")
                if layer.track_matte.source not in id_set:
                    raise ValueError(
                        f"Layer '{layer.id}' track_matte references unknown "
                        f"layer '{layer.track_matte.source}'."
                    )
        return v

    @model_validator(mode="after")
    def _validate_precomps(self) -> Timeline:
        precomp_ids = set(self.precomps)

        def _check_layer_refs(layers: list[Any], scope: str) -> None:
            for layer in layers:
                if getattr(layer, "type", None) == "precomp":
                    if layer.source not in precomp_ids:
                        raise ValueError(
                            f"{scope} layer '{layer.id}' references unknown "
                            f"precomp '{layer.source}'. Defined precomps: "
                            f"{sorted(precomp_ids) or '∅'}."
                        )

        _check_layer_refs(self.layers, "Top-level")
        for name, pc in self.precomps.items():
            _check_layer_refs(pc.layers, f"Precomp '{name}'")

        # Detect precomp cycles via DFS over precomp references.
        graph: dict[str, set[str]] = {
            name: {layer.source for layer in pc.layers if getattr(layer, "type", None) == "precomp"}
            for name, pc in self.precomps.items()
        }
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(graph, WHITE)

        def dfs(n: str) -> None:
            color[n] = GRAY
            for m in graph.get(n, ()):
                if color.get(m) == GRAY:
                    raise ValueError(f"Precomp reference cycle detected involving '{m}'.")
                if color.get(m) == WHITE:
                    dfs(m)
            color[n] = BLACK

        for n in graph:
            if color[n] == WHITE:
                dfs(n)
        return self
