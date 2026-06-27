"""DemoDSL Discovery Harness.

An AI harness that, given a natural-language *query* about a website feature
("show the checkout flow", "test the pricing toggle"), drives a real (optionally
**authenticated**) browser, explores the page, and discovers the **best
DemoDSL configuration** to see / test that feature — then synthesises a
validated :class:`~demodsl.models.DemoConfig` and (optionally) renders the demo
video as proof.

Design pillars (grounded in the web-agent SOTA):

* **Adaptive page representation** — at every step the observation builder picks
  the cheapest representation that still grounds the next action (compact
  accessibility tree → pruned DOM → Set-of-Marks screenshot), under a hard token
  budget. This is the core optimisation (cf. WebArena's a11y-tree observation and
  VisualWebArena / WebVoyager's Set-of-Marks prompting).
* **ReAct policy** with Reflexion-style retries (reason → act → observe).
* **Configurable search** — greedy by default, optional best-of-N tree search
  with self-evaluation (cf. *Tree Search for Language Model Agents*).
* **Robust grounding** — locators are emitted using the same priority ladder as
  the recorder Chrome extension (data-testid > id > role+aria > text > css path).
* **Authenticated discovery** — reuses the project's authenticated-browser
  providers (``playwright-cdp`` / ``playwright-persistent``) and the
  ``oauth_login`` governance flow so gated features can be discovered too.

Public API:
    >>> from demodsl.discover import DiscoveryHarness
    >>> harness = DiscoveryHarness.build(policy="heuristic")
    >>> result = harness.discover(url="https://example.com", query="open pricing")
    >>> result.config_dict["scenarios"][0]["steps"]  # doctest: +SKIP
"""

from __future__ import annotations

from demodsl.discover.actions import ACTION_SPACE, AgentAction
from demodsl.discover.explore import (
    DemoPlan,
    ExplorationGraph,
    SiteElement,
    SitePage,
    crawl_site,
    plan_demo_from_graph,
)
from demodsl.discover.harness import HARNESS_VERSION, DiscoveryHarness, DiscoveryResult
from demodsl.discover.llm import (
    LLMProvider,
    LLMProviderFactory,
    LLMResponse,
    TokenUsage,
)
from demodsl.discover.observation import ElementRef, ObservationBuilder, PageObservation
from demodsl.discover.panel import PANEL_ARCHETYPES, PanelArchetype, build_panel
from demodsl.discover.persona import (
    PERSONA_PRESETS,
    Persona,
    PersonaPolicy,
    PersonaReport,
    PersonaState,
    build_persona_report,
)
from demodsl.discover.review import PersonaRunResult, ReviewReport, run_review
from demodsl.discover.reward import FeatureEvaluator, TrajectoryScore, score_trajectory
from demodsl.discover.search import GreedySearch, SearchResult, TreeSearch
from demodsl.discover.synthesize import synthesize_config

__all__ = [
    "ACTION_SPACE",
    "AgentAction",
    "DemoPlan",
    "DiscoveryHarness",
    "DiscoveryResult",
    "ElementRef",
    "ExplorationGraph",
    "FeatureEvaluator",
    "GreedySearch",
    "HARNESS_VERSION",
    "LLMProvider",
    "LLMProviderFactory",
    "LLMResponse",
    "ObservationBuilder",
    "PageObservation",
    "PANEL_ARCHETYPES",
    "PanelArchetype",
    "PERSONA_PRESETS",
    "Persona",
    "PersonaPolicy",
    "PersonaReport",
    "PersonaRunResult",
    "PersonaState",
    "ReviewReport",
    "SearchResult",
    "SiteElement",
    "SitePage",
    "TokenUsage",
    "TrajectoryScore",
    "TreeSearch",
    "build_panel",
    "build_persona_report",
    "crawl_site",
    "plan_demo_from_graph",
    "run_review",
    "score_trajectory",
    "synthesize_config",
]
