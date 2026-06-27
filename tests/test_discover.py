"""Tests for the AI discovery harness (``demodsl.discover``).

All tests are fully offline and deterministic: they use the ``HeuristicPolicy``
and the simulated environment shipped with the benchmark, so no API key or
network access is required.  This is also what makes the benchmark numbers
reproducible for the paper.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from demodsl.discover import (
    DiscoveryHarness,
    FeatureEvaluator,
    GreedySearch,
    LLMProviderFactory,
    ObservationBuilder,
    score_trajectory,
    synthesize_config,
)
from demodsl.discover.actions import ACTION_SPACE, AgentAction
from demodsl.discover.benchmark import (
    REPRESENTATIONS,
    SimulatedEnvironment,
    _shop_site,
    default_tasks,
    run_benchmark,
)
from demodsl.discover.llm import HeuristicLLMProvider, _extract_json
from demodsl.discover.observation import (
    ElementRef,
    PageObservation,
    estimate_tokens,
    locator_robustness,
)
from demodsl.discover.policy import HeuristicPolicy, LLMPolicy, _parse_action, _strong_match
from demodsl.discover.trajectory import Trajectory, TrajectoryStep
from demodsl.models import BrowserAuthConfig, DemoConfig, Locator

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def shop_env() -> SimulatedEnvironment:
    return SimulatedEnvironment(_shop_site(), "https://shop.example.com/")


def _docs_env() -> SimulatedEnvironment:
    from demodsl.discover.benchmark import _docs_site

    return SimulatedEnvironment(_docs_site(), "https://docs.example.com/")


# ── observation.py ─────────────────────────────────────────────────────────────


def test_locator_robustness_ladder() -> None:
    assert locator_robustness(Locator(type="css", value='[data-testid="x"]')) == 0.95
    assert locator_robustness(Locator(type="id", value="x")) == 0.9
    assert locator_robustness(Locator(type="css", value=".x")) == 0.5
    assert locator_robustness(Locator(type="xpath", value="//x")) == 0.3
    assert locator_robustness(None) == 0.0


def test_estimate_tokens_monotonic() -> None:
    assert estimate_tokens("") >= 1
    assert estimate_tokens("a" * 400) > estimate_tokens("a" * 40)


def test_observation_budget_truncates_large_page() -> None:
    # The docs home page has 62 interactive elements; a tight budget must drop
    # most of them while still surfacing the query-relevant one.
    builder = ObservationBuilder(token_budget=200, max_elements=24)
    obs = builder.build(_docs_env(), query="open the pricing page")

    assert obs.truncated > 0
    assert len(obs.elements) <= 24
    assert obs.token_estimate <= 200 + 60  # header slack
    names = {e.name for e in obs.elements}
    assert "Pricing" in names  # relevance ranking kept the target


def test_observation_relevance_ranks_match_first() -> None:
    builder = ObservationBuilder(token_budget=1024, max_elements=60)
    obs = builder.build(_docs_env(), query="search docs")
    top = max(obs.elements, key=lambda e: e.relevance)
    assert top.name == "Search docs"
    assert top.editable is True


def test_element_serialize_som_includes_coordinates() -> None:
    el = ElementRef(
        mark=0,
        role="button",
        name="Buy",
        bbox={"x": 10, "y": 20, "width": 100, "height": 40},
    )
    assert "@(" in el.serialize("som")
    assert "@(" not in el.serialize("axtree")


# ── llm.py ─────────────────────────────────────────────────────────────────────


def test_llm_factory_registers_all_backends() -> None:
    avail = LLMProviderFactory.available()
    assert {"openai", "openrouter", "anthropic", "heuristic"} <= set(avail)


def test_openrouter_provider_uses_openrouter_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from demodsl.discover.llm import OpenRouterProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.delenv("OPENROUTER_SITE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    provider = LLMProviderFactory.create("openrouter", model="anthropic/claude-3.5-sonnet")
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "anthropic/claude-3.5-sonnet"
    assert provider._api_key == "or-test-key"
    assert provider._base_url == "https://openrouter.ai/api/v1"
    assert provider._app_name == "demodsl"


def test_heuristic_llm_accounts_tokens() -> None:
    provider = HeuristicLLMProvider()
    resp = provider.complete("system text", "user text")
    assert resp.usage.calls == 1
    assert resp.usage.total > 0
    assert isinstance(resp.json(), dict)


def test_extract_json_handles_fenced_block() -> None:
    text = '```json\n{"action": "click", "mark": 3}\n```'
    data = _extract_json(text)
    assert data == {"action": "click", "mark": 3}
    assert _extract_json("no json here") == {}


# ── policy.py ──────────────────────────────────────────────────────────────────


def test_heuristic_policy_clicks_best_match(shop_env: SimulatedEnvironment) -> None:
    builder = ObservationBuilder()
    obs = builder.build(shop_env, query="open the shopping cart")
    decision = HeuristicPolicy().propose("open the shopping cart", obs, [])
    assert decision.action.kind == "click"
    assert decision.action.feature_reached is True
    assert decision.usage.calls == 1


def test_heuristic_policy_types_into_input_without_loop() -> None:
    builder = ObservationBuilder()
    obs = builder.build(_docs_env(), query="search docs")
    decision = HeuristicPolicy().propose("search docs", obs, [])
    assert decision.action.kind == "type"
    # The regression we fixed: typing into a strong-match input must complete.
    assert decision.action.feature_reached is True


def test_heuristic_policy_scrolls_then_gives_up() -> None:
    # An observation with no relevant element forces scrolling, then 'done'.
    empty_obs = ObservationBuilder().build(shop_env_no_match(), query="nonexistent widget")
    pol = HeuristicPolicy(max_scrolls=2)
    first = pol.propose("nonexistent widget", empty_obs, [])
    assert first.action.kind == "scroll"
    done = pol.propose("nonexistent widget", empty_obs, ["scroll", "scroll"])
    assert done.action.kind == "done"
    assert done.action.feature_reached is False


def shop_env_no_match() -> SimulatedEnvironment:
    return SimulatedEnvironment(_shop_site(), "https://shop.example.com/")


def test_llm_policy_parses_action_via_heuristic_backend(shop_env: SimulatedEnvironment) -> None:
    # HeuristicLLMProvider returns a canned scroll action JSON.
    obs = ObservationBuilder().build(shop_env, query="open the shopping cart")
    decision = LLMPolicy(HeuristicLLMProvider()).propose("open the shopping cart", obs, [])
    assert decision.action.kind == "scroll"
    assert decision.usage.calls == 1


def test_parse_action_degrades_type_on_non_input(shop_env: SimulatedEnvironment) -> None:
    obs = ObservationBuilder().build(shop_env, query="open the shopping cart")
    mark = obs.elements[0].mark  # a link/button, not editable
    action = _parse_action({"action": "type", "mark": mark, "value": "x"}, obs)
    assert action.kind == "click"  # degraded because the element is not editable


def test_strong_match() -> None:
    assert _strong_match("Shopping cart", ["shopping", "cart"]) is True
    assert _strong_match("Account", ["shopping", "cart"]) is False


# ── reward.py ──────────────────────────────────────────────────────────────────


def _trajectory_with(action: AgentAction, *, reached: bool) -> Trajectory:
    traj = Trajectory(query="q", start_url="https://x/")
    obs = ObservationBuilder().build(
        SimulatedEnvironment(_shop_site(), "https://shop.example.com/"), query="q"
    )
    from demodsl.discover.actions import StepResult

    traj.add(TrajectoryStep(obs, action, StepResult(ok=True, action=action)))
    traj.feature_reached = reached
    return traj


def test_score_trajectory_rewards_robust_locators() -> None:
    robust = AgentAction(kind="click", locator=Locator(type="css", value='[data-testid="cart"]'))
    fragile = AgentAction(kind="click", locator=Locator(type="xpath", value="//a"))
    s_robust = score_trajectory(_trajectory_with(robust, reached=True))
    s_fragile = score_trajectory(_trajectory_with(fragile, reached=True))
    assert s_robust.coverage == 1.0
    assert s_robust.robustness > s_fragile.robustness
    assert s_robust.total > s_fragile.total


def test_feature_evaluator_heuristic_signal(shop_env: SimulatedEnvironment) -> None:
    obs = ObservationBuilder().build(shop_env, query="shopping cart")
    traj = Trajectory(query="shopping cart", start_url=shop_env.url)
    reached, conf = FeatureEvaluator().reached("shopping cart", obs, traj)
    assert 0.0 <= conf <= 1.0
    assert reached is (conf >= 0.5)


# ── search.py ──────────────────────────────────────────────────────────────────


def test_greedy_search_reaches_cart(shop_env: SimulatedEnvironment) -> None:
    search = GreedySearch(HeuristicPolicy(), builder=ObservationBuilder(), max_steps=6)
    result = search.run(shop_env, "open the shopping cart")
    assert result.trajectory.feature_reached is True
    assert result.trajectory.final_url == "https://shop.example.com/cart"
    assert result.score.total > 0.5


def test_greedy_search_scrolls_to_offscreen_feature(shop_env: SimulatedEnvironment) -> None:
    # The reviews link sits below the fold; the adaptive builder surfaces it.
    search = GreedySearch(HeuristicPolicy(), builder=ObservationBuilder(), max_steps=6)
    result = search.run(shop_env, "view product reviews")
    assert result.trajectory.feature_reached is True


def _obs_with_link(href: str) -> PageObservation:
    return PageObservation(
        url="https://example.com/",
        title="Home",
        strategy="axtree",
        elements=[
            ElementRef(mark=0, role="link", name="Docs", href=href),
        ],
    )


def test_execute_action_rejects_hallucinated_navigation() -> None:
    from demodsl.discover.search import execute_action

    class _Env:
        def navigate(self, url: str) -> None:  # pragma: no cover - must not run
            raise AssertionError("navigate should be blocked for hallucinated URL")

        def current_url(self) -> str:
            return "https://example.com/"

    obs = _obs_with_link("https://example.com/docs")
    action = AgentAction(kind="navigate", url="https://example.com/pricing")
    result = execute_action(_Env(), action, obs.url, observation=obs)
    assert result.ok is False
    assert "hallucination" in (result.error or "")


def test_execute_action_allows_real_link_navigation() -> None:
    from demodsl.discover.search import execute_action

    visited: list[str] = []

    class _Env:
        def navigate(self, url: str) -> None:
            visited.append(url)

        def current_url(self) -> str:
            return "https://example.com/docs"

    obs = _obs_with_link("https://example.com/docs")
    action = AgentAction(kind="navigate", url="https://example.com/docs/")
    result = execute_action(_Env(), action, obs.url, observation=obs)
    assert result.ok is True
    assert visited == ["https://example.com/docs/"]


def test_execute_action_navigation_unrestricted_without_links() -> None:
    """When the page exposes no link hrefs, grounding can't apply and must not block."""
    from demodsl.discover.observation import PageObservation
    from demodsl.discover.search import execute_action

    visited: list[str] = []

    class _Env:
        def navigate(self, url: str) -> None:
            visited.append(url)

        def current_url(self) -> str:
            return url if (url := (visited[-1] if visited else "")) else ""

    obs = PageObservation(
        url="https://example.com/",
        title="Home",
        strategy="axtree",
        elements=[ElementRef(mark=0, role="button", name="Open")],
    )
    action = AgentAction(kind="navigate", url="https://example.com/anything")
    result = execute_action(_Env(), action, obs.url, observation=obs)
    assert result.ok is True
    assert visited == ["https://example.com/anything"]


