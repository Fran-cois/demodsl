"""Tests for the simulated human operator (``humanize:``)."""

from __future__ import annotations

import pytest

from demodsl.determinism import apply_determinism
from demodsl.humanize import build_state, get_profile, neighbour_key
from demodsl.humanize.state import HumanState
from demodsl.models import DemoConfig, HumanizeConfig


def _state(**kw) -> HumanState:
    cfg = HumanizeConfig(seed=1234, **kw)
    state = build_state(cfg)
    assert state is not None
    return state


class TestPersona:
    def test_unknown_persona_falls_back(self):
        assert get_profile("nope").name == "presenter"

    def test_fatigue_only_degrades(self):
        base = get_profile("tired_operator")
        tired = base.with_fatigue(10.0)
        assert tired.precision < base.precision
        assert tired.tempo <= base.tempo

    def test_fatigue_is_bounded(self):
        base = get_profile("tired_operator")
        assert base.with_fatigue(600.0).precision >= 0.15


class TestIntensity:
    def test_zero_intensity_disables_entirely(self):
        assert build_state(HumanizeConfig(intensity=0.0)) is None

    def test_disabled_flag(self):
        assert build_state(HumanizeConfig(enabled=False)) is None

    def test_none_and_false(self):
        assert build_state(None) is None
        assert build_state(False) is None

    def test_true_uses_defaults(self):
        state = build_state(True)
        assert state is not None
        assert state.base_profile.name == "presenter"


class TestDeterminism:
    def test_same_seed_same_stream(self):
        a, b = _state(), _state()
        for i in range(6):
            a.begin_step(i)
            b.begin_step(i)
            assert a.scroll_plan(700) == b.scroll_plan(700)
            assert a.pre_click_pause() == b.pre_click_pause()

    def test_different_seed_differs(self):
        a = build_state(HumanizeConfig(seed=1, persona="first_time_user", intensity=1.0))
        b = build_state(HumanizeConfig(seed=2, persona="first_time_user", intensity=1.0))
        assert a is not None and b is not None
        a.begin_step(0)
        b.begin_step(0)
        assert a.scroll_plan(700) != b.scroll_plan(700)

    def test_strict_mode_freezes_the_operator(self):
        cfg = DemoConfig.model_validate(
            {
                "metadata": {"title": "t"},
                "scenarios": [
                    {
                        "name": "s",
                        "url": "https://example.com",
                        "humanize": {"intensity": 0.8},
                        "steps": [{"action": "pause", "wait": 1}],
                    }
                ],
            }
        )
        report = apply_determinism(cfg, strict=True)
        assert cfg.scenarios[0].humanize.intensity == 0.0
        assert build_state(cfg.scenarios[0].humanize) is None
        assert any("humanize.intensity" in x for x in report["jitter_disabled"])

    def test_seed_is_inherited_from_config(self):
        cfg = DemoConfig.model_validate(
            {
                "metadata": {"title": "t"},
                "seed": 99,
                "scenarios": [
                    {
                        "name": "s",
                        "url": "https://example.com",
                        "humanize": {"intensity": 0.5},
                        "steps": [{"action": "pause", "wait": 1}],
                    }
                ],
            }
        )
        apply_determinism(cfg, strict=False)
        assert cfg.scenarios[0].humanize.seed is not None


class TestImperfectionBudget:
    def test_budget_is_capped(self):
        state = _state(intensity=1.0, max_imperfections=2)
        fired = 0
        for i in range(60):
            state.begin_step(i)
            fired += state.allow_imperfection(1.0)
        assert fired == 2

    def test_never_two_in_a_row(self):
        state = _state(intensity=1.0, max_imperfections=10)
        hits = []
        for i in range(40):
            state.begin_step(i)
            if state.allow_imperfection(1.0):
                hits.append(i)
        assert all(b - a >= 2 for a, b in zip(hits, hits[1:], strict=False))

    def test_critical_step_is_protected(self):
        state = _state(intensity=1.0, max_imperfections=10)
        for i in range(20):
            state.begin_step(i, critical=True)
            assert state.allow_imperfection(1.0) is False

    def test_zero_budget(self):
        state = _state(intensity=1.0, max_imperfections=0)
        state.begin_step(0)
        assert state.allow_imperfection(1.0) is False


