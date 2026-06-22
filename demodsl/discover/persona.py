"""Persona-driven discovery: simulate *who* is using the site, not just the
shortest working path.

The vanilla harness optimises for the **best** demo trajectory (reach the
feature, cheaply, with robust locators).  A *persona* run flips the objective:
instead of finding the path that works, it reproduces the **reflexes and effort**
of a specific kind of user — e.g. *"jeune maman pressée, cadre infirmière"* — and
reports what that user would actually experience (did she find it? how hard did
she try? where did she hesitate or give up?).

This is synthetic user research: a usability finding, not an optimiser.

Design
------
A :class:`Persona` carries four behavioural traits in ``[0, 1]`` plus a free-text
description and a language.  :meth:`Persona.from_description` infers the traits
from the description with a transparent, **offline** keyword model (French and
English), so the whole feature runs with zero API keys (like the rest of the
harness).

A :class:`PersonaPolicy` wraps any base :class:`~demodsl.discover.policy.Policy`
and modulates its decisions:

* **Perception** — the persona only considers what is *in her viewport*; to see
  a feature lower on the page she must scroll (spend effort), exactly like a
  real user.
* **Patience** — a hurried persona scrolls fewer times and abandons sooner; a
  patient one perseveres.  Frustration accumulates and, past her tolerance, she
  gives up (``done`` with ``feature_reached=False``) — a valid, informative
  outcome.
* **Comprehension** — a low-tech persona only dares to act on *obvious* controls;
  an ambiguous element makes her hesitate (and, if hurried, skip it).
* **Reflection** — every step is narrated in the persona's own voice and
  language (first-person "thoughts"), so the trajectory reads like a think-aloud
  usability test.  The voice deliberately mixes honest reactions with a dose of
  (realistic) *bad faith* — a frustrated user blames the interface, doesn't read,
  jumps to conclusions — because that unfairness lands exactly where the design
  failed to guide or reassure her.

A :class:`PersonaReport` summarises the run from the persona's point of view and
distils those reactions into **designer-facing findings** (what to clarify,
surface higher, or shorten) — the actionable half of the *"bad faith + it helps"*
mix: the raw voice complains, the report turns the complaint into guidance.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field, replace

from demodsl.discover.actions import AgentAction
from demodsl.discover.observation import PageObservation
from demodsl.discover.policy import HeuristicPolicy, Policy, PolicyDecision

__all__ = [
    "Persona",
    "PersonaState",
    "PersonaReport",
    "PersonaPolicy",
    "PERSONA_PRESETS",
    "build_persona_report",
]


def _clamp(value: float, lo: float = 0.05, hi: float = 0.95) -> float:
    return max(lo, min(hi, value))


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    return _strip_accents(text).lower()


# Each rule: substrings (accent-stripped, lowercase) → trait deltas applied once
# if any substring is present in the normalised description.  Transparent and
# fully offline — no model call, so persona inference is reproducible.
_TRAIT_RULES: tuple[tuple[tuple[str, ...], dict[str, float]], ...] = (
    # hurried / time-pressured
    (
        (
            "presse",
            "pressee",
            "rapide",
            "vite",
            "debord",
            "occup",
            "busy",
            "hurry",
            "hurried",
            "rushed",
            "no time",
            "peu de temps",
            "impatient",
            "stress",
            "speed",
            "quick",
            "a la bourre",
            "cours apres",
        ),
        {"patience": -0.22, "thoroughness": -0.12},
    ),
    # busy life (parent, family) — less time, more distraction
    (
        (
            "maman",
            "papa",
            "mere",
            "pere",
            "parent",
            "mom",
            "mum",
            "mother",
            "father",
            "dad",
            "famille",
        ),
        {"patience": -0.12, "thoroughness": -0.05},
    ),
    # patient / exploratory
    (
        (
            "patient",
            "curieu",
            "tranquille",
            "explor",
            "calme",
            "pose",
            "relaxed",
            "thorough",
            "perfectionniste",
            "fouineu",
        ),
        {"patience": 0.2, "thoroughness": 0.08},
    ),
    # high tech literacy
    (
        (
            "ingenieur",
            "developpeur",
            "developer",
            "engineer",
            "informaticien",
            "programmeur",
            "geek",
            "power user",
            "data",
            "analyste",
            "scientifique",
            "tech",
            "expert",
            "devops",
            "sysadmin",
            "hacker",
            "dev ",
        ),
        {"tech_savviness": 0.2, "confidence": 0.06},
    ),
    # low tech literacy
    (
        (
            "debutant",
            "novice",
            "non technique",
            "pas a l'aise",
            "peu a l'aise",
            "mal a l'aise",
            "retraite",
            "grand-mere",
            "grand-pere",
            "beginner",
            "elderly",
            "technophobe",
            "peu habitue",
            "pas doue",
        ),
        {"tech_savviness": -0.2},
    ),
    # management / decisiveness (e.g. "cadre")
    (
        (
            "cadre",
            "manager",
            "directeur",
            "directrice",
            "responsable",
            "chef",
            "lead",
            "leader",
            "decideur",
            "executive",
        ),
        {"confidence": 0.2, "tech_savviness": 0.06},
    ),
    # explicit confidence
    (
        (
            "confiant",
            "sur de soi",
            "decide",
            "assertif",
            "experimente",
            "confident",
            "decisive",
            "assertive",
        ),
        {"confidence": 0.18},
    ),
    # hesitant / anxious / uncomfortable
    (
        (
            "hesitant",
            "anxieu",
            "timide",
            "insecure",
            "nervous",
            "pas sur",
            "manque de confiance",
            "pas a l'aise",
            "peu a l'aise",
            "mal a l'aise",
        ),
        {"confidence": -0.2},
    ),
    # explicit thoroughness
    (
        ("minutieu", "rigoureu", "attentif", "careful", "meticuleu", "lit tout"),
        {"thoroughness": 0.18},
    ),
    # skimming
    (
        ("survole", "en diagonale", "skim", "distrait", "zappe"),
        {"thoroughness": -0.15},
    ),
)

# Tokens strongly suggestive of French, used for language auto-detection.
_FRENCH_MARKERS = frozenset(
    {
        "le",
        "la",
        "les",
        "une",
        "un",
        "des",
        "du",
        "jeune",
        "maman",
        "pere",
        "mere",
        "cadre",
        "profession",
        "presse",
        "pressee",
        "francais",
        "francaise",
        "tres",
        "peu",
        "ans",
        "retraite",
        "etudiant",
        "infirmier",
        "infirmiere",
        "occupe",
        "occupee",
        "debutant",
    }
)


@dataclass
class Persona:
    """A simulated user: free-text identity + four behavioural traits in [0, 1].

    Traits (0 → 1):

    * ``patience``        — gives up instantly → perseveres a long time.
    * ``tech_savviness``  — novice → expert (how subtle a control she'll use).
    * ``thoroughness``    — skims → reads everything (dwell / reading effort).
    * ``confidence``      — hesitant → decisive (hesitation before acting).
    """

    description: str
    language: str = "en"  # "fr" | "en" (others fall back to the English voice)
    patience: float = 0.5
    tech_savviness: float = 0.5
    thoroughness: float = 0.5
    confidence: float = 0.5
    label: str = ""

    def __post_init__(self) -> None:
        self.patience = _clamp(float(self.patience))
        self.tech_savviness = _clamp(float(self.tech_savviness))
        self.thoroughness = _clamp(float(self.thoroughness))
        self.confidence = _clamp(float(self.confidence))
        if self.language not in ("fr", "en"):
            # Unknown languages keep their tag but reflect in English.
            self.language = self.language or "en"
        if not self.label:
            self.label = self.description.strip().split(",")[0][:48] or "user"

    # ── trait-derived behaviour ───────────────────────────────────────────

    @property
    def max_scrolls(self) -> int:
        """How many times she'll scroll looking for something before quitting."""
        return max(1, round(1 + self.patience * 6))  # 1 … 7

    @property
    def step_budget(self) -> int:
        """A natural cap on total actions, derived from patience."""
        return max(3, round(4 + self.patience * 10))  # 4 … 14

    @property
    def min_relevance_to_act(self) -> float:
        """How obvious a control must look before she dares to use it.

        A novice needs an obvious, on-topic label; an expert will try subtle
        affordances.
        """
        return round(0.15 + 0.4 * (1.0 - self.tech_savviness), 3)  # 0.15 … 0.55

    @property
    def frustration_tolerance(self) -> float:
        """Accumulated frustration she'll bear before abandoning."""
        return round(0.4 + 1.0 * self.patience, 3)  # 0.4 … 1.4

    @property
    def scroll_cost(self) -> float:
        """Frustration added by each fruitless scroll."""
        return round(0.15 + 0.35 * (1.0 - self.patience), 3)  # 0.15 … 0.5

    @property
    def miss_cost(self) -> float:
        """Frustration added by a confusing / ambiguous control."""
        return round(0.2 + 0.5 * (1.0 - self.patience), 3)

    @property
    def is_decisive(self) -> bool:
        return self.confidence >= 0.6

    @property
    def is_hurried(self) -> bool:
        return self.patience < 0.5

    def traits_line(self) -> str:
        return (
            f"patience={self.patience:.2f} tech={self.tech_savviness:.2f} "
            f"thoroughness={self.thoroughness:.2f} confidence={self.confidence:.2f}"
        )

    # ── construction ──────────────────────────────────────────────────────

    @classmethod
    def from_description(
        cls,
        description: str,
        *,
        language: str | None = None,
        patience: float | None = None,
        tech_savviness: float | None = None,
        thoroughness: float | None = None,
        confidence: float | None = None,
        label: str = "",
    ) -> Persona:
        """Infer traits from a free-text persona description (offline).

        Keyword rules nudge each trait from a neutral 0.5 baseline; explicit
        keyword arguments always win over the inferred value.
        """
        norm = _normalize(description)
        traits = {
            "patience": 0.5,
            "tech_savviness": 0.5,
            "thoroughness": 0.5,
            "confidence": 0.5,
        }
        for needles, deltas in _TRAIT_RULES:
            if any(n in norm for n in needles):
                for trait, delta in deltas.items():
                    traits[trait] += delta

        lang = language or _detect_language(norm)
        overrides = {
            "patience": patience,
            "tech_savviness": tech_savviness,
            "thoroughness": thoroughness,
            "confidence": confidence,
        }
        for trait, value in overrides.items():
            if value is not None:
                traits[trait] = value

        return cls(
            description=description.strip(),
            language=lang,
            label=label,
            **{k: _clamp(v) for k, v in traits.items()},
        )

    @classmethod
    def preset(cls, name: str) -> Persona:
        if name not in PERSONA_PRESETS:
            raise ValueError(
                f"Unknown persona preset {name!r}. Available: {sorted(PERSONA_PRESETS)}"
            )
        return PERSONA_PRESETS[name]

    # ── voice ─────────────────────────────────────────────────────────────

    def reflect(self, situation: str, *, name: str = "", index: int = 0) -> str:
        """Return a first-person 'thought' for *situation* in the persona voice."""
        lang = self.language if self.language in _REFLECTIONS else "en"
        table = _REFLECTIONS[lang]
        key = situation
        if situation == "give_up":
            key = "give_up_hurried" if self.is_hurried else "give_up_patient"
        variants = table.get(key) or table["scroll"]
        text = variants[index % len(variants)]
        return text.format(name=name or _GENERIC_TARGET[lang])


@dataclass
class PersonaState:
    """Mutable effort/affect accumulated while the persona explores."""

    steps: int = 0
    scrolls: int = 0
    hesitations: int = 0
    frustration: float = 0.0
    satisfied: bool = False
    gave_up: bool = False
    give_up_reason: str | None = None
    reflections: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.steps = 0
        self.scrolls = 0
        self.hesitations = 0
        self.frustration = 0.0
        self.satisfied = False
        self.gave_up = False
        self.give_up_reason = None
        self.reflections = []


class PersonaPolicy(Policy):
    """Wrap a base policy and make it behave like *persona*.

    The base policy still proposes the mechanically sensible next action; this
    wrapper restricts perception to the viewport, gates on comprehension,
    accumulates frustration, may abandon, and rewrites every step in the
    persona's voice.
    """

    def __init__(self, persona: Persona, base: Policy | None = None) -> None:
        self.persona = persona
        self.base = base or HeuristicPolicy(max_scrolls=persona.max_scrolls)
        self.state = PersonaState()

    def reset(self) -> None:
        self.state.reset()

    def propose(
        self,
        query: str,
        observation: PageObservation,
        history: list[str],
        *,
        reflection: str | None = None,
    ) -> PolicyDecision:
        p = self.persona
        st = self.state
        st.steps += 1

        # Perception: a real user only reasons about what is on screen.
        visible = [e for e in observation.elements if e.in_viewport]
        visible_obs = replace(observation, elements=visible)

        decision = self.base.propose(query, visible_obs, history, reflection=reflection)
        action = decision.action
        usage = decision.usage
        el = visible_obs.by_mark(action.mark) if action.mark is not None else None
        situation: str | None = None

        # Comprehension gate: ambiguous control + not a decisive persona.
        if (
            action.kind in ("click", "type")
            and el is not None
            and el.relevance < p.min_relevance_to_act
            and not p.is_decisive
        ):
            st.hesitations += 1
            st.frustration += p.miss_cost * 0.6
            if p.is_hurried:
                action = self._look_further()
                el = None
                if action.kind == "done":
                    situation = "give_up"
                    st.gave_up = True
                    st.give_up_reason = "confused by the interface and out of time"
                else:
                    situation = "hesitate"
            else:
                situation = "hesitate"  # cautiously proceeds with the click/type

        # Bookkeeping by action kind.
        if action.kind == "scroll":
            st.scrolls += 1
            st.frustration += p.scroll_cost
            if situation is None:
                situation = "arrive" if st.steps == 1 else "scroll"
        elif action.kind == "click":
            if action.feature_reached:
                st.frustration = max(0.0, st.frustration - 0.3)
                situation = situation or "found"
            else:
                situation = situation or "act_click"
        elif action.kind == "type":
            situation = situation or "act_type"
        elif action.kind in ("hover", "wait_for"):
            situation = situation or "hesitate"
        elif action.kind == "navigate":
            situation = situation or "arrive"
        elif action.kind == "done":
            if action.feature_reached:
                situation = "reached"
            else:
                situation = "give_up"
                st.gave_up = True
                st.give_up_reason = st.give_up_reason or "could not find it after scanning"

        # Frustration-driven abandonment (before mechanically running dry).
        if (
            not st.gave_up
            and not action.feature_reached
            and action.kind != "done"
            and st.frustration >= p.frustration_tolerance
        ):
            action = self._give_up()
            st.gave_up = True
            st.give_up_reason = "ran out of patience while searching"
            situation = "give_up"

        if action.feature_reached:
            st.satisfied = True

        thought = p.reflect(
            situation or "scroll",
            name=(el.name if el is not None else ""),
            index=st.steps,
        )
        st.reflections.append(thought)
        action = replace(action, narration=thought, rationale=thought)
        if situation in ("hesitate", "give_up"):
            action = replace(action, confidence=round(0.2 + 0.3 * p.confidence, 3))

        return PolicyDecision(action=action, usage=usage)

    # ── internals ─────────────────────────────────────────────────────────

    def _look_further(self) -> AgentAction:
        """Skip an ambiguous control: scroll on, or give up if out of patience."""
        if self.state.scrolls >= self.persona.max_scrolls:
            return self._give_up()
        return AgentAction(kind="scroll", direction="down", pixels=720, confidence=0.4)

    @staticmethod
    def _give_up() -> AgentAction:
        return AgentAction(kind="done", feature_reached=False, confidence=0.2)


# ── Reporting ────────────────────────────────────────────────────────────────


@dataclass
class PersonaReport:
    """What the persona experienced — a usability finding, not a score."""

    persona: Persona
    query: str
    reached: bool
    gave_up: bool
    abandonment_reason: str | None
    steps: int
    scrolls: int
    hesitations: int
    frustration: float
    effort: float
    reflections: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def headline(self) -> str:
        if self.reached:
            return "reached the feature"
        if self.gave_up:
            return f"gave up ({self.abandonment_reason})"
        return "did not reach the feature"

    def summary(self) -> str:
        return (
            f"persona={self.persona.label!r} → {self.headline()} | "
            f"steps={self.steps} scrolls={self.scrolls} "
            f"hesitations={self.hesitations} frustration={self.frustration:.2f} "
            f"effort={self.effort:.1f}"
        )

    def to_markdown(self) -> str:
        lines = [
            f"### Persona run — {self.persona.label}",
            "",
            f"- **Profile**: {self.persona.description}",
            f"- **Traits**: {self.persona.traits_line()}",
            f"- **Query**: {self.query}",
            f"- **Outcome**: {self.headline()}",
            f"- **Effort**: {self.effort:.1f} "
            f"(steps={self.steps}, scrolls={self.scrolls}, hesitations={self.hesitations})",
            f"- **Frustration**: {self.frustration:.2f} / "
            f"{self.persona.frustration_tolerance:.2f} tolerance",
            "",
            "**Think-aloud:**",
        ]
        lines += [f"> {r}" for r in self.reflections]
        if self.findings:
            lang = self.persona.language if self.persona.language in ("fr", "en") else "en"
            header = (
                "**Ce que ça révèle pour le concepteur :**"
                if lang == "fr"
                else "**What this reveals for the designer:**"
            )
            lines += ["", header]
            lines += [f"- {f}" for f in self.findings]
        return "\n".join(lines)


_FINDINGS_TMPL: dict[str, dict[str, str]] = {
    "fr": {
        "ambiguous": (
            "{n} contrôle(s) ont paru ambigus pour ce profil (tech={tech:.0%}) "
            "→ clarifier les libellés ou renforcer l'affordance (icône, sous-texte)."
        ),
        "buried": (
            "La cible utile était loin sous la ligne de flottaison ({scrolls} défilements) "
            "→ la remonter, ajouter une ancre ou un CTA visible au-dessus du pli."
        ),
        "too_long": (
            "Parcours trop long pour la patience de ce profil (abandon après {steps} étapes, "
            "frustration {frust:.2f}/{tol:.2f}) → raccourcir le chemin critique ou guider."
        ),
        "high_effort": (
            "Objectif atteint, mais au prix d'un effort élevé (effort={effort:.1f}) "
            "→ l'expérience reste perfectible pour ce profil."
        ),
        "smooth": "Parcours fluide pour ce profil (effort={effort:.1f}) → rien à corriger ici.",
        "blame": (
            "Ce profil rejette la faute sur le site (« mauvaise foi » réaliste) — c'est "
            "justement le signal qu'il manque un repère rassurant à cet endroit."
        ),
    },
    "en": {
        "ambiguous": (
            "{n} control(s) looked ambiguous to this profile (tech={tech:.0%}) "
            "→ clarify the labels or strengthen the affordance (icon, sub-label)."
        ),
        "buried": (
            "The useful target sat far below the fold ({scrolls} scrolls) "
            "→ move it up, add an anchor, or a visible above-the-fold CTA."
        ),
        "too_long": (
            "Path too long for this profile's patience (gave up after {steps} steps, "
            "frustration {frust:.2f}/{tol:.2f}) → shorten the critical path or guide explicitly."
        ),
        "high_effort": (
            "Goal reached, but at high effort (effort={effort:.1f}) "
            "→ still improvable for this profile."
        ),
        "smooth": "Smooth path for this profile (effort={effort:.1f}) → nothing to fix here.",
        "blame": (
            "This profile blames the site (realistic 'bad faith') — that is exactly the "
            "signal that a reassuring cue is missing here."
        ),
    },
}


def _build_findings(
    persona: Persona, state: PersonaState, reached: bool, effort: float
) -> list[str]:
    """Translate the persona's lived experience into designer-facing findings.

    This is the "it helps" half of the *bad-faith + it helps* mix: the raw
    think-aloud voices a frustrated (sometimes unfair) user, while these notes
    turn that friction into actionable design guidance.
    """
    lang = persona.language if persona.language in _FINDINGS_TMPL else "en"
    t = _FINDINGS_TMPL[lang]
    out: list[str] = []
    if state.hesitations >= 1:
        out.append(t["ambiguous"].format(n=state.hesitations, tech=persona.tech_savviness))
    if state.scrolls >= 2:
        out.append(t["buried"].format(scrolls=state.scrolls))
    if state.gave_up:
        out.append(
            t["too_long"].format(
                steps=state.steps,
                frust=state.frustration,
                tol=persona.frustration_tolerance,
            )
        )
        out.append(t["blame"])
    elif reached and (effort >= 8.0 or state.hesitations >= 2):
        out.append(t["high_effort"].format(effort=effort))
    elif reached:
        out.append(t["smooth"].format(effort=effort))
    return out


def build_persona_report(
    persona: Persona, query: str, *, state: PersonaState, reached: bool
) -> PersonaReport:
    effort = round(
        state.steps
        + 0.5 * state.scrolls
        + 0.8 * state.hesitations
        + persona.thoroughness * state.steps * 0.3,
        2,
    )
    return PersonaReport(
        persona=persona,
        query=query,
        reached=reached,
        gave_up=state.gave_up,
        abandonment_reason=state.give_up_reason,
        steps=state.steps,
        scrolls=state.scrolls,
        hesitations=state.hesitations,
        frustration=round(state.frustration, 3),
        effort=effort,
        reflections=list(state.reflections),
        findings=_build_findings(persona, state, reached, effort),
    )


def coerce_persona(persona: Persona | str | dict, **overrides: object) -> Persona:
    """Accept a Persona, a free-text description, or a kwargs dict."""
    if isinstance(persona, Persona):
        return persona
    if isinstance(persona, str):
        return Persona.from_description(persona, **overrides)  # type: ignore[arg-type]
    if isinstance(persona, dict):
        data = {**persona, **{k: v for k, v in overrides.items() if v is not None}}
        desc = str(data.pop("description", "") or "user")
        return Persona.from_description(desc, **data)  # type: ignore[arg-type]
    raise TypeError(f"cannot build a Persona from {type(persona)!r}")


def _detect_language(norm_text: str) -> str:
    if any(m in ("francais", "francaise", "french") for m in norm_text.split()):
        return "fr"
    tokens = set(norm_text.replace(",", " ").split())
    return "fr" if tokens & _FRENCH_MARKERS else "en"


# ── Voice tables ─────────────────────────────────────────────────────────────

_GENERIC_TARGET = {"fr": "ça", "en": "this"}

_REFLECTIONS: dict[str, dict[str, list[str]]] = {
    "fr": {
        "arrive": [
            "Bon, voyons voir cette page.",
            "Alors, qu'est-ce qu'on a ici...",
            "OK, je regarde rapidement ce qu'il y a.",
        ],
        "scroll": [
            "Je ne vois rien d'utile, je descends un peu.",
            "Hmm, rien ici, je continue plus bas.",
            "Il faut que je fasse défiler pour trouver.",
            "Encore défiler ? Ce qui compte devrait être visible tout de suite.",
            "Je ne devrais pas avoir à chercher aussi loin, franchement.",
        ],
        "found": [
            "Ah, « {name} », ça doit être ça.",
            "« {name} », c'est sûrement ce que je cherche.",
            "Tiens, « {name} », parfait.",
        ],
        "hesitate": [
            "Hmm, « {name} »... je ne suis pas sûre de comprendre.",
            "« {name} » ? Pas évident, ça.",
            "Je ne sais pas trop si c'est le bon endroit.",
            "« {name} », ce libellé ne me parle pas du tout.",
            "C'est du jargon, ça ; je ne vais pas deviner.",
        ],
        "act_click": [
            "Je clique sur « {name} » pour voir.",
            "Allez, j'ouvre « {name} ».",
            "Je tente « {name} ».",
            "J'y vais un peu au hasard, « {name} », on verra bien.",
        ],
        "act_type": [
            "Je tape ma recherche.",
            "Je remplis le champ rapidement.",
            "J'écris ce que je veux trouver.",
        ],
        "reached": [
            "Voilà, j'ai trouvé ce que je cherchais.",
            "Parfait, c'est exactement ça.",
            "Bon, j'ai ce qu'il me faut.",
        ],
        "give_up_hurried": [
            "Je n'ai pas le temps pour ça, je laisse tomber.",
            "Trop compliqué, j'abandonne.",
            "Bon, tant pis, je n'ai pas que ça à faire.",
            "Si ce n'est pas évident en deux secondes, c'est le site qui est mal fait.",
        ],
        "give_up_patient": [
            "J'ai bien cherché mais je ne trouve pas, je renonce.",
            "Dommage, je ne vois vraiment pas où c'est.",
            "J'ai essayé, mais je laisse tomber pour l'instant.",
            "J'ai vraiment essayé ; à ce stade, c'est le parcours qui pèche, pas moi.",
        ],
        "wait": [
            "J'attends que ça charge.",
            "Bon, ça charge...",
            "J'attends une seconde.",
        ],
    },
    "en": {
        "arrive": [
            "Right, let's look at this page.",
            "OK, what do we have here...",
            "Let me quickly scan what's on screen.",
        ],
        "scroll": [
            "Nothing useful here, let me scroll down.",
            "Hmm, not here, I'll keep going down.",
            "I need to scroll to find it.",
            "Scrolling again? The important stuff should be right up top.",
            "I really shouldn't have to dig this far.",
        ],
        "found": [
            "Ah, '{name}', that must be it.",
            "'{name}', that's probably what I want.",
            "There — '{name}', perfect.",
        ],
        "hesitate": [
            "Hmm, '{name}'... not sure I get this.",
            "'{name}'? That's not obvious.",
            "I'm not sure this is the right place.",
            "'{name}', that label means nothing to me.",
            "Is this jargon? I'm not going to guess.",
        ],
        "act_click": [
            "Let me click '{name}' and see.",
            "Alright, I'll open '{name}'.",
            "I'll try '{name}'.",
            "I'm half-guessing here, '{name}', let's see.",
        ],
        "act_type": [
            "Let me type my search.",
            "I'll fill the field quickly.",
            "I type what I'm looking for.",
        ],
        "reached": [
            "There, I found what I was looking for.",
            "Perfect, that's exactly it.",
            "Good, that's what I needed.",
        ],
        "give_up_hurried": [
            "I don't have time for this, I'm giving up.",
            "Too complicated, I quit.",
            "Never mind, I've got other things to do.",
            "If it's not obvious in two seconds, the site's just badly made.",
        ],
        "give_up_patient": [
            "I looked hard but can't find it, I'll stop.",
            "Shame, I really can't see where it is.",
            "I tried, but I'll let it go for now.",
            "I genuinely tried; at this point it's the flow's fault, not mine.",
        ],
        "wait": [
            "Waiting for it to load.",
            "OK, it's loading...",
            "Just a second...",
        ],
    },
}


#: A small gallery of ready-made personas for quick CLI use.
PERSONA_PRESETS: dict[str, Persona] = {
    "hurried_parent": Persona(
        description="Jeune maman pressée, cadre infirmière",
        language="fr",
        patience=0.18,
        tech_savviness=0.55,
        thoroughness=0.28,
        confidence=0.7,
        label="hurried parent",
    ),
    "power_user": Persona(
        description="Tech-savvy power user / software engineer",
        language="en",
        patience=0.8,
        tech_savviness=0.95,
        thoroughness=0.6,
        confidence=0.9,
        label="power user",
    ),
    "cautious_senior": Persona(
        description="Retraité peu à l'aise avec le numérique",
        language="fr",
        patience=0.7,
        tech_savviness=0.2,
        thoroughness=0.8,
        confidence=0.3,
        label="cautious senior",
    ),
    "curious_explorer": Persona(
        description="Curious, patient first-time visitor",
        language="en",
        patience=0.85,
        tech_savviness=0.6,
        thoroughness=0.7,
        confidence=0.55,
        label="curious explorer",
    ),
    "impatient_skimmer": Persona(
        description="Impatient skimmer who never reads",
        language="en",
        patience=0.15,
        tech_savviness=0.65,
        thoroughness=0.18,
        confidence=0.65,
        label="impatient skimmer",
    ),
}