def test_synthesize_omits_failed_steps() -> None:
    from demodsl.discover.actions import StepResult

    traj = Trajectory(query="show pricing", start_url="https://example.com/")
    obs = _obs_with_link("https://example.com/docs")
    good = AgentAction(kind="scroll", direction="down", pixels=720)
    bad = AgentAction(kind="navigate", url="https://example.com/pricing")
    traj.add(TrajectoryStep(obs, good, StepResult(ok=True, action=good)))
    traj.add(TrajectoryStep(obs, bad, StepResult(ok=False, action=bad, error="hallucination")))

    _config, data = synthesize_config("show pricing", traj)
    urls = [s.get("url") for s in data["scenarios"][0]["steps"] if s["action"] == "navigate"]
    # The fabricated /pricing navigation must not survive into the demo.
    assert "https://example.com/pricing" not in urls


def test_synthesize_honest_text_when_feature_not_reached() -> None:
    traj = Trajectory(query="show the pricing page", start_url="https://example.com/")
    traj.feature_reached = False

    _config, data = synthesize_config("show the pricing page", traj, feature_reached=False)
    assert "not found" in data["metadata"]["title"]
    assert "could not be located" in data["metadata"]["description"]
    open_narration = data["scenarios"][0]["steps"][0]["narration"]
    assert "not found" in open_narration
    assert "Let's explore" not in open_narration


