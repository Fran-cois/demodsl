"""Adaptive web-page representation for the discovery harness.

At each step this module builds the **cheapest page representation that still
grounds the next action**, under a hard token budget.  Three representation
tiers are supported, escalated on demand (following common web-agent
representations):

1. ``axtree``  — a compact, accessibility-tree-style list of interactive
   elements (role + accessible name).  Cheapest; the default.  (cf. WebArena.)
2. ``dom``     — the same list enriched with structural / textual context for
   disambiguation.  (cf. Mind2Web DOM-candidate ranking.)
3. ``som``     — Set-of-Marks: every candidate carries its bounding box so a
   multimodal model can ground against a screenshot.  (cf. VisualWebArena /
   WebVoyager.)

The builder is deliberately decoupled from *how* elements are obtained: it asks
the :class:`~demodsl.discover.controller.WebEnvironment` for raw element records
and then performs ranking, budgeting and serialisation.  This lets the exact
same optimisation run against a live Playwright browser or an offline simulated
site (used by the benchmark).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from demodsl.discover._tokens import estimate_tokens
from demodsl.models import Locator

if TYPE_CHECKING:  # pragma: no cover - typing only
    from demodsl.discover.controller import WebEnvironment

Strategy = Literal["axtree", "dom", "som"]

#: Representation tiers in escalation order (cheap → rich).
STRATEGY_LADDER: tuple[Strategy, ...] = ("axtree", "dom", "som")

#: Locator-type robustness scores in [0, 1]. Higher = more stable across runs.
#: Mirrors the priority ladder used by the recorder Chrome extension
#: (data-testid > id > role+aria > visible text > css path > xpath).
LOCATOR_ROBUSTNESS: dict[str, float] = {
    "id": 0.9,
    "accessibility_id": 0.85,
    "text": 0.7,
    "css": 0.5,
    "xpath": 0.3,
    "class_name": 0.4,
}

# A css selector built around an explicit data-testid is the most stable of all.
_TESTID_RE = re.compile(r"\[data-test(?:id)?=", re.IGNORECASE)

# Role priority when budget forces truncation (most demo-worthy first).
_ROLE_PRIORITY: dict[str, int] = {
    "button": 5,
    "link": 5,
    "tab": 4,
    "menuitem": 4,
    "checkbox": 3,
    "switch": 3,
    "textbox": 3,
    "combobox": 3,
    "searchbox": 3,
    "radio": 2,
    "option": 2,
    "heading": 1,
}


def locator_robustness(locator: Locator | None) -> float:
    """Return a robustness score in [0, 1] for *locator*."""
    if locator is None:
        return 0.0
    if locator.type == "css" and _TESTID_RE.search(locator.value):
        return 0.95
    return LOCATOR_ROBUSTNESS.get(locator.type, 0.4)


@dataclass
class ElementRef:
    """A single interactive element exposed to the policy via a *mark* id."""

    mark: int
    role: str
    name: str
    tag: str = ""
    locator: Locator | None = None
    bbox: dict[str, float] | None = None
    in_viewport: bool = True
    editable: bool = False
    relevance: float = 0.0
    attrs: str = ""  # flattened DOM attributes used for grounding (not shown in prompt)
    href: str = ""  # absolute destination of a link element (grounds navigation)

    def label(self) -> str:
        name = self.name.strip() or "(no name)"
        return f"{self.role} {name!r}"

    def serialize(self, strategy: Strategy) -> str:
        base = f"[{self.mark}] {self.role}: {self.name.strip() or '—'}"
        if self.editable:
            base += " (input)"
        if strategy == "som" and self.bbox:
            b = self.bbox
            cx = int(b.get("x", 0) + b.get("width", 0) / 2)
            cy = int(b.get("y", 0) + b.get("height", 0) / 2)
            base += f" @({cx},{cy})"
        if strategy == "dom" and self.tag:
            base += f" <{self.tag}>"
        return base


@dataclass
class PageObservation:
    """A budgeted, serialised representation of the current page."""

    url: str
    title: str
    strategy: Strategy
    elements: list[ElementRef] = field(default_factory=list)
    text: str = ""
    token_estimate: int = 0
    screenshot: Path | None = None
    truncated: int = 0  # how many elements were dropped to fit the budget

    def by_mark(self, mark: int) -> ElementRef | None:
        for el in self.elements:
            if el.mark == mark:
                return el
        return None

    def mean_robustness(self) -> float:
        locs = [locator_robustness(el.locator) for el in self.elements if el.locator]
        return sum(locs) / len(locs) if locs else 0.0


@dataclass
class DecisionContext:
    """Structured inputs a policy hands to a provider for the next decision.

    Lets an *offline* provider (e.g. the simulated model) decide from typed data
    instead of reverse-parsing the rendered prompt string — which coupled the
    provider to the exact prompt format (a change to the system prompt silently
    broke the simulator). Cloud providers ignore it and use the ``(system,
    user)`` text as before.
    """

    query: str
    observation: PageObservation
    history: tuple[str, ...] = ()
    reflection: str | None = None


_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "or",
        "for",
        "on",
        "in",
        "with",
        "show",
        "see",
        "test",
        "click",
        "open",
        "view",
        "go",
        "page",
        "feature",
        "me",
        "my",
        "your",
        "this",
        "that",
        "it",
        "is",
        "how",
        "do",
        "i",
        "can",
    }
)


def _keywords(query: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", query.lower())
    return [t for t in toks if t not in _STOPWORDS and len(t) > 1]


_ATTR_KEYS = (
    "aria-label",
    "placeholder",
    "title",
    "name",
    "type",
    "value",
    "alt",
    "id",
    "role",
)


def _attrs_text(rec: dict[str, Any]) -> str:
    """Flatten an element's grounding-relevant DOM attributes into a search blob.

    Accepts either a pre-flattened string (``rec['attrs']``) or a Mind2Web-style
    ``attributes`` dict, mirroring how real datasets expose element metadata.
    """
    a = rec.get("attrs")
    if a is None:
        a = rec.get("attributes")
    if isinstance(a, str):
        return a[:200]
    if isinstance(a, dict):
        return " ".join(str(a[k]) for k in _ATTR_KEYS if a.get(k))[:200]
    return ""


def _fuzzy_overlap(keyword: str, hay: str) -> float:
    """Character-trigram Jaccard between *keyword* and the closest token in *hay*.

    Dependency-free and bounded in [0, 1].  Lets near-synonyms ("checkout" vs
    "check out", "signup" vs "sign up") earn a small positive signal instead of
    a hard zero — the Mind2Web grounding failure mode where the instruction and
    the element label do not share a whole token.
    """
    if len(keyword) < 4:
        return 0.0
    kg = {keyword[i : i + 3] for i in range(len(keyword) - 2)}
    best = 0.0
    for tok in hay.split():
        if len(tok) < 4:
            continue
        tg = {tok[i : i + 3] for i in range(len(tok) - 2)}
        inter = len(kg & tg)
        if inter:
            best = max(best, inter / len(kg | tg))
    return best


def _relevance(
    name: str,
    role: str,
    keywords: list[str],
    attrs: str = "",
    *,
    fuzzy: bool = False,
) -> float:
    """Query relevance of an element in [0, 1].

    Default (``attrs=''``, ``fuzzy=False``) is the lexical name/role signal kept
    for the baseline representations.  In attribute-aware mode the element's DOM
    attributes also count and a bounded character-trigram bonus is added for
    keywords with no whole-token match — this is the data-driven grounding
    improvement validated on the Mind2Web eval.
    """
    if not keywords:
        return 0.0
    hay = f"{name} {role} {attrs}".lower()
    hits = sum(1 for k in keywords if k in hay)
    exact = sum(1 for k in keywords if re.search(rf"\b{re.escape(k)}\b", hay))
    base = (hits + 0.5 * exact) / (len(keywords) + 0.5 * len(keywords))
    if not fuzzy:
        return base
    miss = [k for k in keywords if k not in hay]
    if miss:
        # Bounded so a fuzzy match can never outrank a real lexical one.
        fuzz = sum(_fuzzy_overlap(k, hay) for k in miss) / len(keywords)
        base = min(1.0, base + 0.25 * fuzz)
    return base


def serialize_elements(url: str, title: str, elements: list[ElementRef], strategy: Strategy) -> str:
    """Serialise a page representation exactly as the policy prompt sees it.

    Exposed at module scope so other layers (e.g. the persona's viewport
    restriction) can rebuild a *consistent* textual view after filtering the
    element set, instead of re-implementing the prompt surface.
    """
    lines = [f"URL: {url}", f"TITLE: {title}", f"REPRESENTATION: {strategy}", "ELEMENTS:"]
    if not elements:
        lines.append("  (no interactive elements detected)")
    for el in elements:
        lines.append("  " + el.serialize(strategy))
    return "\n".join(lines)


class ObservationBuilder:
    """Builds budgeted, query-aware page observations.

    Parameters
    ----------
    token_budget:
        Hard cap on the serialised representation size (token estimate).  When
        exceeded, the lowest-value elements are dropped (off-screen first, then
        by role priority and relevance) — this is the representation
        optimisation that keeps cost bounded on huge pages.
    max_elements:
        Absolute cap on the number of marks shown regardless of budget.
    """

    def __init__(
        self,
        *,
        token_budget: int = 1024,
        max_elements: int = 60,
        attribute_aware: bool = True,
        recall_floor: int = 8,
    ) -> None:
        self.token_budget = token_budget
        self.max_elements = max_elements
        # Attribute-aware + fuzzy relevance and a recall floor on truncation are
        # the Mind2Web-driven grounding improvements (see
        # demodsl/discover/mind2web.py for the measured before/after gains).
        self.attribute_aware = attribute_aware
        self.recall_floor = max(0, recall_floor)

    def build(
        self,
        env: WebEnvironment,
        *,
        query: str = "",
        strategy: Strategy = "axtree",
        capture_screenshot: bool = False,
    ) -> PageObservation:
        raw = env.extract_elements()
        keywords = _keywords(query)
        refs = self._to_refs(raw, keywords)
        ranked = self._rank(refs)

        kept, truncated = self._apply_budget(ranked, strategy)
        # Re-number marks densely 0..N for a clean, stable prompt surface.
        for i, el in enumerate(kept):
            el.mark = i

        title = ""
        url = ""
        try:
            url = env.current_url()
            title = env.title()
        except Exception:  # pragma: no cover - defensive
            pass

        text = self._serialize(url, title, kept, strategy)
        shot: Path | None = None
        if strategy == "som" and capture_screenshot:
            shot = self._maybe_screenshot(env)

        return PageObservation(
            url=url,
            title=title,
            strategy=strategy,
            elements=kept,
            text=text,
            token_estimate=estimate_tokens(text),
            screenshot=shot,
            truncated=truncated,
        )

    # ── internals ─────────────────────────────────────────────────────────

    def _to_refs(self, raw: list[dict[str, Any]], keywords: list[str]) -> list[ElementRef]:
        refs: list[ElementRef] = []
        for i, rec in enumerate(raw):
            loc_rec = rec.get("locator") or {}
            locator: Locator | None = None
            if loc_rec.get("value"):
                try:
                    locator = Locator(type=loc_rec.get("type", "css"), value=str(loc_rec["value"]))
                except Exception:
                    locator = None
            name = str(rec.get("name") or rec.get("text") or "").strip()
            role = str(rec.get("role") or "generic")
            attrs = _attrs_text(rec) if self.attribute_aware else ""
            refs.append(
                ElementRef(
                    mark=i,
                    role=role,
                    name=name,
                    tag=str(rec.get("tag") or ""),
                    locator=locator,
                    bbox=rec.get("bbox"),
                    in_viewport=bool(rec.get("in_viewport", True)),
                    editable=bool(rec.get("editable", False)),
                    relevance=_relevance(name, role, keywords, attrs, fuzzy=self.attribute_aware),
                    attrs=attrs,
                    href=str(rec.get("href") or ""),
                )
            )
        return refs

    @staticmethod
    def _element_value(el: ElementRef) -> tuple:
        """Sort key (higher = keep). Viewport > relevance > role > robustness."""
        return (
            el.relevance,
            1 if el.in_viewport else 0,
            _ROLE_PRIORITY.get(el.role, 0),
            locator_robustness(el.locator),
        )

    def _rank(self, refs: list[ElementRef]) -> list[ElementRef]:
        return sorted(refs, key=self._element_value, reverse=True)

    def _apply_budget(
        self, ranked: list[ElementRef], strategy: Strategy
    ) -> tuple[list[ElementRef], int]:
        kept: list[ElementRef] = []
        running = 0
        header = 40  # token allowance for url/title/header lines
        floor = min(self.recall_floor, self.max_elements)
        for el in ranked:
            if len(kept) >= self.max_elements:
                break
            cost = estimate_tokens(el.serialize(strategy)) + 1
            over_budget = bool(running + cost + header > self.token_budget and kept)
            # Recall floor: always keep the top-`floor` ranked candidates even
            # when over budget, so a low-lexical-overlap ground-truth element is
            # not truncated away (Mind2Web candidate-recall objective). Past the
            # floor, respect the token budget exactly as before.
            if over_budget and len(kept) >= floor:
                break
            kept.append(el)
            running += cost
        truncated = len(ranked) - len(kept)
        # Preserve a stable, readable order: viewport-first by mark.
        kept.sort(key=lambda e: (0 if e.in_viewport else 1, -e.relevance))
        return kept, truncated

    @staticmethod
    def _serialize(url: str, title: str, elements: list[ElementRef], strategy: Strategy) -> str:
        return serialize_elements(url, title, elements, strategy)

    @staticmethod
    def _maybe_screenshot(env: WebEnvironment) -> Path | None:
        shot = getattr(env, "screenshot_to_tmp", None)
        if callable(shot):
            try:
                return shot()
            except Exception:  # pragma: no cover - best effort
                return None
        return None
