"""Tests for the offline ``simulated`` LLM backend.

The simulated provider lets the *real* ``LLMPolicy`` code path run end-to-end
with no API key: it decides from the structured ``DecisionContext`` the policy
hands in (typed observation + history) and returns a schema-valid JSON action.
These tests pin its decisions, prove it no longer depends on the prompt wording
(Phase 3 decoupling), and guard the persona viewport fix that keeps a
text-reading base policy honest (it must not "see" off-screen elements).
"""

from __future__ import annotations

from demodsl.discover.benchmark import SimElement, SimPage, SimulatedEnvironment
from demodsl.discover.llm import SimulatedLLMProvider
from demodsl.discover.observation import ObservationBuilder
from demodsl.discover.panel import build_panel
from demodsl.discover.persona import PersonaPolicy
from demodsl.discover.policy import HeuristicPolicy, LLMPolicy
from demodsl.discover.review import ReviewReport, run_review

START = "https://shop.example.com/"
PRICING = "https://shop.example.com/pricing"


def _flat_site() -> SimulatedEnvironment:
    """A site whose pricing target sits in the first viewport."""
    home = SimPage(
        url=START,
        title="Acme — Home",
        height=900,
        elements=[
            SimElement("home", "Home", "link", abs_y=20, target=START, dom_id="nav-home"),
            SimElement(
                "pricing", "Pricing plans", "link", abs_y=200, target=PRICING, testid="pricing-link"
            ),
        ],
    )
    pricing = SimPage(
        url=PRICING,
        title="Pricing plans",
        height=600,
        elements=[SimElement("choose", "Choose a plan", "button", abs_y=120, dom_id="choose")],
    )
    return SimulatedEnvironment({START: home, PRICING: pricing}, START)


def _no_match_home() -> SimulatedEnvironment:
    """A single page with nothing relevant to a pricing query."""
    home = SimPage(
        url=START,
        title="Acme — Home",
        height=900,
        elements=[
            SimElement("home", "Home", "link", abs_y=20, target=START, dom_id="nav-home"),
            SimElement("about", "About us", "link", abs_y=60, target=START, dom_id="nav-about"),
            SimElement("blog", "Blog", "link", abs_y=100, target=START, dom_id="nav-blog"),
        ],
    )
    return SimulatedEnvironment({START: home}, START)


def _deep_site() -> SimulatedEnvironment:
    """The pricing target sits far below the fold (3 scrolls)."""
    home = SimPage(
        url=START,
        title="Acme — Home",
        height=3400,
        elements=[
            SimElement("home", "Home", "link", abs_y=20, target=START, dom_id="nav-home"),
            SimElement("about", "About us", "link", abs_y=60, target=START, dom_id="nav-about"),
            SimElement("blog", "Blog", "link", abs_y=100, target=START, dom_id="nav-blog"),
            SimElement(
                "pricing",
                "Pricing plans",
                "link",
                abs_y=2400,
                target=PRICING,
                testid="pricing-link",
            ),
        ],
    )
    pricing = SimPage(
        url=PRICING,
        title="Pricing plans",
        height=1000,
        elements=[SimElement("choose", "Choose a plan", "button", abs_y=200, dom_id="choose")],
    )
    return SimulatedEnvironment({START: home, PRICING: pricing}, START)


# ── provider decisions through the real LLMPolicy ──────────────────────────────


def test_sim_llm_clicks_matching_element() -> None:
    env = _flat_site()
    obs = ObservationBuilder().build(env, query="pricing plans")
    decision = LLMPolicy(SimulatedLLMProvider()).propose("pricing plans", obs, [])
    action = decision.action
    assert action.kind == "click"
    assert action.locator is not None  # the mark resolved to a real locator
    assert action.feature_reached  # "Pricing plans" is a strong match
    assert decision.usage.total > 0  # accounts tokens like a real call


def test_sim_llm_scrolls_when_nothing_matches() -> None:
    env = _no_match_home()
    obs = ObservationBuilder().build(env, query="pricing plans")
    decision = LLMPolicy(SimulatedLLMProvider()).propose("pricing plans", obs, [])
    assert decision.action.kind == "scroll"
    assert decision.action.direction == "down"


def test_sim_llm_gives_up_after_scroll_budget() -> None:
    env = _no_match_home()
    obs = ObservationBuilder().build(env, query="pricing plans")
    history = ["scroll down"] * 6
    decision = LLMPolicy(SimulatedLLMProvider(max_scrolls=6)).propose("pricing plans", obs, history)
    assert decision.action.kind == "done"
    assert decision.action.feature_reached is False


