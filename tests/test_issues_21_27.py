"""Regression + acceptance tests for GitHub issues #21 → #27.

Each class maps to one issue and starts from the failure described in
the report:

* #21 — no way to observe / try one step / undo / commit: authoring is
  one-shot and blind.
* #22 — a single unhoverable element aborts the whole render.
* #23 — targeting is chosen from a flat DOM listing instead of what the
  page looks like.
* #24 — nothing detects defects that only exist in the composited output.
* #25 — editing one word of narration forces a full re-record.
* #26 — renders are non-deterministic, so demo quality is not measurable.
* #27 — style lives in a dozen unrelated colour fields, with no contrast
  guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.color_utils import contrast_ratio, parse_css_color
from demodsl.models import DemoConfig, Locator, Metadata, Scenario, Step, Viewport


def _config(steps: list[Step], **kwargs: Any) -> DemoConfig:
    return DemoConfig(
        metadata=Metadata(title="t"),
        scenarios=[Scenario(name="s", url="https://example.com", steps=steps)],
        **kwargs,
    )


# ── Issue #22: one unhoverable element must not abort the render ─────────────


class _FakeBrowser:
    """Minimal browser double: every hover times out like the real bug."""

    def __init__(self, *, failing_actions: tuple[str, ...] = ("hover",)) -> None:
        self.failing_actions = failing_actions
        self.hovered: list[str] = []
        self.clicked: list[str] = []
        self.scrolled_into_view: list[str] = []
        self.evaluated: list[str] = []

    def hover(self, locator: Locator) -> None:
        self.hovered.append(locator.value)
        if "hover" in self.failing_actions:
            raise TimeoutError(
                "Page.hover: Timeout 30000ms exceeded.\nCall log:\n  - waiting for "
                'locator("text=/Featured/i")'
            )

    def click(self, locator: Locator) -> None:
        self.clicked.append(locator.value)
        if "click" in self.failing_actions:
            raise TimeoutError("Page.click: Timeout 30000ms exceeded.")

    def navigate(self, url: str) -> None:
        if "navigate" in self.failing_actions:
            raise RuntimeError("net::ERR_NAME_NOT_RESOLVED")

    def scroll_into_view(self, locator: Locator) -> bool:
        self.scrolled_into_view.append(locator.value)
        return True

    def evaluate_js(self, script: str) -> Any:
        self.evaluated.append(script)
        return 0

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        return {"x": 10, "y": 20, "width": 100, "height": 40}

    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        return (60.0, 40.0)

    viewport_size = (1920, 1080)


def _orchestrator(config: DemoConfig):
    from demodsl.effects.registry import EffectRegistry
    from demodsl.orchestrators.scenario import ScenarioOrchestrator

    orch = ScenarioOrchestrator(config, EffectRegistry(), turbo=True)
    return orch


class TestIssue22UnhoverableElementDoesNotAbort:
    def test_hover_timeout_no_longer_propagates(self, tmp_path: Path) -> None:
        """The exact failure from the report: a hover on a section heading."""
        step = Step(action="hover", locator=Locator(type="text", value="Featured"), wait=0.0)
        orch = _orchestrator(_config([step]))
        browser = _FakeBrowser()
        ws = MagicMock()
        ws.frames = tmp_path

        # Before the fix this raised TimeoutError and lost the whole render.
        orch._execute_step(browser, step, ws)

        assert orch.skipped_steps, "the degraded step must be reported"
        assert orch.skipped_steps[0]["code"] == "step.locator_unreachable"

    def test_narration_timing_is_preserved_for_a_skipped_step(self, tmp_path: Path) -> None:
        """Skipping must keep the step's slot so the audio stays in sync."""
        step = Step(
            action="hover",
            locator=Locator(type="text", value="Featured"),
            narration="Look at the featured rail",
            wait=2.0,
        )
        orch = _orchestrator(_config([step]))
        ws = MagicMock()
        ws.frames = tmp_path

        orch._execute_step(_FakeBrowser(), step, ws, narration_duration=1.5)

        assert len(orch.step_timestamps) == 1, "the step must still occupy the timeline"

    def test_fallback_ladder_scrolls_the_target_into_view(self, tmp_path: Path) -> None:
        step = Step(action="hover", locator=Locator(type="text", value="Featured"))
        orch = _orchestrator(_config([step]))
        browser = _FakeBrowser()
        ws = MagicMock()
        ws.frames = tmp_path

        orch._execute_step(browser, step, ws)

        assert browser.scrolled_into_view == ["Featured"]
        assert orch.skipped_steps[0]["fallback"] == "scroll_into_view"

    def test_on_error_fail_still_aborts(self, tmp_path: Path) -> None:
        step = Step(
            action="hover",
            locator=Locator(type="text", value="Featured"),
            on_error="fail",
        )
        orch = _orchestrator(_config([step]))
        ws = MagicMock()
        ws.frames = tmp_path

        with pytest.raises(TimeoutError):
            orch._execute_step(_FakeBrowser(), step, ws)

    def test_navigate_stays_fatal_by_default(self, tmp_path: Path) -> None:
        """Losing the navigation makes everything after it meaningless."""
        step = Step(action="navigate", url="https://example.com/missing")
        orch = _orchestrator(_config([step]))
        ws = MagicMock()
        ws.frames = tmp_path

        with pytest.raises(RuntimeError):
            orch._execute_step(_FakeBrowser(failing_actions=("navigate",)), step, ws)

    def test_scenario_level_policy_applies_to_every_step(self, tmp_path: Path) -> None:
        step = Step(action="navigate", url="https://example.com/missing")
        config = DemoConfig(
            metadata=Metadata(title="t"),
            scenarios=[
                Scenario(
                    name="s",
                    url="https://example.com",
                    steps=[step],
                    on_error="skip",
                )
            ],
        )
        orch = _orchestrator(config)
        ws = MagicMock()
        ws.frames = tmp_path

        orch._execute_step(
            _FakeBrowser(failing_actions=("navigate",)),
            step,
            ws,
            scenario_on_error="skip",
        )
        assert orch.skipped_steps

    def test_resolve_on_error_defaults(self) -> None:
        from demodsl.models import resolve_on_error

        assert resolve_on_error(Step(action="hover", locator=Locator(value="a"))) == "skip"
        assert resolve_on_error(Step(action="navigate", url="https://a.co")) == "fail"
        assert resolve_on_error(Step(action="navigate", url="https://a.co"), "skip") == "skip"

    def test_hover_uses_a_short_timeout(self) -> None:
        """30 s of dead air waiting for a cosmetic hover is itself a defect."""
        from demodsl.providers.browser import _HOVER_TIMEOUT_S, PlaywrightBrowserProvider

        assert _HOVER_TIMEOUT_S <= 10

        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        provider.hover(Locator(type="text", value="Featured"))
        assert provider._page.hover.call_args.kwargs["timeout"] == int(_HOVER_TIMEOUT_S * 1000)


