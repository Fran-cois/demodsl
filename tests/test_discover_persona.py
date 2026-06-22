"""Tests for persona-driven discovery (``demodsl.discover.persona``).

Fully offline and deterministic: the ``HeuristicPolicy`` base + a small
simulated site, so no API key or network is needed (same contract as
``test_discover.py``).
"""

from __future__ import annotations

import pytest

from demodsl.discover import (
    PERSONA_PRESETS,
    DiscoveryHarness,
    Persona,
    PersonaPolicy,
    PersonaReport,
)
from demodsl.discover.benchmark import SimElement, SimPage, SimulatedEnvironment
from demodsl.discover.persona import build_persona_report

START = "https://shop.example.com/"
PRICING = "https://shop.example.com/pricing"


def _deep_site() -> SimulatedEnvironment:
    """A site whose only relevant target sits far below the fold.

    Reaching it requires three scrolls, so a hurried persona gives up while a
    patient one perseveres — the contrast we want to assert.
    """
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
        elements=[
            SimElement("choose", "Choose a plan", "button", abs_y=200, dom_id="choose"),
        ],
    )
    return SimulatedEnvironment({START: home, PRICING: pricing}, START)


# ── trait inference ───────────────────────────────────────────────────────────


def test_from_description_infers_hurried_french_manager() -> None:
    p = Persona.from_description("jeune maman pressée, française profession cadre inf")
    assert p.language == "fr"
    assert p.patience < 0.35  # "pressée" + "maman" → low patience
    assert p.confidence > 0.6  # "cadre" → decisive
    assert p.thoroughness < 0.5  # hurried → skims


def test_from_description_infers_tech_novice() -> None:
    p = Persona.from_description("retraité débutant, peu à l'aise avec le numérique")
    assert p.language == "fr"
    assert p.tech_savviness < 0.35
    assert p.confidence < 0.5  # "peu à l'aise" → hesitant, not falsely confident
    assert p.patience >= 0.5  # nothing hurried → stays patient by default


def test_explicit_overrides_win_over_inference() -> None:
    p = Persona.from_description("jeune maman pressée", patience=0.9, language="en")
    assert p.patience == 0.9
    assert p.language == "en"


def test_language_autodetect_defaults_english() -> None:
    assert Persona.from_description("busy software engineer in a hurry").language == "en"


# ── trait-derived behaviour ───────────────────────────────────────────────────


def test_patience_scales_scrolls_and_tolerance() -> None:
    hurried = Persona.from_description("x", patience=0.1)
    patient = Persona.from_description("x", patience=0.9)
    assert hurried.max_scrolls < patient.max_scrolls
    assert hurried.frustration_tolerance < patient.frustration_tolerance
    assert hurried.scroll_cost > patient.scroll_cost  # frustration builds faster


def test_low_tech_needs_more_obvious_controls() -> None:
    novice = Persona.from_description("x", tech_savviness=0.1)
    expert = Persona.from_description("x", tech_savviness=0.9)
    assert novice.min_relevance_to_act > expert.min_relevance_to_act


# ── reflections (voice) ───────────────────────────────────────────────────────


def test_reflections_localised_french() -> None:
    p = Persona.from_description("x", language="fr")
    assert "défile" in p.reflect("scroll", index=2) or "descends" in p.reflect("scroll", index=0)
    # hurried vs patient give-up wording differs
    hurried = Persona.from_description("x", patience=0.1, language="fr")
    patient = Persona.from_description("x", patience=0.9, language="fr")
    assert hurried.reflect("give_up") != patient.reflect("give_up")


def test_reflections_localised_english() -> None:
    p = Persona.from_description("x", language="en")
    assert (
        "found" in p.reflect("reached", index=0).lower()
        or "perfect" in p.reflect("reached", index=1).lower()
    )


# ── end-to-end persona runs (offline) ─────────────────────────────────────────


def test_hurried_persona_gives_up_before_deep_feature() -> None:
    persona = PERSONA_PRESETS["impatient_skimmer"]
    harness = DiscoveryHarness.build(policy="heuristic", persona=persona, max_steps=10)
    result = harness.discover(
        url=START, query="pricing plans", env_factory=_deep_site, write_yaml=False
    )
    report = result.persona_report
    assert report is not None
    assert report.gave_up is True
    assert report.reached is False
    assert report.scrolls <= persona.max_scrolls + 1
    assert result.score.feature_reached is False


def test_patient_persona_reaches_deep_feature() -> None:
    persona = PERSONA_PRESETS["curious_explorer"]
    harness = DiscoveryHarness.build(policy="heuristic", persona=persona, max_steps=12)
    result = harness.discover(
        url=START, query="pricing plans", env_factory=_deep_site, write_yaml=False
    )
    report = result.persona_report
    assert report is not None
    assert report.reached is True
    assert report.gave_up is False
    assert report.scrolls >= 2  # she had to work for it
    assert result.score.feature_reached is True


def test_persona_report_is_localised_and_has_thoughts() -> None:
    persona = Persona.from_description("jeune maman pressée, cadre infirmière")
    harness = DiscoveryHarness.build(policy="heuristic", persona=persona, max_steps=10)
    result = harness.discover(
        url=START, query="pricing plans", env_factory=_deep_site, write_yaml=False
    )
    report = result.persona_report
    assert report is not None
    assert report.reflections  # think-aloud trace present
    md = report.to_markdown()
    assert "Persona run" in md
    assert "Think-aloud" in md
    # her voice is French
    assert any(("je" in r.lower() or "j'" in r.lower()) for r in report.reflections)


