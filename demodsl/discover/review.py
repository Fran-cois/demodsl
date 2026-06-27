"""Review mode — run a *panel* of personas past a feature and report the spread.

This is the orchestration + reporting layer on top of the discovery harness and
the persona simulation:

1. **Build** a diverse panel (:func:`demodsl.discover.panel.build_panel`).
2. **Run** the same natural-language flow past every persona — each one drives
   the (optionally authenticated) browser with its own reflexes/effort and emits
   a :class:`~demodsl.discover.persona.PersonaReport` (outcome, think-aloud,
   designer findings, predicted emotion) plus a validated ``discovered_demo.yaml``
   (and, with ``render``, a turbo proof video).
3. **Report** the whole panel as a single, print-ready **PDF** (rendered via
   headless Chromium — no new dependency), with a standalone ``review.html`` and
   a machine-readable ``review.json`` alongside.

Everything runs offline when ``policy="heuristic"`` (no API key), exactly like
the persona harness it builds on.
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from demodsl.discover.emotion import Emotion
from demodsl.discover.persona import Persona, PersonaReport
from demodsl.discover.reward import TrajectoryScore

logger = logging.getLogger(__name__)

__all__ = ["PersonaRunResult", "ReviewReport", "run_review"]

ProgressFn = Callable[[int, int, Persona], None]


# ── result containers ─────────────────────────────────────────────────────────


@dataclass
class PersonaRunResult:
    """One persona's pass through the feature."""

    persona: Persona
    slug: str
    report: PersonaReport | None
    score: TrajectoryScore | None = None
    config_path: Path | None = None
    video_path: Path | None = None
    error: str | None = None
    #: full discovery rollout, kept only when a navigation graph is requested.
    trajectory: Any | None = None

    @property
    def reached(self) -> bool:
        return bool(self.report and self.report.reached)

    @property
    def gave_up(self) -> bool:
        return bool(self.report and self.report.gave_up)

    @property
    def emotion(self) -> Emotion | None:
        return self.report.emotion if self.report else None


@dataclass
class ReviewReport:
    """Aggregate of a whole panel run — a usability finding across attitudes."""

    url: str
    query: str
    runs: list[PersonaRunResult]
    created_at: str
    output_dir: Path
    provider: str = "playwright"
    policy: str = "heuristic"
    rendered: bool = False
    hero_data_uri: str | None = None
    html_path: Path | None = None
    pdf_path: Path | None = None
    json_path: Path | None = None
    #: Mermaid source of the unioned persona-paths graph (when ``--graph``).
    graph_mermaid: str | None = None
    #: ``{format: path}`` of the written graph artifacts (when ``--graph``).
    graph_paths: dict[str, str] | None = None
    notes: list[str] = field(default_factory=list)

    # ── aggregates ────────────────────────────────────────────────────────
    @property
    def n(self) -> int:
        return len(self.runs)

    @property
    def reached_count(self) -> int:
        return sum(1 for r in self.runs if r.reached)

    @property
    def gave_up_count(self) -> int:
        return sum(1 for r in self.runs if r.gave_up)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.runs if r.error)

    @property
    def avg_effort(self) -> float:
        vals = [r.report.effort for r in self.runs if r.report]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    @property
    def avg_frustration(self) -> float:
        vals = [r.report.frustration for r in self.runs if r.report]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    def emotion_distribution(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for r in self.runs:
            if r.emotion:
                counts[r.emotion.key] += 1
        return dict(counts)

    def overall_sentiment(self) -> str:
        """Coarse panel sentiment from emotion valences: positive|mixed|negative."""
        score = 0
        seen = 0
        for r in self.runs:
            if not r.emotion:
                continue
            seen += 1
            score += {"positive": 1, "neutral": 0, "negative": -1}.get(r.emotion.valence, 0)
        if seen == 0:
            return "unknown"
        avg = score / seen
        if avg >= 0.34:
            return "positive"
        if avg <= -0.34:
            return "negative"
        return "mixed"

    def recurring_findings(self) -> list[tuple[str, int]]:
        """Findings shared across personas, grouped by signature, count desc.

        A *signature* strips the numeric specifics (``2 controls`` vs ``3
        controls``) and keeps the problem statement (text before the ``→``), so
        the same systemic issue raised by several personas collapses into one
        prioritised recommendation.
        """
        rep: dict[str, str] = {}
        counts: Counter[str] = Counter()
        for r in self.runs:
            if not r.report:
                continue
            for finding in r.report.findings:
                sig = _finding_signature(finding)
                counts[sig] += 1
                rep.setdefault(sig, finding)
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], rep[kv[0]]))
        return [(rep[sig], cnt) for sig, cnt in ordered]

    # ── serialisation ─────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "query": self.query,
            "created_at": self.created_at,
            "provider": self.provider,
            "policy": self.policy,
            "rendered": self.rendered,
            "panel_size": self.n,
            "summary": {
                "reached": self.reached_count,
                "gave_up": self.gave_up_count,
                "errors": self.error_count,
                "overall_sentiment": self.overall_sentiment(),
                "avg_effort": self.avg_effort,
                "avg_frustration": self.avg_frustration,
                "emotion_distribution": self.emotion_distribution(),
                "recurring_findings": [
                    {"finding": text, "personas": cnt} for text, cnt in self.recurring_findings()
                ],
            },
            "runs": [_run_to_dict(r) for r in self.runs],
        }