# ── Issue #23: visual observation instead of DOM order ───────────────────────


@pytest.fixture
def page_payload() -> dict[str, Any]:
    """A hero headline, a logo rail, a stat, a CTA and a nav link."""
    return {
        "viewport": {"w": 1000, "h": 800},
        "page_height": 4000,
        "scroll_y": 0,
        "elements": [
            {
                "tag": "a",
                "role": "link",
                "text": "Docs",
                "locator": {"type": "css", "value": "nav a:nth-of-type(1)"},
                "bbox": {"x": 10, "y": 10, "w": 60, "h": 20},
                "page_y": 10,
                "font_px": 14,
                "font_weight": 400,
                "color": "rgb(60,60,60)",
                "background": "rgb(255,255,255)",
                "pointer_events": "auto",
                "in_carousel": False,
                "is_link": True,
            },
            {
                "tag": "h1",
                "role": "heading",
                "text": "Ship faster with Acme",
                "locator": {"type": "css", "value": "section:nth-of-type(1) h1"},
                "bbox": {"x": 160, "y": 200, "w": 800, "h": 90},
                "page_y": 200,
                "font_px": 64,
                "font_weight": 700,
                "color": "rgb(16,20,24)",
                "background": "rgb(255,255,255)",
                "pointer_events": "auto",
                "in_carousel": False,
                "is_link": False,
            },
            {
                "tag": "a",
                "role": "button",
                "text": "Get started free",
                "locator": {"type": "css", "value": "a.btn-primary"},
                "bbox": {"x": 160, "y": 340, "w": 220, "h": 56},
                "page_y": 340,
                "font_px": 18,
                "font_weight": 600,
                "color": "rgb(255,255,255)",
                "background": "rgb(255,90,31)",
                "pointer_events": "auto",
                "in_carousel": False,
                "is_link": True,
            },
            {
                "tag": "h2",
                "role": "heading",
                "text": "Trusted by 4,000+ teams",
                "locator": {"type": "css", "value": "section:nth-of-type(2) h2"},
                "bbox": {"x": 160, "y": 940, "w": 600, "h": 48},
                "page_y": 1200,
                "font_px": 40,
                "font_weight": 700,
                "color": "rgb(16,20,24)",
                "background": "rgb(255,255,255)",
                "pointer_events": "auto",
                "in_carousel": False,
                "is_link": False,
            },
            *[
                {
                    "tag": "img",
                    "role": "img",
                    "text": "",
                    "locator": {"type": "css", "value": f"img:nth-of-type({i})"},
                    "bbox": {"x": 100 * i, "y": 1000, "w": 80, "h": 40},
                    "page_y": 1300,
                    "font_px": 0,
                    "font_weight": 400,
                    "color": "rgb(0,0,0)",
                    "background": "rgb(255,255,255)",
                    "pointer_events": "auto",
                    "in_carousel": False,
                    "is_link": False,
                }
                for i in range(1, 5)
            ],
            {
                "tag": "p",
                "role": "paragraph",
                "text": "Hidden slide copy",
                "locator": {"type": "css", "value": ".swiper p"},
                "bbox": {"x": 0, "y": 1500, "w": 300, "h": 30},
                "page_y": 2000,
                "font_px": 16,
                "font_weight": 400,
                "color": "rgb(120,120,120)",
                "background": "rgb(255,255,255)",
                "pointer_events": "none",
                "in_carousel": True,
                "is_link": False,
            },
            {
                "tag": "p",
                "role": "paragraph",
                "text": "© 2026 Acme — Privacy",
                "locator": {"type": "css", "value": "footer p"},
                "bbox": {"x": 0, "y": 3800, "w": 300, "h": 20},
                "page_y": 3900,
                "font_px": 13,
                "font_weight": 400,
                "color": "rgb(150,150,150)",
                "background": "rgb(255,255,255)",
                "pointer_events": "auto",
                "in_carousel": False,
                "is_link": False,
            },
        ],
    }


class TestIssue23Observe:
    def test_ranking_is_visual_not_dom_order(self, page_payload: dict[str, Any]) -> None:
        """The nav link comes first in the DOM; the hero headline must win."""
        from demodsl.observe import rank_elements

        elements = rank_elements(page_payload)
        assert elements[0]["text"] == "Ship faster with Acme"
        assert elements[0]["mark"] == 1

        by_text = {e["text"]: e for e in elements}
        assert by_text["Ship faster with Acme"]["prominence"] > by_text["Docs"]["prominence"]

    def test_visual_evidence_is_exposed(self, page_payload: dict[str, Any]) -> None:
        from demodsl.observe import rank_elements

        hero = next(e for e in rank_elements(page_payload) if e["text"].startswith("Ship"))
        visual = hero["visual"]
        assert visual["font_px"] == 64
        assert visual["font_weight"] == 700
        assert 0 < visual["area_ratio"] < 1
        assert visual["contrast"] and visual["contrast"] > 4
        assert visual["above_the_fold"] is True

    def test_only_saturated_cta_is_flagged(self, page_payload: dict[str, Any]) -> None:
        from demodsl.observe import rank_elements

        cta = next(e for e in rank_elements(page_payload) if e["text"] == "Get started free")
        assert cta["visual"]["is_only_saturated_cta"] is True

    def test_carousel_and_pointer_events_make_a_target_unhoverable(
        self, page_payload: dict[str, Any]
    ) -> None:
        """The #22 failure becomes knowable *before* a step is written."""
        from demodsl.observe import rank_elements

        slide = next(e for e in rank_elements(page_payload) if e["text"] == "Hidden slide copy")
        assert slide["visual"]["in_carousel"] is True
        assert slide["hoverable"] is False

    def test_sections_are_derived(self, page_payload: dict[str, Any]) -> None:
        from demodsl.observe import derive_sections, rank_elements

        elements = rank_elements(page_payload)
        sections = derive_sections(elements, page_height=4000, viewport_height=800)
        kinds = [s["kind"] for s in sections]
        assert kinds[0] == "hero"
        assert "footer" in kinds

    def test_candidate_arguments_shortlist(self, page_payload: dict[str, Any]) -> None:
        from demodsl.observe import candidate_arguments, rank_elements

        elements = rank_elements(page_payload)
        candidates = candidate_arguments(elements)
        by_mark = {e["mark"]: e["text"] for e in elements}

        assert any(by_mark[m].startswith("Ship") for m in candidates["biggest_text"])
        assert any("4,000+" in by_mark[m] for m in candidates["metrics"])
        assert len(candidates["logo_rail"]) >= 3
        assert any(by_mark[m] == "Get started free" for m in candidates["primary_cta"])

    def test_set_of_marks_screenshot(self, tmp_path: Path, page_payload: dict[str, Any]) -> None:
        from PIL import Image

        from demodsl.observe import draw_marks, rank_elements

        source = tmp_path / "shot.png"
        Image.new("RGB", (1000, 800), "white").save(source)
        elements = rank_elements(page_payload)

        output = draw_marks(source, elements, tmp_path / "marks.png")

        assert output.exists()
        # Badges are drawn: the frame is no longer uniformly white.
        assert Image.open(output).convert("RGB").getcolors(maxcolors=1) is None


