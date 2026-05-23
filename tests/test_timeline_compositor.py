"""Unit tests for demodsl.effects.timeline_compositor — pure helpers.

These tests cover the deterministic, pure-Python helpers (sampling,
easing, JSON-path resolution, polyline arithmetic, transform composition).
End-to-end ffmpeg piping is exercised by integration demos, not here.
"""

from __future__ import annotations

import math

import pytest

from demodsl.effects.timeline_compositor import (
    _apply_time_remap,
    _draw_trimmed_polyline,
    _ease,
    _hex_to_rgba,
    _interp_value,
    _polyline_lengths,
    _resolve_json_path,
    _sample_kfs,
    _sample_tracker,
    resolve_transform,
    sample_track,
)
from demodsl.models.timeline import (
    Keyframe,
    PropertyTrack,
    TextLayer,
    TimeRemap,
    Tracker,
    TrackPoint,
    Transform,
)


def _text(layer_id: str = "x", **kw):  # noqa: ANN001
    return TextLayer(type="text", id=layer_id, content="hello", **kw)


# ── Easing ──────────────────────────────────────────────────────────────────


class TestEase:
    @pytest.mark.parametrize("kind", ["linear", "ease", "ease-in", "ease-out", "ease-in-out"])
    def test_endpoints(self, kind: str) -> None:
        assert _ease(0.0, kind) == pytest.approx(0.0, abs=1e-6)
        assert _ease(1.0, kind) == pytest.approx(1.0, abs=1e-6)

    def test_hold(self) -> None:
        assert _ease(0.5, "hold") == 0.0
        assert _ease(0.999, "hold") == 0.0

    def test_clamps_outside(self) -> None:
        assert _ease(-1.0, "linear") == 0.0
        assert _ease(2.0, "linear") == 1.0

    def test_unknown_kind_falls_back_linear(self) -> None:
        assert _ease(0.5, "totally-unknown") == 0.5


# ── _interp_value ───────────────────────────────────────────────────────────


class TestInterp:
    def test_scalar(self) -> None:
        assert _interp_value(0.0, 10.0, 0.5) == 5.0

    def test_list(self) -> None:
        assert _interp_value([0.0, 0.0], [10.0, 20.0], 0.5) == [5.0, 10.0]


# ── sample_track / _sample_kfs ──────────────────────────────────────────────


class TestSampleTrack:
    def test_before_first(self) -> None:
        tr = PropertyTrack(
            property="opacity",
            keyframes=[Keyframe(t=1.0, v=0.5), Keyframe(t=2.0, v=1.0)],
        )
        assert sample_track(tr, 0.0) == 0.5

    def test_after_last(self) -> None:
        tr = PropertyTrack(
            property="opacity",
            keyframes=[Keyframe(t=0.0, v=0.0), Keyframe(t=1.0, v=1.0)],
        )
        assert sample_track(tr, 99.0) == 1.0

    def test_linear(self) -> None:
        tr = PropertyTrack(
            property="opacity",
            keyframes=[
                Keyframe(t=0.0, v=0.0, ease="linear"),
                Keyframe(t=1.0, v=10.0),
            ],
        )
        assert sample_track(tr, 0.5) == pytest.approx(5.0)


class TestSampleKfs:
    def test_empty_returns_default(self) -> None:
        assert _sample_kfs(None, 0.0, default=42.0) == 42.0
        assert _sample_kfs([], 0.0, default=7.0) == 7.0

    def test_clamp_left_right(self) -> None:
        kfs = [Keyframe(t=1.0, v=2.0), Keyframe(t=2.0, v=4.0)]
        assert _sample_kfs(kfs, 0.0, default=0.0) == 2.0
        assert _sample_kfs(kfs, 5.0, default=0.0) == 4.0


# ── TimeRemap ───────────────────────────────────────────────────────────────


class TestTimeRemap:
    def test_linear_remap(self) -> None:
        r = TimeRemap(keyframes=[[0.0, 0.0], [1.0, 2.0]])
        assert _apply_time_remap(r, 0.5) == pytest.approx(1.0)

    def test_freeze_outside(self) -> None:
        r = TimeRemap(keyframes=[[0.0, 0.5], [1.0, 2.0]])
        assert _apply_time_remap(r, -0.5) == 0.5
        assert _apply_time_remap(r, 5.0) == 2.0


# ── _sample_tracker ─────────────────────────────────────────────────────────


class TestSampleTracker:
    def test_interp_position(self) -> None:
        t = Tracker(
            points=[
                TrackPoint(t=0.0, x=0.0, y=0.0),
                TrackPoint(t=1.0, x=100.0, y=200.0),
            ]
        )
        x, y, s, r = _sample_tracker(t, 0.5)
        assert x == pytest.approx(50.0)
        assert y == pytest.approx(100.0)
        assert s is None and r is None

    def test_scale_and_rotation_when_both_set(self) -> None:
        t = Tracker(
            points=[
                TrackPoint(t=0.0, x=0.0, y=0.0, scale=1.0, rotation=0.0),
                TrackPoint(t=2.0, x=0.0, y=0.0, scale=2.0, rotation=90.0),
            ]
        )
        _, _, s, r = _sample_tracker(t, 1.0)
        assert s == pytest.approx(1.5)
        assert r == pytest.approx(45.0)


# ── _hex_to_rgba ────────────────────────────────────────────────────────────