# ── orchestration ─────────────────────────────────────────────────────────────


def run_review(
    *,
    url: str,
    query: str,
    personas: list[Persona],
    output_dir: str | Path = "output/review",
    provider: str = "playwright",
    auth: Any | None = None,
    login: dict[str, Any] | None = None,
    policy: str = "heuristic",
    llm_backend: str = "openai",
    model: str = "gpt-4o",
    max_steps: int = 8,
    render: bool = False,
    env_factory: Callable[[], Any] | None = None,
    pdf: bool = True,
    hero: bool = True,
    graph: bool = False,
    progress: ProgressFn | None = None,
) -> ReviewReport:
    """Run every persona in ``personas`` past ``query`` on ``url`` and report.

    Returns a :class:`ReviewReport`; also writes ``review.json``, ``review.html``
    and (when ``pdf`` and Chromium are available) ``review.pdf`` into
    ``output_dir``, with each persona's ``discovered_demo.yaml`` in a sub-folder.
    """
    from demodsl.discover.harness import DiscoveryHarness

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = len(personas)
    runs: list[PersonaRunResult] = []

    for i, persona in enumerate(personas):
        slug = _slugify(persona.label or persona.description, i)
        sub = out / slug
        if progress is not None:
            progress(i, total, persona)
        try:
            harness = DiscoveryHarness.build(
                policy=policy,
                llm_backend=llm_backend,
                model=model,
                max_steps=max_steps,
                persona=persona,
            )
            result = harness.discover(
                url=url,
                query=query,
                provider=provider,
                auth=auth,
                login=login,
                env_factory=env_factory,
                verify=render,
                output_dir=sub,
                verify_turbo=True,
            )
            runs.append(
                PersonaRunResult(
                    persona=persona,
                    slug=slug,
                    report=result.persona_report,
                    score=result.score,
                    config_path=result.config_path,
                    video_path=result.video_path,
                    trajectory=result.trajectory if graph else None,
                )
            )
        except Exception as exc:  # one persona failing must not sink the panel
            logger.warning("review: persona %r failed: %s", persona.label, exc)
            runs.append(PersonaRunResult(persona=persona, slug=slug, report=None, error=str(exc)))

    report = ReviewReport(
        url=url,
        query=query,
        runs=runs,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        output_dir=out,
        provider=provider,
        policy=policy,
        rendered=render,
    )

    if hero and env_factory is None:
        report.hero_data_uri = _capture_hero(url)

    # Optional navigation graph: union every persona's path into one diagram.
    if graph:
        from demodsl.discover.graph import build_path_graph, write_path_graph

        gpaths = [(r.persona.label or r.slug, r.trajectory) for r in runs if r.trajectory]
        if gpaths:
            pg = build_path_graph(query=query, start_url=url, paths=gpaths)
            report.graph_mermaid = pg.to_mermaid()
            written = write_path_graph(pg, out)
            report.graph_paths = {fmt: str(p) for fmt, p in written.items()}

    # Always emit the machine-readable + HTML artifacts.
    report.json_path = out / "review.json"
    report.json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    page_html = render_review_html(report)
    report.html_path = out / "review.html"
    report.html_path.write_text(page_html, encoding="utf-8")

    if pdf:
        pdf_path = out / "review.pdf"
        try:
            _html_to_pdf(page_html, pdf_path)
            report.pdf_path = pdf_path
        except Exception as exc:  # Chromium missing / sandbox — HTML still stands
            logger.warning("review: PDF render failed (%s); HTML report kept", exc)
            report.notes.append(f"PDF render skipped: {exc}")

    return report


