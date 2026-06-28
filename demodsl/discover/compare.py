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

import html as _html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "ConfigInfo",
    "VideoInfo",
    "JudgeVerdict",
    "ComparisonReport",
    "parse_config",
    "compare_configs",
    "judge_configs",
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
class VideoInfo:
    """Metrics for a rendered demo video found next to a config."""

    path: Path
    duration_s: float | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width and self.height else "—"

    @property
    def size_mb(self) -> float | None:
        return round(self.size_bytes / 1_048_576, 2) if self.size_bytes else None


def _find_video(config_path: Path, output_filename: str) -> Path | None:
    """Locate the rendered video for a config (searches its folder recursively)."""
    if not output_filename:
        return None
    parent = config_path.parent
    # Exact filename anywhere under the config's folder (e.g. in a render/ subdir).
    for cand in sorted(parent.rglob(output_filename)):
        if cand.is_file():
            return cand
    # Fall back to any mp4 sharing the config's hash stem.
    stem = config_path.stem
    for cand in sorted(parent.rglob("*.mp4")):
        if stem in cand.name:
            return cand
    return None


def _probe_video(path: Path) -> VideoInfo:
    """Probe *path* for duration/resolution via ffprobe (best-effort)."""
    info = VideoInfo(path=path)
    try:
        info.size_bytes = path.stat().st_size
    except OSError:
        pass
    if not shutil.which("ffprobe"):
        return info
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        data = json.loads(out.stdout or "{}")
        streams = data.get("streams") or []
        if streams:
            info.width = int(streams[0].get("width") or 0) or None
            info.height = int(streams[0].get("height") or 0) or None
        dur = (data.get("format") or {}).get("duration")
        if dur is not None:
            info.duration_s = round(float(dur), 1)
    except Exception:
        pass
    return info


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
    video: VideoInfo | None = None

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

    # Detect + probe a rendered video sitting next to the config (if any).
    output_filename = str((data.get("output") or {}).get("filename") or "")
    video_path = _find_video(path, output_filename)
    if video_path is not None:
        info.video = _probe_video(video_path)
    return info


# ── comparison ───────────────────────────────────────────────────────────────


# ── LLM-as-a-judge (qualitative review of the demo content) ──────────────────


@dataclass
class JudgeVerdict:
    """An LLM's qualitative review of the compared demos."""

    winner: str | None = None
    summary: str = ""
    ranking: list[str] = field(default_factory=list)
    #: per-label dict with keys: score (0-10), verdict, strengths, weaknesses.
    per_config: dict[str, dict[str, Any]] = field(default_factory=dict)
    model: str | None = None
    tokens: int = 0


_JUDGE_SYSTEM = """\
You are an expert product-demo reviewer. You are given a user QUERY (the feature
the demo must showcase) and several candidate demo SCRIPTS — each an ordered list
of browser steps with the narration that will be spoken over them. Judge them on
the *content quality*, not raw metrics:

- Coverage: does the narration actually show AND explain the requested feature
  (e.g. naming the pricing tiers and what they include), or merely navigate to it?
- Clarity & flow: is the walkthrough logical, easy to follow, well paced?
- Accuracy: does the narration match what the steps do, with no invented claims?
- Engagement & professionalism: would this make a convincing demo video?

Respond with ONLY a JSON object:
{
  "winner": "<config label>",
  "summary": "<2-3 sentence overall comparison>",
  "ranking": ["<best label>", "...", "<worst label>"],
  "configs": {
    "<label>": {
      "score": <number 0-10>,
      "verdict": "<one-sentence judgement>",
      "strengths": ["<short point>", "..."],
      "weaknesses": ["<short point>", "..."]
    }
  }
}
"""


