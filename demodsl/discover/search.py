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
from urllib.parse import urlsplit, urlunsplit

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.controller import WebEnvironment
from demodsl.discover.observation import (
    STRATEGY_LADDER,
    ObservationBuilder,
    PageObservation,
    Strategy,
)
from demodsl.discover.policy import HeuristicPolicy, Policy
from demodsl.discover.reward import FeatureEvaluator, TrajectoryScore, score_trajectory
from demodsl.discover.safety import ActionGuard
from demodsl.discover.trajectory import Trajectory, TrajectoryStep

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    trajectory: Trajectory
    score: TrajectoryScore
    candidates: list[Trajectory] = field(default_factory=list)
    strategy_log: list[Strategy] = field(default_factory=list)


def _normalize_url(url: str) -> str:
    """Canonicalise a URL for grounding comparisons.

    Lower-cases scheme/host, drops a trailing slash on the path and ignores the
    fragment, so ``https://Example.com/Pricing/`` and ``https://example.com/pricing``
    compare equal. Returns ``""`` for empty/relative-only inputs we can't resolve.
    """
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    # Keep query (it can select a real page), drop the fragment (same document).
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _grounded_nav_targets(observation: PageObservation) -> set[str]:
    """Normalised set of URLs the agent may legitimately navigate to.

    These are the destinations of links actually present on the page plus the
    current page itself (a reload is always allowed).
    """
    targets = {_normalize_url(observation.url)} - {""}
    for el in observation.elements:
        norm = _normalize_url(el.href)
        if norm:
            targets.add(norm)
    return targets


def _registrable_domain(url: str) -> str:
    """Best-effort registrable domain (last two labels) of *url*'s host.

    ``https://shop.example.com/x`` → ``example.com``. Good enough to keep an
    agent on the *main* site without a public-suffix list dependency.
    """
    try:
        host = urlsplit(url).netloc.lower().split(":")[0]
    except ValueError:
        return ""
    if not host:
        return ""
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _same_site(url_a: str, url_b: str) -> bool:
    da, db = _registrable_domain(url_a), _registrable_domain(url_b)
    return bool(da) and da == db


def _would_jump(action: AgentAction, observation: PageObservation) -> bool:
    """Whether *action* is a cross-page hop (an "href jump").

    A ``navigate`` always is; a ``click`` is one only when its target element is
    a link (carries an ``href``). Other actions stay on the page.
    """
    if action.kind == "navigate":
        return True
    if action.kind == "click" and action.mark is not None:
        el = observation.by_mark(action.mark)
        return bool(el and el.href)
    return False


def _is_grounded_navigation(
    url: str,
    observation: PageObservation,
    *,
    allow_external: bool = True,
    base_url: str | None = None,
) -> bool:
    """Whether *url* corresponds to a real link on the page (anti-hallucination).

    Same-document anchors (``#section``) are always allowed. Otherwise the target
    must match a captured link destination. When the page exposes **no** link
    hrefs at all (e.g. a synthetic/offline environment) grounding cannot be
    applied, so navigation is permitted to preserve backward compatibility.

    When *allow_external* is ``False`` the target must also be on the same
    registrable domain as *base_url* (the start site), so the agent does not
    wander off to third-party sites linked from the page.
    """
    raw = (url or "").strip()
    if not raw or raw.startswith("#"):
        return True
    known = _grounded_nav_targets(observation)
    has_links = any(el.href for el in observation.elements)
    # Resolve relative targets against the current page before comparing.
    target = _normalize_url(raw)
    if not target and observation.url:
        try:
            from urllib.parse import urljoin

            target = _normalize_url(urljoin(observation.url, raw))
        except ValueError:
            target = ""
    if not allow_external:
        anchor = base_url or observation.url
        if anchor and target and not _same_site(target, anchor):
            return False
    if not has_links:
        return True  # nothing to ground against — don't block (domain still checked)
    return bool(target) and target in known


def execute_action(
    env: WebEnvironment,
    action: AgentAction,
    observation_url: str,
    *,
    observation: PageObservation | None = None,
    allow_external: bool = True,
    base_url: str | None = None,
    guard: ActionGuard | None = None,
) -> StepResult:
    """Run *action* against *env*, returning a :class:`StepResult`.

    When *observation* is supplied, a ``navigate`` action is **grounded**: the
    target URL must be a link that actually exists on the page, otherwise the
    step fails (without touching the browser) so the agent re-plans instead of
    walking into a hallucinated page. With ``allow_external=False`` the target
    must also stay on the start site's registrable domain.

    When *guard* is supplied and active (authenticated session, writes not
    allowed), a destructive action (``type``, a risky ``click``, a form-submitting
    ``press_key``) fails **without touching the browser**, so the agent re-plans
    instead of firing an irreversible action on the signed-in account.
    """
    if action.kind in ("done",):
        return StepResult(
            ok=True, action=action, url_before=observation_url, url_after=observation_url
        )
    if guard is not None:
        block = guard.evaluate(action, observation)
        if block is not None:
            return StepResult(ok=False, action=action, error=block, url_before=observation_url)
    if (
        action.kind == "navigate"
        and action.url
        and observation is not None
        and not _is_grounded_navigation(
            action.url, observation, allow_external=allow_external, base_url=base_url
        )
    ):
        reason = (
            "is not a link on the page (possible hallucination)"
            if allow_external
            else "is not a same-site link on the page (off-domain or hallucinated)"
        )
        return StepResult(
            ok=False,
            action=action,
            error=f"navigate target {action.url!r} {reason}; click a real element instead",
            url_before=observation_url,
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
        max_jumps: int | None = None,
        allow_external: bool = False,
        guard: ActionGuard | None = None,
    ) -> None:
        self.policy = policy
        self.builder = builder or ObservationBuilder()
        self.evaluator = evaluator or FeatureEvaluator()
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.weights = weights
        self.max_jumps = max_jumps
        self.allow_external = allow_external
        self.guard = guard

    def run(self, env: WebEnvironment, query: str) -> SearchResult:
        start_url = _safe_url(env)
        traj = Trajectory(query=query, start_url=start_url)
        strategy: Strategy = "axtree"
        strategy_log: list[Strategy] = []
        reflection: str | None = None
        history: list[str] = []
        jumps = 0

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

            # Enforce the href-jump budget: block a cross-page action once spent.
            if self.max_jumps is not None and jumps >= self.max_jumps and _would_jump(action, obs):
                result = StepResult(
                    ok=False,
                    action=action,
                    error=f"href jump limit ({self.max_jumps}) reached; staying on this page",
                    url_before=obs.url,
                )
            else:
                result = execute_action(
                    env,
                    action,
                    obs.url,
                    observation=obs,
                    allow_external=self.allow_external,
                    base_url=start_url,
                    guard=self.guard,
                )
                if result.ok and (_would_jump(action, obs) or result.page_changed):
                    jumps += 1
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
        reached, conf = self.evaluator.reached(query, final_obs, traj)
        traj.feature_reached = reached
        traj.final_url = _safe_url(env)
        score = score_trajectory(traj, feature_reached=reached, coverage=conf, weights=self.weights)
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
        max_jumps: int | None = None,
        allow_external: bool = False,
        guard: ActionGuard | None = None,
    ) -> None:
        self.policy = policy
        self.n_rollouts = max(1, n_rollouts)
        self.builder = builder or ObservationBuilder()
        self.evaluator = evaluator or FeatureEvaluator()
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.weights = weights
        self.max_jumps = max_jumps
        self.allow_external = allow_external
        self.guard = guard

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
                max_jumps=self.max_jumps,
                allow_external=self.allow_external,
                guard=self.guard,
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