# ── HTML rendering ────────────────────────────────────────────────────────────

_CSS = """
:root { --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --bg:#f8fafc;
  --pos:#16a34a; --neg:#dc2626; --mix:#d97706; }
* { box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,
  Arial,sans-serif; color:var(--ink); margin:0; background:#fff; font-size:13px;
  line-height:1.5; }
.wrap { max-width:900px; margin:0 auto; padding:28px 30px 48px; }
h1 { font-size:24px; margin:0 0 4px; }
h2 { font-size:16px; margin:26px 0 12px; padding-bottom:6px;
  border-bottom:2px solid var(--line); }
a { color:#2563eb; text-decoration:none; }
.sub { color:var(--muted); font-size:13px; margin:0 0 2px; }
.meta { color:var(--muted); font-size:12px; }
.badge { display:inline-block; padding:2px 9px; border-radius:999px; font-size:11px;
  font-weight:600; border:1px solid var(--line); }
.hero { width:100%; max-height:240px; object-fit:cover; border-radius:12px;
  border:1px solid var(--line); margin:14px 0 6px; }
.cards { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:14px 0; }
.stat { border:1px solid var(--line); border-radius:12px; padding:12px 14px; background:var(--bg); }
.stat .num { font-size:22px; font-weight:700; }
.stat .lbl { color:var(--muted); font-size:11px; text-transform:uppercase;
  letter-spacing:.04em; }
.senti-positive { color:var(--pos); } .senti-negative { color:var(--neg); }
.senti-mixed { color:var(--mix); } .senti-unknown { color:var(--muted); }
.strip { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 4px; }
.strip .cell { text-align:center; width:78px; }
.strip .cell .nm { font-size:10px; color:var(--muted); margin-top:2px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.findings { padding-left:0; list-style:none; margin:8px 0; }
.findings li { border:1px solid var(--line); border-left:4px solid var(--mix);
  border-radius:8px; padding:8px 12px; margin:7px 0; background:#fffdf7; }
.findings li.shared { border-left-color:var(--neg); background:#fef6f6; }
.findings .tag { font-size:10px; font-weight:700; color:var(--neg);
  text-transform:uppercase; letter-spacing:.03em; }
.persona { border:1px solid var(--line); border-radius:14px; padding:16px 18px;
  margin:14px 0; break-inside:avoid; }
.persona .top { display:flex; gap:14px; align-items:flex-start; }
.persona .who { flex:1; }
.persona .name { font-size:16px; font-weight:700; margin:0; }
.persona .desc { color:var(--muted); margin:2px 0 0; }
.traits { display:grid; grid-template-columns:1fr 1fr; gap:6px 18px; margin:12px 0; }
.trait { font-size:11px; }
.trait .tk { display:flex; justify-content:space-between; color:var(--muted); }
.track { height:6px; background:var(--line); border-radius:4px; overflow:hidden; margin-top:3px; }
.fill { height:100%; border-radius:4px; }
.outcome { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:6px 0 0; }
.think { margin:10px 0 0; }
.think blockquote { margin:5px 0; padding:6px 12px; border-left:3px solid var(--line);
  color:#374151; background:#fafafa; border-radius:0 6px 6px 0; font-style:italic; }
.links { font-size:11px; color:var(--muted); margin-top:8px; }
.err { color:var(--neg); font-size:12px; }
footer { color:var(--muted); font-size:11px; text-align:center; margin-top:30px;
  padding-top:12px; border-top:1px solid var(--line); }
@media print { .persona, .stat, .findings li { break-inside:avoid; } h2 { break-after:avoid; } }
"""

