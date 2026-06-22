"""Search controllers that drive the discovery rollout.

* :class:`GreedySearch` — a single ReAct rollout with Reflexion retries and
  **adaptive representation escalation** (start with the cheap accessibility
  tree; switch to Set-of-Marks when the policy flags ambiguity or after a miss).
* :class:`TreeSearch` — best-of-N rollouts with self-evaluation (the reward
  model ranks the candidates and keeps the best), in the spirit of *Tree Search
  for Language Model Agents*.  Higher quality, higher cost.

Both share one rollout engine so they stay behaviourally consistent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.controller import WebEnvironment
from demodsl.discover.observation import STRATEGY_LADDER, ObservationBuilder, Strategy
from demodsl.discover.policy import HeuristicPolicy, Policy
from demodsl.discover.reward import FeatureEvaluator, TrajectoryScore, score_trajectory
from demodsl.discover.trajectory import Trajectory, TrajectoryStep

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    trajectory: Trajectory
    score: TrajectoryScore
    candidates: list[Trajectory] = field(default_factory=list)
    strategy_log: list[Strategy] = field(default_factory=list)


def execute_action(env: WebEnvironment, action: AgentAction, observation_url: str) -> StepResult:
    """Run *action* against *env*, returning a :class:`StepResult`."""
    if action.kind in ("done",):
        return StepResult(
            ok=True, action=action, url_before=observation_url, url_after=observation_url
        )
    try:
        if action.kind == "navigate" and action.url:
            env.navigate(action.url)
        elif action.kind == "click" and action.locator is not None:
            env.click(action.locator)
        elif action.kind == "type" and action.locator is not None:
            env.type_text(action.locator, action.value or "")
        elif action.kind == "scroll":
            env.scroll(action.direction or "down", action.pixels or 720)
        elif action.kind == "wait_for" and action.locator is not None:
            env.wait_for(action.locator, 5.0)
        elif action.kind == "hover" and action.locator is not None:
            hover = getattr(env, "hover", None)
            if callable(hover):
                hover(action.locator)
        elif action.kind == "press_key" and action.key:
            press = getattr(env, "press_keys", None)
            if callable(press):
                press(action.key)
        else:
            return StepResult(
                ok=False,
                action=action,
                error=f"unsupported or under-specified action: {action.kind}",
                url_before=observation_url,
            )
    except Exception as exc:  # pragma: no cover - exercised via fakes that raise
        return StepResult(ok=False, action=action, error=str(exc)[:200], url_before=observation_url)
    after = ""
    try:
        after = env.current_url()
    except Exception:
        after = observation_url
    return StepResult(
        ok=True,
        action=action,
        url_before=observation_url,
        url_after=after,
        page_changed=after != observation_url,
    )


class GreedySearch:
    def __init__(
        self,
        policy: Policy,
        *,
        builder: ObservationBuilder | None = None,
        evaluator: FeatureEvaluator | None = None,
        max_steps: int = 8,
        token_budget: int = 8000,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.policy = policy
        self.builder = builder or ObservationBuilder()
        self.evaluator = evaluator or FeatureEvaluator()
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.weights = weights

    def run(self, env: WebEnvironment, query: str) -> SearchResult:
        traj = Trajectory(query=query, start_url=_safe_url(env))
        strategy: Strategy = "axtree"
        strategy_log: list[Strategy] = []
        reflection: str | None = None
        history: list[str] = []

        for _ in range(self.max_steps):
            capture = strategy == "som"
            obs = self.builder.build(
                env, query=query, strategy=strategy, capture_screenshot=capture
            )
            strategy_log.append(strategy)

            decision = self.policy.propose(query, obs, history, reflection=reflection)
            traj.usage.add(decision.usage)
            action = decision.action

            if action.kind == "done":
                traj.add(TrajectoryStep(obs, action, StepResult(ok=True, action=action)))
                break

            result = execute_action(env, action, obs.url)
            traj.add(TrajectoryStep(obs, action, result))
            history.append(action.to_summary() + (" [fail]" if not result.ok else ""))

            if not result.ok:
                reflection = (
                    f"action {action.to_summary()} failed at #{action.mark}: {result.error}"
                )
                strategy = _escalate(strategy)  # richer view may disambiguate
                continue
            reflection = None

            # Adaptive escalation: the policy asked for coordinates / was unsure.
            if action.needs_visual or action.confidence < 0.4:
                strategy = _escalate(strategy)
            else:
                strategy = "axtree"

            if action.feature_reached:
                break
            if traj.usage.total >= self.token_budget:
                logger.info("token budget reached (%d)", traj.usage.total)
                break

        final_obs = traj.last_observation()
        reached, _conf = self.evaluator.reached(query, final_obs, traj)
        traj.feature_reached = reached
        traj.final_url = _safe_url(env)
        score = score_trajectory(traj, feature_reached=reached, weights=self.weights)
        return SearchResult(trajectory=traj, score=score, strategy_log=strategy_log)


class TreeSearch:
    """Best-of-N rollouts ranked by the reward model (self-evaluation)."""

    def __init__(
        self,
        policy: Policy,
        *,
        n_rollouts: int = 3,
        builder: ObservationBuilder | None = None,
        evaluator: FeatureEvaluator | None = None,
        max_steps: int = 8,
        token_budget: int = 8000,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.policy = policy
        self.n_rollouts = max(1, n_rollouts)
        self.builder = builder or ObservationBuilder()
        self.evaluator = evaluator or FeatureEvaluator()
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.weights = weights

    def run(self, env_factory, query: str) -> SearchResult:  # type: ignore[no-untyped-def]
        """Run *n_rollouts* searches, each on a fresh env from *env_factory*.

        ``env_factory`` is a zero-arg callable returning a ready
        :class:`WebEnvironment`, so each rollout starts from the same clean
        state (tree search needs independent branches).
        """
        candidates: list[Trajectory] = []
        best: SearchResult | None = None
        for i in range(self.n_rollouts):
            policy = self._explore_variant(i)
            greedy = GreedySearch(
                policy,
                builder=self.builder,
                evaluator=self.evaluator,
                max_steps=self.max_steps,
                token_budget=self.token_budget,
                weights=self.weights,
            )
            env = env_factory()
            try:
                res = greedy.run(env, query)
            finally:
                _maybe_close(env)
            candidates.append(res.trajectory)
            if best is None or res.score.total > best.score.total:
                best = res
        assert best is not None
        best.candidates = candidates
        return best

    def _explore_variant(self, i: int) -> Policy:
        """Diversify rollouts: vary the policy's exploration per branch."""
        if isinstance(self.policy, HeuristicPolicy):
            # Vary scroll depth so branches explore different regions.
            return HeuristicPolicy(
                max_scrolls=self.policy.max_scrolls + i,
                type_text=self.policy.type_text,
            )
        from demodsl.discover.policy import LLMPolicy

        if isinstance(self.policy, LLMPolicy):
            return LLMPolicy(self.policy.llm, temperature=min(1.0, 0.2 * i))
        return self.policy


def _escalate(strategy: Strategy) -> Strategy:
    idx = STRATEGY_LADDER.index(strategy) if strategy in STRATEGY_LADDER else 0
    return STRATEGY_LADDER[min(idx + 1, len(STRATEGY_LADDER) - 1)]


def _safe_url(env: WebEnvironment) -> str:
    try:
        return env.current_url()
    except Exception:
        return ""


def _maybe_close(env: WebEnvironment) -> None:
    close = getattr(env, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # pragma: no cover
            pass
