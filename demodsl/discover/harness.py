"""Top-level discovery harness orchestrator.

Wires the pieces together:

    open env (auth) → search (greedy | tree) → evaluate → synthesise → verify

and returns a :class:`DiscoveryResult` carrying the validated config, the
trajectory, the composite score, and (optionally) the rendered video path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
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
from demodsl.discover.search import GreedySearch, SearchResult, TreeSearch, _maybe_close
from demodsl.discover.synthesize import synthesize_config
from demodsl.discover.trajectory import Trajectory
from demodsl.models import BrowserAuthConfig, DemoConfig

logger = logging.getLogger(__name__)

EnvFactory = Callable[[], WebEnvironment]


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
        tree_search: bool = False,
        n_rollouts: int = 3,
        max_steps: int = 8,
        token_budget: int = 8000,
        weights: dict[str, float] | None = None,
        persona: Persona | None = None,
    ) -> None:
        self.policy = policy
        self.builder = builder or ObservationBuilder()
        self.evaluator = evaluator or FeatureEvaluator()
        self.tree_search = tree_search
        self.n_rollouts = n_rollouts
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.weights = weights
        self.persona = persona
        if persona is not None and tree_search:
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
            tree_search=tree_search,
            n_rollouts=n_rollouts,
            max_steps=max_steps,
            token_budget=token_budget,
            weights=weights,
            persona=persona_obj,
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
        if isinstance(self.policy, PersonaPolicy):
            self.policy.reset()
        search_res = self._run_search(factory, query)
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
        config, config_dict = synthesize_config(
            query, traj, provider=provider, auth=auth, login=login, voice_id=voice_id
        )

        out_dir = Path(output_dir)
        config_path: Path | None = None
        video_path: Path | None = None
        if write_yaml or verify:
            from demodsl.discover.verify import write_config_yaml

            out_dir.mkdir(parents=True, exist_ok=True)
            config_path = write_config_yaml(config_dict, out_dir / "discovered_demo.yaml")
        if verify:
            from demodsl.discover.verify import verify_config

            video_path = verify_config(
                config_dict,
                out_dir,
                config_path=config_path,
                turbo=verify_turbo,
                skip_voice=verify_skip_voice,
            )

        return DiscoveryResult(
            query=query,
            start_url=traj.start_url or url,
            trajectory=traj,
            score=search_res.score,
            config=config,
            config_dict=config_dict,
            strategy_log=list(search_res.strategy_log),
            candidates=search_res.candidates,
            config_path=config_path,
            video_path=video_path,
            persona_report=persona_report,
        )

    # ── internals ─────────────────────────────────────────────────────────

    def _run_search(self, factory: EnvFactory, query: str) -> SearchResult:
        if self.tree_search:
            tree = TreeSearch(
                self.policy,
                n_rollouts=self.n_rollouts,
                builder=self.builder,
                evaluator=self.evaluator,
                max_steps=self.max_steps,
                token_budget=self.token_budget,
                weights=self.weights,
            )
            return tree.run(factory, query)

        greedy = GreedySearch(
            self.policy,
            builder=self.builder,
            evaluator=self.evaluator,
            max_steps=self.max_steps,
            token_budget=self.token_budget,
            weights=self.weights,
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