# ── Issue #24: post-render QA report ─────────────────────────────────────────


@pytest.fixture
def defective_manifest() -> dict[str, Any]:
    return {
        "duration": 70.0,
        "frame": {"width": 1920, "height": 1080},
        "steps": [
            {
                "index": 0,
                "action": "hover",
                "t": 0.0,
                "duration": 6.0,
                "narration_duration": 4.0,
                "motion": True,
            },
            {
                "index": 1,
                "action": "pause",
                "t": 6.0,
                "duration": 12.0,
                "narration_duration": 1.0,
                "motion": False,
            },
            {
                "index": 2,
                "action": "click",
                "t": 60.0,
                "duration": 3.0,
                "narration_duration": 5.3,
                "motion": True,
            },
        ],
        "overlays": [
            {
                "kind": "annotation",
                "step": 0,
                "t": 34.2,
                "duration": 2.0,
                "rect": {"x": 1830, "y": 400, "w": 180, "h": 90},
                "color": "#6366F1",
                "background": "#FFFFFF",
            },
            {
                "kind": "subtitle",
                "step": 1,
                "t": 41.0,
                "duration": 3.0,
                "rect": {"x": 400, "y": 900, "w": 600, "h": 120},
            },
            {
                "kind": "avatar",
                "step": 1,
                "t": 41.0,
                "duration": 3.0,
                "rect": {"x": 800, "y": 900, "w": 200, "h": 200},
            },
        ],
        "skipped_steps": [
            {
                "index": 1,
                "action": "hover",
                "locator": "[text] Featured",
                "code": "step.locator_unreachable",
                "error": "Timeout 30000ms exceeded",
            },
        ],
    }


class TestIssue24QA:
    def test_offscreen_overlay_is_an_error(self, defective_manifest: dict[str, Any]) -> None:
        from demodsl.qa import analyze

        report = analyze(defective_manifest)
        offscreen = [f for f in report.findings if f.code == "overlay.offscreen"]
        assert offscreen and offscreen[0].severity == "error"
        assert "90px past the right edge" in offscreen[0].detail

    def test_overlay_collision_is_detected(self, defective_manifest: dict[str, Any]) -> None:
        from demodsl.qa import analyze

        report = analyze(defective_manifest)
        assert "overlay.collision" in report.codes()

    def test_dead_air_and_audio_overrun(self, defective_manifest: dict[str, Any]) -> None:
        from demodsl.qa import analyze

        report = analyze(defective_manifest)
        assert "shot.dead_air" in report.codes()
        overrun = next(f for f in report.findings if f.code == "audio.overrun")
        assert "2.3s" in overrun.detail

    def test_low_contrast_overlay(self) -> None:
        from demodsl.qa import analyze

        manifest = {
            "frame": {"width": 1920, "height": 1080},
            "overlays": [
                {
                    "kind": "annotation",
                    "t": 12.0,
                    "duration": 1.0,
                    "rect": {"x": 10, "y": 10, "w": 100, "h": 50},
                    "color": "#6366F1",
                    "background": "#A5B4FC",
                },
            ],
        }
        report = analyze(manifest)
        assert "overlay.contrast" in report.codes()
        detail = next(f for f in report.findings if f.code == "overlay.contrast").detail
        assert "2.2:1" in detail

    def test_skipped_step_surfaces_in_the_report(self, defective_manifest: dict[str, Any]) -> None:
        from demodsl.qa import analyze

        report = analyze(defective_manifest)
        assert "step.locator_unreachable" in report.codes()

    def test_clean_render_scores_one(self) -> None:
        from demodsl.qa import analyze

        manifest = {
            "duration": 10.0,
            "frame": {"width": 1920, "height": 1080},
            "steps": [
                {
                    "index": 0,
                    "action": "click",
                    "t": 0.0,
                    "duration": 5.0,
                    "narration_duration": 4.5,
                    "motion": True,
                },
            ],
            "overlays": [
                {
                    "kind": "annotation",
                    "t": 0.0,
                    "duration": 2.0,
                    "rect": {"x": 100, "y": 100, "w": 200, "h": 100},
                    "color": "#101418",
                    "background": "#FFFFFF",
                },
            ],
        }
        report = analyze(manifest)
        assert report.findings == []
        assert report.score == 1.0

    def test_unverified_checks_are_reported_not_silently_passed(self) -> None:
        from demodsl.qa import analyze

        report = analyze({"duration": 5.0})
        assert "overlay.offscreen" in report.checks_skipped
        assert "frame.uniform" in report.checks_skipped

    def test_analyze_file_roundtrip(
        self, tmp_path: Path, defective_manifest: dict[str, Any]
    ) -> None:
        from demodsl.qa import analyze_file

        path = tmp_path / "run.json"
        path.write_text(json.dumps(defective_manifest), encoding="utf-8")
        assert analyze_file(path).score < 1.0


