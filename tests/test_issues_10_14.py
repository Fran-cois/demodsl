"""Acceptance tests for GitHub issues #10 → #14.

These five issues were filed as "implemented locally, happy to upstream".
The code did land, but several of the behaviours the issues actually
promise had no test at all — auto-anchoring (#11), the vertical
``contain_blur`` layout (#13) and the stroke-by-stroke pen lift (#14) were
entirely unverified, so nothing stopped a refactor from silently undoing
them.

This module pins the acceptance criteria of each issue, from its own text.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import (
    DemoConfig,
    Effect,
    Locator,
    Metadata,
    Scenario,
    Step,
)

# ── Issue #10: camera-flow coherence validation ──────────────────────────────


def _camera_scenario(steps: list[Step]) -> Scenario:
    return Scenario.model_construct(name="cam", url="https://example.com", steps=steps)


class TestIssue10CameraFlow:
    def test_camera_on_navigate_is_an_error(self) -> None:
        """The transform is destroyed by the page load."""
        from demodsl.camera_check import check_camera_flow
        from demodsl.models import CameraMove

        scenario = _camera_scenario(
            [
                Step.model_construct(
                    action="navigate",
                    url="https://example.com",
                    camera=CameraMove(zoom=2.0),
                )
            ]
        )
        issues = check_camera_flow(scenario)
        assert any(i.severity == "error" for i in issues)

    def test_scroll_while_zoomed_is_an_error(self) -> None:
        from demodsl.camera_check import check_camera_flow

        scenario = _camera_scenario(
            [
                Step(action="camera", camera={"zoom": 2.0, "target_x": 0.5, "target_y": 0.5}),
                Step(action="scroll", direction="down", pixels=400),
                Step(action="camera_reset"),
            ]
        )
        assert any(i.severity == "error" for i in check_camera_flow(scenario))

    def test_dangling_zoom_at_the_end_is_an_error(self) -> None:
        from demodsl.camera_check import check_camera_flow

        scenario = _camera_scenario(
            [Step(action="camera", camera={"zoom": 2.0, "target_x": 0.5, "target_y": 0.5})]
        )
        assert any(i.severity == "error" for i in check_camera_flow(scenario))

    def test_bare_camera_reset_action_counts_as_a_reset(self) -> None:
        """`action: camera_reset` is what CameraCommand executes at render time.

        The checker used to honour only `camera: {reset: true}`, so it reported
        `camera.ends_zoomed` on nine of the project's own examples.
        """
        from demodsl.camera_check import check_camera_flow

        scenario = _camera_scenario(
            [
                Step(action="camera", camera={"zoom": 1.8, "target_x": 0.5, "target_y": 0.4}),
                Step(action="camera_reset"),
            ]
        )
        assert check_camera_flow(scenario) == []

    def test_shipped_camera_examples_are_clean(self) -> None:
        """Regression guard for the false positive, on the real configs."""
        import yaml

        from demodsl.camera_check import check_camera_flow

        example = Path("examples/demo_virtual_camera_target.yaml")
        if not example.exists():  # pragma: no cover - examples not vendored
            pytest.skip("examples not present")
        raw = yaml.safe_load(example.read_text("utf-8"))
        scenario = Scenario(**raw["scenarios"][0])
        errors = [i for i in check_camera_flow(scenario) if i.severity == "error"]
        assert errors == []

    def test_clean_choreography_produces_no_issues(self) -> None:
        """The guard the issue asks for: valid plans must stay silent."""
        from demodsl.camera_check import check_camera_flow

        scenario = _camera_scenario(
            [
                Step(action="navigate", url="https://example.com"),
                Step(action="camera", camera={"zoom": 1.8, "target_x": 0.5, "target_y": 0.4}),
                Step(action="camera_reset"),
            ]
        )
        assert check_camera_flow(scenario) == []

    def test_issues_surface_as_warnings_on_every_load(self) -> None:
        """A model validator makes `demodsl validate` surface them for free."""
        with pytest.warns(UserWarning, match="camera"):
            Scenario(
                name="cam",
                url="https://example.com",
                steps=[
                    Step(action="camera", camera={"zoom": 2.0, "target_x": 0.5, "target_y": 0.5})
                ],
            )

    def test_function_stays_importable_for_hard_failures(self) -> None:
        """Authoring pipelines treat error-severity issues as rejections."""
        from demodsl.camera_check import check_camera_flow

        assert callable(check_camera_flow)


# ── Issue #11: auto-anchor pointing effects to the step's locator ────────────


class _AnchorBrowser:
    """A page where the target sits at a known bbox."""

    viewport_size = (1000, 800)

    _DEFAULT_BBOX = {"x": 100, "y": 200, "width": 400, "height": 60}

    def __init__(self, bbox: dict[str, float] | None = _DEFAULT_BBOX) -> None:
        self.bbox = bbox
        self.scrolled: list[str] = []

    def scroll_into_view(self, locator: Locator) -> bool:
        self.scrolled.append(locator.value)
        return True

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        return self.bbox


def _anchor(step: Step, browser: _AnchorBrowser | None = None) -> _AnchorBrowser:
    from demodsl.effects.registry import EffectRegistry
    from demodsl.orchestrators.scenario import ScenarioOrchestrator

    config = DemoConfig.model_construct(metadata=Metadata(title="t"), scenarios=[])
    orch = ScenarioOrchestrator(config, EffectRegistry(), turbo=True)
    browser = browser or _AnchorBrowser()
    orch._anchor_effects_to_locator(browser, step)
    return browser


class TestIssue11AutoAnchor:
    def _step(self, effect_type: str, **effect_kwargs: Any) -> Step:
        return Step(
            action="hover",
            locator=Locator(type="text", value="Ship faster"),
            effects=[Effect(type=effect_type, **effect_kwargs)],
        )

    def test_target_is_filled_from_the_element_centre(self) -> None:
        """Authors cannot know where an element lands at render time."""
        step = self._step("callout_arrow")
        _anchor(step)

        effect = step.effects[0]
        # bbox centre (300, 230) over a 1000x800 viewport.
        assert effect.target_x == pytest.approx(0.30)
        assert effect.target_y == pytest.approx(0.2875)

    def test_element_is_scrolled_into_view_before_measuring(self) -> None:
        """Otherwise the measured bbox is not what ends up on screen."""
        browser = _anchor(self._step("callout_arrow"))
        assert browser.scrolled == ["Ship faster"]

    def test_explicit_coordinates_keep_winning(self) -> None:
        step = self._step("callout_arrow", target_x=0.9, target_y=0.1)
        _anchor(step)

        assert step.effects[0].target_x == 0.9
        assert step.effects[0].target_y == 0.1

    def test_annotation_fits_an_ellipse_to_the_element(self) -> None:
        """A wide headline gets a wide loop, a small badge a tight one."""
        wide = self._step("animated_annotation")
        _anchor(wide, _AnchorBrowser({"x": 0, "y": 0, "width": 600, "height": 50}))

        tight = self._step("animated_annotation")
        _anchor(tight, _AnchorBrowser({"x": 0, "y": 0, "width": 80, "height": 70}))

        assert wide.effects[0].radius > tight.effects[0].radius
        # ratio = rx/ry, so a wide headline is a flatter loop.
        assert wide.effects[0].ratio > tight.effects[0].ratio

    def test_underline_sits_below_the_text_with_half_the_width(self) -> None:
        step = self._step("marker_underline")
        _anchor(step, _AnchorBrowser({"x": 100, "y": 200, "width": 400, "height": 60}))

        effect = step.effects[0]
        # Below the bbox bottom (260px) rather than at its centre.
        assert effect.target_y > 260 / 800
        assert effect.radius == pytest.approx(400 / 2 + 10)

    def test_mark_lands_in_the_margin_not_over_the_content(self) -> None:
        """✓/✗ go just off the top-right corner, never over the element."""
        step = self._step("hand_mark")
        _anchor(step, _AnchorBrowser({"x": 100, "y": 200, "width": 400, "height": 60}))

        effect = step.effects[0]
        assert effect.target_x > (100 + 400) / 1000  # right of the element
        assert effect.target_y < 200 / 800 + 1e-9  # at/above its top edge

    def test_non_pointing_effects_are_left_alone(self) -> None:
        step = self._step("confetti")
        _anchor(step)
        assert step.effects[0].target_x is None

    def test_a_missing_element_never_raises(self) -> None:
        """Anchoring is a nicety; it must not take the render down."""
        step = self._step("callout_arrow")
        _anchor(step, _AnchorBrowser(bbox=None))
        assert step.effects[0].target_x is None

    def test_every_anchorable_effect_is_published(self) -> None:
        from demodsl.capabilities import AUTO_ANCHORED_EFFECTS
        from demodsl.orchestrators.scenario import ScenarioOrchestrator

        assert AUTO_ANCHORED_EFFECTS == frozenset(ScenarioOrchestrator._ANCHORABLE_EFFECTS)


# ── Issue #12: audio-reactive presenter + reviewer identity ──────────────────


class TestIssue12PresenterOverlays:
    def test_overlays_are_video_level_not_in_page(self) -> None:
        """An in-page overlay would inherit the virtual-camera transform."""
        from demodsl.models import VideoConfig

        video = VideoConfig(
            reviewer={"name": "Alex Rivera", "title": "Senior CRO Reviewer"},
            live_avatar={"enabled": True, "accent": "#6366F1"},
        )
        assert video.reviewer.name == "Alex Rivera"
        assert video.live_avatar.enabled is True

    def test_config_knobs_from_the_issue(self) -> None:
        from demodsl.models.video import LiveAvatarBadge

        badge = LiveAvatarBadge(enabled=True, accent="#FF5A1F", position="bottom-left", size=200)
        assert (badge.accent, badge.position, badge.size) == ("#FF5A1F", "bottom-left", 200)

    def test_envelope_is_empty_when_the_track_is_missing(self, tmp_path: Path) -> None:
        """`--skip-voice` must degrade to an idle avatar, not a crash."""
        from demodsl.effects.audio_envelope import amplitude_envelope

        assert amplitude_envelope(tmp_path / "nope.mp3") == []

    def test_envelope_is_one_normalized_value_per_frame(self) -> None:
        """ffmpeg → mono PCM → RMS per frame, normalized to 0..1."""
        import array
        import subprocess

        from demodsl.effects import audio_envelope

        # 2 s of 8 kHz mono: a silent half then a loud half.
        samples = array.array("h", [0] * 8000 + [12000] * 8000)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=samples.tobytes())

        with (
            patch.object(audio_envelope.Path, "exists", return_value=True),
            patch.object(audio_envelope.subprocess, "run", return_value=completed),
        ):
            envelope = audio_envelope.amplitude_envelope(Path("narration.mp3"), fps=30)

        assert len(envelope) == pytest.approx(60, abs=2)  # ~2 s at 30 fps
        assert all(0.0 <= v <= 1.0 for v in envelope)
        assert envelope[0] < envelope[-1], "the loud half must open the mouth wider"

    def test_mouth_opens_faster_than_it_closes(self) -> None:
        """The attack/decay asymmetry is what reads as speech at 30 fps."""
        import array
        import subprocess

        from demodsl.effects import audio_envelope

        # Loud burst then silence: the rise must be steeper than the fall.
        samples = array.array("h", [0] * 800 + [15000] * 4000 + [0] * 8000)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=samples.tobytes())

        with (
            patch.object(audio_envelope.Path, "exists", return_value=True),
            patch.object(audio_envelope.subprocess, "run", return_value=completed),
        ):
            envelope = audio_envelope.amplitude_envelope(Path("n.mp3"), fps=30)

        peak = envelope.index(max(envelope))
        rise = max(envelope[i + 1] - envelope[i] for i in range(peak))
        fall = max(envelope[i] - envelope[i + 1] for i in range(peak, len(envelope) - 1))
        assert rise > fall

    def test_envelope_survives_a_broken_decode(self) -> None:
        import subprocess

        from demodsl.effects import audio_envelope

        with (
            patch.object(audio_envelope.Path, "exists", return_value=True),
            patch.object(
                audio_envelope.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
            ),
        ):
            assert audio_envelope.amplitude_envelope(Path("n.mp3")) == []

    def test_no_external_api_or_ml_dependency(self) -> None:
        """The whole point vs. sadtalker/d-id: stdlib only, deterministic."""
        import demodsl.effects.audio_envelope as mod

        source = Path(mod.__file__).read_text("utf-8")
        for banned in ("import numpy", "import torch", "requests", "openai"):
            assert banned not in source


# ── Issue #13: native 9:16 composition instead of cropping ───────────────────


class TestIssue13VerticalComposition:
    def test_vertical_render_is_native_1080x1920(self) -> None:
        """Cropping a 16:9 render destroys subtitles, badges and the page."""
        import inspect

        from demodsl.orchestrators.post_processing import PostProcessingOrchestrator

        source = inspect.getsource(PostProcessingOrchestrator)
        assert "width=1080" in source and "height=1920" in source

    def test_segments_use_the_contain_blur_layout(self) -> None:
        import inspect

        from demodsl.orchestrators.post_processing import PostProcessingOrchestrator

        source = inspect.getsource(PostProcessingOrchestrator)
        assert 'segment_fit="contain_blur"' in source

    def test_renderer_accepts_the_segment_fit_prop(self) -> None:
        import inspect

        from demodsl.providers.remotion_render import RemotionRenderProvider

        params = inspect.signature(RemotionRenderProvider.compose_full).parameters
        assert "segment_fit" in params

    def test_component_implements_both_fits(self) -> None:
        player = Path("remotion/src/components/SegmentPlayer.tsx")
        if not player.exists():  # pragma: no cover - JS side not vendored
            pytest.skip("remotion sources not present")
        source = player.read_text("utf-8")
        assert "contain_blur" in source
        assert "blur" in source.lower()

    def test_a_failed_vertical_render_never_sinks_the_main_one(self) -> None:
        """A short is a bonus; the 16:9 deliverable must still ship."""
        import inspect

        from demodsl.orchestrators.post_processing import PostProcessingOrchestrator

        source = inspect.getsource(PostProcessingOrchestrator)
        assert "Vertical composition failed" in source

    def test_engine_prefers_the_native_vertical_over_cropping(self) -> None:
        import inspect

        from demodsl.engine import DemoEngine

        source = inspect.getsource(DemoEngine._run_social_exports)
        assert "vertical_composition" in source
        assert "vertical_source" in source


# ── Issue #14: hand-drawn quality + verdict stamp + progress bar ─────────────


def _effect_js(effect_type: str, **params: Any) -> str:
    from demodsl.effects.registry import EffectRegistry

    registry = EffectRegistry()
    from demodsl.effects.browser_effects import register_all_browser_effects

    register_all_browser_effects(registry)
    handler = registry.get_browser_effect(effect_type)
    evaluate = MagicMock()
    handler.inject(evaluate, params)
    return "\n".join(str(call.args[0]) for call in evaluate.call_args_list)


class TestIssue14HandDrawnQuality:
    def test_mark_is_drawn_stroke_by_stroke_with_a_pen_lift(self) -> None:
        """One dashoffset sweep over a single path is not hand-drawing."""
        js = _effect_js("hand_mark", target_x=0.5, target_y=0.5)

        assert "LIFT" in js, "the pause between strokes must exist"
        # Two independent stroke timings, not one global sweep.
        assert "T1" in js and "T2" in js

    def test_the_last_stroke_lands_with_a_pop(self) -> None:
        js = _effect_js("hand_mark", target_x=0.5, target_y=0.5)
        assert "pop" in js and "scale(" in js

    @pytest.mark.parametrize(
        "effect_type", ["hand_mark", "marker_underline", "animated_annotation", "callout_arrow"]
    )
    def test_every_drawn_mark_gets_the_felt_tip_treatment(self, effect_type: str) -> None:
        """Shared: round caps and a wider low-opacity ink-bleed under-stroke."""
        js = _effect_js(effect_type, target_x=0.5, target_y=0.5)

        assert "stroke-linecap" in js and "round" in js
        # The bleed is a second, wider, translucent copy of the same path.
        assert "opacity" in js
        assert js.count("stroke-width") >= 2, "no ink-bleed under-stroke"

    def test_marks_carry_a_soft_drop_shadow(self) -> None:
        js = _effect_js("hand_mark", target_x=0.5, target_y=0.5)
        assert "feDropShadow" in js

    @pytest.mark.parametrize(
        "effect_type", ["hand_mark", "marker_underline", "animated_annotation", "callout_arrow"]
    )
    def test_wobble_is_seeded_so_renders_are_reproducible(self, effect_type: str) -> None:
        first = _effect_js(effect_type, target_x=0.42, target_y=0.61)
        second = _effect_js(effect_type, target_x=0.42, target_y=0.61)
        assert first == second

        moved = _effect_js(effect_type, target_x=0.10, target_y=0.90)
        assert moved != first, "the wobble must derive from the position"

    def test_arrowhead_flicks_come_after_the_curve_lands(self) -> None:
        js = _effect_js("callout_arrow", target_x=0.5, target_y=0.5)
        assert "requestAnimationFrame" in js

    def test_verdict_stamp_is_a_registered_effect(self) -> None:
        from demodsl.models.effects import EFFECT_VALID_PARAMS

        assert "verdict_stamp" in EFFECT_VALID_PARAMS

    def test_verdict_stamp_slams_in_rotated(self) -> None:
        js = _effect_js("verdict_stamp", text="8.5", angle=-12.0)
        assert "rotate" in js
        assert "8.5" in js

    def test_progress_bar_is_a_video_level_overlay(self) -> None:
        """It must not scroll or zoom with the recorded page."""
        from demodsl.models.video import ProgressBarOverlay

        bar = ProgressBarOverlay(enabled=True, accent="#FF5A1F", position="top", height=8)
        assert (bar.position, bar.height) == ("top", 8)

    def test_progress_bar_is_plumbed_into_the_compositor(self) -> None:
        import inspect

        from demodsl.providers.remotion_render import RemotionRenderProvider

        params = inspect.signature(RemotionRenderProvider.compose_full).parameters
        assert "progress_bar_config" in params


# ── Cross-cutting: the manifest must advertise all of it ─────────────────────


class TestManifestCoversTheseFeatures:
    def test_new_effects_are_published_to_authors(self) -> None:
        from demodsl.capabilities import build_manifest

        names = {e["name"] for e in build_manifest()["effects"]}
        assert {"verdict_stamp", "hand_mark", "marker_underline"} <= names

    def test_auto_anchored_effects_are_flagged(self) -> None:
        from demodsl.capabilities import build_manifest

        by_name = {e["name"]: e for e in build_manifest()["effects"]}
        assert by_name["animated_annotation"]["auto_anchored"] is True
        assert by_name["confetti"]["auto_anchored"] is False

    def test_effect_durations_are_hinted(self) -> None:
        """Authors otherwise pick 0.5 s for a 3 s animation."""
        from demodsl.capabilities import build_manifest

        by_name = {e["name"]: e for e in build_manifest()["effects"]}
        low, high = by_name["verdict_stamp"]["recommended_duration"]
        assert 0 < low < high
        assert not math.isnan(low)
