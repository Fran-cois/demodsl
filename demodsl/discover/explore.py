"""Two-phase discovery: deterministic crawl → graph → LLM picks the demo.

This is an alternative to the interleaved ReAct loop in
:mod:`~demodsl.discover.search`. Instead of asking the model what to do at every
step, it works in two clearly separated phases:

1. **Explore (no LLM).** A deterministic breadth-first crawl drives the browser
   over the start site's links and records every page it reaches together with
   its interactive elements. The result is an :class:`ExplorationGraph` — a
   compact site map (pages as nodes, links as edges).

2. **Pick (one LLM call).** The whole graph is serialised once and an LLM is
   asked to choose the single best **demo plan** — an ordered list of
   navigate/click/scroll steps — that showcases the requested feature. With no
   LLM provider a deterministic relevance-based planner is used instead, so the
   whole mode stays runnable and testable offline.

The chosen :class:`DemoPlan` is converted into a
:class:`~demodsl.discover.trajectory.Trajectory` so it flows through the exact
same :func:`~demodsl.discover.synthesize.synthesize_config` path as the ReAct
mode.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from demodsl.discover.actions import AgentAction, StepResult
from demodsl.discover.controller import WebEnvironment
from demodsl.discover.llm import LLMProvider, TokenUsage, _estimate_tokens
from demodsl.discover.observation import PageObservation, _keywords, _relevance
from demodsl.discover.search import _normalize_url, _registrable_domain, _same_site
from demodsl.discover.trajectory import Trajectory, TrajectoryStep
from demodsl.models import Locator

logger = logging.getLogger(__name__)

__all__ = [
    "SiteElement",
    "SitePage",
    "ExplorationGraph",
    "DemoPlan",
    "crawl_site",
    "plan_demo_from_graph",
]


# ── exploration graph data model ─────────────────────────────────────────────


@dataclass
class SiteElement:
    """One interactive element discovered on a page."""

    mark: int
    role: str
    name: str
    locator: Locator | None = None
    href: str = ""
    editable: bool = False

    @property
    def is_link(self) -> bool:
        return bool(self.href)


@dataclass
class SitePage:
    """A crawled page and its interactive elements."""

    url: str
    title: str = ""
    elements: list[SiteElement] = field(default_factory=list)

    def by_mark(self, mark: int) -> SiteElement | None:
        for el in self.elements:
            if el.mark == mark:
                return el
        return None


@dataclass
class ExplorationGraph:
    """A site map produced by the deterministic crawl (no LLM)."""

    start_url: str
    pages: dict[str, SitePage] = field(default_factory=dict)
    #: directed link edges ``(src_url, dst_url, link_name)``.
    edges: list[tuple[str, str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.start_url = _normalize_url(self.start_url)

    def add_page(self, page: SitePage) -> None:
        page.url = _normalize_url(page.url)
        self.pages.setdefault(page.url, page)

    def page(self, url: str) -> SitePage | None:
        return self.pages.get(_normalize_url(url))

    def add_edge(self, src: str, dst: str, name: str) -> None:
        edge = (_normalize_url(src), _normalize_url(dst), name)
        if edge not in self.edges:
            self.edges.append(edge)

    @property
    def n_pages(self) -> int:
        return len(self.pages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_url": self.start_url,
            "pages": [
                {
                    "url": p.url,
                    "title": p.title,
                    "elements": [
                        {
                            "mark": e.mark,
                            "role": e.role,
                            "name": e.name,
                            "href": e.href,
                            "editable": e.editable,
                        }
                        for e in p.elements
                    ],
                }
                for p in self.pages.values()
            ],
            "edges": [{"src": s, "dst": d, "name": n} for s, d, n in self.edges],
        }

    def to_prompt(self, *, max_elements_per_page: int = 20) -> str:
        """Serialise the graph compactly for an LLM picker prompt."""
        lines: list[str] = []
        for idx, page in enumerate(self.pages.values()):
            tag = " (start)" if page.url == self.start_url else ""
            title = f" — {page.title}" if page.title else ""
            lines.append(f"PAGE[{idx}] {page.url}{tag}{title}")
            for el in page.elements[:max_elements_per_page]:
                link = f" -> {el.href}" if el.href else ""
                kind = " (input)" if el.editable else ""
                lines.append(f"  [{el.mark}] {el.role}: {el.name}{kind}{link}")
        return "\n".join(lines)


# ── phase 1: deterministic crawl ─────────────────────────────────────────────


def _to_site_element(mark: int, rec: dict[str, Any]) -> SiteElement:
    loc_rec = rec.get("locator") or {}
    locator: Locator | None = None
    if loc_rec.get("value"):
        try:
            locator = Locator(type=loc_rec.get("type", "css"), value=str(loc_rec["value"]))
        except Exception:
            locator = None
    name = str(rec.get("name") or rec.get("text") or "").strip()
    return SiteElement(
        mark=mark,
        role=str(rec.get("role") or "generic"),
        name=name,
        locator=locator,
        href=str(rec.get("href") or ""),
        editable=bool(rec.get("editable", False)),
    )


def crawl_site(
    env: WebEnvironment,
    *,
    start_url: str,
    max_pages: int = 8,
    max_depth: int = 2,
    allow_external: bool = False,
    max_elements: int = 40,
) -> ExplorationGraph:
    """Breadth-first crawl from *start_url* into an :class:`ExplorationGraph`.

    Purely deterministic (no LLM): follows same-site link ``href``s up to
    *max_pages* / *max_depth*. ``allow_external`` permits links to other
    registrable domains. The browser is driven through *env* only.
    """
    graph = ExplorationGraph(start_url=_normalize_url(start_url))
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    seen: set[str] = set()

    while queue and graph.n_pages < max_pages:
        url, depth = queue.popleft()
        key = _normalize_url(url)
        if key in seen:
            continue
        seen.add(key)

        try:
            env.navigate(url)
            raw = env.extract_elements()
            cur = env.current_url() or url
            title = env.title()
        except Exception:
            logger.debug("crawl: failed to visit %s", url, exc_info=True)
            continue

        page = SitePage(
            url=_normalize_url(cur),
            title=title or "",
            elements=[_to_site_element(i, rec) for i, rec in enumerate(raw[:max_elements])],
        )
        graph.add_page(page)

        if depth >= max_depth:
            continue
        for el in page.elements:
            if not el.href or el.href.startswith("#"):
                continue
            if not allow_external and not _same_site(el.href, start_url):
                continue
            tgt = _normalize_url(el.href)
            if not tgt:
                continue
            graph.add_edge(page.url, tgt, el.name)
            if tgt not in seen and graph.n_pages + len(queue) < max_pages * 3:
                queue.append((el.href, depth + 1))

    return graph


# ── phase 2: pick the demo (LLM, or deterministic fallback) ──────────────────


@dataclass
class PlanStep:
    action: str  # navigate | click | scroll | type
    url: str | None = None
    page: str | None = None  # page url the click/type element lives on
    mark: int | None = None
    value: str | None = None
    direction: str | None = None
    pixels: int | None = None
    narration: str | None = None
    effect: str | None = None


@dataclass
class DemoPlan:
    steps: list[PlanStep] = field(default_factory=list)
    feature_reached: bool = False
    rationale: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)


_PLAN_SYSTEM = """\
You are a web-demo planner. You are given a user QUERY describing a feature to
showcase and a SITE MAP discovered by crawling the website (pages with their
links and interactive elements). Choose the single best ordered demo: the
sequence of steps that best shows or exercises the requested feature.