# ── Issue #25: incremental re-render ─────────────────────────────────────────


class TestIssue25IncrementalRender:
    def _cfg(self, narration: str = "Original line") -> DemoConfig:
        return _config(
            [
                Step(action="navigate", url="https://example.com"),
                Step(
                    action="click",
                    locator=Locator(value="#cta"),
                    narration=narration,
                    wait=2.0,
                ),
                Step(action="scroll", direction="down", pixels=400),
            ]
        )

    def test_editing_narration_does_not_dirty_the_recording(self) -> None:
        """The whole point: a word of narration must not cost a re-record."""
        from demodsl.pipeline.segment_cache import plan_segments

        first = plan_segments(self._cfg(), cached_keys={})
        cached = {str(e.index): e.key for e in first.entries}

        second = plan_segments(self._cfg("A totally rewritten line"), cached_keys=cached)

        assert second.dirty == [], second.explain()

    def test_editing_a_step_dirties_only_that_step(self) -> None:
        from demodsl.pipeline.segment_cache import plan_segments

        first = plan_segments(self._cfg(), cached_keys={})
        cached = {str(e.index): e.key for e in first.entries}

        edited = self._cfg()
        edited.scenarios[0].steps[1].locator = Locator(value="#other-cta")
        plan = plan_segments(edited, cached_keys=cached)

        assert plan.dirty == [1]
        assert plan.reused == [0, 2]

    def test_only_steps_forces_a_re_record(self) -> None:
        from demodsl.pipeline.segment_cache import parse_only_steps, plan_segments

        first = plan_segments(self._cfg(), cached_keys={})
        cached = {str(e.index): e.key for e in first.entries}

        plan = plan_segments(self._cfg(), cached_keys=cached, only_steps=parse_only_steps("2,3"))
        assert plan.dirty == [1, 2]
        assert all(e.reason == "forced by --only-steps" for e in plan.entries if not e.hit)

    def test_parse_only_steps_ranges(self) -> None:
        from demodsl.pipeline.segment_cache import parse_only_steps

        assert parse_only_steps("6,7") == {5, 6}
        assert parse_only_steps("4-6") == {3, 4, 5}
        assert parse_only_steps(None) is None
        with pytest.raises(ValueError):
            parse_only_steps("0")

    def test_missing_artefact_is_a_miss_not_a_silent_reuse(self) -> None:
        """A stale/absent segment must never be reused silently."""
        from demodsl.pipeline.segment_cache import plan_segments

        first = plan_segments(self._cfg(), cached_keys={})
        cached = {str(e.index): e.key for e in first.entries}

        plan = plan_segments(self._cfg(), cached_keys=cached, available=set())
        assert plan.dirty == [0, 1, 2]
        assert all("artefact missing" in e.reason for e in plan.entries)

    def test_explain_cache_reports_hit_miss_and_why(self) -> None:
        from demodsl.pipeline.segment_cache import plan_segments

        first = plan_segments(self._cfg(), cached_keys={})
        cached = {str(e.index): e.key for e in first.entries}
        edited = self._cfg()
        edited.scenarios[0].steps[2].pixels = 900

        text = plan_segments(edited, cached_keys=cached).explain()
        assert "HIT" in text and "MISS" in text
        assert "step content changed" in text

    def test_engine_version_is_part_of_the_key(self) -> None:
        from demodsl.pipeline.segment_cache import SegmentKeyInputs, step_key

        base = SegmentKeyInputs(step={"action": "click"}, page_url="u", scenario={})
        bumped = SegmentKeyInputs(
            step={"action": "click"}, page_url="u", scenario={}, engine_version="99.0"
        )
        assert step_key(base) != step_key(bumped)

    def test_narration_key_shape(self) -> None:
        from demodsl.pipeline.segment_cache import narration_key

        a = narration_key("hello", "elevenlabs", "rachel", 1.0)
        b = narration_key("hello", "elevenlabs", "rachel", 1.1)
        assert a != b
        assert a == narration_key("hello", "elevenlabs", "rachel", 1.0)

    def test_segment_store_roundtrip(self, tmp_path: Path) -> None:
        from demodsl.pipeline.segment_cache import SegmentStore

        store = SegmentStore(tmp_path / "segments")
        store.save_keys({"0": "abc"})
        assert store.load_keys() == {"0": "abc"}
        store.path_for("abc").write_bytes(b"x")
        assert store.available() == {"abc"}


# ── Issue #26: determinism + eval harness ────────────────────────────────────


class TestIssue26Determinism:
    def test_seed_is_a_first_class_config_field(self) -> None:
        assert _config([], seed=1234).seed == 1234

    def test_derived_seeds_are_stable_and_namespaced(self) -> None:
        from demodsl.determinism import derive_seed

        assert derive_seed(1234, "particles", 0) == derive_seed(1234, "particles", 0)
        assert derive_seed(1234, "particles", 0) != derive_seed(1234, "wobble", 0)
        assert derive_seed(1234, "particles", 0) != derive_seed(1235, "particles", 0)

    def test_same_seed_gives_the_same_stream(self) -> None:
        from demodsl.determinism import seeded_random

        a = [seeded_random(7, "wobble").random() for _ in range(3)]
        b = [seeded_random(7, "wobble").random() for _ in range(3)]
        assert a == b

    def test_strict_mode_removes_timing_jitter_and_pins_the_frame_rate(self) -> None:
        from demodsl.determinism import DETERMINISTIC_FRAME_RATE, apply_determinism
        from demodsl.models import NaturalConfig, VideoConfig

        config = _config([], seed=1, video=VideoConfig())
        config.scenarios[0].natural = NaturalConfig(jitter=0.3)

        report = apply_determinism(config, strict=True)

        assert config.scenarios[0].natural.jitter == 0.0
        assert config.video.frame_rate == DETERMINISTIC_FRAME_RATE
        assert report["strict"] is True

    def test_without_a_seed_nothing_is_pinned(self) -> None:
        from demodsl.determinism import apply_determinism

        report = apply_determinism(_config([]), strict=False)
        assert report == {"seed": None, "strict": False, "pinned": [], "jitter_disabled": []}