_TRAIT_LABELS = {
    "patience": "Patience",
    "tech_savviness": "Tech-savviness",
    "thoroughness": "Thoroughness",
    "confidence": "Confidence",
}


def render_review_html(report: ReviewReport) -> str:
    """Render the whole panel as a single, self-contained, print-ready HTML page."""
    e = html.escape
    senti = report.overall_sentiment()
    parts: list[str] = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>UX review panel — {e(report.url)}</title>",
        f"<style>{_CSS}</style>",
        _graph_head(report),
        "</head><body><div class='wrap'>",
        "<h1>UX review panel</h1>",
        f"<p class='sub'><strong>Query:</strong> {e(report.query)}</p>",
        f"<p class='sub'><strong>Site:</strong> <a href='{e(report.url)}'>{e(report.url)}</a></p>",
        f"<p class='meta'>{report.n} personas · provider <code>{e(report.provider)}</code> · "
        f"policy <code>{e(report.policy)}</code> · {e(report.created_at)}</p>",
    ]
    if report.hero_data_uri:
        parts.append(f"<img class='hero' src='{report.hero_data_uri}' alt='site preview'>")

    # Summary band
    parts += [
        "<div class='cards'>",
        _stat(f"{report.reached_count}/{report.n}", "reached the feature"),
        _stat(f"{report.gave_up_count}/{report.n}", "gave up"),
        _stat(
            f"<span class='senti-{senti}'>{senti}</span>",
            "overall sentiment",
        ),
        _stat(f"{report.avg_effort:.1f}", "avg effort"),
        _stat(f"{report.avg_frustration:.2f}", "avg frustration"),
        _stat(f"{report.error_count}", "run errors"),
        "</div>",
    ]

    # At-a-glance emotion strip
    parts.append("<div class='strip'>")
    for r in report.runs:
        if r.emotion is not None:
            avatar = r.emotion.avatar_svg(size=56)
            mood = f"{r.emotion.emoji} {e(r.emotion.key)}"
        else:
            avatar = "<div style='width:56px;height:56px'></div>"
            mood = "error"
        parts.append(
            f"<div class='cell'>{avatar}<div class='nm'>{e(r.persona.label)}</div>"
            f"<div class='nm'>{mood}</div></div>"
        )
    parts.append("</div>")

    # Optional navigation graph (union of every persona's path)
    parts.append(_graph_section(report))

    # Priority findings (systemic = shared by >= 2 personas first)
    recurring = report.recurring_findings()
    if recurring:
        parts.append("<h2>Priority findings</h2><ul class='findings'>")
        for text, cnt in recurring:
            shared = " shared" if cnt >= 2 else ""
            tag = f"<span class='tag'>{cnt} personas</span> " if cnt >= 2 else ""
            parts.append(f"<li class='{shared.strip()}'>{tag}{e(text)}</li>")
        parts.append("</ul>")

    # Per-persona detail
    parts.append("<h2>Personas</h2>")
    for r in report.runs:
        parts.append(_persona_block(r))

    parts.append("<footer>Generated by demodsl · synthetic-user review panel</footer>")
    parts.append("</div></body></html>")
    return "".join(parts)


def _stat(num_html: str, label: str) -> str:
    return f"<div class='stat'><div class='num'>{num_html}</div><div class='lbl'>{html.escape(label)}</div></div>"


def _graph_head(report: ReviewReport) -> str:
    """Mermaid loader, included only when a navigation graph is present."""
    if not report.graph_mermaid:
        return ""
    return (
        "<script src='https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'></script>"
        "<script>document.addEventListener('DOMContentLoaded',function(){"
        "if(window.mermaid){mermaid.initialize({startOnLoad:true,securityLevel:'loose',"
        "flowchart:{htmlLabels:true}});}});</script>"
        "<style>.diagram{border:1px solid var(--line);border-radius:12px;padding:16px;"
        "background:var(--bg);overflow:auto;margin:10px 0;}"
        ".diagram pre{margin:0;background:transparent;}"
        ".graphlinks{font-size:11px;color:var(--muted);margin:4px 0 0;}</style>"
    )


