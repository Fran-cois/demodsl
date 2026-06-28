"""Trajectory data structures shared by the search and reward modules."""

from __future__ import annotations

from dataclasses import dataclass, field

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.llm import TokenUsage
from demodsl.discover.observation import PageObservation


@dataclass
class TrajectoryStep:
    """One (observation, action, result) triple in a discovery rollout.

    ``executed`` is ``True`` for a step that actually ran against a live
    environment (the ReAct loop) and ``False`` for a step that was only
    *planned* (the explore-first mode materialises an LLM plan without executing
    it). Scoring and reports use the flag so a planned-but-not-run step is never
    reported as a successful execution.
    """

    observation: PageObservation
    action: AgentAction
    result: StepResult
    executed: bool = True


@dataclass
class Trajectory:
    """A full discovery rollout for a single query."""

    query: str
    start_url: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    feature_reached: bool = False
    final_url: str = ""

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    @property
    def actions(self) -> list[AgentAction]:
        return [s.action for s in self.steps]

    @property
    def successful_actions(self) -> list[AgentAction]:
        """Actions whose execution succeeded — the only ones safe to emit.

        A failed step (e.g. a rejected hallucinated navigation, or a click on a
        stale locator) must never become a step in the synthesised demo, or the
        rendered video would walk into a broken page.
        """
        return [s.action for s in self.steps if s.result.ok]

    def add(self, step: TrajectoryStep) -> None:
        self.steps.append(step)

    def last_observation(self) -> PageObservation | None:
        return self.steps[-1].observation if self.steps else None
