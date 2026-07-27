"""Rubric evaluation harness — ``demodsl eval`` (issue #26).

Comparing two authoring models is currently guesswork: you watch two
videos and form an impression. This module turns "write a nice demo"
into a well-posed objective by scoring a config on dimensions that are
computable from the config itself, plus (when available) a page
observation (:mod:`demodsl.observe`) and a post-render QA report
(:mod:`demodsl.qa`).

The rubric and its weights are public and overridable — the point is
that model selection becomes a measurement instead of an opinion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DEFAULT_WEIGHTS",
    "DIMENSIONS",
    "DimensionScore",
    "EvalReport",
    "evaluate_config",
    "compare",
]

DIMENSIONS = (
    "argument_coverage",
    "target_quality",
    "gesture_variety",
    "judgement_balance",
    "pacing_sanity",
    "robustness",
    "defects",
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "argument_coverage": 0.20,
    "target_quality": 0.20,
    "gesture_variety": 0.10,
    "judgement_balance": 0.10,
    "pacing_sanity": 0.15,
    "robustness": 0.15,
    "defects": 0.10,
}

#: Words that make a narration line read as an endorsement or a critique.
_POSITIVE = (
    "clear",
    "strong",
    "fast",
    "great",
    "excellent",
    "convincing",
    "smart",
    "solid",
    "well",
    "good",
    "efficace",
    "clair",
    "convaincant",
    "réussi",
)
_NEGATIVE = (
    "but ",
    "however",
    "unclear",
    "confusing",
    "buried",
    "missing",
    "weak",
    "slow",
    "cluttered",
    "vague",
    "mais ",
    "cependant",
    "flou",
    "manque",
)

#: Locator text that points at page *chrome* rather than an argument.
_CHROME_TOKENS = (
    "cookie",
    "consent",
    "menu",
    "nav",
    "navbar",
    "hamburger",
    "footer",
    "breadcrumb",
    "skip to",
    "language",
    "search",
    "login",
    "sign in",
)
#: …and the shapes that read as real arguments.
_ARGUMENT_TOKENS = (
    "pricing",
    "price",
    "plan",
    "free",
    "trial",
    "get started",
    "start",
    "demo",
    "customers",
    "trusted",
    "review",
    "testimonial",
    "feature",
)
_METRIC_RE = re.compile(r"\d[\d.,]*\s*(?:%|x|×|k|m|bn|\+)|[€$£]\s*\d", re.IGNORECASE)


@dataclass
class DimensionScore:
    name: str
    score: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "score": round(self.score, 3), "detail": self.detail}


@dataclass
class EvalReport:
    config: str
    score: float = 0.0
    dimensions: list[DimensionScore] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "score": round(self.score, 3),
            "dimensions": {d.name: d.to_dict() for d in self.dimensions},
            "weights": self.weights,
            "stats": self.stats,
        }


def _iter_steps(config: Any) -> list[Any]:
    steps: list[Any] = []
    for scenario in getattr(config, "scenarios", []) or []:
        steps.extend(getattr(scenario, "steps", []) or [])
    return steps


def _locator_text(step: Any) -> str:
    locator = getattr(step, "locator", None)
    return (getattr(locator, "value", "") or "").lower() if locator else ""


def _marked_steps(steps: list[Any]) -> list[Any]:
    """Steps that visually *mark* something (an effect anchored on a target)."""
    return [s for s in steps if getattr(s, "effects", None)]


def _score_argument_coverage(
    steps: list[Any], observation: dict[str, Any] | None
) -> DimensionScore:
    marked = _marked_steps(steps)
    if observation and observation.get("elements"):
        prominent = [e for e in observation["elements"] if e.get("prominence", 0) >= 0.25]
        target = max(3, min(8, len(prominent)))
        ratio = min(1.0, len(marked) / target) if target else 0.0
        return DimensionScore(
            "argument_coverage",
            ratio,
            f"{len(marked)} marked vs {target} prominent elements on the page",
        )
    # No observation: 4–8 marks is the band a good tour lands in.
    n = len(marked)
    if n == 0:
        ratio = 0.0
    elif n < 4:
        ratio = n / 4
    elif n <= 8:
        ratio = 1.0
    else:
        ratio = max(0.4, 1.0 - (n - 8) * 0.1)
    return DimensionScore("argument_coverage", ratio, f"{n} marked element(s), no page observation")


def _score_target_quality(steps: list[Any]) -> DimensionScore:
    targeted = [s for s in steps if _locator_text(s)]
    if not targeted:
        return DimensionScore("target_quality", 0.0, "no step targets an element")
    good = 0
    chrome = 0
    for step in targeted:
        blob = f"{_locator_text(step)} {(getattr(step, 'narration', '') or '').lower()}"
        if any(tok in blob for tok in _CHROME_TOKENS):
            chrome += 1
        elif any(tok in blob for tok in _ARGUMENT_TOKENS) or _METRIC_RE.search(blob):
            good += 2
        else:
            good += 1
    best = 2 * len(targeted)
    return DimensionScore(
        "target_quality",
        max(0.0, min(1.0, good / best)),
        f"{chrome} chrome target(s) out of {len(targeted)}",
    )


def _score_gesture_variety(steps: list[Any]) -> DimensionScore:
    kinds: list[str] = []
    for step in steps:
        for effect in getattr(step, "effects", None) or []:
            kinds.append(getattr(effect, "type", "?"))
    if not kinds:
        return DimensionScore("gesture_variety", 0.0, "no visual marks at all")
    distinct = len(set(kinds))
    dominant = max(kinds.count(k) for k in set(kinds)) / len(kinds)
    score = min(1.0, distinct / 4) * (1.0 - max(0.0, dominant - 0.6))
    return DimensionScore(
        "gesture_variety",
        max(0.0, min(1.0, score)),
        f"{distinct} distinct mark type(s), dominant share {dominant:.0%}",
    )


def _score_judgement_balance(steps: list[Any]) -> DimensionScore:
    positive = negative = 0
    for step in steps:
        text = (getattr(step, "narration", "") or "").lower()
        if not text:
            continue
        if any(tok in text for tok in _POSITIVE):
            positive += 1
        if any(tok in text for tok in _NEGATIVE):
            negative += 1
    total = positive + negative
    if total == 0:
        return DimensionScore("judgement_balance", 0.0, "narration states no verdict")
    balance = 1.0 - abs(positive - negative) / total
    return DimensionScore(
        "judgement_balance",
        balance,
        f"{positive} positive / {negative} critical verdict(s)",
    )


def _score_pacing(steps: list[Any], *, words_per_second: float = 2.6) -> DimensionScore:
    narrated = [s for s in steps if (getattr(s, "narration", "") or "").strip()]
    if not narrated:
        return DimensionScore("pacing_sanity", 0.0, "no narration")
    rushed = cramped = 0
    for step in narrated:
        words = len((step.narration or "").split())
        needed = words / words_per_second
        shot = float(getattr(step, "wait", None) or 0.0)
        if shot and needed > shot + 0.5:
            rushed += 1
        elif shot and shot > needed * 2.5 + 3:
            cramped += 1
    bad = rushed + cramped
    return DimensionScore(
        "pacing_sanity",
        max(0.0, 1.0 - bad / len(narrated)),
        f"{rushed} shot(s) too short for their narration, {cramped} too long",
    )


def _score_robustness(steps: list[Any], probe: dict[str, Any] | None) -> DimensionScore:
    targeted = [s for s in steps if getattr(s, "locator", None)]
    if not targeted:
        return DimensionScore("robustness", 1.0, "no element-dependent step")
    penalties = 0.0
    details: list[str] = []

    fragile = [s for s in targeted if getattr(s.locator, "type", "") == "xpath"]
    if fragile:
        penalties += 0.25 * len(fragile) / len(targeted)
        details.append(f"{len(fragile)} xpath locator(s)")

    guarded = [s for s in targeted if getattr(s, "on_error", None) is not None]
    if guarded:
        details.append(f"{len(guarded)} step(s) declare an on_error policy")

    if probe:
        unresolved = probe.get("unresolved") or []
        ambiguous = probe.get("ambiguous") or []
        unhoverable = probe.get("unhoverable") or []
        penalties += (len(unresolved) * 1.0 + len(ambiguous) * 0.5 + len(unhoverable) * 0.5) / len(
            targeted
        )
        details.append(
            f"probe: {len(unresolved)} unresolved, {len(ambiguous)} ambiguous, "
            f"{len(unhoverable)} unhoverable"
        )
    else:
        details.append("no probe data")

    return DimensionScore(
        "robustness",
        max(0.0, min(1.0, 1.0 - penalties)),
        "; ".join(details),
    )


def _score_defects(qa_report: dict[str, Any] | None) -> DimensionScore:
    if not qa_report:
        return DimensionScore("defects", 0.5, "no QA report (render not analysed)")
    score = float(qa_report.get("score", 1.0))
    findings = qa_report.get("findings") or []
    errors = sum(1 for f in findings if f.get("severity") == "error")
    return DimensionScore(
        "defects",
        max(0.0, min(1.0, score)),
        f"{len(findings)} finding(s), {errors} error(s)",
    )


def evaluate_config(
    config: Any,
    *,
    name: str = "",
    observation: dict[str, Any] | None = None,
    probe: dict[str, Any] | None = None,
    qa_report: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
) -> EvalReport:
    """Score a config on the rubric. Higher is better; 1.0 is a perfect run."""
    steps = _iter_steps(config)
    used_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        unknown = set(weights) - set(DIMENSIONS)
        if unknown:
            raise ValueError(f"Unknown rubric dimension(s): {sorted(unknown)}")
        used_weights.update(weights)

    dimensions = [
        _score_argument_coverage(steps, observation),
        _score_target_quality(steps),
        _score_gesture_variety(steps),
        _score_judgement_balance(steps),
        _score_pacing(steps),
        _score_robustness(steps, probe),
        _score_defects(qa_report),
    ]

    total_weight = sum(used_weights[d.name] for d in dimensions) or 1.0
    score = sum(d.score * used_weights[d.name] for d in dimensions) / total_weight

    return EvalReport(
        config=name or getattr(getattr(config, "metadata", None), "title", "") or "config",
        score=score,
        dimensions=dimensions,
        weights=used_weights,
        stats={
            "steps": len(steps),
            "marked_steps": len(_marked_steps(steps)),
            "narrated_steps": sum(1 for s in steps if (getattr(s, "narration", "") or "").strip()),
            "seed": getattr(config, "seed", None),
            "deterministic": getattr(config, "seed", None) is not None,
        },
    )


def compare(reports: list[EvalReport]) -> list[dict[str, Any]]:
    """Golden-set comparison table, best score first."""
    rows = []
    for report in sorted(reports, key=lambda r: -r.score):
        row: dict[str, Any] = {"config": report.config, "score": round(report.score, 3)}
        row.update({d.name: round(d.score, 3) for d in report.dimensions})
        row.update({k: v for k, v in report.stats.items() if k in ("steps", "marked_steps")})
        rows.append(row)
    return rows
