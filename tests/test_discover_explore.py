"""Tests for the two-phase explore→plan discovery mode (``demodsl.discover.explore``).

Fully offline and deterministic: a crawl over the benchmark's
``SimulatedEnvironment`` builds the exploration graph, and the heuristic picker
selects the demo — no API key or network needed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from demodsl.discover import DiscoveryHarness
from demodsl.discover.benchmark import SimulatedEnvironment, _shop_site
from demodsl.discover.explore import (
    DemoPlan,
    ExplorationGraph,
    SiteElement,
    SitePage,
    _heuristic_plan,
    _parse_plan,
    crawl_site,
    plan_demo_from_graph,
    plan_to_trajectory,
)


def _shop_env() -> SimulatedEnvironment:
    return SimulatedEnvironment(_shop_site(), "https://shop.example.com/")


# ── phase 1: crawl ───────────────────────────────────────────────────────────


def test_crawl_discovers_linked_pages() -> None:
    graph = crawl_site(_shop_env(), start_url="https://shop.example.com/", max_pages=5, max_depth=2)
    assert graph.n_pages >= 2
    assert "https://shop.example.com/" in graph.pages  # start page (normalised)
    # The cart link should have produced an edge to the cart page.
    assert any(dst.endswith("/cart") for _src, dst, _name in graph.edges)


def test_crawl_respects_max_pages() -> None:
    graph = crawl_site(_shop_env(), start_url="https://shop.example.com/", max_pages=1, max_depth=3)
    assert graph.n_pages == 1


def test_crawl_stays_on_domain_by_default() -> None:
    graph = crawl_site(_shop_env(), start_url="https://shop.example.com/", max_pages=8, max_depth=2)
    # docs.example.com shares the registrable domain example.com → same-site OK,
    # but no third-party host should ever appear.
    for page in graph.pages:
        assert "example.com" in page


# ── phase 2: pick ────────────────────────────────────────────────────────────


def _graph_with_cart() -> ExplorationGraph:
    from demodsl.models import Locator

    g = ExplorationGraph(start_url="https://shop.example.com/")
    g.add_page(
        SitePage(
            url="https://shop.example.com/",
            title="Shop",
            elements=[
                SiteElement(
                    mark=0,
                    role="link",
                    name="Shopping cart",
                    locator=Locator(type="text", value="Shopping cart"),
                    href="https://shop.example.com/cart",
                ),
                SiteElement(
                    mark=1, role="link", name="About us", href="https://shop.example.com/about"
                ),
            ],
        )
    )
    return g


def test_heuristic_plan_picks_relevant_element() -> None:
    plan = _heuristic_plan(_graph_with_cart(), "open the shopping cart", max_steps=6)
    assert plan.feature_reached is True
    assert plan.steps
    # The plan should reach the cart (either by navigating to its href).
    assert any(s.url and s.url.endswith("/cart") for s in plan.steps)


def test_plan_demo_without_llm_uses_heuristic() -> None:
    plan = plan_demo_from_graph(_graph_with_cart(), "shopping cart", llm=None, max_steps=6)
    assert isinstance(plan, DemoPlan)
    assert plan.steps


def test_review_query_adds_walkthrough_steps() -> None:
    # A "review" intent must produce on-page steps (scroll), not just a jump.
    graph = crawl_site(_shop_env(), start_url="https://shop.example.com/", max_pages=5, max_depth=2)
    plan = plan_demo_from_graph(graph, "navigate and review the shopping cart", max_steps=8)
    kinds = [s.action for s in plan.steps]
    assert "scroll" in kinds  # the review phase walks through the page
    assert len(plan.steps) >= 2


def test_non_review_query_stays_concise() -> None:
    # A plain "open" intent should not inflate into a walkthrough.
    graph = crawl_site(_shop_env(), start_url="https://shop.example.com/", max_pages=5, max_depth=2)
    plan = plan_demo_from_graph(graph, "open the shopping cart", max_steps=8)
    assert "scroll" not in [s.action for s in plan.steps]


def test_parse_plan_rejects_hallucinated_targets() -> None:
    graph = _graph_with_cart()
    data = {
        "feature_reached": True,
        "steps": [
            {"action": "navigate", "url": "https://shop.example.com/pricing"},  # not in map
            {"action": "click", "page": "https://shop.example.com/", "mark": 99},  # bad mark
            {"action": "click", "page": "https://shop.example.com/", "mark": 0},  # valid
        ],
    }
    plan = _parse_plan(data, graph, max_steps=6)
    # Only the valid click survives; fabricated nav + bad mark are dropped.
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "click"
    assert plan.steps[0].mark == 0


def test_plan_to_trajectory_is_synthesizable() -> None:
    from demodsl.discover import synthesize_config

    graph = _graph_with_cart()
    plan = _heuristic_plan(graph, "open the shopping cart", max_steps=6)
    traj = plan_to_trajectory(plan, graph, "open the shopping cart")
    config, data = synthesize_config("open the shopping cart", traj, feature_reached=True)
    assert config.scenarios[0].steps
    assert data["scenarios"][0]["steps"][0]["action"] == "navigate"


# ── harness end-to-end ───────────────────────────────────────────────────────


def test_harness_explore_first_offline(tmp_path: Path) -> None:
    harness = DiscoveryHarness.build(
        policy="heuristic", explore_first=True, max_pages=5, max_depth=2, max_steps=6
    )
    result = harness.discover(
        url="https://shop.example.com/",
        query="open the shopping cart",
        env_factory=_shop_env,
        output_dir=tmp_path,
    )
    assert result.config_path is not None
    text = result.config_path.read_text(encoding="utf-8")
    assert "representation_path: explore→plan" in text
    assert "crawl:" in text
    # Unique, time- and hash-stamped filename.
    assert result.config_path.name.startswith("discovered_demo_")
    assert "generated:" in text
    assert "id:" in text
    # The exploration graph is written as a first-class artifact alongside it.
    graphs = list(tmp_path.glob("*.graph.json"))
    assert len(graphs) == 1
    import json

    graph_data = json.loads(graphs[0].read_text(encoding="utf-8"))
    assert graph_data["pages"]
    # YAML still parses despite the comment header.
    assert yaml.safe_load(text)["scenarios"]
