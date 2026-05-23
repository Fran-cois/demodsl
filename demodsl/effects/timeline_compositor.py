"""Timeline compositor — bakes an After-Effects-style overlay timeline on top
of an existing video using Pillow + ffmpeg (no MoviePy dependency).

Frames are streamed in/out of ffmpeg via raw-video pipes; compositing happens
in Python with PIL. Audio from the source clip is muxed back in via a second
ffmpeg pass.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from demodsl.effects.expression import EvalEnv, ExpressionError, compile_expression
from demodsl.models.timeline import (
    Camera3D,
    Counter,
    DataBinding,
    DropShadow,
    ImageLayer,
    Keyframe,
    Layer,
    MotionBlur,
    NullLayer,
    ParticleEmitter,
    PolylineLayer,
    Precomp,
    PrecompLayer,
    PropertyTrack,
    ShapeLayer,
    SpotlightLayer,
    TextAnimator,
    TextLayer,
    Timeline,
    TimeRemap,
    Tracker,
    TrackPoint,
    Transform,
)

logger = logging.getLogger(__name__)


# ── Easing curves ────────────────────────────────────────────────────────────


def _ease(t: float, kind: str) -> float:
    """Apply an easing curve, ``t`` ∈ [0,1] → [0,1] (or slight overshoot)."""
    t = max(0.0, min(1.0, t))
    if kind == "linear":
        return t
    if kind == "hold":
        return 0.0
    if kind == "ease":
        # CSS "ease" approximation
        return 0.25 + 0.75 * (1 - (1 - t) ** 3) if t > 0.25 else 4 * t * t * t
    if kind == "ease-in":
        return t * t * t
    if kind == "ease-out":
        return 1 - (1 - t) ** 3
    if kind == "ease-in-out":
        return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2
    if kind == "spring":
        # Snappy spring with light overshoot (no real physics).
        if t == 0.0 or t == 1.0:
            return t
        c = 2 * math.pi / 0.6
        return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c) + 1
    return t


def _interp_scalar(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _apply_time_remap(remap: TimeRemap, t_out: float) -> float:
    """Piecewise-linear remap of layer-local output time → internal time.
    Values outside the first/last keyframe are clamped (freeze frames)."""
    kfs = remap.keyframes
    if t_out <= kfs[0][0]:
        return float(kfs[0][1])
    if t_out >= kfs[-1][0]:
        return float(kfs[-1][1])
    for i in range(len(kfs) - 1):
        a_out, a_in = kfs[i]
        b_out, b_in = kfs[i + 1]
        if a_out <= t_out <= b_out:
            span = b_out - a_out
            if span <= 0:
                return float(b_in)
            r = (t_out - a_out) / span
            return float(a_in) + (float(b_in) - float(a_in)) * r
    return float(kfs[-1][1])


def _interp_value(a: Any, b: Any, t: float) -> Any:
    if isinstance(a, list) and isinstance(b, list):
        return [_interp_scalar(x, y, t) for x, y in zip(a, b)]
    return _interp_scalar(float(a), float(b), t)


def sample_track(track: PropertyTrack, time: float) -> Any:
    """Sample a keyframed track at ``time`` (seconds, layer-local)."""
    kfs = track.keyframes
    if time <= kfs[0].t:
        return kfs[0].v
    if time >= kfs[-1].t:
        return kfs[-1].v
    for i in range(len(kfs) - 1):
        a, b = kfs[i], kfs[i + 1]
        if a.t <= time <= b.t:
            span = b.t - a.t
            if span <= 0:
                return b.v
            raw = (time - a.t) / span
            return _interp_value(a.v, b.v, _ease(raw, a.ease))
    return kfs[-1].v


def resolve_transform(
    layer: Layer,
    layer_time: float,
    *,
    abs_time: float = 0.0,
    duration: float = 0.0,
    fps: float = 30.0,
    parent_transform: Transform | None = None,
    compiled_exprs: dict[str, Any] | None = None,
) -> Transform:
    """Build the live Transform at ``layer_time`` (seconds since layer start)."""
    base = layer.transform.model_copy(deep=True)
    for track in layer.animators:
        v = sample_track(track, layer_time)
        _apply_property(base, track.property, v)
    # Expressions OVERRIDE keyframes for the same property.
    if compiled_exprs:
        env = EvalEnv(
            time=abs_time,
            layer_time=layer_time,
            duration=duration,
            fps=fps,
            parent_transform=parent_transform,
        )
        for prop, fn in compiled_exprs.items():
            try:
                v = fn(env)
            except Exception as exc:  # pragma: no cover - safety net
                logger.warning("expression on '%s.%s' failed: %s", layer.id, prop, exc)
                continue
            _apply_property(base, prop, v)
    # Compose parent transform: parent's translation/scale/rotation are applied
    # AROUND this layer. Phase 2 keeps it simple: additive position, multiplicative
    # scale, additive rotation, multiplicative opacity.
    if parent_transform is not None:
        base.position = [
            base.position[0] + (parent_transform.position[0] - 960.0),
            base.position[1] + (parent_transform.position[1] - 540.0),
        ]
        base.position_z = base.position_z + parent_transform.position_z
        base.scale = base.scale * parent_transform.scale
        base.rotation = base.rotation + parent_transform.rotation
        base.opacity = base.opacity * parent_transform.opacity
    # Phase 9: tracker overrides position (and optionally scale/rotation).
    if layer.tracker is not None:
        tx, ty, ts, tr = _sample_tracker(layer.tracker, abs_time)
        ox, oy = layer.tracker.offset
        base.position = [tx + ox, ty + oy]
        if layer.tracker.attach == "transform":
            if ts is not None:
                base.scale = ts
            if tr is not None:
                base.rotation = tr
    return base


def _sample_tracker(tracker: Tracker, t: float) -> tuple[float, float, float | None, float | None]:
    """Linearly interpolate a tracker's points at absolute time ``t``.

    Returns ``(x, y, scale_or_None, rotation_or_None)`` — scale and rotation
    are only filled when both bracketing points define them.
    """
    pts = tracker.points
    if t <= pts[0].t:
        return pts[0].x, pts[0].y, pts[0].scale, pts[0].rotation
    if t >= pts[-1].t:
        return pts[-1].x, pts[-1].y, pts[-1].scale, pts[-1].rotation
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if a.t <= t <= b.t:
            span = b.t - a.t
            u = 0.0 if span <= 0 else (t - a.t) / span
            x = a.x + (b.x - a.x) * u
            y = a.y + (b.y - a.y) * u
            s = (
                a.scale + (b.scale - a.scale) * u
                if (a.scale is not None and b.scale is not None)
                else None
            )
            r = (
                a.rotation + (b.rotation - a.rotation) * u
                if (a.rotation is not None and b.rotation is not None)
                else None
            )
            return x, y, s, r
    return pts[-1].x, pts[-1].y, pts[-1].scale, pts[-1].rotation


def _apply_property(base: Transform, prop: str, v: Any) -> None:
    if prop == "position" and isinstance(v, list) and len(v) >= 2:
        base.position = [float(v[0]), float(v[1])]
    elif prop == "position_x":
        base.position = [float(v), base.position[1]]
    elif prop == "position_y":
        base.position = [base.position[0], float(v)]
    elif prop == "position_z":
        base.position_z = float(v)
    elif prop == "scale":
        base.scale = max(1e-3, float(v))
    elif prop == "rotation":
        base.rotation = float(v)
    elif prop == "opacity":
        base.opacity = max(0.0, min(1.0, float(v)))


# ── Font resolution ──────────────────────────────────────────────────────────


def _font_candidates(family: str, weight: str) -> list[str]:
    is_bold = weight in ("bold", "black")
    # macOS / Linux common system fonts. Pillow accepts both file paths and
    # PostScript names on macOS when freetype is available.
    bold_suffix = "-Bold" if is_bold else "-Regular"
    return [
        # User-requested family first
        f"{family}{bold_suffix}.ttf",
        f"{family}.ttf",
        # Common inter-platform fallbacks
        "Inter-Bold.ttf" if is_bold else "Inter-Regular.ttf",
        "Helvetica.ttc",
        "Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def _load_font(family: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    for cand in _font_candidates(family, weight):
        try:
            return ImageFont.truetype(cand, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


# ── Per-layer rasterization ──────────────────────────────────────────────────


def _hex_to_rgba(hex_color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(255 * opacity)
        return r, g, b, a
    if len(h) == 8:
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
        return r, g, b, int(a * opacity)
    # Fallback: white
    return 255, 255, 255, int(255 * opacity)


def _render_text_sprite(layer: TextLayer) -> Image.Image:
    font = _load_font(layer.font_family, layer.font_weight, layer.font_size)
    # Measure
    dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), layer.content, font=font, stroke_width=layer.stroke_width or 0)
    w = max(1, bbox[2] - bbox[0])
    h = max(1, bbox[3] - bbox[1])
    pad = (layer.stroke_width or 0) + 4
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stroke_rgba = _hex_to_rgba(layer.stroke_color) if layer.stroke_color else None
    d.text(
        (pad - bbox[0], pad - bbox[1]),
        layer.content,
        font=font,
        fill=_hex_to_rgba(layer.color),
        stroke_width=layer.stroke_width or 0,
        stroke_fill=stroke_rgba,
    )
    return img


def _sample_kfs(kfs: list[Keyframe] | None, time: float, default: float) -> float:
    """Sample a bare list of keyframes (no PropertyTrack wrapper)."""
    if not kfs:
        return default
    if time <= kfs[0].t:
        return float(kfs[0].v)
    if time >= kfs[-1].t:
        return float(kfs[-1].v)
    for i in range(len(kfs) - 1):
        a, b = kfs[i], kfs[i + 1]
        if a.t <= time <= b.t:
            span = b.t - a.t
            if span <= 0:
                return float(b.v)
            raw = (time - a.t) / span
            return float(_interp_value(a.v, b.v, _ease(raw, a.ease)))
    return float(kfs[-1].v)


# ── Phase 8: 3D camera projection ────────────────────────────────────────────


@dataclass
class _CameraState:
    cx: float
    cy: float
    cz: float
    focal: float


def _eval_camera(cam: Camera3D, t: float) -> _CameraState:
    """Resolve camera position + focal length at absolute time ``t``."""
    cx = _sample_kfs(cam.animate_position_x, t, cam.position[0])
    cy = _sample_kfs(cam.animate_position_y, t, cam.position[1])
    cz = _sample_kfs(cam.animate_position_z, t, cam.position[2])
    focal = max(1.0, _sample_kfs(cam.animate_focal_length, t, cam.focal_length))
    return _CameraState(cx=cx, cy=cy, cz=cz, focal=focal)


def _project_transform(tr: Transform, cam: _CameraState) -> tuple[Transform, float]:
    """Project a resolved Transform through ``cam``. Returns (new_tr, depth).

    depth = layer_z - cam_z. If depth <= near-clip, opacity is zeroed.
    """
    near_clip = 1.0
    depth = float(tr.position_z) - cam.cz
    if depth <= near_clip:
        # Behind / on the camera plane → cull by zeroing opacity.
        out = tr.model_copy()
        out.opacity = 0.0
        return out, depth
    persp = cam.focal / depth
    new_x = cam.cx + (tr.position[0] - cam.cx) * persp
    new_y = cam.cy + (tr.position[1] - cam.cy) * persp
    out = tr.model_copy()
    out.position = [new_x, new_y]
    out.scale = tr.scale * persp
    return out, depth


def _render_animated_text_sprite(layer: TextLayer, layer_time: float) -> Image.Image:
    """Render text char-by-char, applying the per-character animator at
    ``layer_time`` (layer-local seconds). Returns a single RGBA sprite with
    enough padding to absorb per-char offsets/scales/rotations.
    """
    anim = layer.animator
    assert anim is not None  # caller guarantees this
    font = _load_font(layer.font_family, layer.font_weight, layer.font_size)
    chars = list(layer.content)
    n = len(chars)
    if n == 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    # Measure advances + per-char bbox
    advances: list[float] = []
    bboxes: list[tuple[int, int, int, int]] = []
    for c in chars:
        bb = font.getbbox(c)
        bboxes.append(bb)
        try:
            adv = float(font.getlength(c))
        except Exception:  # pragma: no cover — bitmap fonts
            adv = float(bb[2] - bb[0])
        advances.append(adv + anim.letter_spacing)
    total_w = sum(advances)

    # Generous padding so per-char offset_y / scale / rotation never clip.
    pad_x = max(layer.font_size * 2, 80)
    pad_y = max(layer.font_size * 2, 80)
    canvas_w = int(total_w + pad_x * 2)
    canvas_h = int(layer.font_size * 3 + pad_y * 2)
    out = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    baseline_y = pad_y + layer.font_size  # baseline of unscaled glyphs
    cursor_x = float(pad_x)
    stroke_rgba = _hex_to_rgba(layer.stroke_color) if layer.stroke_color else None
    fill_rgba = _hex_to_rgba(layer.color)

    for i, c in enumerate(chars):
        idx = (n - 1 - i) if anim.reverse_order else i
        char_t = layer_time - idx * anim.char_delay
        ox = _sample_kfs(anim.offset_x, char_t, 0.0)
        oy = _sample_kfs(anim.offset_y, char_t, 0.0)
        sc = _sample_kfs(anim.scale, char_t, 1.0)
        rot = _sample_kfs(anim.rotation, char_t, 0.0)
        op = max(0.0, min(1.0, _sample_kfs(anim.opacity, char_t, 1.0)))

        bb = bboxes[i]
        ch_w = max(1, bb[2] - bb[0])
        ch_h = max(1, bb[3] - bb[1])
        cpad = (layer.stroke_width or 0) + 4
        ci = Image.new("RGBA", (ch_w + cpad * 2, ch_h + cpad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(ci)
        d.text(
            (cpad - bb[0], cpad - bb[1]),
            c,
            font=font,
            fill=fill_rgba,
            stroke_width=layer.stroke_width or 0,
            stroke_fill=stroke_rgba,
        )

        # Apply per-char scale → rotation → opacity (about glyph centre).
        if abs(sc - 1.0) > 1e-3:
            sw = max(1, int(ci.width * sc))
            sh = max(1, int(ci.height * sc))
            ci = ci.resize((sw, sh), Image.LANCZOS)
        if abs(rot) > 1e-3:
            ci = ci.rotate(-rot, resample=Image.BICUBIC, expand=True)
        if op < 0.999:
            a = ci.split()[-1].point(lambda v: int(v * op))
            ci.putalpha(a)

        # Anchor the (possibly resized/rotated) tile at the glyph's centre,
        # which is itself at (cursor_x + ch_w/2, baseline_y - ch_h/2) in the
        # unanimated layout. Apply offset_x/y AFTER, in screen-space.
        anchor_cx = cursor_x + ch_w / 2.0 + ox
        anchor_cy = baseline_y - ch_h / 2.0 + oy
        px = int(anchor_cx - ci.width / 2.0)
        py = int(anchor_cy - ci.height / 2.0)
        out.alpha_composite(ci, (px, py))
        cursor_x += advances[i]

    return out


def _render_shape_sprite(layer: ShapeLayer) -> Image.Image:
    pad = int(layer.stroke_width) + 2
    w, h = int(layer.width) + pad * 2, int(layer.height) + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = _hex_to_rgba(layer.fill) if layer.fill else None
    stroke = _hex_to_rgba(layer.stroke) if layer.stroke else None
    sw = int(layer.stroke_width)
    box = (pad, pad, pad + int(layer.width), pad + int(layer.height))
    if layer.shape == "rectangle":
        if layer.corner_radius > 0:
            d.rounded_rectangle(
                box, radius=int(layer.corner_radius), fill=fill, outline=stroke, width=sw
            )
        else:
            d.rectangle(box, fill=fill, outline=stroke, width=sw)
    elif layer.shape == "ellipse":
        d.ellipse(box, fill=fill, outline=stroke, width=sw)
    return img


def _render_image_sprite(layer: ImageLayer, base_dir: Path) -> Image.Image:
    path = Path(layer.src)
    if not path.is_absolute():
        path = base_dir / path
    img = Image.open(path).convert("RGBA")
    if layer.width or layer.height:
        target_w = int(layer.width) if layer.width else img.width
        target_h = int(layer.height) if layer.height else img.height
        img = img.resize((target_w, target_h), Image.LANCZOS)
    return img


# ── SaaS B2B toolkit ─────────────────────────────────────────────────────────


def _render_counter_text_sprite(layer: TextLayer, layer_time: float) -> Image.Image:
    """Render a ``TextLayer`` whose ``content`` is overridden each frame by
    its ``counter`` (eased interpolation, formatted via ``counter.format``).
    """
    c = layer.counter
    assert c is not None
    elapsed = layer_time - c.start
    if elapsed <= 0.0:
        u = 0.0
    elif elapsed >= c.duration:
        u = 1.0
    else:
        u = _ease(elapsed / c.duration, c.ease)
    value = c.from_value + (c.to_value - c.from_value) * u
    try:
        rendered = c.format.format(value=value)
    except (KeyError, IndexError, ValueError):
        rendered = str(value)
    # Render with the same code path as the static text sprite.
    mutated = layer.model_copy(update={"content": rendered, "counter": None})
    return _render_text_sprite(mutated)


def _render_drop_shadow(
    sp: Image.Image,
    x: int,
    y: int,
    ds: DropShadow,
) -> tuple[Image.Image, int, int]:
    """Build a shadow tile from the sprite's alpha and return ``(img, x, y)``.

    The returned tile is sized to accommodate the spread + blur radius so the
    shadow doesn't clip. Caller composites it at the returned coordinates
    using a ``normal`` blend BEFORE drawing the sprite itself.
    """
    pad = int(math.ceil(ds.blur + ds.spread)) + 2
    w, h = sp.width + pad * 2, sp.height + pad * 2
    silhouette = Image.new("L", (w, h), 0)
    silhouette.paste(sp.split()[-1], (pad, pad))
    # Dilate by spread (CSS-style) using a MaxFilter — odd-size only.
    if ds.spread > 0:
        s = max(1, int(round(ds.spread)) * 2 + 1)
        silhouette = silhouette.filter(ImageFilter.MaxFilter(s))
    if ds.blur > 0:
        silhouette = silhouette.filter(ImageFilter.GaussianBlur(ds.blur))
    # Multiply by opacity.
    if ds.opacity < 0.999:
        silhouette = silhouette.point(lambda v: int(v * ds.opacity))
    # Tint: solid colour where silhouette > 0.
    r, g, b, _ = _hex_to_rgba(ds.color)
    tile = Image.new("RGBA", (w, h), (r, g, b, 0))
    tile.putalpha(silhouette)
    return tile, x - pad + int(ds.offset_x), y - pad + int(ds.offset_y)


def _polyline_lengths(pts: list[list[float]], closed: bool) -> tuple[list[float], float]:
    """Return per-segment lengths and the total perimeter."""
    lens: list[float] = []
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        lens.append(math.hypot(dx, dy))
    if closed and len(pts) >= 2:
        dx = pts[0][0] - pts[-1][0]
        dy = pts[0][1] - pts[-1][1]
        lens.append(math.hypot(dx, dy))
    return lens, sum(lens) or 1e-6


def _draw_trimmed_polyline(
    draw: ImageDraw.ImageDraw,
    pts: list[list[float]],
    closed: bool,
    color: tuple[int, int, int, int],
    width: float,
    t0: float,
    t1: float,
    line_cap: str,
) -> None:
    """Paint segments of the polyline corresponding to arc-length [t0, t1]
    (both in 0..1). Round caps are emulated with circles at endpoints."""
    if t1 <= t0:
        return
    lens, total = _polyline_lengths(pts, closed)
    a = max(0.0, t0) * total
    b = min(1.0, t1) * total
    n_pts = len(pts) + (1 if closed else 0)
    cum = 0.0
    w = max(1, int(round(width)))
    r = width / 2.0
    for i in range(len(lens)):
        seg_len = lens[i]
        s0, s1 = cum, cum + seg_len
        cum = s1
        if s1 <= a or s0 >= b or seg_len <= 1e-6:
            continue
        p_a = pts[i]
        p_b = pts[(i + 1) % n_pts] if (closed and i == len(pts) - 1) else pts[i + 1]
        local_a = max(0.0, (a - s0) / seg_len)
        local_b = min(1.0, (b - s0) / seg_len)
        x0 = p_a[0] + (p_b[0] - p_a[0]) * local_a
        y0 = p_a[1] + (p_b[1] - p_a[1]) * local_a
        x1 = p_a[0] + (p_b[0] - p_a[0]) * local_b
        y1 = p_a[1] + (p_b[1] - p_a[1]) * local_b
        draw.line([(x0, y0), (x1, y1)], fill=color, width=w)
        if line_cap == "round":
            for cx, cy in ((x0, y0), (x1, y1)):
                draw.ellipse(
                    [cx - r, cy - r, cx + r, cy + r],
                    fill=color,
                )


def _render_polyline_sprite(
    layer: PolylineLayer,
    layer_time: float,
    canvas_size: tuple[int, int],
) -> Image.Image:
    """Render the polyline at ``layer_time`` into a canvas-sized RGBA tile.

    Trim values are sampled from the keyframe lists (falling back to the
    static fields). The sprite is canvas-aligned — the caller composites it
    at (0, 0) ignoring ``transform.position``.
    """
    t_start = _sample_kfs(layer.trim_start_kfs, layer_time, layer.trim_start)
    t_end = _sample_kfs(layer.trim_end_kfs, layer_time, layer.trim_end)
    t_start = max(0.0, min(1.0, t_start))
    t_end = max(0.0, min(1.0, t_end))
    if t_end < t_start:
        t_start, t_end = t_end, t_start
    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if t_end - t_start <= 1e-6:
        return img
    draw = ImageDraw.Draw(img)
    pts = layer.points
    # Optional area fill (under the visible portion). Renders ONCE, ignoring
    # trim — fills under the full chart for simplicity. Render before stroke.
    if layer.fill and layer.fill_baseline_y is not None and t_end >= 0.999:
        poly = [(p[0], p[1]) for p in pts]
        poly.append((pts[-1][0], float(layer.fill_baseline_y)))
        poly.append((pts[0][0], float(layer.fill_baseline_y)))
        draw.polygon(poly, fill=_hex_to_rgba(layer.fill))
    color = _hex_to_rgba(layer.stroke)
    _draw_trimmed_polyline(
        draw,
        pts,
        layer.closed,
        color,
        layer.stroke_width,
        t_start,
        t_end,
        layer.line_cap,
    )
    return img


def _apply_spotlight(
    canvas: Image.Image,
    layer: SpotlightLayer,
    tr: Transform,
) -> Image.Image:
    """Replace ``canvas`` with a blurred + darkened copy of itself, except
    inside a soft-feathered cut-out centred on ``tr.position``."""
    cw, ch = canvas.size
    cx, cy = tr.position
    w = layer.width * max(0.01, tr.scale)
    h = layer.height * max(0.01, tr.scale)
    box = (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
    mask = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(mask)
    if layer.shape == "ellipse":
        d.ellipse(box, fill=255)
    else:
        if layer.corner_radius > 0:
            d.rounded_rectangle(
                box,
                radius=layer.corner_radius,
                fill=255,
            )
        else:
            d.rectangle(box, fill=255)
    if layer.feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(layer.feather))
    bg = canvas
    if layer.blur > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(layer.blur))
    if layer.darken > 0:
        bg_arr = np.asarray(bg, dtype=np.float32)
        bg_arr[..., :3] *= 1.0 - layer.darken
        bg = Image.fromarray(np.clip(bg_arr, 0, 255).astype(np.uint8), "RGBA")
    # Apply layer opacity to dim the whole effect (mix between original
    # canvas and the spotlit canvas).
    spotlit = Image.composite(canvas, bg, mask)
    if tr.opacity < 0.999:
        spotlit = Image.blend(canvas, spotlit, tr.opacity)
    return spotlit


# ── Particle simulation ──────────────────────────────────────────────────────


@dataclass
class _Particle:
    birth_t: float
    life: float
    x0: float
    y0: float
    vx: float
    vy: float
    size: float
    rot0: float
    rot_speed: float
    color_phase: float  # 0..1, used to pick per-particle hue variance


def _build_particles(em: ParticleEmitter, layer_duration: float) -> list[_Particle]:
    """Pre-compute the full particle list for an emitter, deterministically
    from ``em.seed``. Each particle has a birth time, lifetime and initial
    state — frame rendering just samples each particle's analytic trajectory.
    """
    rng = random.Random(em.seed)
    emit_dur = em.emit_duration if em.emit_duration is not None else layer_duration
    emit_dur = max(0.0, min(emit_dur, layer_duration))
    n_total = max(1, int(em.rate * emit_dur))
    parts: list[_Particle] = []
    for i in range(n_total):
        birth = (i + rng.random()) / em.rate
        if birth >= emit_dur:
            break
        life = rng.uniform(*em.lifetime)
        # Spawn offset within emitter shape
        if em.emitter_shape == "circle":
            r = math.sqrt(rng.random()) * (em.emitter_width / 2.0)
            theta = rng.uniform(0.0, 2.0 * math.pi)
            ox, oy = r * math.cos(theta), r * math.sin(theta)
        elif em.emitter_shape == "rectangle":
            ox = rng.uniform(-em.emitter_width / 2.0, em.emitter_width / 2.0)
            oy = rng.uniform(-em.emitter_height / 2.0, em.emitter_height / 2.0)
        else:  # point
            ox = oy = 0.0
        # Velocity (direction ± spread, speed range)
        ang_deg = em.direction + rng.uniform(-em.spread, em.spread)
        ang = math.radians(ang_deg)
        spd = rng.uniform(*em.speed)
        vx = math.cos(ang) * spd
        vy = math.sin(ang) * spd
        size = rng.uniform(*em.particle_size)
        rot0 = rng.uniform(0.0, 360.0)
        rot_spd = rng.uniform(*em.rotation_speed)
        parts.append(
            _Particle(
                birth_t=birth,
                life=life,
                x0=ox,
                y0=oy,
                vx=vx,
                vy=vy,
                size=size,
                rot0=rot0,
                rot_speed=rot_spd,
                color_phase=rng.random(),
            )
        )
    return parts


def _lerp_color(
    c0: tuple[int, int, int, int],
    c1: tuple[int, int, int, int],
    u: float,
) -> tuple[int, int, int, int]:
    u = max(0.0, min(1.0, u))
    return (
        int(c0[0] + (c1[0] - c0[0]) * u),
        int(c0[1] + (c1[1] - c0[1]) * u),
        int(c0[2] + (c1[2] - c0[2]) * u),
        int(c0[3] + (c1[3] - c0[3]) * u),
    )


def _draw_particle_shape(
    draw: ImageDraw.ImageDraw,
    shape: str,
    cx: float,
    cy: float,
    size: float,
    rotation: float,
    color: tuple[int, int, int, int],
) -> None:
    """Draw one particle directly onto ``draw``'s surface. ``size`` is the
    diameter / side length. Rotation only affects square/star."""
    half = size / 2.0
    if shape == "circle":
        draw.ellipse(
            (cx - half, cy - half, cx + half, cy + half),
            fill=color,
        )
        return
    if shape == "square":
        # Rotate 4 corners about (cx, cy).
        c = math.cos(math.radians(rotation))
        s = math.sin(math.radians(rotation))
        pts = []
        for dx, dy in ((-half, -half), (half, -half), (half, half), (-half, half)):
            pts.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
        draw.polygon(pts, fill=color)
        return
    if shape == "star":
        # 5-pointed star
        pts = []
        for i in range(10):
            ang = math.radians(rotation - 90.0 + i * 36.0)
            r = half if (i % 2 == 0) else half * 0.45
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        draw.polygon(pts, fill=color)


def _render_particles_frame(
    em: ParticleEmitter,
    parts: list[_Particle],
    origin_xy: tuple[float, float],
    layer_time: float,
    canvas_size: tuple[int, int],
) -> Image.Image:
    """Build a canvas-sized RGBA frame containing all currently-alive
    particles for ``em`` at ``layer_time`` (seconds, layer-local).
    """
    cw, ch = canvas_size
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ox, oy = origin_xy
    gx, gy = em.gravity
    c_start = _hex_to_rgba(em.color_start)
    c_end = _hex_to_rgba(em.color_end) if em.color_end else c_start

    for p in parts:
        age = layer_time - p.birth_t
        if age < 0.0 or age >= p.life:
            continue
        u = age / p.life  # 0..1
        # Analytic position with gravity
        x = ox + p.x0 + p.vx * age + 0.5 * gx * age * age
        y = oy + p.y0 + p.vy * age + 0.5 * gy * age * age
        if x < -200 or x > cw + 200 or y < -200 or y > ch + 200:
            continue
        size = p.size * (1.0 + (em.scale_end - 1.0) * u)
        if size < 0.5:
            continue
        opacity = em.opacity_start + (em.opacity_end - em.opacity_start) * u
        opacity = max(0.0, min(1.0, opacity))
        if opacity <= 0.005:
            continue
        col = _lerp_color(c_start, c_end, u)
        col = (col[0], col[1], col[2], int(col[3] * opacity))
        rot = p.rot0 + p.rot_speed * age
        _draw_particle_shape(
            draw,
            em.particle_shape,
            x,
            y,
            size,
            rot,
            col,
        )
    return img


def _render_sprite(layer: Layer, base_dir: Path) -> Image.Image | None:
    if isinstance(layer, TextLayer):
        if layer.animator is not None or layer.counter is not None:
            # Animated text & counters are built per-frame inside _compose_frame.
            return None
        sp = _render_text_sprite(layer)
    elif isinstance(layer, ShapeLayer):
        sp = _render_shape_sprite(layer)
    elif isinstance(layer, ImageLayer):
        sp = _render_image_sprite(layer, base_dir)
    elif isinstance(layer, NullLayer):
        return None
    elif isinstance(layer, PrecompLayer):
        # PrecompLayer sprites are rendered per-frame inside _compose_frame.
        return None
    elif isinstance(layer, ParticleEmitter):
        # Particles are simulated per-frame inside _compose_frame.
        return None
    elif isinstance(layer, SpotlightLayer):
        # Spotlights mutate the base canvas, no overlay sprite.
        return None
    elif isinstance(layer, PolylineLayer):
        # Polylines are rendered per-frame (trim animation).
        return None
    else:
        raise TypeError(f"Unknown layer type: {type(layer).__name__}")
    if layer.masks:
        sp = _apply_masks(sp, layer.masks)
    return sp


# ── Masks ────────────────────────────────────────────────────────────────────


def _apply_masks(sprite: Image.Image, masks: list[Any]) -> Image.Image:
    """Combine masks and multiply with the sprite's alpha channel."""
    w, h = sprite.size
    combined = Image.new("L", (w, h), 0)
    for m in masks:
        layer_mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(layer_mask)
        x0 = int(m.bounds[0] * w)
        y0 = int(m.bounds[1] * h)
        x1 = int(m.bounds[2] * w)
        y1 = int(m.bounds[3] * h)
        if x1 <= x0 or y1 <= y0:
            continue
        if m.shape == "rectangle":
            d.rectangle([x0, y0, x1, y1], fill=255)
        else:  # ellipse
            d.ellipse([x0, y0, x1, y1], fill=255)
        if m.feather > 0:
            layer_mask = layer_mask.filter(ImageFilter.GaussianBlur(m.feather))
        if m.inverted:
            layer_mask = Image.eval(layer_mask, lambda v: 255 - v)
        if m.mode == "add":
            combined = ImageChops.lighter(combined, layer_mask)
        elif m.mode == "subtract":
            combined = ImageChops.subtract(combined, layer_mask)
        elif m.mode == "intersect":
            combined = ImageChops.multiply(combined, layer_mask)
    # Multiply with existing alpha
    src_alpha = sprite.split()[-1]
    new_alpha = ImageChops.multiply(src_alpha, combined)
    out = sprite.copy()
    out.putalpha(new_alpha)
    return out