Respond with ONLY a JSON object:
{
  "feature_reached": <true|false>,
  "rationale": "<one short sentence>",
  "steps": [
    {"action": "navigate", "url": "<a page url from the map>", "narration": "..."},
    {"action": "click", "page": "<page url>", "mark": <element id on that page>,
     "narration": "...", "effect": "spotlight|highlight|glow|null"},
    {"action": "scroll", "direction": "down", "pixels": 720, "narration": "..."}
  ]
}
Rules: only navigate to URLs that appear in the SITE MAP; only click a mark that
exists on the referenced page. Keep it concise. Set feature_reached=false if the
map contains nothing relevant to the query.
"""


def _heuristic_plan(graph: ExplorationGraph, query: str, *, max_steps: int) -> DemoPlan:
    """Deterministic picker: rank elements by query relevance across all pages."""
    keywords = _keywords(query)
    best: tuple[float, SitePage, SiteElement] | None = None
    for page in graph.pages.values():
        for el in page.elements:
            rel = _relevance(el.name, el.role, keywords)
            if best is None or rel > best[0]:
                best = (rel, page, el)

    steps: list[PlanStep] = []
    reached = False
    if best is not None and best[0] > 0:
        _, page, el = best
        reached = True
        if page.url != graph.start_url:
            steps.append(
                PlanStep(
                    action="navigate",
                    url=page.url,
                    narration=f"Navigating to {page.title or page.url}.",
                )
            )
        if el.is_link and el.href:
            steps.append(
                PlanStep(
                    action="navigate",
                    url=_normalize_url(el.href),
                    narration=f"Opening '{el.name}'.",
                    effect="spotlight",
                )
            )
        elif el.locator is not None:
            steps.append(
                PlanStep(
                    action="click",
                    page=page.url,
                    mark=el.mark,
                    narration=f"Selecting '{el.name}'.",
                    effect="spotlight",
                )
            )
    if not steps:
        # Nothing relevant: at least open the start page.
        steps.append(
            PlanStep(action="navigate", url=graph.start_url, narration="Opening the site.")
        )
    return DemoPlan(steps=steps[:max_steps], feature_reached=reached, rationale="relevance pick")


def _parse_plan(data: dict[str, Any], graph: ExplorationGraph, *, max_steps: int) -> DemoPlan:
    raw_steps = data.get("steps")
    steps: list[PlanStep] = []
    known_urls = set(graph.pages) | {
        _normalize_url(e.href) for p in graph.pages.values() for e in p.elements if e.href
    }
    if isinstance(raw_steps, list):
        for s in raw_steps:
            if not isinstance(s, dict):
                continue
            kind = str(s.get("action", "")).strip().lower()
            if kind == "navigate":
                url = _normalize_url(str(s.get("url") or ""))
                if not url or url not in known_urls:
                    continue  # only navigate to discovered URLs (anti-hallucination)
                steps.append(PlanStep(action="navigate", url=url, narration=s.get("narration")))
            elif kind in ("click", "type"):
                page_url = _normalize_url(str(s.get("page") or ""))
                mark = s.get("mark")
                mark = int(mark) if isinstance(mark, int | float) else None
                page = graph.page(page_url)
                if page is None or mark is None or page.by_mark(mark) is None:
                    continue
                steps.append(
                    PlanStep(
                        action=kind,
                        page=page_url,
                        mark=mark,
                        value=s.get("value"),
                        narration=s.get("narration"),
                        effect=s.get("effect") or None,
                    )
                )
            elif kind == "scroll":
                steps.append(
                    PlanStep(
                        action="scroll",
                        direction=str(s.get("direction") or "down"),
                        pixels=int(s["pixels"])
                        if isinstance(s.get("pixels"), int | float)
                        else 720,
                        narration=s.get("narration"),
                    )
                )
            if len(steps) >= max_steps:
                break
    return DemoPlan(
        steps=steps,
        feature_reached=bool(data.get("feature_reached", bool(steps))),
        rationale=str(data.get("rationale", "")),
    )


def plan_demo_from_graph(
    graph: ExplorationGraph,
    query: str,
    *,
    llm: LLMProvider | None = None,
    max_steps: int = 8,
) -> DemoPlan:
    """Pick the demo for *query* from the exploration *graph*.

    With an *llm* the site map is serialised and the model returns a JSON plan
    (validated against the discovered pages/elements so it can't invent
    targets). Without one, a deterministic relevance-based picker is used.
    """
    if llm is None:
        return _heuristic_plan(graph, query, max_steps=max_steps)

    user = f"QUERY: {query}\n\nSITE MAP:\n{graph.to_prompt()}\n\nReturn the JSON plan."
    resp = llm.complete(_PLAN_SYSTEM, user, temperature=0.0)
    plan = _parse_plan(resp.json(), graph, max_steps=max_steps)
    plan.usage = resp.usage
    if not plan.steps:
        # Model returned nothing usable — fall back so we still produce a demo.
        plan = _heuristic_plan(graph, query, max_steps=max_steps)
        plan.usage = resp.usage
    return plan


# ── plan → trajectory (so it flows through synthesize_config) ─────────────────


def plan_to_trajectory(plan: DemoPlan, graph: ExplorationGraph, query: str) -> Trajectory:
    """Materialise *plan* into a :class:`Trajectory` for synthesis/scoring."""
    traj = Trajectory(query=query, start_url=graph.start_url)
    cur_url = graph.start_url
    for step in plan.steps:
        action = _plan_step_to_action(step, graph)
        if action is None:
            continue
        obs = PageObservation(url=cur_url, title="", strategy="axtree")
        result = StepResult(ok=True, action=action, url_before=cur_url)
        if action.kind == "navigate" and action.url:
            result.url_after = action.url
            result.page_changed = action.url != cur_url
            cur_url = action.url
        traj.add(TrajectoryStep(obs, action, result))
    traj.feature_reached = plan.feature_reached
    traj.final_url = cur_url
    return traj


def _plan_step_to_action(step: PlanStep, graph: ExplorationGraph) -> AgentAction | None:
    if step.action == "navigate" and step.url:
        return AgentAction(kind="navigate", url=step.url, narration=step.narration)
    if step.action in ("click", "type") and step.page is not None and step.mark is not None:
        page = graph.page(step.page)
        el = page.by_mark(step.mark) if page else None
        if el is None or el.locator is None:
            return None
        if step.action == "type":
            return AgentAction(
                kind="type",
                mark=step.mark,
                locator=el.locator,
                value=step.value or "demo",
                narration=step.narration,
                effect_hint=step.effect,
            )
        return AgentAction(
            kind="click",
            mark=step.mark,
            locator=el.locator,
            narration=step.narration,
            effect_hint=step.effect,
        )
    if step.action == "scroll":
        return AgentAction(
            kind="scroll",
            direction=step.direction or "down",
            pixels=step.pixels or 720,
            narration=step.narration,
        )
    return None


def _plan_tokens(plan: DemoPlan) -> int:
    return _estimate_tokens(plan.rationale) + plan.usage.total
