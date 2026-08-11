"""Planning for partial (windowed) Remotion composition.

Remotion rasterises every frame through headless Chrome, which costs the same
whether the frame carries an effect or is a plain passthrough of the recorded
screencast. Measured on a 24 s 1080p clip with two cores: 27 s through Remotion
against 7 s through ffmpeg alone.

Across the demo corpus only ~16 % of steps carry an effect, yet a single one is
enough to send the whole timeline through Chrome. Splitting the timeline lets
the untouched stretches take the cheap path.
"""

from __future__ import annotations

from typing import Any

# Below this, a passthrough stretch costs more in cuts and re-encodes than the
# rasterisation it saves.
MIN_PASSTHROUGH_SECONDS = 1.5

# Above this coverage, windowing buys too little to be worth the extra seams.
MAX_WORTHWHILE_COVERAGE = 0.75

Window = tuple[float, float, list[dict[str, Any]] | None]


def merge_effect_windows(
    step_effects: list[tuple[float, float, list[dict[str, Any]]]],
    total_duration: float,
    *,
    min_gap: float = MIN_PASSTHROUGH_SECONDS,
) -> list[tuple[float, float, list[dict[str, Any]]]]:
    """Merge overlapping/adjacent effect windows, clamped to the timeline."""
    windows = []
    for start, end, effects in step_effects:
        if not effects:
            continue
        start = max(0.0, min(float(start), total_duration))
        end = max(0.0, min(float(end), total_duration))
        if end > start:
            windows.append((start, end, list(effects)))
    if not windows:
        return []

    windows.sort(key=lambda w: w[0])
    merged: list[tuple[float, float, list[dict[str, Any]]]] = [windows[0]]
    for start, end, effects in windows[1:]:
        prev_start, prev_end, prev_effects = merged[-1]
        # A gap too small to be worth a separate passthrough is absorbed, which
        # also keeps effects that merely touch from producing a zero-length cut.
        if start - prev_end < min_gap:
            merged[-1] = (prev_start, max(prev_end, end), prev_effects + effects)
        else:
            merged.append((start, end, effects))
    return merged


def plan_windows(
    step_effects: list[tuple[float, float, list[dict[str, Any]]]],
    total_duration: float,
    *,
    min_gap: float = MIN_PASSTHROUGH_SECONDS,
) -> list[Window]:
    """Split ``[0, total_duration]`` into rasterised and passthrough windows.

    Returns contiguous, non-overlapping windows covering the whole timeline.
    A ``None`` payload means the stretch carries no effect and can be copied
    instead of rendered.
    """
    if total_duration <= 0:
        return []

    merged = merge_effect_windows(step_effects, total_duration, min_gap=min_gap)
    if not merged:
        return [(0.0, total_duration, None)]

    plan: list[Window] = []
    cursor = 0.0
    for start, end, effects in merged:
        if start - cursor >= min_gap:
            plan.append((cursor, start, None))
        elif start > cursor:
            # Too short to split off: hand it to the rendered window instead.
            start = cursor
        plan.append((start, end, effects))
        cursor = end

    if total_duration - cursor >= min_gap:
        plan.append((cursor, total_duration, None))
    elif total_duration > cursor:
        last_start, _, last_effects = plan[-1]
        plan[-1] = (last_start, total_duration, last_effects)
    return plan


def coverage_ratio(plan: list[Window], total_duration: float) -> float:
    """Share of the timeline that still has to go through Chrome."""
    if total_duration <= 0:
        return 1.0
    rendered = sum(end - start for start, end, effects in plan if effects)
    return min(1.0, rendered / total_duration)


def is_worthwhile(plan: list[Window], total_duration: float) -> bool:
    """True when windowing saves enough rasterisation to justify the seams."""
    if len(plan) < 2:
        return False
    return coverage_ratio(plan, total_duration) <= MAX_WORTHWHILE_COVERAGE


def shift_effects(
    effects: list[dict[str, Any]],
    window_start: float,
) -> list[dict[str, Any]]:
    """Rebase effect timestamps onto a window that now starts at zero."""
    shifted = []
    for effect in effects:
        item = dict(effect)
        for key in ("startTime", "endTime", "start", "end"):
            if isinstance(item.get(key), (int, float)):
                item[key] = max(0.0, item[key] - window_start)
        shifted.append(item)
    return shifted