def _judge_prompt(report: ComparisonReport) -> str:
    query = next((c.query for c in report.configs if c.query), None) or "(unknown)"
    blocks: list[str] = []
    for c in report.configs:
        steps = "\n".join(
            f"  {i}. {s.summary()}" + (f" — {s.narration}" if s.narration else "")
            for i, s in enumerate(c.steps, start=1)
        )
        blocks.append(f"CONFIG [{c.label}] (model: {c.model or 'n/a'}):\n{steps}")
    return f"QUERY: {query}\n\n" + "\n\n".join(blocks) + "\n\nReturn the JSON verdict."


def judge_configs(report: ComparisonReport, *, llm: Any, model: str | None = None) -> JudgeVerdict:
    """Ask *llm* (an :class:`~demodsl.discover.llm.LLMProvider`) to review the demos.

    Returns a :class:`JudgeVerdict`; the LLM grounds its judgement in the actual
    step narration, so it complements the automated score with a qualitative,
    human-like content review. Best-effort: a malformed reply yields an empty
    verdict rather than raising.
    """
    resp = llm.complete(_JUDGE_SYSTEM, _judge_prompt(report), temperature=0.0, max_tokens=900)
    data = resp.json() if hasattr(resp, "json") else {}
    per: dict[str, dict[str, Any]] = {}
    for label, val in (data.get("configs") or {}).items():
        if isinstance(val, dict):
            per[str(label)] = val
    usage = getattr(resp, "usage", None)
    return JudgeVerdict(
        winner=data.get("winner") or None,
        summary=str(data.get("summary", "")),
        ranking=[str(x) for x in (data.get("ranking") or [])],
        per_config=per,
        model=model or getattr(llm, "model", None),
        tokens=getattr(usage, "total", 0) if usage is not None else 0,
    )