class TestMotorParams:
    def test_scroll_plan_nets_to_the_requested_distance(self):
        state = _state(intensity=1.0)
        for i in range(20):
            state.begin_step(i)
            assert sum(state.scroll_plan(600)) == 600

    def test_scroll_plan_overshoots_then_corrects(self):
        state = _state(persona="first_time_user", intensity=1.0)
        state.begin_step(0)
        plan = state.scroll_plan(900)
        assert len(plan) > 1
        assert plan[-1] < 0, "a human scrolls past, then comes back"

    def test_sloppier_persona_overshoots_more(self):
        careful = _state(persona="presenter", intensity=1.0)
        sloppy = _state(persona="tired_operator", intensity=1.0)
        assert sloppy.cursor_params()["overshoot_max"] > careful.cursor_params()["overshoot_max"]
        assert sloppy.typo_rate() > careful.typo_rate()

    def test_typo_rate_stays_low_enough_to_be_believable(self):
        assert _state(persona="tired_operator", intensity=1.0).typo_rate() <= 0.08


class TestKeyboard:
    @pytest.mark.parametrize("layout", ["qwerty", "azerty"])
    def test_neighbour_is_adjacent_and_never_the_same(self, layout):
        rng = __import__("random").Random(0)
        for ch in "asdfghjkl":
            wrong = neighbour_key(ch, rng, layout=layout)
            assert wrong is not None
            assert wrong != ch

    def test_case_is_preserved(self):
        rng = __import__("random").Random(0)
        assert neighbour_key("S", rng).isupper()

    def test_unknown_char_returns_none(self):
        rng = __import__("random").Random(0)
        assert neighbour_key("€", rng) is None

    def test_alternating_hands_beats_same_finger(self):
        from demodsl.humanize.keyboard import bigram_factor

        alternating = bigram_factor("a", "l")  # left hand then right
        same_finger = bigram_factor("a", "q")  # same column, same finger
        assert alternating < 1.0 < same_finger

    def test_unknown_chars_cost_nothing_extra(self):
        from demodsl.humanize.keyboard import bigram_factor

        assert bigram_factor("€", "a") == 1.0


class TestKeystrokeRhythm:
    def test_delays_match_the_text_length(self):
        state = _state(intensity=0.8)
        state.begin_step(0)
        assert len(state.keystroke_delays("hello world", 0.08)) == 11

    def test_zero_intensity_is_a_metronome(self):
        state = HumanState(get_profile("presenter"), intensity=0.0, seed=1)
        assert set(state.keystroke_delays("abcdef", 0.05)) == {0.05}

    def test_rhythm_is_uneven(self):
        import statistics

        state = _state(intensity=0.9)
        state.begin_step(0)
        d = state.keystroke_delays("the quick brown fox jumps", 0.08)
        assert statistics.pstdev(d) > 0.01, "a flat rhythm reads as a machine"

    def test_symbols_and_digits_get_a_beat(self):
        state = _state(intensity=1.0)
        state.begin_step(0)
        text = "contact9@acme.com"
        d = state.keystroke_delays(text, 0.08)
        assert d[text.index("@")] > d[text.index("c")]
        assert d[text.index("9")] > d[text.index("c")]

    def test_a_long_text_contains_read_back_pauses(self):
        state = _state(intensity=1.0)
        state.begin_step(0)
        d = state.keystroke_delays("a" * 60, 0.08)
        assert max(d) > 5 * min(d), "no burst structure — nobody types 60 chars flat"

    def test_delays_are_never_absurdly_short(self):
        state = _state(intensity=1.0)
        state.begin_step(0)
        assert min(state.keystroke_delays("hello there world", 0.08)) >= 0.08 * 0.2


class TestDetour:
    def test_never_on_a_critical_step(self):
        state = _state(persona="first_time_user", intensity=1.0)
        for i in range(30):
            state.begin_step(i, critical=True)
            assert state.wants_detour() is False

    def test_never_back_to_back(self):
        state = _state(persona="first_time_user", intensity=1.0)
        hits = [i for i in range(60) if (state.begin_step(i), state.wants_detour())[1]]
        assert hits
        assert all(b - a >= 3 for a, b in zip(hits, hits[1:], strict=False))

    def test_curiosity_drives_it(self):
        curious = _state(persona="first_time_user", intensity=1.0)
        focused = _state(persona="expert_confident", intensity=1.0)

        def count(state):
            return sum((state.begin_step(i), state.wants_detour())[1] for i in range(200))

        assert count(curious) > count(focused)

    def test_off_when_disabled(self):
        state = HumanState(get_profile("first_time_user"), intensity=0.0, seed=1)
        state.begin_step(0)
        assert state.wants_detour() is False