# ── Blend modes ──────────────────────────────────────────────────────────────


def _blend(base: Image.Image, top: Image.Image, x: int, y: int, mode: str) -> None:
    """Composite ``top`` onto ``base`` at (x, y) using the given blend mode.
    Mutates ``base`` in place."""
    if mode == "normal":
        base.alpha_composite(top, (x, y))
        return
    # Crop the region of base under top
    tw, th = top.size
    bw, bh = base.size
    if x >= bw or y >= bh or x + tw <= 0 or y + th <= 0:
        return
    # Clamp
    sx = max(0, -x)
    sy = max(0, -y)
    dx = max(0, x)
    dy = max(0, y)
    cw = min(tw - sx, bw - dx)
    ch = min(th - sy, bh - dy)
    if cw <= 0 or ch <= 0:
        return
    top_crop = top.crop((sx, sy, sx + cw, sy + ch))
    base_crop = base.crop((dx, dy, dx + cw, dy + ch))
    blended = _blend_pixels(base_crop, top_crop, mode)
    base.paste(blended, (dx, dy))


def _blend_pixels(base: Image.Image, top: Image.Image, mode: str) -> Image.Image:
    """Blend ``top`` over ``base`` (same size) using ``mode``. Honours top's
    alpha as a per-pixel mix factor."""
    import numpy as np

    b = np.asarray(base.convert("RGBA"), dtype=np.float32) / 255.0
    t = np.asarray(top.convert("RGBA"), dtype=np.float32) / 255.0
    br, bg, bb, ba = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    tr, tg, tb, ta = t[..., 0], t[..., 1], t[..., 2], t[..., 3]

    if mode == "multiply":
        rr, rg, rb_ = br * tr, bg * tg, bb * tb
    elif mode == "screen":
        rr = 1 - (1 - br) * (1 - tr)
        rg = 1 - (1 - bg) * (1 - tg)
        rb_ = 1 - (1 - bb) * (1 - tb)
    elif mode == "overlay":

        def _ov(a, c):
            return np.where(a < 0.5, 2 * a * c, 1 - 2 * (1 - a) * (1 - c))

        rr, rg, rb_ = _ov(br, tr), _ov(bg, tg), _ov(bb, tb)
    elif mode == "add":
        rr = np.clip(br + tr, 0, 1)
        rg = np.clip(bg + tg, 0, 1)
        rb_ = np.clip(bb + tb, 0, 1)
    elif mode == "subtract":
        rr = np.clip(br - tr, 0, 1)
        rg = np.clip(bg - tg, 0, 1)
        rb_ = np.clip(bb - tb, 0, 1)
    elif mode == "darken":
        rr = np.minimum(br, tr)
        rg = np.minimum(bg, tg)
        rb_ = np.minimum(bb, tb)
    elif mode == "lighten":
        rr = np.maximum(br, tr)
        rg = np.maximum(bg, tg)
        rb_ = np.maximum(bb, tb)
    elif mode == "difference":
        rr = np.abs(br - tr)
        rg = np.abs(bg - tg)
        rb_ = np.abs(bb - tb)
    elif mode == "color-dodge":
        rr = np.where(tr >= 1, 1, np.clip(br / np.maximum(1 - tr, 1e-6), 0, 1))
        rg = np.where(tg >= 1, 1, np.clip(bg / np.maximum(1 - tg, 1e-6), 0, 1))
        rb_ = np.where(tb >= 1, 1, np.clip(bb / np.maximum(1 - tb, 1e-6), 0, 1))
    elif mode == "color-burn":
        rr = np.where(tr <= 0, 0, 1 - np.clip((1 - br) / np.maximum(tr, 1e-6), 0, 1))
        rg = np.where(tg <= 0, 0, 1 - np.clip((1 - bg) / np.maximum(tg, 1e-6), 0, 1))
        rb_ = np.where(tb <= 0, 0, 1 - np.clip((1 - bb) / np.maximum(tb, 1e-6), 0, 1))
    else:
        return base

    # Mix with alpha: out = mix(base, blend_result, top.alpha)
    out_r = br * (1 - ta) + rr * ta
    out_g = bg * (1 - ta) + rg * ta
    out_b = bb * (1 - ta) + rb_ * ta
    out_a = ba + ta * (1 - ba)
    out = np.stack([out_r, out_g, out_b, np.clip(out_a, 0, 1)], axis=-1)
    out = (out * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# ── Compositing per-frame ────────────────────────────────────────────────────


def _is_active(layer: Layer, t: float) -> bool:
    if t < layer.start:
        return False
    if layer.duration is not None and t > layer.start + layer.duration:
        return False
    return True


def _compose_frame(
    base_frame: Image.Image,
    layers: list[Layer],
    sprites: dict[str, Image.Image | None],
    compiled: dict[str, dict[str, Any]],
    by_id: dict[str, Layer],
    t: float,
    *,
    duration: float,
    fps: float,
    matte_sources: set[str],
    precomp_renders: dict[str, _PrecompRender] | None = None,
    particle_systems: dict[str, list[_Particle]] | None = None,
    camera_3d: Camera3D | None = None,
) -> Image.Image:
    canvas = base_frame.convert("RGBA")
    precomp_renders = precomp_renders or {}
    particle_systems = particle_systems or {}
    cam_state = _eval_camera(camera_3d, t) if camera_3d is not None else None
    # First pass: resolve transforms (including parent chains) for ALL layers.
    transforms: dict[str, Transform] = {}
    depths: dict[str, float] = {}

    def resolve(layer_id: str) -> Transform:
        if layer_id in transforms:
            return transforms[layer_id]
        layer = by_id[layer_id]
        parent_t = resolve(layer.parent) if layer.parent else None
        layer_dur = layer.duration if layer.duration is not None else duration
        layer_time = t - layer.start
        if layer.time_remap is not None:
            layer_time = _apply_time_remap(layer.time_remap, layer_time)
        tr = resolve_transform(
            layer,
            layer_time,
            abs_time=t,
            duration=layer_dur,
            fps=fps,
            parent_transform=parent_t,
            compiled_exprs=compiled.get(layer.id),
        )
        transforms[layer_id] = tr
        return tr

    for layer in layers:
        resolve(layer.id)

    # Phase 8: project all transforms through the camera, and build a
    # back-to-front render order based on depth.
    render_layers: list[Layer] = list(layers)
    if cam_state is not None:
        for lid, tr in list(transforms.items()):
            proj, d = _project_transform(tr, cam_state)
            transforms[lid] = proj
            depths[lid] = d
        # Stable sort: deeper layers (farther) first; preserve YAML order on ties.
        order_index = {lid: i for i, lid in enumerate(by_id)}
        render_layers = sorted(
            layers,
            key=lambda L: (-depths.get(L.id, 0.0), order_index.get(L.id, 0)),
        )

    # Cache of placed sprites (sprite + top-left position) so track-mattes can
    # reuse the matte source's transformed sprite without re-rendering.
    placed_cache: dict[str, tuple[Image.Image, int, int]] = {}

    def place_sprite(layer: Layer) -> tuple[Image.Image, int, int] | None:
        if layer.id in placed_cache:
            return placed_cache[layer.id]
        # Resolve the sprite — static for most layers, dynamic for precomps.
        if isinstance(layer, PrecompLayer):
            pr = precomp_renders.get(layer.source)
            if pr is None:
                return None
            raw_local = t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            t_local = raw_local + layer.time_offset
            sprite = _render_precomp_frame(pr, t_local)
            # Resize to the layer's display size if overridden.
            disp_w = int(layer.width) if layer.width else pr.width
            disp_h = int(layer.height) if layer.height else pr.height
            if (disp_w, disp_h) != sprite.size:
                sprite = sprite.resize((disp_w, disp_h), Image.LANCZOS)
        elif isinstance(layer, TextLayer) and layer.animator is not None:
            raw_local = t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            sprite = _render_animated_text_sprite(layer, raw_local)
            if layer.masks:
                sprite = _apply_masks(sprite, layer.masks)
        elif isinstance(layer, TextLayer) and layer.counter is not None:
            raw_local = t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            sprite = _render_counter_text_sprite(layer, raw_local)
            if layer.masks:
                sprite = _apply_masks(sprite, layer.masks)
        else:
            sprite = sprites.get(layer.id)
            if sprite is None:
                return None
        tr = transforms[layer.id]
        if tr.opacity <= 0.001:
            return None
        if abs(tr.scale - 1.0) > 1e-3:
            sw = max(1, int(sprite.width * tr.scale))
            sh = max(1, int(sprite.height * tr.scale))
            sp = sprite.resize((sw, sh), Image.LANCZOS)
        else:
            sp = sprite.copy()
        if abs(tr.rotation) > 1e-3:
            sp = sp.rotate(-tr.rotation, resample=Image.BICUBIC, expand=True)
        if tr.opacity < 0.999:
            alpha = sp.split()[-1].point(lambda a: int(a * tr.opacity))
            sp.putalpha(alpha)
        ax, ay = layer.transform.anchor
        x = int(tr.position[0] - sp.width * ax)
        y = int(tr.position[1] - sp.height * ay)
        placed_cache[layer.id] = (sp, x, y)
        return placed_cache[layer.id]

    # ── Motion-blur helper: render `layer` at arbitrary output time ──────
    def _resolve_transform_at(layer_id: str, sub_t: float) -> Transform:
        l = by_id[layer_id]
        parent_t = _resolve_transform_at(l.parent, sub_t) if l.parent else None
        layer_dur = l.duration if l.duration is not None else duration
        layer_time = sub_t - l.start
        if l.time_remap is not None:
            layer_time = _apply_time_remap(l.time_remap, layer_time)
        tr = resolve_transform(
            l,
            layer_time,
            abs_time=sub_t,
            duration=layer_dur,
            fps=fps,
            parent_transform=parent_t,
            compiled_exprs=compiled.get(l.id),
        )
        if camera_3d is not None:
            sub_cam = _eval_camera(camera_3d, sub_t)
            tr, _ = _project_transform(tr, sub_cam)
        return tr

    def _render_layer_at(layer: Layer, sub_t: float) -> tuple[Image.Image, int, int] | None:
        """Build the sprite tile (sp, x, y) for ``layer`` at ``sub_t`` — no
        caching, parent chain re-resolved. Used by motion-blur sampling."""
        if isinstance(layer, PrecompLayer):
            pr = precomp_renders.get(layer.source)
            if pr is None:
                return None
            raw_local = sub_t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            t_local = raw_local + layer.time_offset
            sprite = _render_precomp_frame(pr, t_local)
            disp_w = int(layer.width) if layer.width else pr.width
            disp_h = int(layer.height) if layer.height else pr.height
            if (disp_w, disp_h) != sprite.size:
                sprite = sprite.resize((disp_w, disp_h), Image.LANCZOS)
        elif isinstance(layer, TextLayer) and layer.animator is not None:
            raw_local = sub_t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            sprite = _render_animated_text_sprite(layer, raw_local)
            if layer.masks:
                sprite = _apply_masks(sprite, layer.masks)
        elif isinstance(layer, TextLayer) and layer.counter is not None:
            raw_local = sub_t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            sprite = _render_counter_text_sprite(layer, raw_local)
            if layer.masks:
                sprite = _apply_masks(sprite, layer.masks)
        else:
            sprite = sprites.get(layer.id)
            if sprite is None:
                return None
        tr = _resolve_transform_at(layer.id, sub_t)
        if tr.opacity <= 0.001:
            return None
        if abs(tr.scale - 1.0) > 1e-3:
            sw = max(1, int(sprite.width * tr.scale))
            sh = max(1, int(sprite.height * tr.scale))
            sp = sprite.resize((sw, sh), Image.LANCZOS)
        else:
            sp = sprite.copy()
        if abs(tr.rotation) > 1e-3:
            sp = sp.rotate(-tr.rotation, resample=Image.BICUBIC, expand=True)
        if tr.opacity < 0.999:
            alpha = sp.split()[-1].point(lambda a: int(a * tr.opacity))
            sp.putalpha(alpha)
        ax, ay = layer.transform.anchor
        x = int(tr.position[0] - sp.width * ax)
        y = int(tr.position[1] - sp.height * ay)
        return sp, x, y

    def _render_motion_blurred(layer: Layer, mb: MotionBlur) -> Image.Image | None:
        """Average N sub-samples across the shutter window → canvas-sized RGBA."""
        n = mb.samples
        shutter_s = (mb.shutter_angle / 360.0) / max(fps, 1e-3)
        cw, ch = canvas.size
        acc = np.zeros((ch, cw, 4), dtype=np.float32)
        contributed = 0
        for i in range(n):
            # Centre window on `t`. With angle=180 → samples span half a frame.
            sub_t = t + ((i + 0.5) / n - 0.5) * shutter_s
            placed = _render_layer_at(layer, sub_t)
            if placed is None:
                continue
            sp, x, y = placed
            tile = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            tile.paste(sp, (x, y), sp)
            acc += np.asarray(tile, dtype=np.float32)
            contributed += 1
        if contributed == 0:
            return None
        acc /= n  # divide by total samples (not just contributors) → correct partial visibility
        return Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGBA")

    for layer in render_layers:
        if not _is_active(layer, t):
            continue
        if layer.id in matte_sources:
            # Source used as matte for another layer → don't render visually.
            place_sprite(layer)  # still cache it for matte usage
            continue
        if isinstance(layer, SpotlightLayer):
            tr = transforms[layer.id]
            canvas = _apply_spotlight(canvas, layer, tr)
            continue
        if isinstance(layer, PolylineLayer):
            tr = transforms[layer.id]
            if tr.opacity <= 0.001:
                continue
            raw_local = t - layer.start
            if layer.time_remap is not None:
                raw_local = _apply_time_remap(layer.time_remap, raw_local)
            poly_img = _render_polyline_sprite(layer, raw_local, canvas.size)
            if tr.opacity < 0.999:
                alpha = poly_img.split()[-1].point(
                    lambda v: int(v * max(0.0, min(1.0, tr.opacity)))
                )
                poly_img.putalpha(alpha)
            if layer.drop_shadow is not None:
                shadow_tile, sx, sy = _render_drop_shadow(
                    poly_img,
                    0,
                    0,
                    layer.drop_shadow,
                )
                _blend(canvas, shadow_tile, sx, sy, "normal")
            _blend(canvas, poly_img, 0, 0, layer.blend_mode)
            continue
        if isinstance(layer, ParticleEmitter):
            parts = particle_systems.get(layer.id)
            if not parts:
                continue
            # Emitter origin = resolved transform position (parenting works).
            tr = transforms[layer.id]
            origin = (float(tr.position[0]), float(tr.position[1]))
            layer_t = t - layer.start
            if layer.time_remap is not None:
                layer_t = _apply_time_remap(layer.time_remap, layer_t)
            particles_img = _render_particles_frame(
                layer,
                parts,
                origin,
                layer_t,
                canvas.size,
            )
            if tr.opacity < 0.999:
                alpha = particles_img.split()[-1].point(
                    lambda v: int(v * max(0.0, min(1.0, tr.opacity)))
                )
                particles_img.putalpha(alpha)
            _blend(canvas, particles_img, 0, 0, layer.blend_mode)
            continue
        if layer.motion_blur is not None and not isinstance(layer, NullLayer):
            blurred = _render_motion_blurred(layer, layer.motion_blur)
            if blurred is not None:
                if layer.drop_shadow is not None:
                    shadow_tile, sx, sy = _render_drop_shadow(
                        blurred,
                        0,
                        0,
                        layer.drop_shadow,
                    )
                    _blend(canvas, shadow_tile, sx, sy, "normal")
                _blend(canvas, blurred, 0, 0, layer.blend_mode)
            continue
        placed = place_sprite(layer)
        if placed is None:
            continue
        sp, x, y = placed
        # Apply track matte: combine our alpha with the matte source.
        if layer.track_matte is not None:
            src_placed = place_sprite(by_id[layer.track_matte.source])
            if src_placed is not None:
                sp = _apply_track_matte(sp, x, y, src_placed, layer.track_matte.mode)
        if layer.drop_shadow is not None:
            shadow_tile, sx, sy = _render_drop_shadow(
                sp,
                x,
                y,
                layer.drop_shadow,
            )
            _blend(canvas, shadow_tile, sx, sy, "normal")
        _blend(canvas, sp, x, y, layer.blend_mode)
    return canvas


def _apply_track_matte(
    sprite: Image.Image,
    x: int,
    y: int,
    matte_placed: tuple[Image.Image, int, int],
    mode: str,
) -> Image.Image:
    """Multiply ``sprite``'s alpha by the matte source's alpha (or luma)
    aligned to the canvas. ``mode`` is one of ``alpha``, ``alpha-inverted``,
    ``luma``, ``luma-inverted``."""
    matte_img, mx, my = matte_placed
    w, h = sprite.size
    # Build a mask in canvas-aligned coordinates, then crop to the sprite rect.
    matte_full = Image.new("L", (w, h), 0)
    # Compute overlap between matte (placed at mx,my of size matte_img.size)
    # and sprite (placed at x,y of size w,h).
    ox0 = max(x, mx)
    oy0 = max(y, my)
    ox1 = min(x + w, mx + matte_img.width)
    oy1 = min(y + h, my + matte_img.height)
    if ox0 < ox1 and oy0 < oy1:
        if mode.startswith("alpha"):
            src = matte_img.split()[-1]
        else:  # luma
            src = matte_img.convert("L")
        crop = src.crop((ox0 - mx, oy0 - my, ox1 - mx, oy1 - my))
        if mode.endswith("inverted"):
            crop = Image.eval(crop, lambda v: 255 - v)
        matte_full.paste(crop, (ox0 - x, oy0 - y))
    else:
        # No overlap: result fully masked out (unless inverted → fully kept).
        if mode.endswith("inverted"):
            matte_full = Image.new("L", (w, h), 255)
    out = sprite.copy()
    new_alpha = ImageChops.multiply(sprite.split()[-1], matte_full)
    out.putalpha(new_alpha)
    return out


# ── Pre-compositions (nested timelines) ──────────────────────────────────────


class _PrecompRender:
    """Mutable state used to render a precomp's frames on demand.

    A precomp is a self-contained sub-composition (layers + their static
    sprites + compiled expressions + matte sources + size + fps + duration).
    Sibling precomps share the same ``_PrecompRender`` mapping so a precomp
    can reference another precomp recursively.
    """

    __slots__ = (
        "name",
        "width",
        "height",
        "fps",
        "duration",
        "layers",
        "sprites",
        "compiled",
        "by_id",
        "matte_sources",
        "frame_cache",
        "particle_systems",
        "_global_renders",
    )

    def __init__(
        self,
        name: str,
        precomp: Precomp,
        base_dir: Path,
    ) -> None:
        self.name = name
        self.width = precomp.width
        self.height = precomp.height
        self.fps = precomp.fps
        self.duration = precomp.duration
        self.layers: list[Layer] = list(precomp.layers)
        self.sprites: dict[str, Image.Image | None] = {
            layer.id: _render_sprite(layer, base_dir) for layer in self.layers
        }
        self.compiled: dict[str, dict[str, Any]] = {}
        for layer in self.layers:
            if layer.expressions:
                self.compiled[layer.id] = {
                    prop: compile_expression(src) for prop, src in layer.expressions.items()
                }
        self.by_id: dict[str, Layer] = {layer.id: layer for layer in self.layers}
        self.matte_sources: set[str] = {
            layer.track_matte.source for layer in self.layers if layer.track_matte is not None
        }
        # Cache rendered RGBA frames keyed by the precomp's quantised frame
        # index so neighbouring parent-frame samples hit the same precomp frame.
        self.frame_cache: dict[int, Image.Image] = {}
        # Pre-built particle lists for any ParticleEmitter layers inside.
        self.particle_systems: dict[str, list[_Particle]] = {
            layer.id: _build_particles(
                layer,
                layer.duration if layer.duration is not None else precomp.duration,
            )
            for layer in self.layers
            if isinstance(layer, ParticleEmitter)
        }
        # Filled in by ``_build_precomp_renders`` so nested precomps resolve.
        self._global_renders: dict[str, _PrecompRender] | None = None


def _build_precomp_renders(
    precomps: dict[str, Precomp], base_dir: Path
) -> dict[str, _PrecompRender]:
    renders = {name: _PrecompRender(name, pc, base_dir) for name, pc in precomps.items()}
    # Cross-link so nested ``PrecompLayer`` inside a precomp can resolve to
    # other precomps via ``_render_precomp_frame``.
    for pr in renders.values():
        pr._global_renders = renders  # type: ignore[attr-defined]
    return renders


def _render_precomp_frame(pr: _PrecompRender, t_local: float) -> Image.Image:
    """Render the precomp's RGBA frame at the given LOCAL time. Frames are
    cached at the precomp's native fps so multiple parent frames hitting the
    same precomp frame reuse the same composite.
    """
    # Hold the last frame once beyond the precomp's declared duration.
    t_clamped = max(0.0, min(t_local, pr.duration))
    frame_idx = int(round(t_clamped * pr.fps))
    if frame_idx in pr.frame_cache:
        return pr.frame_cache[frame_idx]
    t_q = frame_idx / float(pr.fps) if pr.fps > 0 else t_clamped
    base = Image.new("RGBA", (pr.width, pr.height), (0, 0, 0, 0))
    # Note: precomps cannot reference other precomps via this same dict here.
    # Recursion is supported by passing the SAME global ``precomp_renders``
    # at call sites — handled in ``_compose_frame`` via the parameter passed
    # to ``composite_timeline``. Inside a precomp's own render we rely on
    # the outer ``precomp_renders`` being threaded; for simplicity we re-use
    # the local frame_cache only. Nested precomp references inside a precomp
    # are resolved by the same global lookup attached to ``pr``.
    composed = _compose_frame(
        base,
        pr.layers,
        pr.sprites,
        pr.compiled,
        pr.by_id,
        t_q,
        duration=pr.duration,
        fps=float(pr.fps),
        matte_sources=pr.matte_sources,
        precomp_renders=pr._global_renders,
        particle_systems=pr.particle_systems,
    )
    # Keep cache bounded so very long animations don't OOM.
    if len(pr.frame_cache) > 600:  # ~20 s at 30 fps
        pr.frame_cache.clear()
    pr.frame_cache[frame_idx] = composed
    return composed


def _probe_video(path: Path) -> dict[str, Any]:
    """Return ``{width, height, fps, duration, has_audio}`` for ``path`` using ffprobe."""
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    v_stream = next(s for s in data["streams"] if s.get("codec_type") == "video")
    a_stream = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    num, den = (v_stream.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    duration = float(data["format"].get("duration") or v_stream.get("duration") or 0.0)
    return {
        "width": int(v_stream["width"]),
        "height": int(v_stream["height"]),
        "fps": fps,
        "duration": duration,
        "has_audio": a_stream is not None,
    }


# ── Phase 9: data-driven bindings ────────────────────────────────────────────


def _resolve_json_path(data: Any, path: str) -> Any:
    """Walk a dot/index path through nested JSON.

    Supports ``a.b.c`` and ``a[0].b[2]``. Raises ``KeyError`` if missing.
    """
    cur = data
    # Tokenise on '.' first, then peel off '[N]' suffixes.
    for raw in path.split("."):
        # Pull a leading name (may be empty when path starts with [N])
        name, _, rest = raw.partition("[")
        if name:
            if not isinstance(cur, dict) or name not in cur:
                raise KeyError(f"Missing key '{name}' in data path '{path}'.")
            cur = cur[name]
        if rest:
            # rest looks like "0].b[1]" — re-prepend the '[' we split on.
            chunk = "[" + rest
            while chunk.startswith("["):
                end = chunk.index("]")
                idx = int(chunk[1:end])
                if not isinstance(cur, list) or idx >= len(cur):
                    raise KeyError(f"Bad index [{idx}] in data path '{path}'.")
                cur = cur[idx]
                chunk = chunk[end + 1 :]
                if chunk.startswith("."):
                    chunk = chunk[1:]
                    # remaining chunk is a key – fall through to outer loop
                    if chunk:
                        cur = _resolve_json_path(cur, chunk)
                        chunk = ""
    return cur


_NUMERIC_TARGETS = {
    "position_x",
    "position_y",
    "position_z",
    "scale",
    "rotation",
    "opacity",
}


def _apply_data_bindings_inplace(timeline: Timeline, base_dir: Path) -> None:
    """Mutate ``timeline`` layers by resolving each ``DataBinding``.

    - ``content`` bindings rewrite ``TextLayer.content`` with the formatted
      scalar.
    - Numeric scalar bindings replace the static transform field.
    - Time-series bindings (``time_key`` + ``value_key``) append a
      synthetic ``PropertyTrack`` animator on the target property.
    """
    cache: dict[Path, Any] = {}

    def _load(src: str) -> Any:
        p = (base_dir / src).resolve() if not Path(src).is_absolute() else Path(src)
        if p not in cache:
            cache[p] = json.loads(p.read_text(encoding="utf-8"))
        return cache[p]

    def _process_layer(layer: Layer) -> None:
        if not getattr(layer, "data_bindings", None):
            return
        for binding in layer.data_bindings:
            try:
                data = _load(binding.source)
                value = _resolve_json_path(data, binding.path)
            except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
                logger.warning(
                    "data_binding on '%s' (%s/%s) failed: %s",
                    layer.id,
                    binding.source,
                    binding.path,
                    exc,
                )
                continue

            # Time-series mode: build a synthetic animator.
            if binding.time_key and binding.value_key and isinstance(value, list):
                if binding.target == "content":
                    logger.warning(
                        "data_binding on '%s' targets 'content' but provided "
                        "a time-series; ignoring.",
                        layer.id,
                    )
                    continue
                kfs: list[Keyframe] = []
                for item in value:
                    try:
                        kfs.append(
                            Keyframe(
                                t=float(item[binding.time_key]),
                                v=float(item[binding.value_key]),
                                ease="ease-in-out",
                            )
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        logger.warning(
                            "skipping malformed time-series item on '%s': %s",
                            layer.id,
                            exc,
                        )
                if not kfs:
                    continue
                # Replace any existing animator targeting the same property.
                layer.animators = [a for a in layer.animators if a.property != binding.target]
                layer.animators.append(
                    PropertyTrack(
                        property=binding.target,
                        keyframes=kfs,
                    )
                )
                continue

            # Scalar mode.
            if binding.target == "content":
                if not isinstance(layer, TextLayer):
                    logger.warning(
                        "data_binding 'content' only valid on text layers (got %s for '%s')",
                        type(layer).__name__,
                        layer.id,
                    )
                    continue
                try:
                    layer.content = binding.format.format(value=value)
                except (KeyError, IndexError, ValueError) as exc:
                    logger.warning(
                        "format '%s' failed on '%s': %s",
                        binding.format,
                        layer.id,
                        exc,
                    )
            elif binding.target in _NUMERIC_TARGETS:
                try:
                    num = float(value)
                except (TypeError, ValueError):
                    logger.warning(
                        "non-numeric value for '%s' on '%s': %r",
                        binding.target,
                        layer.id,
                        value,
                    )
                    continue
                if binding.target == "position_x":
                    layer.transform.position = [num, layer.transform.position[1]]
                elif binding.target == "position_y":
                    layer.transform.position = [layer.transform.position[0], num]
                elif binding.target == "position_z":
                    layer.transform.position_z = num
                elif binding.target == "scale":
                    layer.transform.scale = max(1e-3, num)
                elif binding.target == "rotation":
                    layer.transform.rotation = num
                elif binding.target == "opacity":
                    layer.transform.opacity = max(0.0, min(1.0, num))

    for layer in timeline.layers:
        _process_layer(layer)
    for pc in timeline.precomps.values():
        for layer in pc.layers:
            _process_layer(layer)


def composite_timeline(
    input_video: Path,
    output_video: Path,
    timeline: Timeline,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Composite ``timeline`` on top of ``input_video`` and write to
    ``output_video``. Returns ``output_video`` on success.

    Implementation: streams RGB frames from ffmpeg → PIL compositing →
    streams encoded frames back to ffmpeg. No MoviePy.
    """
    base_dir = base_dir or Path.cwd()
    # Phase 9: resolve all data bindings before rasterising sprites — text
    # ``content`` substitutions must happen before the static sprite is baked.
    _apply_data_bindings_inplace(timeline, base_dir)
    sprites: dict[str, Image.Image | None] = {
        layer.id: _render_sprite(layer, base_dir) for layer in timeline.layers
    }
    compiled: dict[str, dict[str, Any]] = {}
    for layer in timeline.layers:
        if layer.expressions:
            compiled[layer.id] = {
                prop: compile_expression(src) for prop, src in layer.expressions.items()
            }
    by_id = {layer.id: layer for layer in timeline.layers}
    matte_sources = {
        layer.track_matte.source for layer in timeline.layers if layer.track_matte is not None
    }
    precomp_renders = _build_precomp_renders(timeline.precomps, base_dir)

    info = _probe_video(input_video)
    width, height = info["width"], info["height"]
    src_fps = info["fps"] or 30.0
    duration = info["duration"]
    has_audio = info["has_audio"]
    frame_bytes = width * height * 3

    # Pre-build particle lists for top-level ParticleEmitter layers.
    particle_systems: dict[str, list[_Particle]] = {
        layer.id: _build_particles(
            layer,
            layer.duration if layer.duration is not None else duration,
        )
        for layer in timeline.layers
        if isinstance(layer, ParticleEmitter)
    }

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    # No-audio temp output (we'll mux audio back at the end if needed).
    video_tmp = output_video.with_suffix(".video.tmp.mp4")

    decode_cmd = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(input_video),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-an",
        "-",
    ]
    encode_cmd = [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{src_fps}",
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        str(os.cpu_count() or 4),
        str(video_tmp),
    ]

    decoder = subprocess.Popen(decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    encoder = subprocess.Popen(encode_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert decoder.stdout is not None and encoder.stdin is not None

    frame_idx = 0
    try:
        while True:
            buf = decoder.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            t = frame_idx / src_fps
            arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 3))
            base = Image.fromarray(arr).convert("RGBA")
            composed = _compose_frame(
                base,
                list(timeline.layers),
                sprites,
                compiled,
                by_id,
                t,
                duration=duration,
                fps=src_fps,
                matte_sources=matte_sources,
                precomp_renders=precomp_renders,
                particle_systems=particle_systems,
                camera_3d=timeline.camera_3d,
            ).convert("RGB")
            encoder.stdin.write(np.asarray(composed, dtype=np.uint8).tobytes())
            frame_idx += 1
    finally:
        try:
            encoder.stdin.close()
        except BrokenPipeError:
            pass
        dec_rc = decoder.wait()
        enc_rc = encoder.wait()
        if dec_rc not in (0, None):
            err = decoder.stderr.read().decode("utf-8", errors="replace") if decoder.stderr else ""
            raise RuntimeError(f"ffmpeg decoder failed (rc={dec_rc}): {err}")
        if enc_rc != 0:
            err = encoder.stderr.read().decode("utf-8", errors="replace") if encoder.stderr else ""
            raise RuntimeError(f"ffmpeg encoder failed (rc={enc_rc}): {err}")

    # Mux source audio back in if present, otherwise just rename.
    if has_audio:
        mux_tmp = output_video.with_suffix(".mux.tmp.mp4")
        mux_cmd = [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            str(video_tmp),
            "-i",
            str(input_video),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(mux_tmp),
        ]
        subprocess.run(mux_cmd, check=True, capture_output=True)
        os.replace(mux_tmp, output_video)
        video_tmp.unlink(missing_ok=True)
    else:
        os.replace(video_tmp, output_video)

    logger.info("composite_timeline: %d layers baked → %s", len(timeline.layers), output_video)
    return output_video
