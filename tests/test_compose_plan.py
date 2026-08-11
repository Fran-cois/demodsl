import pytest

from demodsl.compose_plan import (
    MAX_WORTHWHILE_COVERAGE,
    coverage_ratio,
    is_worthwhile,
    merge_effect_windows,
    plan_windows,
    shift_effects,
)

FX = [{"type": "zoom", "startTime": 0.0, "endTime": 1.0}]


class TestPlanWindows:
    def test_no_effects_is_a_single_passthrough(self):
        assert plan_windows([], 30.0) == [(0.0, 30.0, None)]

    def test_zero_duration_plans_nothing(self):
        assert plan_windows([(0.0, 1.0, FX)], 0.0) == []

    def test_windows_cover_the_whole_timeline_without_gaps(self):
        plan = plan_windows([(10.0, 12.0, FX), (20.0, 22.0, FX)], 30.0)
        assert plan[0][0] == 0.0
        assert plan[-1][1] == 30.0
        for (_, prev_end, _), (next_start, _, _) in zip(plan, plan[1:]):
            assert prev_end == next_start

    def test_only_effect_windows_are_marked_for_rendering(self):
        plan = plan_windows([(10.0, 12.0, FX)], 30.0)
        assert plan == [(0.0, 10.0, None), (10.0, 12.0, FX), (12.0, 30.0, None)]

    def test_a_single_effect_no_longer_rasterises_everything(self):
        """One effect on a twelve-step demo used to send the whole clip to Chrome."""
        plan = plan_windows([(50.0, 53.0, FX)], 120.0)
        assert coverage_ratio(plan, 120.0) == pytest.approx(3 / 120)

    def test_effects_are_clamped_to_the_timeline(self):
        plan = plan_windows([(-5.0, 3.0, FX), (28.0, 99.0, FX)], 30.0)
        assert plan[0] == (0.0, 3.0, FX)
        assert plan[-1][1] == 30.0

    def test_effects_covering_everything_yield_one_window(self):
        plan = plan_windows([(0.0, 30.0, FX)], 30.0)
        assert plan == [(0.0, 30.0, FX)]


class TestMerging:
    def test_overlapping_windows_merge(self):
        merged = merge_effect_windows([(0.0, 5.0, FX), (4.0, 8.0, FX)], 30.0)
        assert len(merged) == 1
        assert merged[0][:2] == (0.0, 8.0)

    def test_a_gap_too_short_to_split_is_absorbed(self):
        merged = merge_effect_windows([(0.0, 5.0, FX), (5.5, 8.0, FX)], 30.0, min_gap=1.5)
        assert len(merged) == 1

    def test_a_wide_enough_gap_is_kept(self):
        merged = merge_effect_windows([(0.0, 5.0, FX), (9.0, 12.0, FX)], 30.0, min_gap=1.5)
        assert len(merged) == 2

    def test_empty_effect_lists_are_ignored(self):
        assert merge_effect_windows([(1.0, 2.0, [])], 30.0) == []


class TestWorthwhile:
    def test_sparse_effects_are_worth_windowing(self):
        assert is_worthwhile(plan_windows([(10.0, 12.0, FX)], 60.0), 60.0)

    def test_dense_effects_are_not(self):
        plan = plan_windows([(0.0, 28.0, FX)], 30.0)
        assert not is_worthwhile(plan, 30.0)

    def test_coverage_never_exceeds_one(self):
        assert coverage_ratio([(0.0, 99.0, FX)], 30.0) == 1.0

    def test_threshold_is_a_ratio(self):
        assert 0 < MAX_WORTHWHILE_COVERAGE < 1


class TestShiftEffects:
    def test_timestamps_are_rebased_to_the_window(self):
        shifted = shift_effects([{"type": "zoom", "startTime": 10.0, "endTime": 12.0}], 10.0)
        assert shifted[0]["startTime"] == 0.0
        assert shifted[0]["endTime"] == 2.0

    def test_never_goes_negative(self):
        shifted = shift_effects([{"startTime": 1.0}], 5.0)
        assert shifted[0]["startTime"] == 0.0

    def test_non_numeric_fields_are_untouched(self):
        shifted = shift_effects([{"type": "zoom", "startTime": None}], 5.0)
        assert shifted[0] == {"type": "zoom", "startTime": None}

    def test_input_is_not_mutated(self):
        original = [{"startTime": 10.0}]
        shift_effects(original, 10.0)
        assert original[0]["startTime"] == 10.0
