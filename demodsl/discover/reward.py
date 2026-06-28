"""Reward model: did we reach the feature, and how good is the trajectory?

The composite score blends the five criteria the user asked to optimise:

* **coverage**   — did the trajectory reach / exercise the queried feature?
* **robustness** — how stable are the emitted locators (data-testid/id > css/xpath)?
* **efficiency** — fewer steps to the feature is better.
* **cost**       — fewer tokens spent discovering is better.
* **quality**    — visual/demo quality proxy (effects + narration coverage,
                   action variety, ending on a meaningful element).

``FeatureEvaluator`` decides *coverage* either heuristically (URL/text/element
signals — used offline and as a cheap gate) or via an optional LLM judge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from demodsl.discover.llm import LLMProvider, TokenUsage
from demodsl.discover.observation import PageObservation, _keywords, locator_robustness
from demodsl.discover.trajectory import Trajectory

logger = logging.getLogger(__name__)

#: Default score weights (sum = 1.0).
DEFAULT_WEIGHTS: dict[str, float] = {
    "coverage": 0.45,
    "robustness": 0.2,
    "efficiency": 0.15,
    "cost": 0.1,
    "quality": 0.1,
}


@dataclass
class TrajectoryScore:
    coverage: float = 0.0
    robustness: float = 0.0
    efficiency: float = 0.0
    cost: float = 0.0
    quality: float = 0.0
    total: float = 0.0
    feature_reached: bool = False
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def as_dict(self) -> dict[str, float]:
        return {
            "coverage": round(self.coverage, 4),
            "robustness": round(self.robustness, 4),
            "efficiency": round(self.efficiency, 4),
            "cost": round(self.cost, 4),
            "quality": round(self.quality, 4),
            "total": round(self.total, 4),
        }


class FeatureEvaluator:
    """Decides whether the queried feature was reached.

    With no ``judge`` LLM this is a fast, deterministic heuristic over the final
    observation; pass an :class:`LLMProvider` to add a confirmatory LLM vote.
    """

    def __init__(self, judge: LLMProvider | None = None) -> None:
        self.judge = judge
        self.usage = TokenUsage()

    def reached(
        self, query: str, observation: PageObservation | None, trajectory: Trajectory
    ) -> tuple[bool, float]:
        if observation is None:
            return False, 0.0

        signal = self._heuristic_signal(query, observation, trajectory)
        if self.judge is None:
            return signal >= 0.5, signal

        verdict = self._llm_vote(query, observation)
        # Average the heuristic confidence with the LLM's binary vote.
        conf = 0.5 * signal + 0.5 * (1.0 if verdict else 0.0)
        return conf >= 0.5, conf

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _heuristic_signal(
        query: str, observation: PageObservation, trajectory: Trajectory
    ) -> float:
        kws = _keywords(query)
        if not kws:
            return 0.5 if trajectory.n_steps else 0.0

        haystack = (observation.text + " " + observation.url + " " + observation.title).lower()
        url_title = (observation.url + " " + observation.title).lower()

        text_hits = sum(1 for k in kws if k in haystack)
        url_hits = sum(1 for k in kws if k in url_title)
        # Did the agent act on a relevant element and self-report success?
        acted_relevant = any(s.action.feature_reached and s.result.ok for s in trajectory.steps)

        score = 0.0
        score += 0.5 * (text_hits / len(kws))
        score += 0.3 * min(1.0, url_hits)
        score += 0.2 * (1.0 if acted_relevant else 0.0)
        return min(1.0, score)

    def _llm_vote(self, query: str, observation: PageObservation) -> bool:  # pragma: no cover
        system = (
            "You judge whether a web page now shows or exercises the feature a "
            "user asked for. Answer strictly 'YES' or 'NO'."
        )
        user = f"QUERY: {query}\n\nPAGE:\n{observation.text}\n\nIs the feature visible? YES/NO."
        resp = self.judge.complete(system, user, max_tokens=4)
        self.usage.add(resp.usage)
        return resp.text.strip().upper().startswith("Y")


def _efficiency_score(n_steps: int, *, ideal: int = 3, cap: int = 12) -> float:
    """1.0 at <=ideal steps, decaying linearly to 0 at *cap* steps."""
    if n_steps <= ideal:
        return 1.0
    if n_steps >= cap:
        return 0.0
    return 1.0 - (n_steps - ideal) / (cap - ideal)


def _cost_score(tokens: int, *, budget: int = 6000) -> float:
    """1.0 when free, decaying to 0 at the *budget*."""
    if tokens <= 0:
        return 1.0
    return max(0.0, 1.0 - tokens / budget)


def _quality_score(trajectory: Trajectory) -> float:
    """Visual/demo-quality proxy built from signals the policy cannot trivially max.

    Deliberately omits the old "fraction of steps carrying an ``effect_hint``"
    term: the heuristic policy attaches an effect to *every* click/type, so that
    term was ~1.0 by construction (reward hacking — the policy emitted exactly
    what the reward paid for). Instead we reward narration *coverage* and
    *diversity* (distinct, non-boilerplate narrations), action variety, and
    ending on a concrete element — none of which a one-line policy maxes for free.
    """
    if not trajectory.steps:
        return 0.0
    acts = trajectory.actions
    narrations = [a.narration.strip() for a in acts if a.narration and a.narration.strip()]
    narrated = len(narrations) / len(acts)
    diversity = (len(set(narrations)) / len(narrations)) if narrations else 0.0
    variety = len({a.kind for a in acts})
    ends_on_element = bool(trajectory.steps[-1].action.mark is not None)
    score = 0.0
    score += 0.35 * narrated
    score += 0.25 * diversity
    score += 0.25 * min(1.0, variety / 3)
    score += 0.15 * (1.0 if ends_on_element else 0.0)
    return min(1.0, score)


def score_trajectory(
    trajectory: Trajectory,
    *,
    feature_reached: bool | None = None,
    coverage: float | None = None,
    weights: dict[str, float] | None = None,
) -> TrajectoryScore:
    """Compute the composite :class:`TrajectoryScore` for *trajectory*.

    ``coverage`` is the *graded* confidence (in ``[0, 1]``) that the feature was
    reached — pass the evaluator's confidence so a near-miss and a clear hit do
    not collapse onto the same 0/1 cliff. When omitted, coverage falls back to
    the binary verdict (``1.0`` reached / ``0.0`` not).
    """
    w = dict(weights or DEFAULT_WEIGHTS)
    reached = trajectory.feature_reached if feature_reached is None else feature_reached

    cov = coverage if coverage is not None else (1.0 if reached else 0.0)
    cov = max(0.0, min(1.0, cov))
    # Mean robustness of locators actually used in click/type/wait steps.
    used = [
        a.locator
        for a in trajectory.actions
        if a.kind in ("click", "type", "wait_for", "hover") and a.locator is not None
    ]
    robustness = sum(locator_robustness(loc) for loc in used) / len(used) if used else 0.0
    efficiency = _efficiency_score(trajectory.n_steps)
    cost = _cost_score(trajectory.usage.total)
    quality = _quality_score(trajectory)

    total = (
        w["coverage"] * cov
        + w["robustness"] * robustness
        + w["efficiency"] * efficiency
        + w["cost"] * cost
        + w["quality"] * quality
    )
    return TrajectoryScore(
        coverage=cov,
        robustness=robustness,
        efficiency=efficiency,
        cost=cost,
        quality=quality,
        total=total,
        feature_reached=reached,
        weights=w,
    )