@dataclass
class ComparisonReport:
    configs: list[ConfigInfo]
    judge: JudgeVerdict | None = None

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
                    "video": (
                        {
                            "path": str(c.video.path),
                            "duration_s": c.video.duration_s,
                            "size_mb": c.video.size_mb,
                            "resolution": c.video.resolution,
                        }
                        if c.video
                        else None
                    ),
                }
                for c in self.configs
            ],
            "highlights": self._highlights(),
            "judge": (
                {
                    "winner": self.judge.winner,
                    "summary": self.judge.summary,
                    "ranking": self.judge.ranking,
                    "configs": self.judge.per_config,
                    "model": self.judge.model,
                }
                if self.judge
                else None
            ),
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
        videos = [c for c in self.configs if c.video and c.video.duration_s is not None]
        if videos:
            longest = max(videos, key=lambda c: c.video.duration_s or 0)
            h["longest_video"] = {
                "label": longest.label,
                "duration_s": longest.video.duration_s,
            }
        return h

    def to_markdown(self) -> str:
        query = next((c.query for c in self.configs if c.query), None)
        lines: list[str] = [f"# Configuration comparison ({len(self.configs)} configs)"]
        if query:
            lines.append(f"\nQuery: **{query}**")

        # Summary table.
        lines.append(
            "\n| Config | Reached | Score | Cost (USD) | Tokens in/out | Steps | Robust loc "
            "| Video |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for c in self.configs:
            reached = "✓" if c.feature_reached else ("✗" if c.feature_reached is False else "?")
            score = f"{c.score:.3f}" if c.score is not None else "—"
            cost = f"${c.cost_usd:.6f}" if c.cost_usd is not None else "n/a"
            toks = f"{c.tokens_input}/{c.tokens_output}" if c.tokens_total else "—"
            if c.video and c.video.duration_s is not None:
                vid = f"{c.video.duration_s:g}s · {c.video.resolution}"
                if c.video.size_mb:
                    vid += f" · {c.video.size_mb}MB"
            elif c.video:
                vid = f"{c.video.size_mb}MB" if c.video.size_mb else "rendered"
            else:
                vid = "—"
            lines.append(
                f"| {c.label} | {reached} | {score} | {cost} | {toks} | {c.n_steps} "
                f"| {c.robust_locator_share:.0%} | {vid} |"
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
            if "longest_video" in h:
                lv = h["longest_video"]
                lines.append(f"- **Longest video**: {lv['label']} ({lv['duration_s']:g}s)")

        # LLM judge (qualitative content review).
        if self.judge is not None:
            j = self.judge
            lines.append(f"\n## LLM judge{f' ({j.model})' if j.model else ''}\n")
            if j.winner:
                lines.append(f"**Winner: {j.winner}**\n")
            if j.summary:
                lines.append(f"{j.summary}\n")
            for label in j.ranking or list(j.per_config):
                pc = j.per_config.get(label, {})
                score = pc.get("score")
                head = f"### {label}" + (f" — {score}/10" if score is not None else "")
                lines.append(head)
                if pc.get("verdict"):
                    lines.append(f"{pc['verdict']}")
                for s in pc.get("strengths") or []:
                    lines.append(f"- 👍 {s}")
                for w in pc.get("weaknesses") or []:
                    lines.append(f"- 👎 {w}")
                lines.append("")
        return "\n".join(lines)

    def to_html(self, *, out_path: Path | None = None) -> str:
        """A self-contained HTML visualisation of the comparison.

        If *out_path* is given, video ``<source>`` links are made relative to it
        so the embedded players resolve when the file is opened from disk.
        """
        configs = self.configs
        query = next((c.query for c in configs if c.query), None)
        best_score = max((c.score or 0) for c in configs) if configs else 0

        def esc(s: Any) -> str:
            return _html.escape(str(s))

        def rel(p: Path) -> str:
            try:
                return p.relative_to(out_path.parent).as_posix() if out_path else p.as_posix()
            except ValueError:
                return p.as_posix()

        cards: list[str] = []
        for c in configs:
            winner = c.score is not None and c.score == best_score and best_score > 0
            metric_bars = "".join(
                f'<div class="bar"><span>{esc(m)}</span>'
                f'<div class="track"><div class="fill" style="width:{c.score_breakdown.get(m, 0) * 100:.0f}%"></div></div>'
                f"<b>{c.score_breakdown.get(m, 0):.2f}</b></div>"
                for m in ("coverage", "robustness", "efficiency", "cost", "quality")
            )
            steps_html = "".join(
                f"<li><code>{esc(s.summary())}</code>"
                + (f'<p class="narr">{esc(s.narration)}</p>' if s.narration else "")
                + "</li>"
                for s in c.steps
            )
            video_html = ""
            if c.video:
                v = c.video
                bits = []
                if v.duration_s is not None:
                    bits.append(f"{v.duration_s:g}s")
                bits.append(v.resolution)
                if v.size_mb:
                    bits.append(f"{v.size_mb} MB")
                src = rel(v.path)
                video_html = (
                    f'<div class="video"><div class="vmeta">🎬 {esc(" · ".join(bits))}</div>'
                    f'<video controls preload="metadata" src="{esc(src)}"></video></div>'
                )
            cost = f"${c.cost_usd:.6f}" if c.cost_usd is not None else "n/a"
            score = f"{c.score:.3f}" if c.score is not None else "—"
            cards.append(
                f'<section class="card{" win" if winner else ""}">'
                f"<h2>{esc(c.label)}{' 🏆' if winner else ''}</h2>"
                f'<div class="kpis">'
                f'<div class="kpi"><b>{esc(score)}</b><span>score</span></div>'
                f'<div class="kpi"><b>{esc(cost)}</b><span>est. cost</span></div>'
                f'<div class="kpi"><b>{c.tokens_input}/{c.tokens_output}</b><span>tokens in/out</span></div>'
                f'<div class="kpi"><b>{c.n_steps}</b><span>steps</span></div>'
                f'<div class="kpi"><b>{c.robust_locator_share:.0%}</b><span>robust loc</span></div>'
                f"</div>"
                f'<div class="bars">{metric_bars}</div>'
                f"{video_html}"
                f'<ol class="steps">{steps_html}</ol>'
                f"</section>"
            )

        highlights = self._highlights()
        hl_items = "".join(
            f"<li>{esc(k.replace('_', ' ').title())}: <b>{esc(v.get('label'))}</b></li>"
            for k, v in highlights.items()
            if isinstance(v, dict)
        )

        judge_html = ""
        if self.judge is not None:
            j = self.judge
            rows: list[str] = []
            for label in j.ranking or list(j.per_config):
                pc = j.per_config.get(label, {})
                score = pc.get("score")
                badge = f'<span class="jscore">{esc(score)}/10</span>' if score is not None else ""
                strengths = "".join(f"<li>👍 {esc(s)}</li>" for s in pc.get("strengths") or [])
                weaknesses = "".join(f"<li>👎 {esc(w)}</li>" for w in pc.get("weaknesses") or [])
                win = " 🏆" if label == j.winner else ""
                rows.append(
                    f'<div class="jrow"><h3>{esc(label)}{win} {badge}</h3>'
                    f"<p>{esc(pc.get('verdict', ''))}</p>"
                    f"<ul>{strengths}{weaknesses}</ul></div>"
                )
            judge_html = (
                f'<div class="judge"><b>🧑‍⚖️ LLM judge'
                f"{f' ({esc(j.model)})' if j.model else ''}</b>"
                + (f'<p class="jsum">{esc(j.summary)}</p>' if j.summary else "")
                + "".join(rows)
                + "</div>"
            )

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DemoDSL config comparison</title>
<style>
:root{{--bg:#0f1117;--card:#191c24;--fg:#e6e8ee;--mut:#9aa0ab;--accent:#6366F1;--win:#22c55e}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);padding:24px}}
h1{{margin:0 0 4px}} .sub{{color:var(--mut);margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid #262a35;border-radius:14px;padding:18px}}
.card.win{{border-color:var(--win)}}
.card h2{{margin:0 0 12px;font-size:18px}}
.kpis{{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:14px}}
.kpi{{display:flex;flex-direction:column}} .kpi b{{font-size:18px}} .kpi span{{color:var(--mut);font-size:12px}}
.bars{{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}}
.bar{{display:grid;grid-template-columns:90px 1fr 40px;align-items:center;gap:8px;font-size:12px}}
.bar .track{{background:#262a35;border-radius:6px;height:8px;overflow:hidden}}
.bar .fill{{background:var(--accent);height:100%}}
.video{{margin:0 0 14px}} .video video{{width:100%;border-radius:10px;background:#000}}
.vmeta{{color:var(--mut);font-size:13px;margin-bottom:6px}}
.steps{{margin:0;padding-left:20px}} .steps li{{margin-bottom:10px}}
.steps code{{background:#0c0e14;padding:2px 6px;border-radius:6px;font-size:12px;color:#c7d2fe}}
.narr{{margin:4px 0 0;color:var(--mut)}}
.hl,.judge{{margin-top:20px;background:var(--card);border-radius:14px;padding:16px}}
.hl ul{{margin:8px 0 0;padding-left:20px}}
.judge .jsum{{color:var(--fg);margin:8px 0 14px}}
.jrow{{border-top:1px solid #262a35;padding-top:10px;margin-top:10px}}
.jrow h3{{margin:0 0 4px;font-size:15px}}
.jrow ul{{margin:6px 0 0;padding-left:20px;color:var(--mut)}}
.jscore{{color:var(--accent);font-weight:700;font-size:13px}}
</style></head><body>
<h1>Configuration comparison</h1>
<div class="sub">{esc(len(configs))} configs{f" — query: <b>{esc(query)}</b>" if query else ""}</div>
<div class="grid">{"".join(cards)}</div>
{judge_html}
<div class="hl"><b>Highlights</b><ul>{hl_items}</ul></div>
</body></html>"""


def compare_configs(paths: list[str | Path]) -> ComparisonReport:
    """Parse and compare the discovered configs at *paths*."""
    return ComparisonReport(configs=[parse_config(p) for p in paths])
