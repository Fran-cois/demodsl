"""Easing curves + keyframe sampling (pure functions)."""

from __future__ import annotations

import math
from typing import Any

from demodsl.models.timeline import Keyframe, PropertyTrack, TimeRemap


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


def _interp_value(a: Any, b: Any, t: float) -> Any:
    if isinstance(a, list) and isinstance(b, list):
        return [_interp_scalar(x, y, t) for x, y in zip(a, b)]
    return _interp_scalar(float(a), float(b), t)


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
