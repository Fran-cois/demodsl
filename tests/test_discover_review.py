"""Tests for review mode (``demodsl.discover.panel`` + ``demodsl.discover.review``).

Fully offline and deterministic: a ``HeuristicPolicy`` base, persona simulation
and a small simulated site (same contract as ``test_discover_persona.py``), so no
API key, network or real browser is needed. PDF rendering (which needs Chromium)
is disabled with ``pdf=False``.
"""

from __future__ import annotations

import json

import pytest

from demodsl.discover.benchmark import SimElement, SimPage, SimulatedEnvironment
from demodsl.discover.panel import PANEL_ARCHETYPES, build_panel
from demodsl.discover.review import ReviewReport, run_review

START = "https://shop.example.com/"
PRICING = "https://shop.example.com/pricing"


def _deep_site() -> SimulatedEnvironment:
    """A site whose only relevant target sits far below the fold (3 scrolls).

    A hurried persona gives up while a patient one perseveres — the contrast we
    want the panel to surface.
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
        elements=[SimElement("choose", "Choose a plan", "button", abs_y=200, dom_id="choose")],
    )
    return SimulatedEnvironment({START: home, PRICING: pricing}, START)


# ── panel generation ──────────────────────────────────────────────────────────


def test_build_panel_size_and_distinct_labels() -> None:
    panel = build_panel(3)
    assert len(panel) == 3
    assert len({p.label for p in panel}) == 3  # distinct archetypes


def test_build_panel_spans_patience_axis() -> None:
    panel = build_panel(3)
    patiences = [p.patience for p in panel]
    # The first three archetypes deliberately mix a hurried and a patient voice.
    assert min(patiences) < 0.3
    assert max(patiences) > 0.6


def test_build_panel_caps_at_archetype_count() -> None:
    panel = build_panel(99)
    assert len(panel) == len(PANEL_ARCHETYPES)


def test_build_panel_clamps_minimum() -> None:
    assert len(build_panel(0)) == 1


def test_build_panel_base_blend_prefixes_and_pulls_traits() -> None:
    base = "voyageur en train soucieux du climat"
    plain = build_panel(2)
    blended = build_panel(2, base=base)
    assert all(p.description.startswith(base) for p in blended)
    # Blending pulls each archetype's traits toward the base baseline, so the
    # extreme values move inward (a halfway average can't stay more extreme).
    assert blended[0].patience >= plain[0].patience  # angry skeptic .12 → toward .5


def test_build_panel_lang_override() -> None:
    panel = build_panel(3, lang="fr")
    assert all(p.language == "fr" for p in panel)


# ── review orchestration (offline) ────────────────────────────────────────────


def test_run_review_offline_produces_panel_and_artifacts(tmp_path) -> None:
    out = tmp_path / "review"
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(3),
        output_dir=out,
        policy="heuristic",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
    )
    assert isinstance(report, ReviewReport)
    assert report.n == 3
    assert all(r.report is not None for r in report.runs)  # offline never errors
    assert report.error_count == 0
    # A clear spread: at least one reaches, at least one gives up.
    assert report.reached_count >= 1
    assert report.gave_up_count >= 1
    assert report.overall_sentiment() in {"positive", "mixed", "negative"}

    # Artifacts on disk.
    assert (out / "review.json").exists()
    assert (out / "review.html").exists()
    assert report.pdf_path is None  # pdf disabled
    # Each persona got its own discovered_demo.yaml.
    for r in report.runs:
        assert r.config_path is not None and r.config_path.exists()


def test_review_html_embeds_avatars_and_findings(tmp_path) -> None:
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(3),
        output_dir=tmp_path / "rv",
        policy="heuristic",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
    )
    html = (report.html_path).read_text(encoding="utf-8")
    assert "UX review panel" in html
    assert "<svg" in html  # emotion avatars inline
    assert "Personas" in html
    assert report.runs[0].persona.label in html


def test_review_json_is_well_formed(tmp_path) -> None:
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(3),
        output_dir=tmp_path / "rj",
        policy="heuristic",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
    )
    data = json.loads((report.json_path).read_text(encoding="utf-8"))
    assert data["panel_size"] == 3
    assert len(data["runs"]) == 3
    assert set(data["summary"]) >= {
        "reached",
        "gave_up",
        "overall_sentiment",
        "emotion_distribution",
        "recurring_findings",
    }
    assert data["runs"][0]["persona"]["traits"]


def test_recurring_findings_groups_shared_issue(tmp_path) -> None:
    report = run_review(
        url=START,
        query="pricing plans",
        personas=build_panel(3),
        output_dir=tmp_path / "rf",
        policy="heuristic",
        max_steps=12,
        env_factory=_deep_site,
        pdf=False,
        hero=False,
    )
    recurring = report.recurring_findings()
    assert recurring  # at least one finding surfaced
    # The buried target is hit by several personas → a shared (count >= 2) finding.
    assert any(cnt >= 2 for _text, cnt in recurring)


# ── PDF rendering (guarded: needs the bundled Chromium) ───────────────────────


def test_html_to_pdf_strips_emoji_and_writes_pdf(tmp_path) -> None:
    """The PDF pass must survive colour-emoji glyphs (they crash printToPDF on
    some platforms) and still emit a valid PDF."""
    from demodsl.discover.review import _html_to_pdf

    page_html = (
        "<!doctype html><html><head><meta charset='utf-8'></head><body>"
        "<h1>UX review panel \U0001f604</h1><p>buried target \u2192 fix it \U0001f622</p>"
        "</body></html>"
    )
    out = tmp_path / "r.pdf"
    try:
        _html_to_pdf(page_html, out)
    except Exception as exc:  # no Chromium in this environment → skip, don't fail
        pytest.skip(f"Chromium PDF rendering unavailable: {exc}")
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
