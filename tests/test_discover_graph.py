"""Tests for the optional navigation-graph export (``demodsl.discover.graph``).

Fully offline and deterministic: trajectories are built by hand (no browser,
network or API key), plus one end-to-end ``run_review(graph=True)`` pass on the
simulated site used by ``test_discover_review.py`` (PDF disabled).
"""

from __future__ import annotations

import json

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.benchmark import SimElement, SimPage, SimulatedEnvironment
from demodsl.discover.graph import (
    GraphNode,
    PathGraph,
    build_path_graph,
    write_path_graph,
)
from demodsl.discover.observation import PageObservation
from demodsl.discover.panel import build_panel
from demodsl.discover.review import run_review
from demodsl.discover.trajectory import Trajectory, TrajectoryStep

START = "https://shop.example.com/"
PAGE_A = "https://shop.example.com/a"
PAGE_B = "https://shop.example.com/b"


def _step(
    *,
    url_before: str,
    url_after: str,
    kind: str,
    ok: bool = True,
    feature_reached: bool = False,
    title: str = "",
    **action_kw,
) -> TrajectoryStep:
    """Build a (observation, action, result) triple — observation is pre-action."""
    obs = PageObservation(url=url_before, title=title, strategy="axtree")
    action = AgentAction(kind=kind, feature_reached=feature_reached, **action_kw)
    result = StepResult(
        ok=ok,
        action=action,
        url_before=url_before,
        url_after=url_after,
        page_changed=url_before != url_after,
    )
    return TrajectoryStep(observation=obs, action=action, result=result)


def _linear_trajectory() -> Trajectory:
    """START --navigate--> /a --scroll(intra)--> /a --click--> /b (feature)."""
    traj = Trajectory(query="see the offers", start_url=START)
    traj.add(_step(url_before=START, url_after=PAGE_A, kind="navigate", url=PAGE_A, title="Home"))
    traj.add(_step(url_before=PAGE_A, url_after=PAGE_A, kind="scroll", direction="down", title="A"))
    traj.add(
        _step(
            url_before=PAGE_A,
            url_after=PAGE_B,
            kind="click",
            mark=3,
            feature_reached=True,
            title="A",
        )
    )
    traj.feature_reached = True
    traj.final_url = PAGE_B
    return traj


# ── builder ────────────────────────────────────────────────────────────────────


def test_build_single_path_nodes_and_edges() -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])

    assert isinstance(g, PathGraph)
    # Three distinct pages, two page-changing transitions.
    assert g.n_nodes == 3
    assert g.n_edges == 2

    start_node = g.nodes[_norm(START)]
    assert start_node.is_start is True
    assert g.nodes[PAGE_B].is_goal is True
    # The scroll is an intra-page action recorded on /a, not an edge.
    assert g.nodes[PAGE_A].action_counts == {"scroll": 1}

    kinds = sorted(e.kind for e in g.edges.values())
    assert kinds == ["click", "navigate"]
    # Step ordering is preserved on the edges.
    nav = next(e for e in g.edges.values() if e.kind == "navigate")
    click = next(e for e in g.edges.values() if e.kind == "click")
    assert nav.order == 1
    assert click.order == 3


def test_path_summary_recorded() -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    assert len(g.paths) == 1
    assert g.paths[0].label == "best"
    assert g.paths[0].reached is True
    assert g.paths[0].n_steps == 3
    assert g.paths[0].final_url == PAGE_B
    assert g.reached_count == 1


def test_union_two_paths_merges_shared_edges() -> None:
    # Second path diverges: START --navigate--> /a then gives up (no feature).
    alt = Trajectory(query="q", start_url=START)
    alt.add(_step(url_before=START, url_after=PAGE_A, kind="navigate", url=PAGE_A))
    alt.add(_step(url_before=PAGE_A, url_after=PAGE_A, kind="done"))
    alt.final_url = PAGE_A

    g = build_path_graph(
        query="q", start_url=START, paths=[("best", _linear_trajectory()), ("alt", alt)]
    )
    # The shared START->/a navigate edge is merged with count 2 and both sources.
    nav = next(e for e in g.edges.values() if e.kind == "navigate")
    assert nav.count == 2
    assert set(nav.sources) == {"best", "alt"}
    assert len(g.paths) == 2
    assert g.reached_count == 1


# ── serialisation ──────────────────────────────────────────────────────────────


