"""Navigation-graph export for discovered paths.

Turns one or more discovery :class:`~demodsl.discover.trajectory.Trajectory`
rollouts into a compact *navigation graph* — **nodes are pages** (keyed by URL),
**edges are the actions** that moved between them — and serialises it to Mermaid,
GraphViz DOT, JSON and a self-contained HTML report.

This is an entirely **optional** artifact: nothing in the harness depends on it.
The ``discover`` and ``review`` CLI commands emit it only when ``--graph`` is set.
Everything is dependency-free (plain string templating); the HTML embeds Mermaid
from a CDN with a plain-text fallback, so it still reads fine offline.

Sources of multiple paths:

* ``discover`` — the best trajectory plus every ``DiscoveryResult.candidates``
  rollout (tree search / best-of-N), so alternative explored branches show up.
* ``review`` — every persona's own trajectory, unioned into one graph whose
  edges remember *which* personas walked them.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from demodsl.discover.trajectory import Trajectory

__all__ = [
    "GraphNode",
    "GraphEdge",
    "PathSummary",
    "PathGraph",
    "build_path_graph",
    "write_path_graph",
]


# ── URL helpers ────────────────────────────────────────────────────────────────


def _normalize_url(url: str | None) -> str:
    """Canonicalise a URL for use as a node key (drop fragment + trailing slash)."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def _short_label(url: str, start_host: str) -> str:
    """A compact, human-readable node label derived from the URL path."""
    if not url:
        return "(start)"
    parts = urlsplit(url)
    label = parts.path or "/"
    if parts.query:
        label += "?" + parts.query
    if parts.netloc and parts.netloc != start_host:
        label = parts.netloc + label
    if len(label) > 48:
        label = label[:47] + "…"
    return label


def _oneline(s: str, *, limit: int = 60) -> str:
    """Collapse whitespace/newlines and clip — keeps node labels single-line."""
    s = " ".join((s or "").split())
    return s[: limit - 1] + "…" if len(s) > limit else s


# ── data model ─────────────────────────────────────────────────────────────────


@dataclass
class GraphNode:
    """A page/state in the navigation graph."""

    url: str
    node_id: str
    label: str
    title: str = ""
    visits: int = 0
    is_start: bool = False
    is_goal: bool = False
    #: intra-page actions performed here, e.g. ``{"scroll": 3, "type": 1}``.
    action_counts: dict[str, int] = field(default_factory=dict)

    def add_action(self, kind: str) -> None:
        self.action_counts[kind] = self.action_counts.get(kind, 0) + 1

    def actions_label(self) -> str:
        bits = [f"{k}×{c}" if c > 1 else k for k, c in self.action_counts.items()]
        return " · ".join(bits)


@dataclass
class GraphEdge:
    """A transition (an action that changed the page) between two nodes."""

    src: str
    dst: str
    kind: str
    order: int = 0
    count: int = 0
    ok: bool = True
    #: trajectory labels (e.g. persona names) that traversed this edge.
    sources: list[str] = field(default_factory=list)

    def edge_label(self) -> str:
        lbl = f"{self.order}·{self.kind}"
        if self.count > 1:
            lbl += f" ×{self.count}"
        return lbl


@dataclass
class PathSummary:
    """One trajectory's outcome, kept for the report table."""

    label: str
    reached: bool
    n_steps: int
    final_url: str