def test_synthesize_normal_text_when_feature_reached() -> None:
    traj = Trajectory(query="open the cart", start_url="https://example.com/")
    traj.feature_reached = True

    _config, data = synthesize_config("open the cart", traj, feature_reached=True)
    assert data["metadata"]["title"] == "Demo — open the cart"
    assert "not found" not in data["metadata"]["title"]


def test_grounding_blocks_external_domain_by_default() -> None:
    from demodsl.discover.observation import PageObservation
    from demodsl.discover.search import _is_grounded_navigation

    obs = PageObservation(
        url="https://example.com/",
        title="Home",
        strategy="axtree",
        elements=[
            ElementRef(mark=0, role="link", name="Twitter", href="https://twitter.com/acme"),
            ElementRef(mark=1, role="link", name="Docs", href="https://example.com/docs"),
        ],
    )
    # Off-domain link is rejected by default ...
    assert (
        _is_grounded_navigation(
            "https://twitter.com/acme", obs, allow_external=False, base_url="https://example.com/"
        )
        is False
    )
    # ... but allowed when external navigation is explicitly enabled.
    assert (
        _is_grounded_navigation(
            "https://twitter.com/acme", obs, allow_external=True, base_url="https://example.com/"
        )
        is True
    )
    # Same-site link is always fine.
    assert _is_grounded_navigation(
        "https://example.com/docs", obs, allow_external=False, base_url="https://example.com/"
    )