def test_mermaid_output_has_shapes_and_classes() -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    mer = g.to_mermaid()
    assert "flowchart TD" in mer
    assert "classDef start" in mer
    assert "classDef goal" in mer
    # navigate edge is solid, label carries the step order.
    assert "-->|" in mer
    assert "1·navigate" in mer


def test_failed_transition_is_dashed() -> None:
    traj = Trajectory(query="q", start_url=START)
    traj.add(_step(url_before=START, url_after=PAGE_A, kind="navigate", url=PAGE_A, ok=False))
    traj.final_url = PAGE_A
    g = build_path_graph(query="q", start_url=START, paths=[("best", traj)])
    assert "-.->|" in g.to_mermaid()
    assert 'style="dashed"' in g.to_dot()


def test_dot_output_is_a_digraph() -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    dot = g.to_dot()
    assert dot.startswith("digraph paths {")
    assert " -> " in dot
    assert dot.rstrip().endswith("}")


def test_json_round_trips() -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    data = json.loads(g.to_json())
    assert data["n_nodes"] == 3
    assert data["n_edges"] == 2
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    assert data["paths"][0]["reached"] is True


def test_html_embeds_mermaid_source() -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    page = g.to_html()
    assert '<pre class="mermaid">' in page
    assert "flowchart TD" in page
    assert START in page


def test_escaping_handles_quotes_and_angle_brackets() -> None:
    node = GraphNode(url="u", node_id="n0", label='a "b" <c>', title='T&"<>')
    from demodsl.discover.graph import _dot_escape, _mmd_escape

    assert "&quot;" in _mmd_escape(node.label)
    assert "&lt;" in _mmd_escape(node.label)
    assert '\\"' in _dot_escape(node.label)


# ── writer ─────────────────────────────────────────────────────────────────────


def test_write_path_graph_emits_all_formats(tmp_path) -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    written = write_path_graph(g, tmp_path)
    assert set(written) == {"mermaid", "dot", "json", "html"}
    assert (tmp_path / "paths_graph.mmd").exists()
    assert (tmp_path / "paths_graph.dot").exists()
    assert (tmp_path / "paths_graph.json").exists()
    assert (tmp_path / "paths_graph.html").exists()
    for p in written.values():
        assert p.read_text(encoding="utf-8").strip()


def test_write_path_graph_respects_formats(tmp_path) -> None:
    g = build_path_graph(query="q", start_url=START, paths=[("best", _linear_trajectory())])
    written = write_path_graph(g, tmp_path, formats=("json",))
    assert set(written) == {"json"}
    assert not (tmp_path / "paths_graph.mmd").exists()


# ── end-to-end via run_review (offline) ────────────────────────────────────────


def _deep_site() -> SimulatedEnvironment:
    home = SimPage(
        url=START,
        title="Acme — Home",
        height=3400,
        elements=[
            SimElement("home", "Home", "link", abs_y=20, target=START, dom_id="nav-home"),
            SimElement(
                "pricing",
                "Pricing plans",
                "link",
                abs_y=2400,
                target="https://shop.example.com/pricing",
                testid="pricing-link",
            ),
        ],
    )
    pricing = SimPage(
        url="https://shop.example.com/pricing",
        title="Pricing plans",
        height=1000,
        elements=[SimElement("choose", "Choose a plan", "button", abs_y=200, dom_id="choose")],
    )
    return SimulatedEnvironment({START: home, "https://shop.example.com/pricing": pricing}, START)


def test_run_review_with_graph_writes_artifacts(tmp_path) -> None:
    out = tmp_path / "review"
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(2),
        output_dir=out,
        policy="heuristic",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
        graph=True,
    )
    assert report.graph_mermaid is not None
    assert "flowchart TD" in report.graph_mermaid
    assert report.graph_paths is not None
    assert set(report.graph_paths) == {"mermaid", "dot", "json", "html"}
    for p in report.graph_paths.values():
        from pathlib import Path

        assert Path(p).exists()
    # The report HTML embeds the diagram + loads Mermaid.
    page = (out / "review.html").read_text(encoding="utf-8")
    assert "User paths" in page
    assert "class='mermaid'" in page or 'class="mermaid"' in page


def test_run_review_without_graph_skips_artifacts(tmp_path) -> None:
    out = tmp_path / "review"
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(2),
        output_dir=out,
        policy="heuristic",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
    )
    assert report.graph_mermaid is None
    assert report.graph_paths is None
    assert not (out / "paths_graph.mmd").exists()


def _norm(u: str) -> str:
    from demodsl.discover.graph import _normalize_url

    return _normalize_url(u)
