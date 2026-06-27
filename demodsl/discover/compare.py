"""Compare two or more discovered DemoDSL configurations.

Each config written by the discovery harness carries an embedded *exploration
report* (the ``# `` comment header) plus a normal scenario body. This module
parses both and produces a side-by-side analysis — model, score breakdown, token
usage, estimated cost, and the step-by-step walkthrough — so you can pick the
best of a ``discover --models`` batch.

Everything is dependency-free (stdlib + PyYAML, already a project dep) and works
entirely offline on the generated files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "ConfigInfo",
    "ComparisonReport",
    "parse_config",
    "compare_configs",
]

#: LLM backends that may prefix a model in the report's ``policy:`` line.
_BACKENDS = frozenset({"openai", "anthropic", "openrouter", "simulated", "heuristic"})

_RE_KV = re.compile(r"^#\s{2,}([a-z_]+):\s*(.*)$")
_RE_SCORE = re.compile(
    r"score:\s*([0-9.]+)\s*\(cov=([0-9.]+)\s*rob=([0-9.]+)\s*eff=([0-9.]+)"
    r"\s*cost=([0-9.]+)\s*qual=([0-9.]+)\)"
)
_RE_TOKENS = re.compile(
    r"tokens:\s*(\d+)\s*\(input:\s*(\d+)\s*·\s*output:\s*(\d+)\s*·\s*calls:\s*(\d+)\)"
)
_RE_COST = re.compile(r"estimated_cost:\s*\$([0-9.]+)\s*USD")
_RE_STEPS = re.compile(r"steps:\s*(\d+)")


def _model_from_policy(policy: str) -> str | None:
    """Extract the model id from a ``policy:`` value like ``llm:openrouter/openai/gpt-4o``."""
    p = policy.strip()
    if not p.startswith("llm:"):
        return None
    rest = p[4:]
    parts = rest.split("/")
    if parts and parts[0] in _BACKENDS:
        parts = parts[1:]  # drop the single leading backend token (e.g. "openrouter")
    return "/".join(parts) or None


@dataclass
class StepInfo:
    action: str
    narration: str = ""
    locator_type: str = ""
    locator_value: str = ""
    effects: list[str] = field(default_factory=list)
    url: str = ""

    def summary(self) -> str:
        target = self.url or (
            f"{self.locator_type}={self.locator_value}" if self.locator_type else ""
        )
        fx = f" [{', '.join(self.effects)}]" if self.effects else ""
        head = f"{self.action} {target}".strip() + fx
        return head


@dataclass
class ConfigInfo:
    """Parsed view of one discovered config: report header + scenario steps."""

    path: Path
    label: str = ""
    model: str | None = None
    demo_id: str | None = None
    query: str | None = None
    feature_reached: bool | None = None
    score: float | None = None
    score_breakdown: dict[str, float] = field(default_factory=dict)
    tokens_total: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    calls: int = 0
    cost_usd: float | None = None
    steps: list[StepInfo] = field(default_factory=list)

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    @property
    def action_sequence(self) -> list[str]:
        return [s.action for s in self.steps]

    @property
    def narration_chars(self) -> int:
        return sum(len(s.narration) for s in self.steps)

    @property
    def robust_locator_share(self) -> float:
        """Fraction of locator-bearing steps using a robust (testid/id/text) locator."""
        located = [s for s in self.steps if s.locator_type]
        if not located:
            return 0.0
        robust = sum(1 for s in located if s.locator_type in {"id", "accessibility_id", "text"})
        return robust / len(located)


def _parse_header(text: str) -> dict[str, str]:
    """Collect ``#   key: value`` lines from the leading comment block."""
    kv: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("#"):
            if line.strip() == "":
                continue
            break  # first real YAML line ends the header
        m = _RE_KV.match(line)
        if m:
            kv.setdefault(m.group(1), m.group(2).strip())
    return kv


def _parse_steps(data: dict[str, Any]) -> list[StepInfo]:
    steps: list[StepInfo] = []
    scenarios = data.get("scenarios") or []
    if not scenarios:
        return steps
    for raw in scenarios[0].get("steps") or []:
        if not isinstance(raw, dict):
            continue
        loc = raw.get("locator") or {}
        effects = [
            e.get("type", "")
            for e in (raw.get("effects") or [])
            if isinstance(e, dict) and e.get("type")
        ]
        steps.append(
            StepInfo(
                action=str(raw.get("action", "")),
                narration=str(raw.get("narration") or ""),
                locator_type=str(loc.get("type") or ""),
                locator_value=str(loc.get("value") or ""),
                effects=effects,
                url=str(raw.get("url") or ""),
            )
        )
    return steps


