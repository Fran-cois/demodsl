"""Tests for demodsl.recipe — the opinionated "good demo" house style."""

from __future__ import annotations

import pytest

from demodsl.models import DemoConfig
from demodsl.recipe import (
    MAX_WAIT,
    MIN_WAIT,
    extract_score,
    pace,
    scenario_defaults,
    video_defaults,
    walkthrough,
)


class TestPace:
    def test_empty_narration_hits_floor(self) -> None:
        assert pace(None) == MIN_WAIT
        assert pace("") == MIN_WAIT

    def test_scales_with_word_count(self) -> None:
        short = pace("Five words are spoken here.")
        long = pace(" ".join(["word"] * 30))
        assert short < long

    def test_clamped_to_max(self) -> None:
        assert pace(" ".join(["word"] * 500)) == MAX_WAIT

    def test_custom_floor(self) -> None:
        assert pace("Hi.", floor=5.0) == 5.0


class TestWalkthrough:
    BEATS = [
        {
            "locator": {"type": "css", "value": "h1"},
            "narration": "The hero promises effortless invoicing for freelancers.",
        },
        {
            "locator": {"type": "text", "value": "Start free"},
            "narration": "One clear call to action seals the pitch.",
        },
        {"locator": None, "narration": "Further proof lives below the fold."},
    ]

    def _cfg(self, **kw) -> dict:
        return walkthrough(company="Acme", url="https://acme.com", beats=self.BEATS, **kw)

    def test_output_validates(self) -> None:
        DemoConfig(**self._cfg())  # walkthrough validates too; belt & braces

    def test_camera_on_locator_beats_with_reset(self) -> None:
        steps = self._cfg()["scenarios"][0]["steps"]
        hovers = [s for s in steps if s["action"] == "hover"]
        resets = [s for s in steps if s["action"] == "camera_reset"]
        assert len(hovers) == 2  # two locator-backed beats
        assert len(resets) == 2  # one reset per framed beat
        assert all(s["camera"]["target"] == s["locator"] for s in hovers)

    def test_hero_frames_wider_than_arguments(self) -> None:
        hovers = [s for s in self._cfg()["scenarios"][0]["steps"] if s["action"] == "hover"]
        assert hovers[0]["camera"]["zoom"] < hovers[1]["camera"]["zoom"]

    def test_locatorless_beat_becomes_scroll(self) -> None:
        steps = self._cfg()["scenarios"][0]["steps"]
        scrolls = [s for s in steps if s["action"] == "scroll"]
        # locator-less beat + closing verdict scroll
        assert len(scrolls) == 2
        assert scrolls[0]["narration"] == "Further proof lives below the fold."

    def test_cta_role_gets_finale(self) -> None:
        beats = [dict(self.BEATS[0]), {**self.BEATS[1], "role": "cta"}]
        cfg = walkthrough(company="Acme", url="https://acme.com", beats=beats)
        cta = [s for s in cfg["scenarios"][0]["steps"] if s["action"] == "hover"][-1]
        types = [e["type"] for e in cta["effects"]]
        assert "zoom_pulse" in types and "callout_arrow" in types

    def test_proof_role_gets_annotation_circle(self) -> None:
        beats = [dict(self.BEATS[0]), {**self.BEATS[1], "role": "proof", "note": "STRONG PROOF"}]
        cfg = walkthrough(company="Acme", url="https://acme.com", beats=beats)
        proof = [s for s in cfg["scenarios"][0]["steps"] if s["action"] == "hover"][-1]
        ann = [e for e in proof["effects"] if e["type"] == "animated_annotation"]
        assert len(ann) == 1
        assert ann[0]["text"] == "STRONG PROOF"
        # No hard-coded coords: the orchestrator anchors to the locator at runtime.
        assert "target_x" not in ann[0]

    def test_waits_are_paced_not_fixed(self) -> None:
        steps = self._cfg()["scenarios"][0]["steps"]
        narrated = [s for s in steps if s.get("narration")]
        for s in narrated:
            assert MIN_WAIT <= s["wait"] <= MAX_WAIT

    def test_house_framing(self) -> None:
        cfg = self._cfg()
        sc = cfg["scenarios"][0]
        assert sc["viewport"] == {"width": 1920, "height": 1080}
        assert sc["natural"]["bezier_cursor"] is True
        assert sc["glow_select"]["enabled"] is True
        assert cfg["video"]["intro"]["text"] == "Acme"
        assert cfg["video"]["outro"]["cta"]
        assert cfg["video"]["transitions"]["type"] == "crossfade"

    def test_effects_budget_one_mark_per_beat(self) -> None:
        hovers = [s for s in self._cfg()["scenarios"][0]["steps"] if s["action"] == "hover"]
        for s in hovers:
            marks = [
                e
                for e in s["effects"]
                if e["type"]
                in ("spotlight", "animated_annotation", "callout_arrow", "marker_underline")
            ]
            assert len(marks) == 1

    def test_hero_gets_marker_underline(self) -> None:
        hero = [s for s in self._cfg()["scenarios"][0]["steps"] if s["action"] == "hover"][0]
        assert hero["effects"][0]["type"] == "marker_underline"

    def test_reviewer_badge_on_by_default(self) -> None:
        rev = self._cfg()["video"]["reviewer"]
        assert rev["enabled"] is True
        assert rev["company"] == "DemoBro"

    def test_reviewer_badge_override(self) -> None:
        cfg = walkthrough(
            company="Acme",
            url="https://acme.com",
            beats=self.BEATS,
            reviewer={"name": "François M.", "enabled": True},
        )
        assert cfg["video"]["reviewer"]["name"] == "François M."
        assert cfg["video"]["reviewer"]["title"] == "Senior CRO Reviewer"

    def test_live_avatar_on_by_default_bottom_right(self) -> None:
        la = self._cfg()["video"]["live_avatar"]
        assert la["enabled"] is True
        assert la["position"] == "bottom-right"

    def test_progress_bar_on_by_default(self) -> None:
        pb = self._cfg()["video"]["progress_bar"]
        assert pb["enabled"] is True
        assert pb["position"] == "top"

    def test_tiktok_short_declared_by_default(self) -> None:
        social = self._cfg()["output"]["social"]
        assert social[0]["platform"] == "tiktok"
        assert social[0]["crop_mode"] == "blur_pad"
        assert social[0]["max_duration"] == 60

    def test_shorts_opt_out(self) -> None:
        cfg = walkthrough(company="Acme", url="https://acme.com", beats=self.BEATS, shorts=False)
        assert "social" not in cfg["output"]

    def test_sentiment_drops_hand_mark(self) -> None:
        beats = [{**self.BEATS[0], "sentiment": "good"}, {**self.BEATS[1], "sentiment": "bad"}]
        cfg = walkthrough(company="Acme", url="https://acme.com", beats=beats)
        hovers = [s for s in cfg["scenarios"][0]["steps"] if s["action"] == "hover"]
        marks = [[e for e in s["effects"] if e["type"] == "hand_mark"] for s in hovers]
        assert marks[0][0]["style"] == "check"
        assert marks[1][0]["style"] == "cross"

    def test_verdict_score_is_stamped(self) -> None:
        cfg = walkthrough(
            company="Acme",
            url="https://acme.com",
            beats=self.BEATS,
            verdict="Solid page overall, scoring a 3 out of 5.",
        )
        closing = cfg["scenarios"][0]["steps"][-1]
        stamp = [e for e in closing.get("effects", []) if e["type"] == "verdict_stamp"]
        assert stamp and stamp[0]["text"] == "3/5"

    def test_no_score_no_stamp(self) -> None:
        cfg = walkthrough(
            company="Acme",
            url="https://acme.com",
            beats=self.BEATS,
            verdict="A clean and focused page.",
        )
        closing = cfg["scenarios"][0]["steps"][-1]
        assert not closing.get("effects")

    def test_intro_and_verdict_are_used(self) -> None:
        cfg = self._cfg(intro="Welcome aboard.", verdict="Solid — 4 out of 5.")
        steps = cfg["scenarios"][0]["steps"]
        assert steps[0]["narration"] == "Welcome aboard."
        assert steps[-1]["narration"] == "Solid — 4 out of 5."