class TestIssue26EvalHarness:
    def _weak(self) -> DemoConfig:
        return _config(
            [
                Step(action="navigate", url="https://example.com"),
                Step(
                    action="click",
                    locator=Locator(value="#cookie-consent-accept"),
                    narration="This is great, really great, truly great.",
                    wait=0.5,
                ),
            ]
        )

    def _strong(self) -> DemoConfig:
        from demodsl.models import Effect

        return _config(
            [
                Step(action="navigate", url="https://example.com"),
                Step(
                    action="hover",
                    locator=Locator(type="text", value="Trusted by 4,000+ teams"),
                    narration="The proof rail is strong and lands early.",
                    effects=[Effect(type="animated_annotation")],
                    wait=4.0,
                    on_error="skip",
                ),
                Step(
                    action="hover",
                    locator=Locator(type="text", value="Get started free"),
                    narration="But the pricing is buried three clicks away.",
                    effects=[Effect(type="marker_underline")],
                    wait=4.0,
                ),
            ],
            seed=1234,
        )

    def test_a_better_config_scores_higher(self) -> None:
        from demodsl.evaluation import evaluate_config

        weak = evaluate_config(self._weak(), name="weak")
        strong = evaluate_config(self._strong(), name="strong")
        assert strong.score > weak.score

    def test_chrome_targets_lower_target_quality(self) -> None:
        from demodsl.evaluation import evaluate_config

        report = evaluate_config(self._weak())
        target = next(d for d in report.dimensions if d.name == "target_quality")
        assert target.score < 0.6
        assert "chrome target" in target.detail

    def test_all_positive_narration_is_penalised(self) -> None:
        from demodsl.evaluation import evaluate_config

        weak = evaluate_config(self._weak())
        balance = next(d for d in weak.dimensions if d.name == "judgement_balance")
        assert balance.score < 0.5

    def test_qa_report_feeds_the_defects_dimension(self) -> None:
        from demodsl.evaluation import evaluate_config

        clean = evaluate_config(self._strong(), qa_report={"score": 1.0, "findings": []})
        broken = evaluate_config(
            self._strong(),
            qa_report={"score": 0.3, "findings": [{"severity": "error"}]},
        )
        assert clean.score > broken.score

    def test_rubric_weights_are_overridable(self) -> None:
        from demodsl.evaluation import evaluate_config

        report = evaluate_config(self._strong(), weights={"pacing_sanity": 0.5})
        assert report.weights["pacing_sanity"] == 0.5
        with pytest.raises(ValueError):
            evaluate_config(self._strong(), weights={"nope": 1.0})

    def test_comparison_table(self) -> None:
        from demodsl.evaluation import compare, evaluate_config

        rows = compare(
            [
                evaluate_config(self._weak(), name="weak.yaml"),
                evaluate_config(self._strong(), name="strong.yaml"),
            ]
        )
        assert rows[0]["config"] == "strong.yaml"
        assert "argument_coverage" in rows[0]


# ── Issue #27: theme tokens + brand extraction ───────────────────────────────