class TestStepOverride:
    def test_step_can_opt_out(self):
        cfg = DemoConfig.model_validate(
            {
                "metadata": {"title": "t"},
                "scenarios": [
                    {
                        "name": "s",
                        "url": "https://example.com",
                        "humanize": True,
                        "steps": [
                            {"action": "pause", "wait": 1, "humanize": False},
                        ],
                    }
                ],
            }
        )
        assert cfg.scenarios[0].steps[0].humanize is False


class TestAimMiss:
    def test_lands_outside_the_element(self):
        w, h = 160.0, 44.0
        for seed in range(40):
            state = HumanizeConfig(
                seed=seed, persona="tired_operator", intensity=1.0, max_imperfections=20
            )
            s = build_state(state)
            s.begin_step(0)
            miss = s.aim_miss(w, h)
            if miss is None:
                continue
            dx, dy = miss
            assert abs(dx) > w / 2 or abs(dy) > h / 2, "a near-miss must land off the element"

    def test_stays_a_near_miss_not_a_wild_throw(self):
        seen = 0
        for seed in range(60):
            s = build_state(
                HumanizeConfig(
                    seed=seed, persona="tired_operator", intensity=1.0, max_imperfections=20
                )
            )
            s.begin_step(0)
            miss = s.aim_miss(160.0, 44.0)
            if miss is None:
                continue
            seen += 1
            dx, dy = miss
            assert abs(dx) < 160.0 and abs(dy) < 80.0
        assert seen, "the miss never fired — the test proves nothing"

    def test_is_budget_gated(self):
        state = _state(intensity=1.0, max_imperfections=1)
        fired = 0
        for i in range(40):
            state.begin_step(i)
            fired += state.aim_miss(120.0, 40.0) is not None
        assert fired == 1

    def test_never_on_a_critical_step(self):
        state = _state(intensity=1.0, max_imperfections=20)
        for i in range(20):
            state.begin_step(i, critical=True)
            assert state.aim_miss(120.0, 40.0) is None


class TestOrchestratorWiring:
    """The detour and the near-miss only run inside a real render, so their
    call signatures need a test of their own."""

    def _orch(self):
        from demodsl.effects.registry import EffectRegistry
        from demodsl.orchestrators.scenario import ScenarioOrchestrator

        cfg = DemoConfig.model_validate(
            {
                "metadata": {"title": "t"},
                "scenarios": [
                    {
                        "name": "s",
                        "url": "https://example.com",
                        "steps": [{"action": "pause", "wait": 1}],
                    }
                ],
            }
        )
        return ScenarioOrchestrator(cfg, EffectRegistry(), turbo=True)

    def _step(self):
        from demodsl.models import Step

        return Step.model_validate({"action": "click", "locator": {"type": "css", "value": "#go"}})

    def test_stray_hover_moves_the_cursor_and_fires_hover(self):
        from unittest.mock import MagicMock

        browser = MagicMock()
        browser.get_element_bbox.return_value = {
            "x": 400.0,
            "y": 400.0,
            "width": 120.0,
            "height": 40.0,
        }
        browser.evaluate_js.return_value = [520.0, 180.0]
        cursor = MagicMock()
        state = _state(persona="first_time_user", intensity=1.0)
        state.begin_step(0)

        self._orch()._stray_hover(browser, cursor, self._step(), state)

        assert browser.evaluate_js.called
        assert "mouseenter" in browser.evaluate_js.call_args[0][0]
        # Only a real pointer move applies CSS :hover.
        browser.move_mouse.assert_called_once_with(520.0, 180.0)
        cursor.move_to.assert_called_once()

    def test_stray_hover_does_nothing_when_there_is_no_neighbour(self):
        from unittest.mock import MagicMock

        browser = MagicMock()
        browser.get_element_bbox.return_value = {
            "x": 0.0,
            "y": 0.0,
            "width": 10.0,
            "height": 10.0,
        }
        browser.evaluate_js.return_value = None
        cursor = MagicMock()
        state = _state(intensity=1.0)
        state.begin_step(0)

        self._orch()._stray_hover(browser, cursor, self._step(), state)

        cursor.move_to.assert_not_called()
        browser.move_mouse.assert_not_called()

    def test_aim_miss_moves_the_cursor_off_target_before_the_click(self):
        from unittest.mock import MagicMock

        browser = MagicMock()
        browser.get_element_bbox.return_value = {
            "x": 400.0,
            "y": 400.0,
            "width": 160.0,
            "height": 44.0,
        }
        cursor = MagicMock()
        state = _state(persona="tired_operator", intensity=1.0, max_imperfections=20)
        state.begin_step(0)

        self._orch()._aim_miss(browser, cursor, self._step(), state, (480.0, 422.0))

        if cursor.move_to.called:
            _, x, y = cursor.move_to.call_args[0]
            assert (x, y) != (480.0, 422.0), "the miss must not land on the centre"

    def test_a_missing_element_is_not_fatal(self):
        from unittest.mock import MagicMock

        browser = MagicMock()
        browser.get_element_bbox.return_value = None
        cursor = MagicMock()
        state = _state(intensity=1.0)
        state.begin_step(0)

        orch = self._orch()
        orch._aim_miss(browser, cursor, self._step(), state, (10.0, 10.0))
        orch._stray_hover(browser, cursor, self._step(), state)

        cursor.move_to.assert_not_called()


