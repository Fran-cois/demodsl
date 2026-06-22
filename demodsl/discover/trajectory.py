"""Trajectory data structures shared by the search and reward modules."""

from __future__ import annotations

from dataclasses import dataclass, field

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.llm import TokenUsage
from demodsl.discover.observation import PageObservation


@dataclass
class TrajectoryStep:
    """One (observation, action, result) triple in a discovery rollout."""

    observation: PageObservation
    action: AgentAction
    result: StepResult


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

    def add(self, step: TrajectoryStep) -> None:
        self.steps.append(step)

    def last_observation(self) -> PageObservation | None:
        return self.steps[-1].observation if self.steps else None