class TestIssue27Theme:
    def test_theme_is_a_first_class_config_object(self) -> None:
        config = _config([], theme={"accent": "#FF5A1F", "ink": "#101418"})
        assert config.theme is not None
        assert config.theme.accent == "#FF5A1F"

    def test_named_presets(self) -> None:
        config = _config([], theme="dark-dev")
        assert config.theme.surface == "#0B0E14"
        assert config.theme.is_light is False
        with pytest.raises(Exception):
            _config([], theme="does-not-exist")

    def test_unreadable_theme_is_rejected_at_parse_time(self) -> None:
        """Contrast is a validated property, not a hope."""
        from demodsl.models.theme import ThemeConfig

        with pytest.raises(ValueError, match="unreadable"):
            ThemeConfig(ink="#FFFFFF", surface="#FEFEFE")

    def test_contrast_issues_are_reported(self) -> None:
        from demodsl.models.theme import ThemeConfig

        theme = ThemeConfig(accent="#FFF3C4", ink="#101418", surface="#FFFFFF")
        issues = theme.contrast_issues()
        assert any(i["token"] == "accent" for i in issues)

    def test_theme_flows_into_every_overlay(self) -> None:
        from demodsl.models import CursorConfig, PopupCardConfig, SubtitleConfig, VideoConfig
        from demodsl.models.video import ProgressBarOverlay
        from demodsl.theme import apply_theme

        config = _config([], theme={"accent": "#FF5A1F"}, video=VideoConfig())
        config.scenarios[0].cursor = CursorConfig()
        config.scenarios[0].popup_card = PopupCardConfig()
        config.subtitle = SubtitleConfig()
        config.video.progress_bar = ProgressBarOverlay()

        applied = apply_theme(config)

        assert config.scenarios[0].cursor.color == "#FF5A1F"
        assert config.scenarios[0].popup_card.accent_color == "#FF5A1F"
        assert config.subtitle.highlight_color == "#FF5A1F"
        assert config.video.progress_bar.accent == "#FF5A1F"
        assert len(applied) >= 4

    def test_explicit_overrides_keep_winning(self) -> None:
        from demodsl.models import CursorConfig
        from demodsl.theme import apply_theme

        config = _config([], theme={"accent": "#FF5A1F"})
        config.scenarios[0].cursor = CursorConfig(color="#00FF00")

        apply_theme(config)

        assert config.scenarios[0].cursor.color == "#00FF00"

    # ── Per-scenario theme override — several looks in one video ────────

    def test_scenario_theme_overrides_the_top_level_theme(self) -> None:
        """One video, two visual identities: each scenario keeps its own."""
        from demodsl.theme import apply_theme

        config = DemoConfig(
            metadata=Metadata(title="t"),
            theme={"accent": "#FF5A1F"},
            scenarios=[
                Scenario(name="a", url="https://example.com", steps=[]),
                Scenario(
                    name="b",
                    url="https://example.com",
                    theme={"accent": "#00A3FF"},
                    steps=[],
                ),
            ],
        )
        from demodsl.models import CursorConfig

        config.scenarios[0].cursor = CursorConfig()
        config.scenarios[1].cursor = CursorConfig()

        apply_theme(config)

        assert config.scenarios[0].cursor.color == "#FF5A1F"
        assert config.scenarios[1].cursor.color == "#00A3FF"

    def test_scenario_theme_accepts_a_preset_name(self) -> None:
        scenario = Scenario(name="s", url="https://example.com", theme="dark-dev", steps=[])
        assert scenario.theme is not None
        assert scenario.theme.surface == "#0B0E14"

        with pytest.raises(Exception):
            Scenario(name="s", url="https://example.com", theme="does-not-exist", steps=[])

    def test_scenario_theme_works_with_no_top_level_theme(self) -> None:
        """A themeless demo can still theme just one of its scenarios."""
        from demodsl.models import CursorConfig
        from demodsl.theme import apply_theme

        config = DemoConfig(
            metadata=Metadata(title="t"),
            scenarios=[
                Scenario(name="a", url="https://example.com", steps=[]),
                Scenario(
                    name="b",
                    url="https://example.com",
                    theme={"accent": "#00A3FF"},
                    steps=[],
                ),
            ],
        )
        config.scenarios[0].cursor = CursorConfig()
        config.scenarios[1].cursor = CursorConfig()

        apply_theme(config)

        assert config.scenarios[0].cursor.color != "#00A3FF"
        assert config.scenarios[1].cursor.color == "#00A3FF"

    # ── Shared theme: step effects inherit the same tokens ──────────────

    @staticmethod
    def _effects_config(*effects: dict[str, Any]):
        return _config(
            [Step(action="navigate", url="https://example.com", effects=list(effects))],
            theme={"accent": "#D4583A", "ink": "#0F0C08", "surface": "#FFFFFF"},
        )

    def test_effects_inherit_the_demo_theme(self) -> None:
        from demodsl.theme import apply_theme

        config = self._effects_config({"type": "notification_toast"})
        applied = apply_theme(config)
        effect = config.scenarios[0].steps[0].effects[0]

        assert (effect.color, effect.surface, effect.ink) == ("#D4583A", "#FFFFFF", "#0F0C08")
        assert any("steps[0].effects[0].surface" in path for path in applied)

    def test_only_tokens_the_effect_declares_are_written(self) -> None:
        """``spotlight`` takes no colour — theming must not invent one."""
        from demodsl.theme import apply_theme

        config = self._effects_config({"type": "spotlight"}, {"type": "cursor_trail_glow"})
        apply_theme(config)
        spotlight, trail = config.scenarios[0].steps[0].effects

        assert spotlight.color is None and spotlight.surface is None
        assert trail.color == "#D4583A"
        assert trail.surface is None  # not in cursor_trail_glow's params

    def test_palette_tokens_reach_multi_colour_effects(self) -> None:
        from demodsl.theme import apply_theme

        config = self._effects_config({"type": "morphing_background"})
        apply_theme(config)

        colors = config.scenarios[0].steps[0].effects[0].colors
        assert colors is not None and colors[0] == "#D4583A"

    def test_explicit_effect_colour_survives_theming(self) -> None:
        from demodsl.theme import apply_theme

        config = self._effects_config({"type": "glow", "color": "#00FF00"})
        apply_theme(config)

        assert config.scenarios[0].steps[0].effects[0].color == "#00FF00"

    def test_effect_outside_the_params_registry_is_skipped(self) -> None:
        """Plugin effects with no declared params must not gain stray colours."""
        from demodsl.models.effects import Effect
        from demodsl.models.theme import ThemeConfig
        from demodsl.theme import _theme_effect

        effect = Effect.model_construct(type="a-plugin-effect-with-no-params")
        assert _theme_effect(effect, ThemeConfig(accent="#D4583A"), ["#D4583A"]) == []

    def test_extraction_never_proposes_an_unreadable_accent(self) -> None:
        """A pale brand yellow on a white page is the real defect class."""
        from demodsl.theme import extract_theme

        proposal = extract_theme(
            {
                "background": "rgb(255,255,255)",
                "text_color": "rgb(17,24,39)",
                "heading_font": '"Söhne", Inter, sans-serif',
                "cta": {"background": "rgb(255,235,120)", "color": "#000", "text": "Start"},
                "palette": [{"color": "rgb(255,235,120)", "weight": 900}],
            }
        )
        assert proposal["accent_adjusted"] is True
        assert proposal["accent_contrast"] >= 3.0
        assert proposal["issues"] == []
        assert proposal["theme"].font == "Söhne"

    def test_extraction_detects_dark_mode_and_keeps_a_strong_accent(self) -> None:
        from demodsl.theme import extract_theme

        proposal = extract_theme(
            {
                "background": "rgb(11,14,20)",
                "text_color": "rgb(230,232,235)",
                "heading_font": "Inter",
                "cta": {"background": "rgb(99,102,241)", "color": "#fff", "text": "Try it"},
                "palette": [],
            }
        )
        assert proposal["mode"] == "dark"
        assert proposal["closest_preset"] == "dark-dev"
        assert proposal["accent_adjusted"] is False

    def test_neutral_buttons_are_not_mistaken_for_a_brand_colour(self) -> None:
        from demodsl.theme import extract_theme

        proposal = extract_theme(
            {
                "background": "#FFFFFF",
                "text_color": "#111111",
                "heading_font": "Georgia",
                "cta": {"background": "rgb(240,240,240)", "color": "#111", "text": "More"},
                "palette": [
                    {"color": "rgb(240,240,240)", "weight": 5000},
                    {"color": "rgb(20,120,200)", "weight": 300},
                ],
            }
        )
        assert proposal["accent_source"] == "palette"
        assert proposal["accent_raw"] == "#1478C8"

    def test_contrast_helpers(self) -> None:
        assert round(contrast_ratio("#000000", "#FFFFFF") or 0, 1) == 21.0
        assert parse_css_color("rgba(255, 90, 31, 0.5)") == (255.0, 90.0, 31.0, 0.5)
        assert parse_css_color("not-a-colour") is None


# ── Issue #21: interactive authoring session ─────────────────────────────────


