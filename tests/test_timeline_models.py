"""Unit tests for demodsl.models.timeline — Pydantic validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from demodsl.models.timeline import (
    Camera3D,
    Counter,
    DropShadow,
    Keyframe,
    Mask,
    Precomp,
    PrecompLayer,
    PropertyTrack,
    ShapeLayer,
    TextLayer,
    Timeline,
    TimeRemap,
    Tracker,
    TrackMatte,
    TrackPoint,
    Transform,
)

# ── Keyframe / PropertyTrack ────────────────────────────────────────────────


class TestKeyframe:
    def test_negative_t_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Keyframe(t=-1.0, v=0.0)

    def test_scalar_and_vector(self) -> None:
        Keyframe(t=0.0, v=10.0)
        Keyframe(t=1.0, v=[10.0, 20.0])

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Keyframe(t=0.0, v=0.0, foo="bar")  # type: ignore[call-arg]


class TestPropertyTrack:
    def test_unsorted_keyframes_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sorted"):
            PropertyTrack(
                property="opacity",
                keyframes=[Keyframe(t=2.0, v=1.0), Keyframe(t=1.0, v=0.0)],
            )

    def test_sorted_keyframes_ok(self) -> None:
        tr = PropertyTrack(
            property="opacity",
            keyframes=[Keyframe(t=0.0, v=0.0), Keyframe(t=1.0, v=1.0)],
        )
        assert len(tr.keyframes) == 2

    def test_empty_keyframes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PropertyTrack(property="opacity", keyframes=[])


# ── Mask ────────────────────────────────────────────────────────────────────


class TestMask:
    def test_bounds_length(self) -> None:
        with pytest.raises(ValidationError):
            Mask(bounds=[0.0, 0.0, 1.0])  # type: ignore[arg-type]

    def test_defaults(self) -> None:
        m = Mask()
        assert m.bounds == [0.0, 0.0, 1.0, 1.0]
        assert m.feather == 0.0
        assert m.mode == "add"


# ── TimeRemap ───────────────────────────────────────────────────────────────


class TestTimeRemap:
    def test_min_two_keyframes(self) -> None:
        with pytest.raises(ValidationError):
            TimeRemap(keyframes=[[0.0, 0.0]])

    def test_unsorted_outs_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sorted"):
            TimeRemap(keyframes=[[1.0, 0.0], [0.5, 1.0]])

    def test_bad_pair_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TimeRemap(keyframes=[[0.0, 0.0, 0.0], [1.0, 1.0]])

    def test_ok(self) -> None:
        TimeRemap(keyframes=[[0.0, 0.0], [1.0, 2.0]])


# ── DropShadow / Counter ────────────────────────────────────────────────────


class TestDropShadow:
    def test_invalid_color(self) -> None:
        with pytest.raises(ValidationError):
            DropShadow(color="not-a-color")

    def test_negative_blur(self) -> None:
        with pytest.raises(ValidationError):
            DropShadow(blur=-1.0)

    def test_defaults(self) -> None:
        ds = DropShadow()
        assert 0.0 <= ds.opacity <= 1.0


class TestCounter:
    def test_zero_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Counter(to_value=100, duration=0.0)

    def test_ok(self) -> None:
        c = Counter(to_value=1000, duration=2.0)
        assert c.from_value == 0.0
        assert c.format == "{value:,.0f}"


# ── Tracker ─────────────────────────────────────────────────────────────────


class TestTracker:
    def test_empty_points_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tracker(points=[])

    def test_single_point_ok(self) -> None:
        # min_length=1 — a single point is a static "tracker".
        t = Tracker(points=[TrackPoint(t=0.0, x=0.0, y=0.0)])
        assert len(t.points) == 1

    def test_unsorted_points_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tracker(
                points=[
                    TrackPoint(t=1.0, x=0.0, y=0.0),
                    TrackPoint(t=0.0, x=0.0, y=0.0),
                ]
            )


# ── Camera3D ────────────────────────────────────────────────────────────────


class TestCamera3D:
    def test_position_must_be_xyz(self) -> None:
        with pytest.raises(ValidationError, match="\\[x, y, z\\]"):
            Camera3D(position=[0.0, 0.0])

    def test_defaults(self) -> None:
        c = Camera3D()
        assert c.position == [960.0, 540.0, -1000.0]


# ── Timeline validators ─────────────────────────────────────────────────────


def _make_text(layer_id: str, **kw: object) -> TextLayer:
    return TextLayer(type="text", id=layer_id, content="x", **kw)  # type: ignore[arg-type]


class TestTimelineValidators:
    def test_unique_ids(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            Timeline(layers=[_make_text("a"), _make_text("a")])

    def test_unknown_parent(self) -> None:
        with pytest.raises(ValidationError, match="unknown parent"):
            Timeline(layers=[_make_text("a", parent="ghost")])

    def test_self_parent_cycle(self) -> None:
        with pytest.raises(ValidationError, match="cycle"):
            Timeline(layers=[_make_text("a", parent="a")])

    def test_parent_cycle_two_layers(self) -> None:
        with pytest.raises(ValidationError, match="cycle"):
            Timeline(
                layers=[
                    _make_text("a", parent="b"),
                    _make_text("b", parent="a"),
                ]
            )

    def test_valid_parent(self) -> None:
        tl = Timeline(
            layers=[
                _make_text("parent_l"),
                _make_text("child", parent="parent_l"),
            ]
        )
        assert len(tl.layers) == 2

    def test_track_matte_self_rejected(self) -> None:
        with pytest.raises(ValidationError, match="itself"):
            Timeline(layers=[_make_text("a", track_matte=TrackMatte(source="a"))])

    def test_track_matte_unknown_source(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            Timeline(layers=[_make_text("a", track_matte=TrackMatte(source="missing"))])

    def test_precomp_reference_unknown(self) -> None:
        with pytest.raises(ValidationError, match="unknown precomp"):
            Timeline(
                layers=[PrecompLayer(type="precomp", id="pl", source="missing")],
            )

    def test_precomp_cycle(self) -> None:
        # precomp A references B, B references A
        with pytest.raises(ValidationError, match="cycle"):
            Timeline(
                precomps={
                    "A": Precomp(layers=[PrecompLayer(type="precomp", id="ref_b", source="B")]),
                    "B": Precomp(layers=[PrecompLayer(type="precomp", id="ref_a", source="A")]),
                }
            )


# ── ShapeLayer / TextLayer ──────────────────────────────────────────────────


class TestShapeLayer:
    def test_invalid_fill_color(self) -> None:
        with pytest.raises(ValidationError):
            ShapeLayer(type="shape", id="x", shape="rectangle", fill="totallybroken")

    def test_negative_width_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ShapeLayer(type="shape", id="x", shape="rectangle", width=-1.0)


class TestTextLayer:
    def test_empty_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TextLayer(type="text", id="x", content="")

    def test_default_transform_anchor(self) -> None:
        layer = _make_text("x")
        assert layer.transform.anchor == [0.5, 0.5]

    def test_duplicate_animator_property_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate animator"):
            _make_text(
                "x",
                animators=[
                    PropertyTrack(
                        property="opacity",
                        keyframes=[Keyframe(t=0.0, v=0.0), Keyframe(t=1.0, v=1.0)],
                    ),
                    PropertyTrack(
                        property="opacity",
                        keyframes=[Keyframe(t=0.0, v=0.0), Keyframe(t=1.0, v=1.0)],
                    ),
                ],
            )


# ── Transform defaults ──────────────────────────────────────────────────────


class TestTransform:
    def test_defaults(self) -> None:
        t = Transform()
        assert t.position == [960.0, 540.0]
        assert t.anchor == [0.5, 0.5]
        assert t.scale == 1.0
        assert t.opacity == 1.0

    def test_zero_scale_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Transform(scale=0.0)

    def test_opacity_clamp(self) -> None:
        with pytest.raises(ValidationError):
            Transform(opacity=1.5)