class TestCamera:
    def test_the_first_framing_is_off_then_corrected(self):
        seen = 0
        for seed in range(40):
            s = build_state(HumanizeConfig(seed=seed, persona="tired_operator", intensity=1.0))
            s.begin_step(0)
            miss = s.camera_miss(1.6)
            if miss is None:
                continue
            seen += 1
            first_zoom, jitter, correction = miss
            assert first_zoom != 1.6
            assert 0.9 < first_zoom < 2.4, "the first push must stay in the same shot"
            assert jitter > 0
            assert 0.2 < correction < 0.7, "a reframe is quick, not a second move"
        assert seen, "the camera never missed — the test proves nothing"

    def test_a_move_without_zoom_still_jitters_the_origin(self):
        for seed in range(40):
            s = build_state(HumanizeConfig(seed=seed, intensity=1.0))
            s.begin_step(0)
            miss = s.camera_miss(None)
            if miss is None:
                continue
            first_zoom, jitter, _ = miss
            assert first_zoom is None
            assert jitter > 0
            return
        raise AssertionError("the camera never missed")

    def test_disabled_when_intensity_is_zero(self):
        s = HumanState(get_profile("presenter"), intensity=0.0, seed=1)
        s.begin_step(0)
        assert s.camera_miss(1.5) is None
        assert s.camera_reaction_delay() == 0.0

    def test_the_reaction_delay_stays_imperceptible(self):
        for seed in range(30):
            s = build_state(HumanizeConfig(seed=seed, persona="first_time_user", intensity=1.0))
            s.begin_step(0)
            assert 0.0 <= s.camera_reaction_delay() < 0.35

    def test_a_slower_operator_reacts_later(self):
        def mean(persona):
            total = 0.0
            for seed in range(60):
                s = build_state(HumanizeConfig(seed=seed, persona=persona, intensity=1.0))
                s.begin_step(0)
                total += s.camera_reaction_delay()
            return total / 60

        assert mean("first_time_user") > mean("expert_confident")


class TestNarrationBreathing:
    """Widening a TTS clip's internal silences, on synthetic audio."""

    def _clip(self, pauses=(400, 250, 600)):
        from pydub import AudioSegment
        from pydub.generators import Sine

        tone = Sine(440).to_audio_segment(duration=700).apply_gain(-3)
        clip = tone
        for p in pauses:
            clip += AudioSegment.silent(duration=p) + tone
        return clip

    def _state(self, **kw):
        state = _state(**kw)
        state.begin_step(0)
        return state

    def test_the_clip_gets_longer(self):
        from demodsl.orchestrators.narration import NarrationOrchestrator

        clip = self._clip()
        out = NarrationOrchestrator._breathe(clip, self._state(intensity=0.9), 0)
        assert out is not None
        assert len(out) > len(clip)

    def test_it_never_balloons_the_clip(self):
        from demodsl.orchestrators.narration import NarrationOrchestrator

        clip = self._clip(pauses=(400,) * 30)
        out = NarrationOrchestrator._breathe(clip, self._state(intensity=1.0), 0)
        assert out is not None
        assert len(out) <= len(clip) * 1.16

    def test_a_clip_without_pauses_is_left_alone(self):
        from pydub.generators import Sine

        from demodsl.orchestrators.narration import NarrationOrchestrator

        clip = Sine(440).to_audio_segment(duration=2500)
        assert NarrationOrchestrator._breathe(clip, self._state(intensity=1.0), 0) is None

    def test_replaying_a_step_reproduces_it(self):
        from demodsl.orchestrators.narration import NarrationOrchestrator

        clip = self._clip()
        state = self._state(intensity=0.9)
        a = NarrationOrchestrator._breathe(clip, state, 0)
        b = NarrationOrchestrator._breathe(clip, state, 0)
        assert len(a) == len(b)

    def test_intensity_drives_the_amount(self):
        from demodsl.orchestrators.narration import NarrationOrchestrator

        clip = self._clip(pauses=(400, 250, 600, 300, 500))
        low = NarrationOrchestrator._breathe(clip, self._state(intensity=0.3), 0)
        high = NarrationOrchestrator._breathe(clip, self._state(intensity=1.0), 0)
        assert len(high) > len(low)

    def test_no_operator_means_no_rewrite(self, tmp_path):
        from demodsl.orchestrators.narration import NarrationOrchestrator

        cfg = DemoConfig.model_validate(
            {
                "metadata": {"title": "t"},
                "scenarios": [
                    {
                        "name": "s",
                        "url": "https://example.com",
                        "steps": [{"action": "pause", "wait": 1, "narration": "Hi"}],
                    }
                ],
            }
        )
        orch = NarrationOrchestrator(cfg)
        original = {0: tmp_path / "narration_001.mp3"}
        assert orch.apply_breathing(original, object()) == original