class _SessionBrowser:
    """A scriptable page: locators resolve, hover on '#ghost' times out."""

    def __init__(self) -> None:
        self.url = "https://example.com"
        self.scroll_y = 0
        self.closed = False
        self.cleanups = 0
        self.navigations: list[str] = []
        self.hovered: list[str] = []

    def navigate(self, url: str) -> None:
        self.url = url
        self.navigations.append(url)

    def hover(self, locator: Locator) -> None:
        self.hovered.append(locator.value)
        if locator.value == "#ghost":
            raise TimeoutError("Page.hover: Timeout 5000ms exceeded.")

    def click(self, locator: Locator) -> None:
        self.url = "https://example.com/pricing"

    def scroll(self, direction: str, pixels: int, smooth: bool = False) -> None:
        self.scroll_y += pixels

    def evaluate_js(self, script: str) -> Any:
        if "__demodsl" in script:
            self.cleanups += 1
            return 0
        if "window.location.href" in script and "scroll" not in script:
            return self.url
        if "scrollY" in script and "url" in script:
            return {"url": self.url, "scroll_y": self.scroll_y, "scroll_x": 0}
        if script.startswith("window.scrollTo"):
            return None
        if "matches" in script:
            if "#ghost" in script:
                return {
                    "matches": 1,
                    "bbox": {"x": 100, "y": 100, "w": 200, "h": 50},
                    "visible": True,
                    "pointer_events": "none",
                }
            if "ambiguous" in script:
                return {
                    "matches": 4,
                    "bbox": {"x": 0, "y": 0, "w": 10, "h": 10},
                    "visible": True,
                    "pointer_events": "auto",
                }
            return {
                "matches": 1,
                "bbox": {"x": 1800, "y": 100, "w": 100, "h": 40},
                "visible": True,
                "pointer_events": "auto",
            }
        return None

    def screenshot(self, path: Path) -> Path:
        from PIL import Image

        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (40, 30), "white").save(path)
        return path

    def close(self) -> Path | None:
        self.closed = True
        return None


@pytest.fixture
def session():
    from demodsl.session import AuthoringSession

    browser = _SessionBrowser()
    s = AuthoringSession(
        "https://example.com", provider=browser, viewport=(1920, 1080), include_frames=False
    )
    s.open()
    yield s, browser
    s.close()


class TestIssue21AuthoringSession:
    def test_try_one_step_returns_what_the_model_needs(self, session) -> None:
        s, _ = session

        result = s.try_step({"action": "hover", "locator": {"type": "css", "value": "#cta"}})

        assert result.ok is True
        assert result.resolved_locator["matches"] == 1
        assert result.effect_anchor == {"x": 0.9635, "y": 0.1111}
        assert result.duration_s >= 0

    def test_a_failing_step_is_reported_not_raised(self, session) -> None:
        """The smallest feedback increment must not be a crashed process."""
        s, _ = session

        result = s.try_step({"action": "hover", "locator": {"type": "css", "value": "#ghost"}})

        assert result.ok is False
        assert "Timeout" in (result.error or "")
        assert s.timeline() == [], "a failed step must not enter the timeline"

    def test_warnings_flag_ambiguity_and_dead_targets(self, session) -> None:
        s, _ = session

        ambiguous = s.try_step(
            {"action": "hover", "locator": {"type": "css", "value": ".ambiguous"}}
        )
        assert any("ambiguous" in w for w in ambiguous.warnings)

        ghost = s.try_step({"action": "hover", "locator": {"type": "css", "value": "#ghost"}})
        assert any("pointer-events" in w for w in ghost.warnings)

    def test_offscreen_overlay_is_warned_before_the_render(self, session) -> None:
        s, _ = session

        result = s.try_step(
            {
                "action": "hover",
                "locator": {"type": "css", "value": "#cta"},
                "effects": [{"type": "animated_annotation", "radius": 300}],
            }
        )

        assert any("past the right edge" in w for w in result.warnings)

    def test_try_is_side_effect_scoped(self, session) -> None:
        s, browser = session
        before = browser.cleanups

        s.try_step({"action": "hover", "locator": {"type": "css", "value": "#cta"}})

        assert browser.cleanups > before, "injected effects must be torn down"

    def test_undo_reverts_the_last_step(self, session) -> None:
        s, browser = session
        s.try_step({"action": "hover", "locator": {"type": "css", "value": "#cta"}})
        s.try_step({"action": "click", "locator": {"type": "css", "value": "#cta"}})
        assert len(s.timeline()) == 2

        undone = s.undo()

        assert undone["undone"]["action"] == "click"
        assert len(s.timeline()) == 1
        assert browser.navigations[-1] == "https://example.com"

    def test_undo_on_an_empty_timeline_is_a_no_op(self, session) -> None:
        s, _ = session
        assert s.undo() == {"undone": None, "steps": 0}

    def test_commit_emits_a_replayable_config(self, session) -> None:
        s, _ = session
        s.try_step({"action": "hover", "locator": {"type": "css", "value": "#cta"}})

        config = s.commit()

        assert isinstance(config, DemoConfig)
        assert config.scenarios[0].steps[0].action == "navigate"
        assert config.scenarios[0].steps[1].action == "hover"
        # Round-trips through validation exactly as `demodsl run` would.
        assert DemoConfig(**config.model_dump(exclude_none=True))

    def test_observe_ranks_the_live_page(self, monkeypatch: pytest.MonkeyPatch, session) -> None:
        s, browser = session
        payload = {
            "viewport": {"w": 1920, "h": 1080},
            "page_height": 3000,
            "elements": [
                {
                    "tag": "h1",
                    "role": "heading",
                    "text": "Hero",
                    "locator": {"type": "css", "value": "h1"},
                    "bbox": {"x": 0, "y": 0, "w": 900, "h": 90},
                    "page_y": 0,
                    "font_px": 60,
                    "font_weight": 700,
                    "color": "#000",
                    "background": "#fff",
                    "pointer_events": "auto",
                    "in_carousel": False,
                    "is_link": False,
                }
            ],
        }
        monkeypatch.setattr(browser, "evaluate_js", lambda script: payload)

        observation = s.observe()

        assert observation["elements"][0]["mark"] == 1
        assert observation["sections"][0]["kind"] == "hero"

    def test_invalid_step_is_rejected_gracefully(self, session) -> None:
        s, _ = session
        result = s.try_step({"action": "click"})  # missing locator
        assert result.ok is False
        assert "invalid step" in (result.error or "")

    def test_expired_session_refuses_further_calls(self) -> None:
        from demodsl.session import AuthoringSession, SessionExpiredError

        s = AuthoringSession(
            "https://example.com", provider=_SessionBrowser(), ttl=-1, include_frames=False
        )
        s.open()
        with pytest.raises(SessionExpiredError):
            s.timeline()

    def test_manager_caps_open_browsers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from demodsl import session as session_mod

        monkeypatch.setattr(session_mod.AuthoringSession, "open", lambda self: {"id": self.id})
        manager = session_mod.SessionManager(max_sessions=2)
        manager.create("https://a.co", provider=_SessionBrowser())
        manager.create("https://b.co", provider=_SessionBrowser())

        with pytest.raises(RuntimeError, match="Too many open"):
            manager.create("https://c.co", provider=_SessionBrowser())

        manager.close_all()
        assert len(manager) == 0

    def test_manager_reaps_expired_sessions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from demodsl import session as session_mod

        monkeypatch.setattr(session_mod.AuthoringSession, "open", lambda self: {"id": self.id})
        manager = session_mod.SessionManager(ttl=-1, max_sessions=4)
        manager.create("https://a.co", provider=_SessionBrowser())

        assert manager.reap() == 1
        assert len(manager) == 0