# ── structured decoupling (Phase 3): no dependence on the prompt wording ────────


def test_sim_llm_decision_independent_of_prompt_wording() -> None:
    # The simulated provider decides from the structured DecisionContext, so it
    # no longer breaks when the policy's prompt text changes.
    from demodsl.discover.observation import DecisionContext

    env = _flat_site()
    obs = ObservationBuilder().build(env, query="pricing plans")
    ctx = DecisionContext(query="pricing plans", observation=obs)
    provider = SimulatedLLMProvider()

    r1 = provider.complete("SYS A", "garbage prompt body", context=ctx)
    r2 = provider.complete("a totally different system prompt", "and user", context=ctx)
    assert r1.json() == r2.json()
    assert r1.json()["action"] == "click"


def test_sim_llm_structured_matches_legacy_prompt_path() -> None:
    # The structured path and the legacy prompt-parsing fallback agree.
    from demodsl.discover.observation import DecisionContext

    env = _flat_site()
    obs = ObservationBuilder().build(env, query="pricing plans")
    provider = SimulatedLLMProvider()

    structured = provider.complete(
        "sys", "ignored", context=DecisionContext(query="pricing plans", observation=obs)
    ).json()
    user = (
        f"QUERY: pricing plans\n\nHISTORY:\n(none yet)\n\n"
        f"CURRENT PAGE:\n{obs.text}\n\nReturn the JSON action."
    )
    legacy = provider.complete("sys", user).json()
    assert structured["action"] == legacy["action"]
    assert structured.get("mark") == legacy.get("mark")


def test_sim_llm_types_into_input() -> None:
    home = SimPage(
        url=START,
        title="Search",
        height=600,
        elements=[
            SimElement("q", "Search products", "textbox", abs_y=120, dom_id="q", editable=True),
        ],
    )
    env = SimulatedEnvironment({START: home}, START)
    obs = ObservationBuilder().build(env, query="search products")
    decision = LLMPolicy(SimulatedLLMProvider()).propose("search products", obs, [])
    assert decision.action.kind == "type"
    assert decision.action.value  # a non-empty query was typed


def test_sim_llm_holds_out_where_heuristic_grabs_weak_banner() -> None:
    home = SimPage(
        url=START,
        title="Acme",
        height=2000,
        elements=[
            SimElement(
                "promo",
                "Discover the club with exclusive plans and member stories for travellers everywhere today",
                "link",
                abs_y=120,
                target=START,
                dom_id="promo",
            ),
        ],
    )
    env = SimulatedEnvironment({START: home}, START)
    obs = ObservationBuilder().build(env, query="pricing plans tickets")
    heur = HeuristicPolicy().propose("pricing plans tickets", obs, [])
    sim = LLMPolicy(SimulatedLLMProvider()).propose("pricing plans tickets", obs, [])
    # The heuristic grabs any positive lexical match (clicks the verbose banner);
    # the simulated model holds out for a precise affordance and scrolls instead.
    assert heur.action.kind == "click"
    assert sim.action.kind == "scroll"


# ── persona viewport honesty (regression for the .text re-serialisation fix) ───


def test_persona_llm_base_cannot_see_off_viewport_target() -> None:
    env = _deep_site()
    obs = ObservationBuilder().build(env, query="pricing plans")
    # The builder *does* surface the off-viewport target in the full prompt...
    assert "Pricing plans" in obs.text
    assert any((not e.in_viewport) and "Pricing" in e.name for e in obs.elements)

    persona = build_panel(3)[1]  # enthusiast — patient enough not to bail on step 1
    pol = PersonaPolicy(persona, base=LLMPolicy(SimulatedLLMProvider()))
    pol.reset()
    decision = pol.propose("pricing plans", obs, [])
    # ...but the persona only perceives her viewport, so the text-reading base
    # must NOT have clicked the off-screen target — it scrolls to look for it.
    assert decision.action.kind == "scroll"
    assert not decision.action.feature_reached


# ── full review run on the simulated LLM (offline) ─────────────────────────────


def test_run_review_with_simulated_llm_offline(tmp_path) -> None:
    out = tmp_path / "review"
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(3),
        output_dir=out,
        policy="llm",
        llm_backend="simulated",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
    )
    assert isinstance(report, ReviewReport)
    assert report.n == 3
    assert report.policy == "llm"
    assert report.error_count == 0
    assert all(r.report is not None for r in report.runs)
    assert report.overall_sentiment() in {"positive", "mixed", "negative"}
    assert (out / "review.json").exists()
    assert (out / "review.html").exists()
    # The LLM policy guides the patient persona all the way to the deep target.
    assert report.reached_count >= 1