@dataclass
class PathGraph:
    """A union of one or more trajectories as a page/action graph."""

    query: str
    start_url: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], GraphEdge] = field(default_factory=dict)
    paths: list[PathSummary] = field(default_factory=list)

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_edges(self) -> int:
        return len(self.edges)

    @property
    def reached_count(self) -> int:
        return sum(1 for p in self.paths if p.reached)

    # ── serialisation ─────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "start_url": self.start_url,
            "n_nodes": self.n_nodes,
            "n_edges": self.n_edges,
            "nodes": [
                {
                    "id": n.node_id,
                    "url": n.url,
                    "label": n.label,
                    "title": n.title,
                    "visits": n.visits,
                    "is_start": n.is_start,
                    "is_goal": n.is_goal,
                    "actions": n.action_counts,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from": self.nodes[e.src].node_id,
                    "to": self.nodes[e.dst].node_id,
                    "from_url": e.src,
                    "to_url": e.dst,
                    "kind": e.kind,
                    "order": e.order,
                    "count": e.count,
                    "ok": e.ok,
                    "sources": e.sources,
                }
                for e in self.edges.values()
            ],
            "paths": [
                {
                    "label": p.label,
                    "reached": p.reached,
                    "n_steps": p.n_steps,
                    "final_url": p.final_url,
                }
                for p in self.paths
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_mermaid(self) -> str:
        lines = [
            "%%{init: {'flowchart': {'htmlLabels': true}}}%%",
            "flowchart TD",
        ]
        for node in self.nodes.values():
            parts = []
            if node.title:
                parts.append(_mmd_escape(node.title))
            parts.append(_mmd_escape(node.label))
            acts = node.actions_label()
            if acts:
                parts.append(_mmd_escape(acts))
            text = "<br/>".join(parts)
            if node.is_start:
                lines.append(f'    {node.node_id}(["{text}"])')
            elif node.is_goal:
                lines.append(f'    {node.node_id}{{{{"{text}"}}}}')
            else:
                lines.append(f'    {node.node_id}["{text}"]')
        for edge in self.edges.values():
            src = self.nodes[edge.src].node_id
            dst = self.nodes[edge.dst].node_id
            lbl = _mmd_escape(edge.edge_label()).replace("|", "/")
            arrow = "-->" if edge.ok else "-.->"
            lines.append(f'    {src} {arrow}|"{lbl}"| {dst}')
        starts = [n.node_id for n in self.nodes.values() if n.is_start]
        goals = [n.node_id for n in self.nodes.values() if n.is_goal]
        lines.append("    classDef start fill:#dcfce7,stroke:#16a34a,color:#14532d;")
        lines.append("    classDef goal fill:#fef9c3,stroke:#ca8a04,color:#713f12;")
        if starts:
            lines.append(f"    class {','.join(starts)} start;")
        if goals:
            lines.append(f"    class {','.join(goals)} goal;")
        return "\n".join(lines)

    def to_dot(self) -> str:
        lines = [
            "digraph paths {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fillcolor="#eef2ff", '
            'fontname="Helvetica", fontsize=10];',
            '  edge [fontname="Helvetica", fontsize=9, color="#6b7280"];',
        ]
        for node in self.nodes.values():
            label = f"{node.title}\n{node.label}" if node.title else node.label
            acts = node.actions_label()
            if acts:
                label += f"\n{acts}"
            attrs = [f'label="{_dot_escape(label)}"']
            if node.is_start:
                attrs += ['fillcolor="#dcfce7"', 'color="#16a34a"']
            elif node.is_goal:
                attrs += ['fillcolor="#fef9c3"', 'color="#ca8a04"']
            lines.append(f"  {node.node_id} [{', '.join(attrs)}];")
        for edge in self.edges.values():
            src = self.nodes[edge.src].node_id
            dst = self.nodes[edge.dst].node_id
            style = "" if edge.ok else ', style="dashed"'
            lines.append(f'  {src} -> {dst} [label="{_dot_escape(edge.edge_label())}"{style}];')
        lines.append("}")
        return "\n".join(lines)

    def to_html(self, title: str | None = None) -> str:
        e = html.escape
        heading = title or f"Path graph — {self.query}"
        rows = "".join(
            f"<tr><td>{e(p.label)}</td><td>{'✅' if p.reached else '—'}</td>"
            f"<td>{p.n_steps}</td><td><code>{e(p.final_url)}</code></td></tr>"
            for p in self.paths
        )
        table = (
            "<table><thead><tr><th>Path</th><th>Reached</th><th>Steps</th>"
            f"<th>Final URL</th></tr></thead><tbody>{rows}</tbody></table>"
            if rows
            else ""
        )
        mermaid_src = e(self.to_mermaid())
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(heading)}</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,
    Arial,sans-serif; color:#1f2937; margin:0; background:#fff; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:28px 30px 48px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .meta {{ color:#6b7280; font-size:13px; margin:0 0 18px; }}
  .diagram {{ border:1px solid #e5e7eb; border-radius:12px; padding:16px;
    background:#f8fafc; overflow:auto; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; margin:18px 0; }}
  th,td {{ text-align:left; padding:6px 10px; border-bottom:1px solid #e5e7eb; }}
  th {{ color:#6b7280; font-weight:600; }}
  code {{ font-size:12px; color:#374151; }}
  .legend {{ font-size:12px; color:#6b7280; margin:10px 0 0; }}
  .legend b {{ color:#1f2937; }}
  details {{ margin-top:16px; }}
  pre {{ background:#0f172a; color:#e2e8f0; padding:14px; border-radius:10px;
    overflow:auto; font-size:12px; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', function () {{
    if (window.mermaid) {{
      mermaid.initialize({{ startOnLoad: true, securityLevel: 'loose',
        flowchart: {{ htmlLabels: true }} }});
    }}
  }});
</script>
</head><body><div class="wrap">
<h1>{e(heading)}</h1>
<p class="meta"><strong>Start:</strong> <code>{e(self.start_url)}</code> ·
  {self.n_nodes} pages · {self.n_edges} transitions ·
  {self.reached_count}/{len(self.paths)} paths reached the feature</p>
<div class="diagram"><pre class="mermaid">{mermaid_src}</pre></div>
<p class="legend"><b>Green</b> = start · <b>Gold</b> = feature reached ·
  solid arrow = successful transition · dashed = failed.</p>
{table}
<details><summary>Mermaid source</summary><pre>{mermaid_src}</pre></details>
<footer style="color:#9ca3af;font-size:11px;margin-top:24px">Generated by demodsl · path graph</footer>
</div></body></html>"""


# ── escaping ───────────────────────────────────────────────────────────────────


def _mmd_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ── builder ────────────────────────────────────────────────────────────────────


def build_path_graph(
    *,
    query: str,
    start_url: str,
    paths: list[tuple[str, Trajectory]],
) -> PathGraph:
    """Union ``paths`` (``(label, trajectory)`` pairs) into a single page graph.

    Nodes are unique pages (by normalised URL); edges are actions that changed
    the page (``navigate`` or any action whose ``url_after`` differs from
    ``url_before``). Same-page actions (scroll/type/hover/click-without-nav) are
    recorded *inside* the originating node. The start page and any page where the
    feature was reached are flagged for highlighting.
    """
    graph = PathGraph(query=query, start_url=_normalize_url(start_url))
    start_host = urlsplit(graph.start_url).netloc
    counter = {"n": 0}

    def _node(url: str, title: str = "") -> GraphNode:
        key = _normalize_url(url)
        node = graph.nodes.get(key)
        title = _oneline(title)
        if node is None:
            node = GraphNode(
                url=key,
                node_id=f"n{counter['n']}",
                label=_short_label(key, start_host),
                title=title,
            )
            counter["n"] += 1
            graph.nodes[key] = node
        elif title and not node.title:
            node.title = title
        return node

    if graph.start_url:
        _node(graph.start_url).is_start = True

    for label, traj in paths:
        if traj is None:
            continue
        first_url = traj.start_url or graph.start_url
        if not first_url and traj.steps:
            first = traj.steps[0]
            first_url = first.result.url_before or first.observation.url
        cur = _node(first_url)
        cur.visits += 1
        for order, step in enumerate(traj.steps, start=1):
            act = step.action
            before = _normalize_url(step.result.url_before or step.observation.url or cur.url)
            after = _normalize_url(step.result.url_after or before)
            before_node = _node(before, step.observation.title)
            if act.kind == "navigate" or (after and after != before):
                dst = _node(after)
                dst.visits += 1
                _add_edge(graph, before_node.url, dst.url, act.kind, order, label, step.result.ok)
                cur = dst
            else:
                if act.kind != "done":
                    before_node.add_action(act.kind)
                cur = before_node
            if act.feature_reached:
                cur.is_goal = True
        final = _normalize_url(traj.final_url or cur.url)
        if traj.feature_reached and final in graph.nodes:
            graph.nodes[final].is_goal = True
        graph.paths.append(
            PathSummary(
                label=label,
                reached=traj.feature_reached,
                n_steps=traj.n_steps,
                final_url=final,
            )
        )

    if graph.start_url in graph.nodes:
        graph.nodes[graph.start_url].is_start = True
    return graph


def _add_edge(
    graph: PathGraph,
    src: str,
    dst: str,
    kind: str,
    order: int,
    source: str,
    ok: bool,
) -> None:
    key = (src, dst, kind)
    edge = graph.edges.get(key)
    if edge is None:
        edge = GraphEdge(src=src, dst=dst, kind=kind, order=order)
        graph.edges[key] = edge
    edge.count += 1
    edge.ok = edge.ok and ok
    edge.order = min(edge.order, order) if edge.order else order
    if source and source not in edge.sources:
        edge.sources.append(source)


# ── writer ─────────────────────────────────────────────────────────────────────


def write_path_graph(
    graph: PathGraph,
    out_dir: str | Path,
    *,
    basename: str = "paths_graph",
    formats: tuple[str, ...] = ("mermaid", "dot", "json", "html"),
) -> dict[str, Path]:
    """Write the selected ``formats`` and return a ``{format: path}`` mapping."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    if "mermaid" in formats:
        p = out / f"{basename}.mmd"
        p.write_text(graph.to_mermaid() + "\n", encoding="utf-8")
        written["mermaid"] = p
    if "dot" in formats:
        p = out / f"{basename}.dot"
        p.write_text(graph.to_dot() + "\n", encoding="utf-8")
        written["dot"] = p
    if "json" in formats:
        p = out / f"{basename}.json"
        p.write_text(graph.to_json() + "\n", encoding="utf-8")
        written["json"] = p
    if "html" in formats:
        p = out / f"{basename}.html"
        p.write_text(graph.to_html(), encoding="utf-8")
        written["html"] = p
    return written