def test_persona_effort_grows_with_search_depth() -> None:
    patient = DiscoveryHarness.build(
        policy="heuristic", persona=PERSONA_PRESETS["curious_explorer"], max_steps=12
    ).discover(url=START, query="pricing plans", env_factory=_deep_site, write_yaml=False)
    hurried = DiscoveryHarness.build(
        policy="heuristic", persona=PERSONA_PRESETS["impatient_skimmer"], max_steps=12
    ).discover(url=START, query="pricing plans", env_factory=_deep_site, write_yaml=False)
    # The patient explorer invests strictly more effort than the one who quits.
    assert patient.persona_report.effort > hurried.persona_report.effort


def test_persona_run_disables_tree_search() -> None:
    harness = DiscoveryHarness.build(
        policy="heuristic",
        persona="curious patient explorer",
        tree_search=True,
        n_rollouts=3,
    )
    assert harness.tree_search is False
    assert isinstance(harness.policy, PersonaPolicy)


def test_string_and_dict_persona_coercion() -> None:
    h1 = DiscoveryHarness.build(policy="heuristic", persona="hurried busy mom")
    h2 = DiscoveryHarness.build(
        policy="heuristic",
        persona={"description": "engineer", "patience": 0.8},
    )
    assert isinstance(h1.persona, Persona)
    assert isinstance(h2.persona, Persona)
    assert h2.persona.patience == 0.8


def test_preset_gallery_well_formed() -> None:
    assert "hurried_parent" in PERSONA_PRESETS
    for name, persona in PERSONA_PRESETS.items():
        assert isinstance(persona, Persona)
        assert 0.0 <= persona.patience <= 1.0
        assert persona.label


def test_build_persona_report_standalone() -> None:
    from demodsl.discover.persona import PersonaState

    persona = Persona.from_description("x", patience=0.2)
    st = PersonaState(
        steps=3,
        scrolls=2,
        hesitations=1,
        frustration=0.9,
        gave_up=True,
        give_up_reason="ran out of patience",
        reflections=["a", "b"],
    )
    report = build_persona_report(persona, "find pricing", state=st, reached=False)
    assert isinstance(report, PersonaReport)
    assert report.gave_up
    assert report.effort > 0
    assert "gave up" in report.headline()


# ── designer-facing findings ("bad faith + it helps") ─────────────────────────


def _state(**kw: object):
    from demodsl.discover.persona import PersonaState

    return PersonaState(**kw)  # type: ignore[arg-type]


def test_findings_giveup_flags_long_path_and_blame() -> None:
    persona = Persona.from_description("x", patience=0.2, language="en")
    st = _state(steps=5, scrolls=3, hesitations=2, frustration=1.1, gave_up=True)
    report = build_persona_report(persona, "find pricing", state=st, reached=False)
    blob = " ".join(report.findings).lower()
    assert report.findings  # actionable guidance present
    assert "shorten" in blob  # too-long path → shorten the critical path
    assert "bad faith" in blob  # the realistic blame is surfaced as a signal


def test_findings_ambiguous_labels_when_hesitating() -> None:
    persona = Persona.from_description("x", tech_savviness=0.2, language="en")
    st = _state(steps=4, scrolls=0, hesitations=2, frustration=0.3)
    report = build_persona_report(persona, "open settings", state=st, reached=True)
    blob = " ".join(report.findings).lower()
    assert "ambiguous" in blob and "label" in blob


def test_findings_smooth_when_low_effort_reach() -> None:
    persona = Persona.from_description("x", language="en")
    st = _state(steps=2, scrolls=0, hesitations=0, frustration=0.0)
    report = build_persona_report(persona, "open pricing", state=st, reached=True)
    blob = " ".join(report.findings).lower()
    assert "smooth" in blob
    assert "shorten" not in blob  # nothing to fix


def test_findings_localised_french() -> None:
    persona = Persona.from_description("x", patience=0.2, language="fr")
    st = _state(steps=5, scrolls=3, hesitations=1, frustration=1.0, gave_up=True)
    report = build_persona_report(persona, "trouver le prix", state=st, reached=False)
    blob = " ".join(report.findings).lower()
    assert "concepteur" in report.to_markdown().lower()
    assert "raccourcir" in blob or "mauvaise foi" in blob


def test_markdown_has_designer_section_when_findings() -> None:
    persona = Persona.from_description("busy hurried user", language="en")
    st = _state(steps=4, scrolls=2, hesitations=1, frustration=0.9, gave_up=True)
    report = build_persona_report(persona, "find it", state=st, reached=False)
    md = report.to_markdown()
    assert "What this reveals for the designer" in md


def test_critical_voice_variants_present() -> None:
    # The nudge added (realistic) bad-faith lines to the voice tables.
    p_fr = Persona.from_description("x", language="fr")
    fr_scrolls = {p_fr.reflect("scroll", index=i) for i in range(6)}
    assert any("mal fait" in s or "aussi loin" in s or "tout de suite" in s for s in fr_scrolls)
    p_en = Persona.from_description("x", language="en")
    en_hes = {p_en.reflect("hesitate", index=i) for i in range(6)}
    assert any("jargon" in s or "means nothing" in s for s in en_hes)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