class TestVideoFinish:
    def test_handheld_is_on_by_default_film_look_is_not(self):
        names = [n for n, _ in _state().video_finish()]
        assert names == ["handheld"]

    def test_film_look_adds_grain_and_vignette(self):
        names = [n for n, _ in _state(film_look=True).video_finish()]
        assert names == ["handheld", "film_grain", "vignette"]

    def test_can_be_turned_off(self):
        assert _state(handheld=False).video_finish() == []

    def test_steadier_hands_hold_the_frame_tighter(self):
        steady = dict(_state(persona="expert_confident", intensity=1.0).video_finish())
        shaky = dict(_state(persona="tired_operator", intensity=1.0).video_finish())
        assert shaky["handheld"]["intensity"] > steady["handheld"]["intensity"]

    def test_handheld_stays_subtle(self):
        for persona in ("expert_confident", "first_time_user", "tired_operator", "presenter"):
            params = dict(_state(persona=persona, intensity=1.0).video_finish())["handheld"]
            assert params["intensity"] <= 0.45, "a visible shake is not a handheld camera"

    def test_seed_is_stable_across_steps(self):
        state = _state()
        state.begin_step(0)
        first = dict(state.video_finish())["handheld"]["seed"]
        state.begin_step(9)
        assert dict(state.video_finish())["handheld"]["seed"] == first

    def test_is_a_registered_post_effect(self):
        from demodsl.effects.post_effects import register_all_post_effects
        from demodsl.effects.registry import EffectRegistry

        registry = EffectRegistry()
        register_all_post_effects(registry)
        assert registry.is_post_effect("handheld")


class TestOverheadAccounting:
    def _cfg(self, humanize):
        return DemoConfig.model_validate(
            {
                "metadata": {"title": "t"},
                "seed": 5,
                "scenarios": [
                    {
                        "name": "s",
                        "url": "https://example.com",
                        "humanize": humanize,
                        "steps": [
                            {"action": "navigate", "url": "https://example.com", "wait": 1},
                            {"action": "scroll", "direction": "down", "pixels": 800, "wait": 2},
                            {
                                "action": "type",
                                "locator": {"type": "css", "value": "#q"},
                                "value": "hello there",
                                "char_rate": 12,
                                "wait": 2,
                            },
                        ],
                    }
                ],
            }
        )

    def test_estimate_reports_and_adds_the_overhead(self):
        from demodsl.estimate import estimate_config

        plain = estimate_config(self._cfg(None))
        human = estimate_config(self._cfg({"persona": "first_time_user", "intensity": 0.9}))
        assert plain["humanize_seconds"] == 0.0
        assert human["humanize_seconds"] > 0.5
        assert human["total_seconds"] > plain["total_seconds"]

    def test_zero_intensity_costs_nothing(self):
        from demodsl.estimate import estimate_config

        assert estimate_config(self._cfg({"intensity": 0.0}))["humanize_seconds"] == 0.0

    def test_typing_overhead_scales_with_text_length(self):
        state = _state(persona="first_time_user", intensity=1.0)
        state.begin_step(0)
        short = state.expected_overhead("type", value_len=5, char_rate=12)
        long = state.expected_overhead("type", value_len=40, char_rate=12)
        assert long > short