def test_max_jumps_limits_href_navigations() -> None:
    """A jump budget of zero stops the agent from leaving the start page."""
    search = GreedySearch(HeuristicPolicy(), builder=ObservationBuilder(), max_steps=8, max_jumps=0)
    result = search.run(
        SimulatedEnvironment(_shop_site(), "https://shop.example.com/"), "open the shopping cart"
    )
    jumps = sum(
        1
        for s in result.trajectory.steps
        if s.result.ok and (s.action.kind == "navigate" or s.result.page_changed)
    )
    assert jumps == 0
    # Every cross-page attempt is rejected with a jump-limit error.
    assert any(
        (not s.result.ok) and "jump limit" in (s.result.error or "")
        for s in result.trajectory.steps
    )
    assert result.trajectory.final_url == "https://shop.example.com/"


def test_exploration_report_embedded_in_yaml(tmp_path: Path) -> None:
    from demodsl.discover import HARNESS_VERSION

    harness = DiscoveryHarness.build(policy="heuristic", max_steps=6, max_jumps=3)
    result = harness.discover(
        url="https://shop.example.com/",
        query="open the shopping cart",
        env_factory=lambda: SimulatedEnvironment(_shop_site(), "https://shop.example.com/"),
        output_dir=tmp_path,
    )
    assert result.config_path is not None
    text = result.config_path.read_text(encoding="utf-8")
    assert f"# DemoDSL discovery harness v{HARNESS_VERSION}" in text
    assert "# Exploration report" in text
    assert "href_jumps:" in text
    assert "max_jumps: 3" in text
    assert "policy: heuristic" in text
    # Unique, time- and hash-stamped output: filename + report carry id/time.
    assert result.config_path.name.startswith("discovered_demo_")
    assert result.config_path.suffix == ".yaml"
    assert "generated:" in text
    assert "id:" in text
    # Token accounting breaks down into input/output.
    assert "tokens:" in text
    assert "input:" in text
    assert "output:" in text
    # The commented header must not break YAML parsing.
    loaded = yaml.safe_load(text)
    assert loaded["metadata"]["title"]
    # The output video filename mirrors the unique config stem.
    assert loaded["output"]["filename"] == result.config_path.stem + ".mp4"


# ── synthesize.py ──────────────────────────────────────────────────────────────


def test_synthesize_produces_valid_config(shop_env: SimulatedEnvironment) -> None:
    search = GreedySearch(HeuristicPolicy(), builder=ObservationBuilder(), max_steps=6)
    traj = search.run(shop_env, "open the shopping cart").trajectory
    config, data = synthesize_config("open the shopping cart", traj)
    assert isinstance(config, DemoConfig)
    assert config.scenarios[0].steps
    # The scenario must always open with a navigate.
    assert data["scenarios"][0]["steps"][0]["action"] == "navigate"
    # round-trips through YAML
    assert yaml.safe_load(yaml.safe_dump(data))["metadata"]["title"]