# ── CLI surface for the new commands ─────────────────────────────────────────


class TestNewCommandsAreWired:
    def _runner(self):
        from typer.testing import CliRunner

        return CliRunner()

    def test_commands_are_registered(self) -> None:
        from demodsl.cli import app

        result = self._runner().invoke(app, ["--help"])
        assert result.exit_code == 0
        for command in ("observe", "qa", "eval", "theme", "session"):
            assert command in result.output

    def test_run_exposes_the_incremental_flags(self) -> None:
        # Introspect the registered options rather than the rendered --help:
        # Rich wraps help text to the terminal width, so asserting on it makes
        # the test pass on a wide terminal and fail on a narrow CI one.
        import typer

        from demodsl.cli import app

        run_cmd = typer.main.get_command(app).commands["run"]
        declared = {opt for param in run_cmd.params for opt in param.opts}
        for flag in ("--incremental", "--only-steps", "--explain-cache", "--deterministic"):
            assert flag in declared

    def test_qa_command_reports_and_can_fail_a_threshold(
        self, tmp_path: Path, defective_manifest: dict[str, Any]
    ) -> None:
        from demodsl.cli import app

        manifest = tmp_path / "run.json"
        manifest.write_text(json.dumps(defective_manifest), encoding="utf-8")

        result = self._runner().invoke(
            app,
            ["qa", "--manifest", str(manifest), "--json", str(tmp_path / "qa.json")],
        )
        assert result.exit_code == 0
        assert "overlay.offscreen" in result.output
        assert json.loads((tmp_path / "qa.json").read_text())["score"] < 1.0

        failed = self._runner().invoke(
            app, ["qa", "--manifest", str(manifest), "--fail-under", "0.99"]
        )
        assert failed.exit_code == 1

    def test_eval_command_scores_a_config(self, tmp_path: Path) -> None:
        import yaml

        from demodsl.cli import app

        path = tmp_path / "demo.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "metadata": {"title": "demo"},
                    "seed": 7,
                    "theme": "light-consumer",
                    "scenarios": [
                        {
                            "name": "s",
                            "url": "https://example.com",
                            "steps": [
                                {"action": "navigate", "url": "https://example.com"},
                                {
                                    "action": "hover",
                                    "locator": {"type": "text", "value": "Pricing"},
                                    "narration": "Clear pricing, but the trial is hidden.",
                                    "wait": 4,
                                    "effects": [{"type": "animated_annotation"}],
                                },
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._runner().invoke(app, ["eval", str(path)])
        assert result.exit_code == 0
        assert "argument_coverage" in result.output


# ── Engine-side wiring: the run manifest QA consumes ─────────────────────────


class TestRunManifestWiring:
    def test_manifest_carries_steps_overlays_and_skipped_steps(self, tmp_path: Path) -> None:
        import yaml

        from demodsl.engine import DemoEngine

        config_path = tmp_path / "demo.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "metadata": {"title": "demo"},
                    "seed": 42,
                    "theme": "dark-dev",
                    "scenarios": [
                        {
                            "name": "s",
                            "url": "https://example.com",
                            "viewport": {"width": 1920, "height": 1080},
                            "steps": [
                                {"action": "navigate", "url": "https://example.com"},
                                {
                                    "action": "hover",
                                    "locator": {"type": "text", "value": "Featured"},
                                    "narration": "The featured rail",
                                    "effects": [
                                        {
                                            "type": "animated_annotation",
                                            "target_x": 0.98,
                                            "target_y": 0.5,
                                            "radius": 120,
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        engine = DemoEngine(config_path=config_path, dry_run=True, run_cache=False)
        engine._skipped_steps = [
            {
                "index": 1,
                "action": "hover",
                "locator": "[text] Featured",
                "code": "step.locator_unreachable",
                "error": "Timeout",
            }
        ]

        manifest = engine.build_run_manifest(
            step_timestamps=[0.0, 5.0],
            narration_durations={1: 9.0},
        )

        assert manifest["seed"] == 42
        assert manifest["frame"] == {"width": 1920, "height": 1080}
        assert len(manifest["steps"]) == 2
        assert manifest["overlays"][0]["kind"] == "animated_annotation"
        assert manifest["skipped_steps"][0]["t"] == 5.0

        from demodsl.qa import analyze

        report = analyze(manifest)
        # The annotation is anchored at x=0.98 with a 120px radius → off-frame,
        # and the narration outlasts its step → both must be caught.
        assert "overlay.offscreen" in report.codes()
        assert "audio.overrun" in report.codes()
        assert "step.locator_unreachable" in report.codes()

    def test_theme_and_determinism_are_applied_at_load(self, tmp_path: Path) -> None:
        import yaml

        from demodsl.engine import DemoEngine

        config_path = tmp_path / "demo.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "metadata": {"title": "demo"},
                    "seed": 5,
                    "theme": {"accent": "#FF5A1F"},
                    "video": {"progress_bar": {"enabled": True}},
                    "scenarios": [
                        {
                            "name": "s",
                            "url": "https://example.com",
                            "cursor": {"visible": True},
                            "natural": {"jitter": 0.4},
                            "steps": [{"action": "navigate", "url": "https://example.com"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        engine = DemoEngine(
            config_path=config_path, dry_run=True, run_cache=False, deterministic=True
        )

        assert engine.config.scenarios[0].cursor.color == "#FF5A1F"
        assert engine.config.video.progress_bar.accent == "#FF5A1F"
        assert engine.config.scenarios[0].natural.jitter == 0.0
        assert engine.determinism["strict"] is True