def _graph_section(report: ReviewReport) -> str:
    """The 'User paths' block: an inline Mermaid diagram + links to the artifacts."""
    if not report.graph_mermaid:
        return ""
    e = html.escape
    links = ""
    if report.graph_paths:
        bits = [
            f"<a href='{e(Path(p).name)}'>{e(fmt)}</a>" for fmt, p in report.graph_paths.items()
        ]
        links = f"<p class='graphlinks'>Download: {' · '.join(bits)}</p>"
    return (
        "<h2>User paths</h2>"
        "<p class='meta'>Pages visited (nodes) and the actions that moved between "
        "them (edges), unioned across every persona. "
        "<span style='color:var(--pos)'>Green</span> = start · "
        "<span style='color:var(--mix)'>gold</span> = feature reached.</p>"
        f"<div class='diagram'><pre class='mermaid'>{e(report.graph_mermaid)}</pre></div>"
        f"{links}"
    )


def _trait_bar(name: str, value: float, color: str) -> str:
    pct = max(0, min(100, round(value * 100)))
    label = _TRAIT_LABELS.get(name, name)
    return (
        f"<div class='trait'><div class='tk'><span>{html.escape(label)}</span>"
        f"<span>{pct}%</span></div><div class='track'>"
        f"<div class='fill' style='width:{pct}%;background:{color}'></div></div></div>"
    )


def _persona_block(r: PersonaRunResult) -> str:
    e = html.escape
    p = r.persona
    rep = r.report
    color = rep.emotion.color if (rep and rep.emotion) else "#6b7280"
    avatar = rep.emotion.avatar_svg(size=72) if (rep and rep.emotion) else ""

    if rep is None:
        body = f"<p class='err'>Run failed: {e(r.error or 'unknown error')}</p>"
        return (
            f"<div class='persona'><div class='top'>{avatar}<div class='who'>"
            f"<p class='name'>{e(p.label)}</p><p class='desc'>{e(p.description)}</p>"
            f"</div></div>{body}</div>"
        )

    lang = p.language if p.language in ("fr", "en") else "en"
    if rep.reached:
        badge = f"<span class='badge' style='border-color:{_C_POS};color:{_C_POS}'>reached</span>"
    elif rep.gave_up:
        reason = e(rep.abandonment_reason or "gave up")
        badge = f"<span class='badge' style='border-color:{_C_NEG};color:{_C_NEG}'>gave up · {reason}</span>"
    else:
        badge = (
            f"<span class='badge' style='border-color:{_C_MIX};color:{_C_MIX}'>did not reach</span>"
        )

    mood = (
        f"<span class='badge' style='border-color:{color};color:{color}'>"
        f"{rep.emotion.emoji} {e(rep.emotion.label(lang))}</span>"
    )

    traits = "".join(
        _trait_bar(k, getattr(p, k), color)
        for k in ("patience", "tech_savviness", "thoroughness", "confidence")
    )
    think = "".join(f"<blockquote>{e(t)}</blockquote>" for t in rep.reflections)
    findings = "".join(f"<li>{e(f)}</li>" for f in rep.findings)
    findings_html = f"<ul class='findings'>{findings}</ul>" if findings else ""

    links: list[str] = []
    if r.config_path:
        links.append(f"config: <code>{e(str(r.config_path))}</code>")
    if r.video_path:
        links.append(f"video: <code>{e(str(r.video_path))}</code>")
    links_html = f"<div class='links'>{' · '.join(links)}</div>" if links else ""

    return (
        "<div class='persona'><div class='top'>"
        f"{avatar}<div class='who'><p class='name'>{e(p.label)}</p>"
        f"<p class='desc'>{e(p.description)}</p>"
        f"<div class='outcome'>{badge}{mood}"
        f"<span class='meta'>effort {rep.effort:.1f} · frustration "
        f"{rep.frustration:.2f}/{p.frustration_tolerance:.2f} · "
        f"{rep.steps} steps · {rep.scrolls} scrolls · {rep.hesitations} hesitations</span>"
        f"</div></div></div>"
        f"<div class='traits'>{traits}</div>"
        f"<div class='think'>{think}</div>"
        f"{findings_html}{links_html}</div>"
    )