class TestHexToRgba:
    def test_six_digit(self) -> None:
        assert _hex_to_rgba("#ff0000") == (255, 0, 0, 255)

    def test_three_digit(self) -> None:
        assert _hex_to_rgba("#f00") == (255, 0, 0, 255)

    def test_eight_digit_alpha(self) -> None:
        r, g, b, a = _hex_to_rgba("#ff000080")
        assert (r, g, b) == (255, 0, 0)
        assert a == 128

    def test_opacity_scales_alpha(self) -> None:
        _, _, _, a = _hex_to_rgba("#ffffff", opacity=0.5)
        assert a == 127


# ── _polyline_lengths ───────────────────────────────────────────────────────


class TestPolylineLengths:
    def test_open(self) -> None:
        pts = [[0.0, 0.0], [3.0, 0.0], [3.0, 4.0]]
        lens, total = _polyline_lengths(pts, closed=False)
        assert lens == pytest.approx([3.0, 4.0])
        assert total == pytest.approx(7.0)

    def test_closed_adds_back_edge(self) -> None:
        pts = [[0.0, 0.0], [3.0, 0.0], [3.0, 4.0]]
        lens, total = _polyline_lengths(pts, closed=True)
        # 3 + 4 + 5 (hypot) = 12
        assert total == pytest.approx(12.0)
        assert lens[-1] == pytest.approx(5.0)

    def test_total_never_zero(self) -> None:
        pts = [[0.0, 0.0], [0.0, 0.0]]
        _, total = _polyline_lengths(pts, closed=False)
        assert total > 0.0


# ── _resolve_json_path ──────────────────────────────────────────────────────


class TestResolveJsonPath:
    def test_simple_dot(self) -> None:
        assert _resolve_json_path({"a": {"b": 7}}, "a.b") == 7

    def test_index(self) -> None:
        assert _resolve_json_path({"a": [10, 20, 30]}, "a[1]") == 20

    def test_index_then_key(self) -> None:
        data = {"items": [{"v": 1}, {"v": 2}, {"v": 3}]}
        assert _resolve_json_path(data, "items[2].v") == 3

    def test_missing_key_raises(self) -> None:
        with pytest.raises(KeyError):
            _resolve_json_path({"a": 1}, "b")

    def test_bad_index_raises(self) -> None:
        with pytest.raises(KeyError):
            _resolve_json_path({"a": [1, 2]}, "a[5]")


# ── resolve_transform ───────────────────────────────────────────────────────


class TestResolveTransform:
    def test_static_transform_unchanged(self) -> None:
        layer = _text("x", transform=Transform(position=[100.0, 200.0], scale=1.5))
        tr = resolve_transform(layer, 0.0)
        assert tr.position == [100.0, 200.0]
        assert tr.scale == 1.5

    def test_animator_overrides_default(self) -> None:
        layer = _text(
            "x",
            animators=[
                PropertyTrack(
                    property="opacity",
                    keyframes=[Keyframe(t=0.0, v=0.0), Keyframe(t=1.0, v=1.0, ease="linear")],
                )
            ],
        )
        # Sample mid-way (with ease-in-out from t=0, see ease default).
        tr = resolve_transform(layer, 1.0)
        assert tr.opacity == pytest.approx(1.0)

    def test_parent_composition_uses_canvas_size(self) -> None:
        """Bug regression: B1 — parent composition should use the supplied
        canvas centre, not a hardcoded 1920x1080 centre."""
        child = _text("c", transform=Transform(position=[100.0, 100.0]))
        # Parent transform is centred on a 800x600 canvas → no offset
        parent_t = Transform(position=[400.0, 300.0])
        tr = resolve_transform(
            child,
            0.0,
            parent_transform=parent_t,
            canvas_size=(800, 600),
        )
        assert tr.position == [100.0, 100.0]

    def test_parent_composition_offsets(self) -> None:
        child = _text("c", transform=Transform(position=[100.0, 100.0]))
        # Parent 50px right of centre on 800x600 canvas
        parent_t = Transform(position=[450.0, 300.0])
        tr = resolve_transform(
            child,
            0.0,
            parent_transform=parent_t,
            canvas_size=(800, 600),
        )
        assert tr.position == [150.0, 100.0]

    def test_parent_scale_multiplies(self) -> None:
        child = _text("c", transform=Transform(scale=2.0))
        parent_t = Transform(scale=3.0)
        tr = resolve_transform(child, 0.0, parent_transform=parent_t)
        assert tr.scale == pytest.approx(6.0)

    def test_parent_opacity_multiplies(self) -> None:
        child = _text("c", transform=Transform(opacity=0.5))
        parent_t = Transform(opacity=0.5)
        tr = resolve_transform(child, 0.0, parent_transform=parent_t)
        assert tr.opacity == pytest.approx(0.25)


# ── _draw_trimmed_polyline smoke test ───────────────────────────────────────


class TestDrawTrimmedPolyline:
    def test_no_op_when_t1_le_t0(self) -> None:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        _draw_trimmed_polyline(
            d,
            [[0.0, 0.0], [10.0, 10.0]],
            closed=False,
            color=(255, 0, 0, 255),
            width=2.0,
            t0=0.5,
            t1=0.5,
            line_cap="round",
        )
        # Untouched — full alpha 0
        assert img.getextrema()[3] == (0, 0)

    def test_full_draw_paints_pixels(self) -> None:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        _draw_trimmed_polyline(
            d,
            [[10.0, 50.0], [90.0, 50.0]],
            closed=False,
            color=(255, 0, 0, 255),
            width=3.0,
            t0=0.0,
            t1=1.0,
            line_cap="round",
        )
        # Some pixels are now opaque red
        assert img.getextrema()[3][1] > 0
