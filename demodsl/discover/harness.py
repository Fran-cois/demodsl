"""Top-level discovery harness orchestrator.

Wires the pieces together:

    open env (auth) → search (greedy | tree) → evaluate → synthesise → verify

and returns a :class:`DiscoveryResult` carrying the validated config, the
trajectory, the composite score, and (optionally) the rendered video path.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from demodsl.discover.controller import BrowserController, WebEnvironment
from demodsl.discover.llm import LLMProvider, LLMProviderFactory
from demodsl.discover.observation import ObservationBuilder
from demodsl.discover.persona import (
    Persona,
    PersonaPolicy,
    PersonaReport,
    build_persona_report,
    coerce_persona,
)
from demodsl.discover.policy import HeuristicPolicy, LLMPolicy, Policy
from demodsl.discover.reward import FeatureEvaluator, TrajectoryScore
from demodsl.discover.safety import ActionGuard
from demodsl.discover.search import GreedySearch, SearchResult, TreeSearch, _maybe_close
from demodsl.discover.synthesize import synthesize_config
from demodsl.discover.trajectory import Trajectory
from demodsl.models import BrowserAuthConfig, DemoConfig

logger = logging.getLogger(__name__)

EnvFactory = Callable[[], WebEnvironment]

#: Version of the discovery harness itself (independent of the DemoDSL package
#: version). Bump when the discovery behaviour/output format changes.
HARNESS_VERSION = "1.1"


@dataclass
class DiscoveryConfig:
    """Tuning knobs for a discovery run (search depth, budgets, safety).

    Grouping these here keeps :meth:`DiscoveryHarness.__init__` small and gives
    the defaults a single home (they were previously repeated across both
    ``__init__`` and ``build``).
    """

    tree_search: bool = False
    n_rollouts: int = 3
    max_steps: int = 8
    token_budget: int = 8000
    weights: dict[str, float] | None = None
    max_jumps: int | None = None
    allow_external: bool = False
    allow_writes: bool = False
    explore_first: bool = False
    max_pages: int = 8
    max_depth: int = 2
    live_pricing: bool = False


@dataclass
class _DemoIdentity:
    """Unique identity for a generated demo: creation time + short content hash."""

    stem: str  # e.g. "discovered_demo_20260627-153012_a1b2c3d4"
    created_at: str  # ISO-8601 local timestamp (seconds precision)
    demo_id: str  # 8-char hex hash


def _make_demo_identity(query: str, url: str) -> _DemoIdentity:
    """Build a time- and content-stamped identity for the generated demo files."""
    now = datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    demo_id = hashlib.sha1(
        f"{url}|{query}|{now.isoformat()}".encode(), usedforsecurity=False
    ).hexdigest()[:8]
    return _DemoIdentity(
        stem=f"discovered_demo_{stamp}_{demo_id}",
        created_at=now.isoformat(timespec="seconds"),
        demo_id=demo_id,
    )


def _log_run_command(config_path: Path, out_dir: Path) -> None:
    """Log, at INFO, the command to render the freshly discovered demo."""
    logger.info("Discovered demo written to %s", config_path)
    logger.info("Run it with: demodsl run %s -o %s --force", config_path, out_dir)


@dataclass
class DiscoveryResult:
    query: str
    start_url: str
    trajectory: Trajectory
    score: TrajectoryScore
    config: DemoConfig
    config_dict: dict[str, Any]
    strategy_log: list[str] = field(default_factory=list)
    candidates: list[Trajectory] = field(default_factory=list)
    config_path: Path | None = None
    video_path: Path | None = None
    persona_report: PersonaReport | None = None

    @property
    def yaml_text(self) -> str:
        return yaml.safe_dump(self.config_dict, sort_keys=False, allow_unicode=True)

    def summary(self) -> str:
        s = self.score
        base = (
            f"query={self.query!r} reached={s.feature_reached} "
            f"steps={self.trajectory.n_steps} tokens={self.trajectory.usage.total} "
            f"score={s.total:.3f} (cov={s.coverage:.2f} rob={s.robustness:.2f} "
            f"eff={s.efficiency:.2f} cost={s.cost:.2f} qual={s.quality:.2f})"
        )
        if self.persona_report is not None:
            base += "\n" + self.persona_report.summary()
        return base


class DiscoveryHarness:
    def __init__(
        self,
        policy: Policy,
        *,
        builder: ObservationBuilder | None = None,
        evaluator: FeatureEvaluator | None = None,
        persona: Persona | None = None,
        config: DiscoveryConfig | None = None,
    ) -> None:
        self.policy = policy
        self.builder = builder or ObservationBuilder()
        self.evaluator = evaluator or FeatureEvaluator()
        self.persona = persona
        cfg = config or DiscoveryConfig()
        self.config = cfg
        # Flatten the tuning knobs onto self for terse internal access.
        self.tree_search = cfg.tree_search
        self.n_rollouts = cfg.n_rollouts
        self.max_steps = cfg.max_steps
        self.token_budget = cfg.token_budget
        self.weights = cfg.weights
        self.max_jumps = cfg.max_jumps
        self.allow_external = cfg.allow_external
        self.explore_first = cfg.explore_first
        self.max_pages = cfg.max_pages
        self.max_depth = cfg.max_depth
        self.live_pricing = cfg.live_pricing
        self.allow_writes = cfg.allow_writes
        if persona is not None and self.tree_search:
            # A persona models *one* user's experience; best-of-N optimisation
            # contradicts that goal, so we run a single faithful rollout.
            logger.info("persona run: forcing greedy search (tree search disabled)")
            self.tree_search = False

    # ── construction helpers ──────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        *,
        policy: str = "llm",
        model: str = "gpt-4o",
        llm_backend: str = "openai",
        llm_provider: LLMProvider | None = None,
        judge: bool = False,
        token_budget: int = 8000,
        observation_budget: int = 1024,
        max_elements: int = 60,
        max_steps: int = 8,
        tree_search: bool = False,
        n_rollouts: int = 3,
        weights: dict[str, float] | None = None,
        persona: Persona | str | dict | None = None,
        persona_traits: dict[str, float] | None = None,
        max_jumps: int | None = None,
        allow_external: bool = False,
        explore_first: bool = False,
        max_pages: int = 8,
        max_depth: int = 2,
        live_pricing: bool = False,
        allow_writes: bool = False,
    ) -> DiscoveryHarness:
        """Construct a harness from simple options.

        ``policy='heuristic'`` builds the fully-offline deterministic agent;
        ``policy='llm'`` wires an :class:`LLMProvider` (default OpenAI).

        When ``persona`` is set (a :class:`Persona`, a free-text description, or
        a kwargs dict) the chosen base policy is wrapped in a
        :class:`~demodsl.discover.persona.PersonaPolicy`, so discovery
        reproduces that user's reflexes and effort instead of the optimal path.
        ``persona_traits`` overrides inferred trait values (patience,
        tech_savviness, thoroughness, confidence).
        """
        builder = ObservationBuilder(token_budget=observation_budget, max_elements=max_elements)
        if policy == "heuristic":
            pol: Policy = HeuristicPolicy()
            judge_llm: LLMProvider | None = None
        else:
            provider = llm_provider or LLMProviderFactory.create(llm_backend, model=model)
            pol = LLMPolicy(provider)
            judge_llm = provider if judge else None
        evaluator = FeatureEvaluator(judge=judge_llm)

        persona_obj: Persona | None = None
        if persona is not None:
            persona_obj = coerce_persona(persona, **(persona_traits or {}))
            pol = PersonaPolicy(persona_obj, base=pol)

        return cls(
            pol,
            builder=builder,
            evaluator=evaluator,
            persona=persona_obj,
            config=DiscoveryConfig(
                tree_search=tree_search,
                n_rollouts=n_rollouts,
                max_steps=max_steps,
                token_budget=token_budget,
                weights=weights,
                max_jumps=max_jumps,
                allow_external=allow_external,
                allow_writes=allow_writes,
                explore_first=explore_first,
                max_pages=max_pages,
                max_depth=max_depth,
                live_pricing=live_pricing,
            ),
        )

    # ── main entrypoint ───────────────────────────────────────────────────

    def discover(
        self,
        *,
        url: str,
        query: str,
        provider: str = "playwright",
        auth: BrowserAuthConfig | None = None,
        login: dict[str, Any] | None = None,
        env_factory: EnvFactory | None = None,
        verify: bool = False,
        output_dir: str | Path = "output",
        verify_turbo: bool = True,
        verify_skip_voice: bool = False,
        write_yaml: bool = True,
    ) -> DiscoveryResult:
        factory = env_factory or self._live_factory(url, provider, auth)
        if self.explore_first:
            return self._discover_explore_first(
                url=url,
                query=query,
                provider=provider,
                auth=auth,
                login=login,
                factory=factory,
                verify=verify,
                output_dir=output_dir,
                verify_turbo=verify_turbo,
                verify_skip_voice=verify_skip_voice,
                write_yaml=write_yaml,
            )
        if isinstance(self.policy, PersonaPolicy):
            self.policy.reset()
        guard = ActionGuard(authenticated=auth is not None, allow_writes=self.allow_writes)
        search_res = self._run_search(factory, query, guard=guard)
        traj = search_res.trajectory

        persona_report: PersonaReport | None = None
        if self.persona is not None and isinstance(self.policy, PersonaPolicy):
            # The persona "reaches" the feature only if *she* actually acted on
            # it — not if the omniscient observation merely contained it. Rebase
            # the verdict (and the score) on her lived experience so the summary
            # stays consistent with what she did.
            from demodsl.discover.reward import score_trajectory

            st = self.policy.state
            traj.feature_reached = st.satisfied
            search_res.score = score_trajectory(
                traj, feature_reached=st.satisfied, weights=self.weights
            )
            persona_report = build_persona_report(
                self.persona, query, state=st, reached=st.satisfied
            )

        # Narration is written in the persona's voice, so render it with a
        # matching TTS language (French reflections shouldn't be read in English).
        voice_id = self.persona.language if self.persona is not None else "en"
        identity = _make_demo_identity(query, traj.start_url or url)
        config, config_dict = synthesize_config(
            query,
            traj,
            provider=provider,
            auth=auth,
            login=login,
            voice_id=voice_id,
            feature_reached=traj.feature_reached,
            filename=f"{identity.stem}.mp4",
        )

        out_dir = Path(output_dir)
        config_path: Path | None = None
        video_path: Path | None = None
        report = self._exploration_report(
            query=query,
            start_url=traj.start_url or url,
            trajectory=traj,
            score=search_res.score,
            strategy_log=search_res.strategy_log,
            created_at=identity.created_at,
            demo_id=identity.demo_id,
        )
        return self._finalize(
            query=query,
            start_url=traj.start_url or url,
            trajectory=traj,
            score=search_res.score,
            config=config,
            config_dict=config_dict,
            report=report,
            identity=identity,
            strategy_log=list(search_res.strategy_log),
            output_dir=output_dir,
            write_yaml=write_yaml,
            verify=verify,
            verify_turbo=verify_turbo,
            verify_skip_voice=verify_skip_voice,
            candidates=search_res.candidates,
            persona_report=persona_report,
        )

    # ── internals ─────────────────────────────────────────────────────────

    def _plan_provider(self) -> LLMProvider | None:
        """The LLM provider that should *pick* the demo (None ⇒ heuristic pick)."""
        policy: Policy = self.policy
        if isinstance(policy, PersonaPolicy):
            policy = policy.base
        if isinstance(policy, LLMPolicy):
            return policy.llm
        return None

    def _finalize(
        self,
        *,
        query: str,
        start_url: str,
        trajectory: Trajectory,
        score: TrajectoryScore,
        config: DemoConfig,
        config_dict: dict[str, Any],
        report: str,
        identity: _DemoIdentity,
        strategy_log: list[str],
        output_dir: str | Path,
        write_yaml: bool,
        verify: bool,
        verify_turbo: bool,
        verify_skip_voice: bool,
        candidates: list[Trajectory] | None = None,
        persona_report: PersonaReport | None = None,
        extra_artifacts: dict[str, str] | None = None,
    ) -> DiscoveryResult:
        """Write the YAML (+ any *extra_artifacts*), optionally render, build result.

        Shared tail of both the ReAct (:meth:`discover`) and explore-first
        (:meth:`_discover_explore_first`) paths so the two stay behaviourally
        identical. *extra_artifacts* maps a filename suffix (e.g. ``"graph.json"``)
        to its text content, written alongside ``<stem>.yaml``.
        """
        out_dir = Path(output_dir)
        config_path: Path | None = None
        video_path: Path | None = None
        if write_yaml or verify:
            from demodsl.discover.verify import write_config_yaml

            out_dir.mkdir(parents=True, exist_ok=True)
            config_path = write_config_yaml(
                config_dict, out_dir / f"{identity.stem}.yaml", header_comment=report
            )
            for suffix, content in (extra_artifacts or {}).items():
                (out_dir / f"{identity.stem}.{suffix}").write_text(content, encoding="utf-8")
            _log_run_command(config_path, out_dir)
        if verify:
            from demodsl.discover.verify import verify_config

            video_path = verify_config(
                config_dict,
                out_dir,
                config_path=config_path,
                turbo=verify_turbo,
                skip_voice=verify_skip_voice,
                header_comment=report,
            )
        return DiscoveryResult(
            query=query,
            start_url=start_url,
            trajectory=trajectory,
            score=score,
            config=config,
            config_dict=config_dict,
            strategy_log=list(strategy_log),
            candidates=candidates or [],
            config_path=config_path,
            video_path=video_path,
            persona_report=persona_report,
        )

    def _discover_explore_first(
        self,
        *,
        url: str,
        query: str,
        provider: str,
        auth: BrowserAuthConfig | None,
        login: dict[str, Any] | None,
        factory: EnvFactory,
        verify: bool,
        output_dir: str | Path,
        verify_turbo: bool,
        verify_skip_voice: bool,
        write_yaml: bool,
    ) -> DiscoveryResult:
        """Two-phase mode: deterministic crawl → graph → LLM picks the demo."""
        from demodsl.discover.explore import (
            crawl_site,
            destination_observation,
            plan_demo_from_graph,
            plan_to_trajectory,
        )
        from demodsl.discover.reward import score_trajectory

        identity = _make_demo_identity(query, url)
        env = factory()
        try:
            graph = crawl_site(
                env,
                start_url=url,
                max_pages=self.max_pages,
                max_depth=self.max_depth,
                allow_external=self.allow_external,
            )
        finally:
            _maybe_close(env)

        plan = plan_demo_from_graph(
            graph, query, llm=self._plan_provider(), max_steps=self.max_steps
        )
        guard = ActionGuard(authenticated=auth is not None, allow_writes=self.allow_writes)
        traj = plan_to_trajectory(plan, graph, query, guard=guard)
        traj.usage.add(plan.usage)
        # Grade coverage on real captured evidence (the destination page's title,
        # headings and elements), not the planner's self-asserted feature_reached.
        dest_obs = destination_observation(plan, graph)
        reached, conf = self.evaluator.reached(query, dest_obs, traj)
        traj.feature_reached = reached
        score = score_trajectory(traj, feature_reached=reached, coverage=conf, weights=self.weights)

        config, config_dict = synthesize_config(
            query,
            traj,
            provider=provider,
            auth=auth,
            login=login,
            feature_reached=traj.feature_reached,
            filename=f"{identity.stem}.mp4",
        )

        report = self._exploration_report(
            query=query,
            start_url=graph.start_url or url,
            trajectory=traj,
            score=score,
            strategy_log=["explore→plan"],
            created_at=identity.created_at,
            demo_id=identity.demo_id,
            extra_lines=[
                f"  crawl: {graph.n_pages} pages · {len(graph.edges)} links"
                f" · max_pages: {self.max_pages} · max_depth: {self.max_depth}",
                f"  plan_rationale: {plan.rationale}" if plan.rationale else "",
            ],
        )
        import json as _json

        return self._finalize(
            query=query,
            start_url=graph.start_url or url,
            trajectory=traj,
            score=score,
            config=config,
            config_dict=config_dict,
            report=report,
            identity=identity,
            strategy_log=["explore→plan"],
            output_dir=output_dir,
            write_yaml=write_yaml,
            verify=verify,
            verify_turbo=verify_turbo,
            verify_skip_voice=verify_skip_voice,
            extra_artifacts={
                "graph.json": _json.dumps(graph.to_dict(), indent=2, ensure_ascii=False)
            },
        )

    def _policy_descriptor(self) -> str:
        """Describe the acting policy, including the LLM backend/model if any.

        Unwraps a :class:`PersonaPolicy` to its base, then reports the LLM
        provider name and model when the policy is LLM-driven (the data is only
        present for cloud/simulated backends); otherwise reports the rule engine.
        """
        policy: Policy = self.policy
        persona_prefix = ""
        if isinstance(policy, PersonaPolicy):
            persona_prefix = "persona+"
            policy = policy.base
        if isinstance(policy, LLMPolicy):
            provider = policy.llm
            name = getattr(provider, "name", "llm")
            model = getattr(provider, "model", None)
            desc = f"llm:{name}" + (f"/{model}" if model else "")
        elif isinstance(policy, HeuristicPolicy):
            desc = "heuristic"
        else:
            desc = type(policy).__name__
        return persona_prefix + desc

    def _active_model(self) -> str | None:
        """The model id of the acting LLM provider (None for heuristic policy)."""
        policy: Policy = self.policy
        if isinstance(policy, PersonaPolicy):
            policy = policy.base
        if isinstance(policy, LLMPolicy):
            return getattr(policy.llm, "model", None)
        return None

    def _cost_line(self, trajectory: Trajectory) -> str:
        """The estimated-USD-cost report line, or ``""`` when not applicable.

        Only emitted for LLM runs (the offline heuristic policy is free). When
        the model has no known price, a hint about the override env vars is
        shown instead of a bogus number.
        """
        model = self._active_model()
        if not model:
            return ""  # heuristic / no LLM → no cost to report
        from demodsl.discover.pricing import estimate_cost, lookup_price

        live = self.live_pricing or os.environ.get("DEMODSL_OPENROUTER_PRICING", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        usage = trajectory.usage
        cost = estimate_cost(model, usage.prompt_tokens, usage.completion_tokens, live=live)
        if cost is None:
            return (
                f"  estimated_cost: n/a — no price for {model!r} "
                "(set DEMODSL_LLM_PRICE_INPUT/OUTPUT, USD per 1M tokens)"
            )
        price = lookup_price(model, live=live)
        source = "openrouter" if live and price is not None else "estimate"
        rate = (
            f" (model {model}, ${price.input_per_1m:g}/${price.output_per_1m:g} per 1M tokens"
            f", {source})"
            if price is not None
            else f" ({source})"
        )
        return f"  estimated_cost: ${cost:.6f} USD{rate}"

    def _exploration_report(
        self,
        *,
        query: str,
        start_url: str,
        trajectory: Trajectory,
        score: TrajectoryScore,
        strategy_log: list[str],
        extra_lines: list[str] | None = None,
        created_at: str | None = None,
        demo_id: str | None = None,
    ) -> str:
        """A human-readable exploration report, embedded as YAML comments.

        Captures the harness version and what discovery actually did (query,
        outcome, href jumps, per-step trace) so the generated config is
        self-documenting.
        """
        from demodsl import __version__ as _pkg_version

        jumps = sum(
            1
            for s in trajectory.steps
            if s.result.ok and (s.action.kind == "navigate" or s.result.page_changed)
        )
        pages = []
        for s in trajectory.steps:
            after = s.result.url_after
            if after and after not in pages:
                pages.append(after)
        repr_path = " → ".join(dict.fromkeys(strategy_log)) or "axtree"
        lines = [
            f"DemoDSL discovery harness v{HARNESS_VERSION} (demodsl {_pkg_version})",
            "Exploration report",
            f"  query: {query}",
            f"  start_url: {start_url}",
            f"  feature_reached: {trajectory.feature_reached}",
        ]
        if created_at:
            lines.append(f"  generated: {created_at}")
        if demo_id:
            lines.append(f"  id: {demo_id}")
        policy_desc = self._policy_descriptor()
        if policy_desc:
            lines.append(f"  policy: {policy_desc}")
        lines += [
            f"  steps: {trajectory.n_steps} · href_jumps: {jumps}"
            f" · max_jumps: {self.max_jumps if self.max_jumps is not None else '∞'}"
            f" · allow_external: {self.allow_external}",
            f"  score: {score.total:.3f} (cov={score.coverage:.2f} rob={score.robustness:.2f}"
            f" eff={score.efficiency:.2f} cost={score.cost:.2f} qual={score.quality:.2f})",
            f"  tokens: {trajectory.usage.total}"
            f" (input: {trajectory.usage.prompt_tokens} · output:"
            f" {trajectory.usage.completion_tokens} · calls: {trajectory.usage.calls})"
            f" · representation_path: {repr_path}",
        ]
        cost_line = self._cost_line(trajectory)
        if cost_line:
            lines.append(cost_line)
        for extra in extra_lines or []:
            if extra:
                lines.append(extra)
        lines.append("  trajectory:")
        for i, s in enumerate(trajectory.steps, start=1):
            if not s.executed:
                status = "planned (not executed)"
            elif s.result.ok:
                status = "ok"
            else:
                status = f"FAIL({s.result.error})"
            lines.append(f"    {i}. {s.action.to_summary()} -> {status}")
        if not trajectory.steps:
            lines.append("    (no actions taken)")
        return "\n".join(lines)

    def _run_search(
        self, factory: EnvFactory, query: str, *, guard: ActionGuard | None = None
    ) -> SearchResult:
        if self.tree_search:
            tree = TreeSearch(
                self.policy,
                n_rollouts=self.n_rollouts,
                builder=self.builder,
                evaluator=self.evaluator,
                max_steps=self.max_steps,
                token_budget=self.token_budget,
                weights=self.weights,
                max_jumps=self.max_jumps,
                allow_external=self.allow_external,
                guard=guard,
            )
            return tree.run(factory, query)

        greedy = GreedySearch(
            self.policy,
            builder=self.builder,
            evaluator=self.evaluator,
            max_steps=self.max_steps,
            token_budget=self.token_budget,
            weights=self.weights,
            max_jumps=self.max_jumps,
            allow_external=self.allow_external,
            guard=guard,
        )
        env = factory()
        try:
            return greedy.run(env, query)
        finally:
            _maybe_close(env)

    @staticmethod
    def _live_factory(url: str, provider: str, auth: BrowserAuthConfig | None) -> EnvFactory:
        def factory() -> WebEnvironment:
            controller = BrowserController(provider=provider, auth=auth)
            try:
                controller.open(url)
            except Exception:
                # ``open()`` may have already launched a browser before failing
                # (e.g. navigate crashes post-launch). Close it so a half-open
                # Chrome doesn't keep the persistent profile locked and break
                # every subsequent run.
                _maybe_close(controller)
                raise
            return controller

        return factory