_C_POS = "#16a34a"
_C_NEG = "#dc2626"
_C_MIX = "#d97706"


# ── PDF + hero capture (headless Chromium, no new dependency) ──────────────────


def _html_to_pdf(page_html: str, path: Path) -> None:
    """Render ``page_html`` to a PDF at ``path`` via headless Chromium.

    The HTML is served from a ``file://`` URL (more reliable for ``printToPDF``
    than ``set_content``) and the geometry is owned entirely by ``page.pdf`` —
    the stylesheet deliberately omits an ``@page`` size to avoid the
    "Printing failed" protocol error a conflicting directive triggers.

    Colour emoji are stripped for the PDF pass only: Chromium's headless
    ``printToPDF`` crashes ("Printing failed") on astral-plane colour-emoji
    glyphs on some platforms. The emotion is already carried by the inline SVG
    avatars and colour-coded labels, so the PDF loses nothing; the standalone
    ``review.html`` keeps the emoji for browser viewing.
    """
    import tempfile

    from playwright.sync_api import sync_playwright

    safe_html = _EMOJI_RE.sub("", page_html)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "review.html"
        src.write_text(safe_html, encoding="utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(src.as_uri(), wait_until="load")
                page.emulate_media(media="print")
                page.wait_for_timeout(250)
                page.pdf(
                    path=str(path),
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "12mm",
                        "bottom": "14mm",
                        "left": "10mm",
                        "right": "10mm",
                    },
                )
            finally:
                browser.close()


def _capture_hero(url: str, *, timeout_ms: int = 9000) -> str | None:
    """Best-effort: screenshot ``url`` and return a base64 PNG data-URI (or None)."""
    import base64

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(800)
                png = page.screenshot(type="png")
            finally:
                browser.close()
        return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    except Exception as exc:  # network/Chromium issues are non-fatal
        logger.info("review: hero screenshot skipped (%s)", exc)
        return None


# ── helpers ───────────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_DIGIT_RE = re.compile(r"[\d.%]+")
# Colour-emoji / pictograph ranges (emoticons, symbols, dingbats, flags, VS-16).
# Stripped only for the PDF pass — normal-font glyphs like the "→" arrow (U+2192)
# are intentionally left untouched.
_EMOJI_RE = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff\ufe0f]")


def _slugify(text: str, index: int) -> str:
    base = _SLUG_RE.sub("_", text.lower()).strip("_") or "persona"
    return f"{index + 1:02d}_{base[:32]}"


def _finding_signature(finding: str) -> str:
    head = finding.split("→", 1)[0]
    return _DIGIT_RE.sub("#", head).strip().lower()


def _persona_dict(persona: Persona) -> dict[str, Any]:
    return {
        "label": persona.label,
        "description": persona.description,
        "language": persona.language,
        "traits": {
            "patience": persona.patience,
            "tech_savviness": persona.tech_savviness,
            "thoroughness": persona.thoroughness,
            "confidence": persona.confidence,
        },
    }


def _run_to_dict(r: PersonaRunResult) -> dict[str, Any]:
    data: dict[str, Any] = {
        "slug": r.slug,
        "persona": _persona_dict(r.persona),
        "reached": r.reached,
        "gave_up": r.gave_up,
        "error": r.error,
        "config_path": str(r.config_path) if r.config_path else None,
        "video_path": str(r.video_path) if r.video_path else None,
    }
    if r.score is not None:
        data["score"] = round(r.score.total, 3)
    if r.report is not None:
        rep = r.report
        data.update(
            {
                "outcome": rep.headline(),
                "effort": rep.effort,
                "frustration": rep.frustration,
                "steps": rep.steps,
                "scrolls": rep.scrolls,
                "hesitations": rep.hesitations,
                "reflections": list(rep.reflections),
                "findings": list(rep.findings),
            }
        )
        if rep.emotion is not None:
            data["emotion"] = {
                "key": rep.emotion.key,
                "emoji": rep.emotion.emoji,
                "valence": rep.emotion.valence,
            }
    return data
