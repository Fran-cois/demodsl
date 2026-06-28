"""Tests for the reward-model honesty fixes (Phase 2).

* coverage is a graded confidence, not a 0/1 cliff;
* quality cannot be gamed by attaching an effect to every step;
* explore-first plan steps are recorded as *planned* (not executed).
"""

from __future__ import annotations

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.observation import PageObservation
from demodsl.discover.reward import score_trajectory
from demodsl.discover.trajectory import Trajectory, TrajectoryStep
from demodsl.models import Locator


def _obs() -> PageObservation:
    return PageObservation(url="https://x.test/", title="X", strategy="axtree")


def _traj(*actions: AgentAction) -> Trajectory:
    t = Trajectory(query="q", start_url="https://x.test/")
    for a in actions:
        t.add(TrajectoryStep(_obs(), a, StepResult(ok=True, action=a)))
    return t


# ── continuous coverage ────────────────────────────────────────────────────────


def test_coverage_is_graded_not_binary() -> None:
    t = _traj(AgentAction(kind="click", mark=0, locator=Locator(type="id", value="a")))
    s = score_trajectory(t, feature_reached=True, coverage=0.6)
    assert s.coverage == 0.6
    assert s.feature_reached is True


def test_coverage_falls_back_to_binary_when_absent() -> None:
    t = _traj(AgentAction(kind="click", mark=0))
    assert score_trajectory(t, feature_reached=True).coverage == 1.0
    assert score_trajectory(t, feature_reached=False).coverage == 0.0


def test_coverage_is_clamped_to_unit_interval() -> None:
    t = _traj(AgentAction(kind="click", mark=0))
    assert score_trajectory(t, coverage=2.0).coverage == 1.0
    assert score_trajectory(t, coverage=-1.0).coverage == 0.0


def test_graded_coverage_flows_into_total() -> None:
    t = _traj(AgentAction(kind="click", mark=0, locator=Locator(type="id", value="a")))
    low = score_trajectory(t, feature_reached=True, coverage=0.4)
    high = score_trajectory(t, feature_reached=True, coverage=0.95)
    assert high.total > low.total


# ── quality cannot be gamed by uniform effects ─────────────────────────────────


def test_quality_not_gamed_by_uniform_effect_hints() -> None:
    # Both trajectories attach an effect to *every* step; they differ only in
    # narration diversity and action variety. The honest score must prefer the
    # richer one — the old `effected/len` term made them tie at ~1.0.
    same = _traj(
        AgentAction(kind="click", mark=0, narration="Same.", effect_hint="spotlight"),
        AgentAction(kind="click", mark=1, narration="Same.", effect_hint="spotlight"),
        AgentAction(kind="click", mark=2, narration="Same.", effect_hint="spotlight"),
    )
    diverse = _traj(
        AgentAction(kind="click", mark=0, narration="Open pricing.", effect_hint="spotlight"),
        AgentAction(kind="scroll", direction="down", narration="Scroll to the plans."),
        AgentAction(
            kind="click", mark=2, narration="Highlight the Pro tier.", effect_hint="spotlight"
        ),
    )
    assert score_trajectory(diverse).quality > score_trajectory(same).quality


# ── explore-first steps are planned, not executed ──────────────────────────────


def test_plan_to_trajectory_marks_steps_not_executed() -> None:
    from demodsl.discover.explore import (
        DemoPlan,
        ExplorationGraph,
        PlanStep,
        SitePage,
        plan_to_trajectory,
    )

    graph = ExplorationGraph(start_url="https://x.test/")
    graph.add_page(SitePage(url="https://x.test/", title="Home"))
    plan = DemoPlan(steps=[PlanStep(action="navigate", url="https://x.test/", narration="open")])
    traj = plan_to_trajectory(plan, graph, "q")
    assert traj.steps
    assert all(not s.executed for s in traj.steps)
