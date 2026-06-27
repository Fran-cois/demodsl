"""Synthetic-user *panel* generation for review mode.

Where :mod:`demodsl.discover.persona` models *one* simulated user, a **panel** is
a small, deliberately *diverse* set of them — enough variety to surface how a
feature lands across attitudes (a hostile skeptic vs. an enthusiast) and across
behaviours (hurried vs. patient, novice vs. expert). Running the same flow past
the whole panel is synthetic user research at a glance: a clear spread of
outcomes instead of a single happy-path.

Generation is fully **offline and deterministic** (like the rest of the
harness). A curated, order-for-spread :data:`_PANEL_ARCHETYPES` list is the
backbone: taking the first ``N`` always yields a balanced cross-section. An
optional free-text ``base`` (e.g. *"voyageur soucieux du climat"*) keeps the
domain flavour while still spanning the attitude/behaviour axes — each archetype
description is prefixed with the base and its traits are pulled halfway toward
the base's inferred baseline.
"""

from __future__ import annotations

from dataclasses import dataclass

from demodsl.discover.persona import Persona

__all__ = ["PanelArchetype", "build_panel", "PANEL_ARCHETYPES"]

_TRAIT_KEYS = ("patience", "tech_savviness", "thoroughness", "confidence")


@dataclass(frozen=True)
class PanelArchetype:
    """A reusable persona template for the review panel (bilingual)."""

    slug: str
    label: str
    desc_en: str
    desc_fr: str
    language: str
    patience: float
    tech_savviness: float
    thoroughness: float
    confidence: float

    def description(self, lang: str) -> str:
        return self.desc_fr if lang == "fr" else self.desc_en

    def traits(self) -> dict[str, float]:
        return {
            "patience": self.patience,
            "tech_savviness": self.tech_savviness,
            "thoroughness": self.thoroughness,
            "confidence": self.confidence,
        }


# Ordered so that taking the first N maximises spread: a negative-hurried voice,
# a positive-patient one, then a novice, an expert, and so on. N=3 already gives
# angry skeptic + enthusiast + cautious senior — a clear, contrasting panel.
PANEL_ARCHETYPES: tuple[PanelArchetype, ...] = (
    PanelArchetype(
        slug="angry_skeptic",
        label="angry skeptic",
        desc_en="Frustrated, distrustful visitor in a hurry, quick to blame the site",
        desc_fr="Visiteuse pressée, méfiante et vite agacée, prompte à blâmer le site",
        language="en",
        patience=0.12,
        tech_savviness=0.5,
        thoroughness=0.3,
        confidence=0.72,
    ),
    PanelArchetype(
        slug="enthusiast",
        label="enthusiast",
        desc_en="Patient enthusiast who already loves the concept and is forgiving",
        desc_fr="Enthousiaste patient·e, déjà conquis·e par le concept et indulgent·e",
        language="en",
        patience=0.82,
        tech_savviness=0.6,
        thoroughness=0.62,
        confidence=0.72,
    ),
    PanelArchetype(
        slug="cautious_senior",
        label="cautious senior",
        desc_en="Retiree, uneasy with technology, careful and easily unsure",
        desc_fr="Retraité peu à l'aise avec le numérique, prudent et vite hésitant",
        language="fr",
        patience=0.7,
        tech_savviness=0.2,
        thoroughness=0.8,
        confidence=0.3,
    ),
    PanelArchetype(
        slug="power_user",
        label="power user",
        desc_en="Tech-savvy power user / software engineer, decisive and quick",
        desc_fr="Utilisateur expert, ingénieur logiciel, décidé et rapide",
        language="en",
        patience=0.8,
        tech_savviness=0.95,
        thoroughness=0.6,
        confidence=0.9,
    ),
    PanelArchetype(
        slug="hurried_parent",
        label="hurried parent",
        desc_en="Busy parent with no time, juggling tasks, skims everything",
        desc_fr="Jeune parent pressé, débordé, qui survole tout faute de temps",
        language="fr",
        patience=0.18,
        tech_savviness=0.55,
        thoroughness=0.28,
        confidence=0.7,
    ),
    PanelArchetype(
        slug="methodical_researcher",
        label="methodical researcher",
        desc_en="Methodical researcher who reads every detail before deciding",
        desc_fr="Chercheuse méthodique qui lit chaque détail avant de décider",
        language="en",
        patience=0.78,
        tech_savviness=0.7,
        thoroughness=0.95,
        confidence=0.6,
    ),
    PanelArchetype(
        slug="bargain_hunter",
        label="bargain hunter",
        desc_en="Comparison shopper, price-sensitive, weighs every alternative",
        desc_fr="Comparateur attentif au prix, qui pèse chaque alternative",
        language="en",
        patience=0.52,
        tech_savviness=0.6,
        thoroughness=0.75,
        confidence=0.6,
    ),
    PanelArchetype(
        slug="curious_explorer",
        label="curious explorer",
        desc_en="Curious, patient first-time visitor exploring without a goal",
        desc_fr="Visiteuse curieuse et patiente, qui explore sans but précis",
        language="en",
        patience=0.85,
        tech_savviness=0.6,
        thoroughness=0.7,
        confidence=0.55,
    ),
    PanelArchetype(
        slug="impatient_skimmer",
        label="impatient skimmer",
        desc_en="Impatient skimmer who never reads and abandons fast",
        desc_fr="Lecteur pressé qui ne lit jamais et abandonne vite",
        language="en",
        patience=0.15,
        tech_savviness=0.65,
        thoroughness=0.18,
        confidence=0.65,
    ),
    PanelArchetype(
        slug="distracted_mobile",
        label="distracted mobile user",
        desc_en="Distracted mobile user, multitasking, half-paying-attention",
        desc_fr="Utilisatrice mobile distraite, multitâche, à moitié attentive",
        language="fr",
        patience=0.3,
        tech_savviness=0.5,
        thoroughness=0.25,
        confidence=0.5,
    ),
)


def _blend(a: float, b: float) -> float:
    return round((a + b) / 2.0, 3)


def build_panel(
    n: int,
    *,
    base: str | None = None,
    lang: str | None = None,
) -> list[Persona]:
    """Build a diverse panel of up to ``n`` personas (deterministic, offline).

    Parameters
    ----------
    n:
        Desired panel size. Clamped to ``1 .. len(PANEL_ARCHETYPES)``; the first
        ``n`` archetypes are used (they are ordered for maximum spread).
    base:
        Optional free-text seed describing the audience/domain (e.g. *"voyageur
        en train soucieux du climat"*). When given, every archetype keeps its
        attitude/behaviour but is prefixed with the base and has its traits
        pulled halfway toward the base's inferred baseline — so the panel stays
        on-domain while still spanning the axes.
    lang:
        Force the reflection language (``"fr"`` / ``"en"``) for every persona;
        otherwise the base's (or each archetype's) language is used.
    """
    count = max(1, min(int(n), len(PANEL_ARCHETYPES)))
    base_persona = Persona.from_description(base) if base and base.strip() else None
    base_lang = lang or (base_persona.language if base_persona else None)

    personas: list[Persona] = []
    for arch in PANEL_ARCHETYPES[:count]:
        traits = arch.traits()
        lang_final = lang or base_lang or arch.language
        desc = arch.description(lang_final)
        if base_persona is not None:
            traits = {k: _blend(traits[k], getattr(base_persona, k)) for k in _TRAIT_KEYS}
            desc = f"{base.strip()} — {desc}"
        personas.append(
            Persona(
                description=desc,
                language=lang_final,
                label=arch.label,
                **traits,
            )
        )
    return personas