def parse_config(path: str | Path) -> ConfigInfo:
    """Parse a discovered config file into a :class:`ConfigInfo`."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    header = _parse_header(text)
    data = yaml.safe_load(text) or {}

    info = ConfigInfo(path=path)
    info.query = header.get("query")
    info.demo_id = header.get("id")
    info.model = _model_from_policy(header.get("policy", "")) or None
    if "feature_reached" in header:
        info.feature_reached = header["feature_reached"].strip().lower() == "true"

    if m := _RE_SCORE.search(text):
        info.score = float(m.group(1))
        info.score_breakdown = {
            "coverage": float(m.group(2)),
            "robustness": float(m.group(3)),
            "efficiency": float(m.group(4)),
            "cost": float(m.group(5)),
            "quality": float(m.group(6)),
        }
    if m := _RE_TOKENS.search(text):
        info.tokens_total = int(m.group(1))
        info.tokens_input = int(m.group(2))
        info.tokens_output = int(m.group(3))
        info.calls = int(m.group(4))
    if m := _RE_COST.search(text):
        info.cost_usd = float(m.group(1))

    info.steps = _parse_steps(data)
    info.label = info.model or path.parent.name or path.stem
    return info


# ── comparison ───────────────────────────────────────────────────────────────


@dataclass
class ComparisonReport:
    configs: list[ConfigInfo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": next((c.query for c in self.configs if c.query), None),
            "configs": [
                {
                    "label": c.label,
                    "model": c.model,
                    "path": str(c.path),
                    "feature_reached": c.feature_reached,
                    "score": c.score,
                    "score_breakdown": c.score_breakdown,
                    "tokens_input": c.tokens_input,
                    "tokens_output": c.tokens_output,
                    "cost_usd": c.cost_usd,
                    "n_steps": c.n_steps,
                    "action_sequence": c.action_sequence,
                    "narration_chars": c.narration_chars,
                    "robust_locator_share": round(c.robust_locator_share, 3),
                }
                for c in self.configs
            ],
            "highlights": self._highlights(),
        }

    def _highlights(self) -> dict[str, Any]:
        h: dict[str, Any] = {}
        scored = [c for c in self.configs if c.score is not None]
        if scored:
            best = max(scored, key=lambda c: c.score or 0)
            h["highest_score"] = {"label": best.label, "score": best.score}
        priced = [c for c in self.configs if c.cost_usd is not None]
        if priced:
            cheap = min(priced, key=lambda c: c.cost_usd or 0)
            h["cheapest"] = {"label": cheap.label, "cost_usd": cheap.cost_usd}
        if self.configs:
            most = max(self.configs, key=lambda c: c.n_steps)
            h["most_steps"] = {"label": most.label, "n_steps": most.n_steps}
            wordiest = max(self.configs, key=lambda c: c.narration_chars)
            h["most_narration"] = {
                "label": wordiest.label,
                "narration_chars": wordiest.narration_chars,
            }
        return h

    def to_markdown(self) -> str:
        query = next((c.query for c in self.configs if c.query), None)
        lines: list[str] = [f"# Configuration comparison ({len(self.configs)} configs)"]
        if query:
            lines.append(f"\nQuery: **{query}**")

        # Summary table.
        lines.append(
            "\n| Config | Reached | Score | Cost (USD) | Tokens in/out | Steps | Robust loc |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for c in self.configs:
            reached = "✓" if c.feature_reached else ("✗" if c.feature_reached is False else "?")
            score = f"{c.score:.3f}" if c.score is not None else "—"
            cost = f"${c.cost_usd:.6f}" if c.cost_usd is not None else "n/a"
            toks = f"{c.tokens_input}/{c.tokens_output}" if c.tokens_total else "—"
            lines.append(
                f"| {c.label} | {reached} | {score} | {cost} | {toks} | {c.n_steps} "
                f"| {c.robust_locator_share:.0%} |"
            )

        # Score breakdown.
        metrics = ["coverage", "robustness", "efficiency", "cost", "quality"]
        if any(c.score_breakdown for c in self.configs):
            lines.append("\n## Score breakdown\n")
            lines.append("| Metric | " + " | ".join(c.label for c in self.configs) + " |")
            lines.append("|---" * (len(self.configs) + 1) + "|")
            for metric in metrics:
                row = " | ".join(
                    f"{c.score_breakdown.get(metric, 0):.2f}" if c.score_breakdown else "—"
                    for c in self.configs
                )
                lines.append(f"| {metric} | {row} |")

        # Per-config walkthrough.
        lines.append("\n## Walkthroughs\n")
        for c in self.configs:
            lines.append(f"### {c.label} — {c.n_steps} steps")
            for i, s in enumerate(c.steps, start=1):
                lines.append(f"{i}. `{s.summary()}`")
                if s.narration:
                    lines.append(f"   > {s.narration}")
            lines.append("")

        # Highlights.
        h = self._highlights()
        if h:
            lines.append("## Highlights\n")
            if "highest_score" in h:
                hs = h["highest_score"]
                lines.append(f"- **Best score**: {hs['label']} ({hs['score']:.3f})")
            if "cheapest" in h:
                ch = h["cheapest"]
                lines.append(f"- **Cheapest**: {ch['label']} (${ch['cost_usd']:.6f})")
            if "most_steps" in h:
                ms = h["most_steps"]
                lines.append(f"- **Most steps**: {ms['label']} ({ms['n_steps']})")
            if "most_narration" in h:
                mn = h["most_narration"]
                lines.append(f"- **Most narration**: {mn['label']} ({mn['narration_chars']} chars)")
        return "\n".join(lines)


def compare_configs(paths: list[str | Path]) -> ComparisonReport:
    """Parse and compare the discovered configs at *paths*."""
    return ComparisonReport(configs=[parse_config(p) for p in paths])
