"""SOTA benchmark for the discovery harness (offline & reproducible).

The benchmark is an **ablation of the page-representation strategy**, which is
the central contribution of the harness.  Three agents run the *same* policy on
the *same* deterministic simulated web environment; only how they represent the
page differs:

* ``full_dom``      — dumps every interactive element each step with raw XPath
  locators and no budget.  Stand-in for a full-DOM / HTML web agent
  (WebArena-style text observation without pruning).
* ``viewport_som``  — only in-viewport elements with coordinate/CSS locators,
  must scroll to discover off-screen features.  Stand-in for a screenshot /
  Set-of-Marks agent (WebVoyager / VisualWebArena style).
* ``adaptive``      — **ours**: relevance-ranked, token-budgeted representation
  that surfaces off-viewport targets, escalates to Set-of-Marks only on demand,
  and emits robust locators (data-testid > id > role+aria > text > css).

Because the environment is fully simulated and deterministic, the numbers are
reproducible — suitable for a paper's results table.  No network, no API key.

Run it:
    >>> from demodsl.discover.benchmark import run_default_benchmark
    >>> report = run_default_benchmark()
    >>> print(report.to_markdown())  # doctest: +SKIP
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from demodsl.discover.observation import (
    ElementRef,
    PageObservation,
    Strategy,
    _keywords,
    _relevance,
    estimate_tokens,
)
from demodsl.discover.policy import HeuristicPolicy, Policy
from demodsl.discover.reward import FeatureEvaluator, score_trajectory
from demodsl.discover.search import GreedySearch
from demodsl.models import Locator

logger = logging.getLogger(__name__)

_VIEWPORT_H = 800
_SCROLL_PX = 720


# ── Simulated web environment ────────────────────────────────────────────────


@dataclass
class SimElement:
    eid: str
    name: str
    role: str
    abs_y: int
    target: str | None = None  # url to navigate to on click
    editable: bool = False
    testid: str | None = None
    dom_id: str | None = None

    def robust_locator(self) -> Locator:
        """Priority ladder: data-testid > id > visible text > css path."""
        if self.testid:
            return Locator(type="css", value=f'[data-testid="{self.testid}"]')
        if self.dom_id:
            return Locator(type="id", value=self.dom_id)
        if self.name and len(self.name) <= 40:
            return Locator(type="text", value=self.name)
        return Locator(type="css", value=f"#{self.eid}")

    def xpath_locator(self) -> Locator:
        return Locator(type="xpath", value=f"//*[@data-eid='{self.eid}']")

    def css_locator(self) -> Locator:
        return Locator(type="css", value=f"[data-eid='{self.eid}']")


@dataclass
class SimPage:
    url: str
    title: str
    elements: list[SimElement]
    height: int = 1000


class SimulatedEnvironment:
    """A deterministic, scrollable multi-page site implementing WebEnvironment."""

    def __init__(self, pages: dict[str, SimPage], start_url: str) -> None:
        self.pages = pages
        self.start_url = start_url
        self.url = start_url
        self.scroll_y = 0
        # Resolve any emitted locator back to an element id.
        self._index: dict[tuple[str, str], str] = {}
        for page in pages.values():
            for el in page.elements:
                for loc in (el.robust_locator(), el.xpath_locator(), el.css_locator()):
                    self._index[(loc.type, loc.value)] = el.eid

    # WebEnvironment surface ------------------------------------------------

    def extract_elements(self) -> list[dict[str, Any]]:
        page = self.pages[self.url]
        records: list[dict[str, Any]] = []
        for el in page.elements:
            top = el.abs_y - self.scroll_y
            in_view = 0 <= top < _VIEWPORT_H
            loc = el.robust_locator()
            records.append(
                {
                    "tag": "a" if el.target else ("input" if el.editable else "button"),
                    "role": el.role,
                    "name": el.name,
                    "text": el.name,
                    "editable": el.editable,
                    "in_viewport": in_view,
                    "bbox": {"x": 40.0, "y": float(top), "width": 200.0, "height": 36.0},
                    "locator": {"type": loc.type, "value": loc.value},
                    # a link element exposes its destination (grounds navigation):
                    "href": el.target or "",
                    # extras consumed by baseline representations:
                    "_eid": el.eid,
                    "_xpath": el.xpath_locator().value,
                    "_css": el.css_locator().value,
                    "_abs_y": el.abs_y,
                }
            )
        return records

    def current_url(self) -> str:
        return self.url

    def title(self) -> str:
        return self.pages[self.url].title

    def navigate(self, url: str) -> None:
        if url in self.pages:
            self.url = url
            self.scroll_y = 0

    def click(self, locator: Locator) -> None:
        eid = self._index.get((locator.type, locator.value))
        if eid is None:
            raise RuntimeError(f"element not found for locator {locator.type}={locator.value!r}")
        el = self._find(eid)
        if el is not None and el.target:
            self.navigate(el.target)

    def type_text(self, locator: Locator, value: str) -> None:
        if (locator.type, locator.value) not in self._index:
            raise RuntimeError("input not found")

    def scroll(self, direction: str, pixels: int) -> None:
        page = self.pages[self.url]
        delta = pixels if direction == "down" else -pixels
        self.scroll_y = max(0, min(self.scroll_y + delta, max(0, page.height - _VIEWPORT_H)))

    def wait_for(self, locator: Locator, timeout: float = 5.0) -> None:
        if (locator.type, locator.value) not in self._index:
            raise RuntimeError("element never appeared")

    def close(self) -> None:
        return None

    def _find(self, eid: str) -> SimElement | None:
        for page in self.pages.values():
            for el in page.elements:
                if el.eid == eid:
                    return el
        return None


# ── Representation strategies (the variable under test) ──────────────────────


class Representation:
    """Common ``.build()`` contract so GreedySearch can use any strategy."""

    name = "abstract"

    def build(
        self,
        env: Any,
        *,
        query: str = "",
        strategy: Strategy = "axtree",
        capture_screenshot: bool = False,
    ) -> PageObservation:  # pragma: no cover - overridden
        raise NotImplementedError


def _refs_from_records(
    records: list[dict[str, Any]],
    keywords: list[str],
    *,
    locator_kind: str,
    viewport_only: bool,
) -> list[ElementRef]:
    refs: list[ElementRef] = []
    for i, rec in enumerate(records):
        if viewport_only and not rec.get("in_viewport", True):
            continue
        if locator_kind == "xpath":
            loc = Locator(type="xpath", value=rec["_xpath"])
        elif locator_kind == "css":
            loc = Locator(type="css", value=rec["_css"])
        else:  # robust
            lr = rec["locator"]
            loc = Locator(type=lr["type"], value=lr["value"])
        name = rec.get("name", "")
        role = rec.get("role", "generic")
        refs.append(
            ElementRef(
                mark=i,
                role=role,
                name=name,
                tag=rec.get("tag", ""),
                locator=loc,
                bbox=rec.get("bbox"),
                in_viewport=bool(rec.get("in_viewport", True)),
                editable=bool(rec.get("editable", False)),
                relevance=_relevance(name, role, keywords),
            )
        )
    return refs


def _serialize(url: str, title: str, elements: list[ElementRef], strategy: Strategy) -> str:
    lines = [f"URL: {url}", f"TITLE: {title}", f"REPRESENTATION: {strategy}", "ELEMENTS:"]
    for el in elements:
        lines.append("  " + el.serialize(strategy))
    return "\n".join(lines)


class FullDomRepresentation(Representation):
    """SOTA-style: full element dump, raw XPath locators, no budget."""

    name = "full_dom"

    def build(self, env, *, query="", strategy="axtree", capture_screenshot=False):  # type: ignore[no-untyped-def]
        records = env.extract_elements()
        kws = _keywords(query)
        refs = _refs_from_records(records, kws, locator_kind="xpath", viewport_only=False)
        refs.sort(key=lambda e: e.bbox["y"] if e.bbox else 0)
        for i, el in enumerate(refs):
            el.mark = i
        text = _serialize(env.current_url(), env.title(), refs, "dom")
        return PageObservation(
            url=env.current_url(),
            title=env.title(),
            strategy="dom",
            elements=refs,
            text=text,
            token_estimate=estimate_tokens(text),
        )


class ViewportSomRepresentation(Representation):
    """Screenshot / Set-of-Marks style: in-viewport only, CSS/coord locators."""

    name = "viewport_som"

    def build(self, env, *, query="", strategy="axtree", capture_screenshot=False):  # type: ignore[no-untyped-def]
        records = env.extract_elements()
        kws = _keywords(query)
        refs = _refs_from_records(records, kws, locator_kind="css", viewport_only=True)
        for i, el in enumerate(refs):
            el.mark = i
        text = _serialize(env.current_url(), env.title(), refs, "som")
        return PageObservation(
            url=env.current_url(),
            title=env.title(),
            strategy="som",
            elements=refs,
            text=text,
            token_estimate=estimate_tokens(text),
        )


class AdaptiveRepresentation(Representation):
    """Ours: relevance-ranked, token-budgeted, robust locators, off-viewport aware."""

    name = "adaptive"

    def __init__(self, token_budget: int = 320, max_elements: int = 24) -> None:
        from demodsl.discover.observation import ObservationBuilder

        self._builder = ObservationBuilder(token_budget=token_budget, max_elements=max_elements)

    def build(self, env, *, query="", strategy="axtree", capture_screenshot=False):  # type: ignore[no-untyped-def]
        return self._builder.build(
            env, query=query, strategy=strategy, capture_screenshot=capture_screenshot
        )


REPRESENTATIONS: dict[str, Callable[[], Representation]] = {
    "full_dom": FullDomRepresentation,
    "viewport_som": ViewportSomRepresentation,
    "adaptive": AdaptiveRepresentation,
}


# ── Tasks & sites ────────────────────────────────────────────────────────────


@dataclass
class BenchmarkTask:
    name: str
    query: str
    site: str
    start_url: str


def _shop_site() -> dict[str, SimPage]:
    home = SimPage(
        url="https://shop.example.com/",
        title="Shop — Home",
        height=6800,
        elements=[
            SimElement(
                "nav-cart",
                "Shopping cart",
                "link",
                40,
                target="https://shop.example.com/cart",
                testid="nav-cart",
            ),
            SimElement("nav-account", "Account", "link", 40, dom_id="account"),
            SimElement("hero-buy", "Buy now", "button", 360, testid="buy"),
            SimElement("feat-1", "Free shipping", "button", 1200),
            SimElement(
                "feat-2",
                "Product reviews",
                "link",
                2600,
                target="https://shop.example.com/reviews",
                testid="reviews",
            ),
            SimElement("settings-dark", "Dark mode toggle", "switch", 6000, dom_id="dark-mode"),
        ],
    )
    cart = SimPage(
        url="https://shop.example.com/cart",
        title="Shopping cart — Checkout",
        height=1200,
        elements=[
            SimElement("checkout", "Proceed to checkout", "button", 200, testid="checkout"),
        ],
    )
    reviews = SimPage(
        url="https://shop.example.com/reviews",
        title="Product reviews",
        height=1400,
        elements=[
            SimElement("write-review", "Write a review", "button", 200, testid="write-review"),
        ],
    )
    return {p.url: p for p in (home, cart, reviews)}


def _docs_site() -> dict[str, SimPage]:
    # A deliberately large page to stress the token budget of full_dom.
    big_elems = [
        SimElement(f"link-{i}", f"Doc section {i}", "link", 200 + i * 120) for i in range(60)
    ]
    home = SimPage(
        url="https://docs.example.com/",
        title="Docs — Home",
        height=8000,
        elements=[
            SimElement(
                "nav-pricing",
                "Pricing",
                "link",
                40,
                target="https://docs.example.com/pricing",
                testid="pricing",
            ),
            SimElement("search", "Search docs", "searchbox", 120, editable=True, testid="search"),
            *big_elems,
        ],
    )
    pricing = SimPage(
        url="https://docs.example.com/pricing",
        title="Pricing plans",
        height=1000,
        elements=[
            SimElement("plan-pro", "Choose Pro plan", "button", 200, testid="plan-pro"),
        ],
    )
    return {p.url: p for p in (home, pricing)}


_SITES: dict[str, Callable[[], dict[str, SimPage]]] = {
    "shop": _shop_site,
    "docs": _docs_site,
}


def default_tasks() -> list[BenchmarkTask]:
    return [
        BenchmarkTask("cart_nav", "open the shopping cart", "shop", "https://shop.example.com/"),
        BenchmarkTask("reviews", "view product reviews", "shop", "https://shop.example.com/"),
        BenchmarkTask(
            "dark_mode", "change to dark mode toggle", "shop", "https://shop.example.com/"
        ),
        BenchmarkTask("pricing", "open the pricing page", "docs", "https://docs.example.com/"),
        BenchmarkTask("search_docs", "search docs", "docs", "https://docs.example.com/"),
    ]


# ── Runner & report ──────────────────────────────────────────────────────────


@dataclass
class TaskOutcome:
    task: str
    agent: str
    reached: bool
    steps: int
    tokens: int
    robustness: float
    score: float


@dataclass
class AgentMetrics:
    agent: str
    success_rate: float
    avg_steps: float
    avg_tokens: float
    avg_robustness: float
    avg_score: float
    n: int


@dataclass
class BenchmarkReport:
    outcomes: list[TaskOutcome] = field(default_factory=list)
    metrics: list[AgentMetrics] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "metrics": [m.__dict__ for m in self.metrics],
                "outcomes": [o.__dict__ for o in self.outcomes],
            },
            indent=2,
        )

    def to_markdown(self) -> str:
        lines = [
            "# DemoDSL Discovery — Representation Ablation",
            "",
            "Same policy + same deterministic environment; only the page "
            "representation differs. Higher success / robustness / score is "
            "better; lower steps / tokens is better.",
            "",
            "| Agent | Success | Avg steps | Avg tokens | Robustness | Score |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for m in sorted(self.metrics, key=lambda x: x.avg_score, reverse=True):
            lines.append(
                f"| `{m.agent}` | {m.success_rate * 100:.0f}% | {m.avg_steps:.1f} | "
                f"{m.avg_tokens:.0f} | {m.avg_robustness:.2f} | {m.avg_score:.3f} |"
            )
        lines += [
            "",
            "## Per-task detail",
            "",
            "| Task | Agent | Reached | Steps | Tokens | Robustness | Score |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for o in self.outcomes:
            lines.append(
                f"| {o.task} | `{o.agent}` | {'✓' if o.reached else '✗'} | {o.steps} | "
                f"{o.tokens} | {o.robustness:.2f} | {o.score:.3f} |"
            )
        return "\n".join(lines)


def run_benchmark(
    tasks: list[BenchmarkTask] | None = None,
    *,
    agents: list[str] | None = None,
    policy_factory: Callable[[], Policy] | None = None,
    max_steps: int = 6,
) -> BenchmarkReport:
    tasks = tasks or default_tasks()
    agents = agents or list(REPRESENTATIONS)
    policy_factory = policy_factory or (lambda: HeuristicPolicy(max_scrolls=4))

    report = BenchmarkReport()
    per_agent: dict[str, list[TaskOutcome]] = {a: [] for a in agents}

    for task in tasks:
        for agent in agents:
            builder = REPRESENTATIONS[agent]()
            search = GreedySearch(
                policy_factory(),
                builder=builder,  # type: ignore[arg-type]
                evaluator=FeatureEvaluator(),
                max_steps=max_steps,
            )
            env = SimulatedEnvironment(_SITES[task.site](), task.start_url)
            result = search.run(env, task.query)
            traj = result.trajectory
            score = score_trajectory(traj, feature_reached=traj.feature_reached)
            outcome = TaskOutcome(
                task=task.name,
                agent=agent,
                reached=traj.feature_reached,
                steps=traj.n_steps,
                tokens=traj.usage.total,
                robustness=score.robustness,
                score=score.total,
            )
            report.outcomes.append(outcome)
            per_agent[agent].append(outcome)

    for agent, outs in per_agent.items():
        n = len(outs) or 1
        report.metrics.append(
            AgentMetrics(
                agent=agent,
                success_rate=sum(1 for o in outs if o.reached) / n,
                avg_steps=sum(o.steps for o in outs) / n,
                avg_tokens=sum(o.tokens for o in outs) / n,
                avg_robustness=sum(o.robustness for o in outs) / n,
                avg_score=sum(o.score for o in outs) / n,
                n=len(outs),
            )
        )
    return report


def run_default_benchmark(out_dir: str | Path | None = None) -> BenchmarkReport:
    """Run the default suite and optionally write report.md + report.json."""
    report = run_benchmark()
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "benchmark_report.md").write_text(report.to_markdown(), encoding="utf-8")
        (out / "benchmark_report.json").write_text(report.to_json(), encoding="utf-8")
        logger.info("benchmark report written to %s", out)
    return report