def test_synthesize_with_auth_and_oauth(shop_env: SimulatedEnvironment, tmp_path: Path) -> None:
    search = GreedySearch(HeuristicPolicy(), builder=ObservationBuilder(), max_steps=6)
    traj = search.run(shop_env, "open the shopping cart").trajectory
    profile = tmp_path / "profile"
    auth = BrowserAuthConfig(user_data_dir=str(profile), channel="chrome")
    config, data = synthesize_config(
        "open the shopping cart",
        traj,
        provider="playwright-persistent",
        auth=auth,
        login={"provider": "google"},
    )
    scenario = data["scenarios"][0]
    assert scenario["provider"] == "playwright-persistent"
    assert scenario["auth"]["user_data_dir"] == str(profile)
    actions = [s["action"] for s in scenario["steps"]]
    assert "oauth_login" in actions
    assert isinstance(config, DemoConfig)


# ── harness.py (end-to-end, offline) ───────────────────────────────────────────


def test_harness_end_to_end_offline(tmp_path: Path) -> None:
    harness = DiscoveryHarness.build(policy="heuristic", max_steps=6)
    result = harness.discover(
        url="https://shop.example.com/",
        query="open the shopping cart",
        env_factory=lambda: SimulatedEnvironment(_shop_site(), "https://shop.example.com/"),
        verify=False,
        output_dir=tmp_path,
    )
    assert result.score.feature_reached is True
    assert isinstance(result.config, DemoConfig)
    assert result.config_path is not None and result.config_path.exists()
    assert "metadata" in yaml.safe_load(result.yaml_text)
    assert "reached=True" in result.summary()


def test_harness_tree_search_offline(tmp_path: Path) -> None:
    harness = DiscoveryHarness.build(
        policy="heuristic", max_steps=6, tree_search=True, n_rollouts=3
    )
    result = harness.discover(
        url="https://shop.example.com/",
        query="open the shopping cart",
        env_factory=lambda: SimulatedEnvironment(_shop_site(), "https://shop.example.com/"),
        verify=False,
        output_dir=tmp_path,
    )
    assert result.score.feature_reached is True
    assert len(result.candidates) == 3  # best-of-N rollouts recorded


# ── benchmark.py (the SOTA ablation) ───────────────────────────────────────────


def test_benchmark_runs_and_ranks_adaptive_first() -> None:
    report = run_benchmark()
    metrics = {m.agent: m for m in report.metrics}
    assert set(metrics) == set(REPRESENTATIONS)

    adaptive = metrics["adaptive"]
    # Our representation should solve every task...
    assert adaptive.success_rate == 1.0
    # ...with the best (or tied-best) composite score.
    assert adaptive.avg_score >= max(m.avg_score for m in report.metrics)
    # ...and the most robust locators of the three.
    assert adaptive.avg_robustness >= metrics["full_dom"].avg_robustness
    assert adaptive.avg_robustness >= metrics["viewport_som"].avg_robustness


def test_benchmark_viewport_som_misses_deep_feature() -> None:
    # The dark-mode toggle sits far below the fold; a viewport-only agent that
    # must scroll cannot reach it within the scroll budget — that gap is the
    # whole point of the adaptive representation.
    report = run_benchmark()
    viewport = next(m for m in report.metrics if m.agent == "viewport_som")
    assert viewport.success_rate < 1.0


def test_benchmark_adaptive_cheaper_than_full_dom() -> None:
    report = run_benchmark()
    metrics = {m.agent: m for m in report.metrics}
    # The token-budgeted representation must cost fewer tokens than dumping the
    # full DOM on the large docs page.
    assert metrics["adaptive"].avg_tokens < metrics["full_dom"].avg_tokens


def test_benchmark_report_serialises() -> None:
    report = run_benchmark(tasks=default_tasks()[:1])
    md = report.to_markdown()
    assert "Representation Ablation" in md
    assert "adaptive" in md
    import json

    payload = json.loads(report.to_json())
    assert "metrics" in payload and "outcomes" in payload


def test_action_space_documented() -> None:
    # Every action kind the policy can emit must be documented for the prompt.
    for kind in ("navigate", "click", "type", "scroll", "wait_for", "hover", "press_key", "done"):
        assert kind in ACTION_SPACE