class TestDefaults:
    def test_scenario_defaults_validate_inside_config(self) -> None:
        cfg = walkthrough(
            company="X",
            url="https://x.io",
            beats=[
                {
                    "locator": {"type": "css", "value": "h1"},
                    "narration": "Hello world from the hero.",
                }
            ],
        )
        assert cfg["scenarios"][0]["cursor"]["visible"] is True

    def test_video_defaults_custom_cta(self) -> None:
        v = video_defaults("X", cta="Try X now")
        assert v["outro"]["cta"] == "Try X now"

    def test_scenario_defaults_shape(self) -> None:
        d = scenario_defaults()
        assert d["provider"] == "playwright"
        assert d["natural"]["smooth_scroll"] is True


@pytest.mark.parametrize("bad_beats", [[], None])
def test_walkthrough_requires_beats(bad_beats) -> None:
    with pytest.raises(Exception):
        walkthrough(company="X", url="https://x.io", beats=bad_beats or [])


@pytest.mark.parametrize(
    "verdict,expected",
    [
        ("Overall a 4 out of 5.", "4/5"),
        ("Je mets 3,5 sur 5.", "3.5/5"),
        ("Scores an 8/10 for clarity.", "8/10"),
        ("A crisp page with no number.", None),
        (None, None),
    ],
)
def test_extract_score(verdict, expected) -> None:
    assert extract_score(verdict) == expected
