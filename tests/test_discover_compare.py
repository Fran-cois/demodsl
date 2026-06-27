"""Tests for the discovered-config comparison tool (``demodsl.discover.compare``)."""

from __future__ import annotations

from pathlib import Path

from demodsl.discover.compare import compare_configs, parse_config

_GPT4O = """\
# DemoDSL discovery harness v1.1 (demodsl 3.2.0)
# Exploration report
#   query: navigate and review the pricing page
#   start_url: https://capycms.com/
#   feature_reached: True
#   id: 90630dfb
#   policy: llm:openrouter/openai/gpt-4o
#   steps: 4 · href_jumps: 1 · max_jumps: ∞ · allow_external: False
#   score: 0.859 (cov=1.00 rob=0.70 eff=0.89 cost=0.51 qual=0.85)
#   tokens: 2946 (input: 2671 · output: 275 · calls: 1) · representation_path: explore→plan
#   estimated_cost: $0.009428 USD (model openai/gpt-4o, $2.5/$10 per 1M tokens, estimate)

metadata:
  title: Demo
  version: 2.0.0
voice: {engine: gtts, voice_id: en, speed: 1.0}
scenarios:
- name: d
  url: https://capycms.com/
  steps:
  - {action: navigate, url: 'https://capycms.com/', narration: Start., wait: 3.0}
  - action: click
    locator: {type: text, value: Tarifs}
    narration: Open pricing.
    effects: [{type: spotlight, duration: 1.6}]
  - {action: scroll, direction: down, pixels: 700, narration: Review.}
pipeline: [{generate_narration: {}}]
output: {filename: d.mp4, directory: output/}
"""

_CLAUDE = """\
# DemoDSL discovery harness v1.1 (demodsl 3.2.0)
# Exploration report
#   query: navigate and review the pricing page
#   start_url: https://capycms.com/
#   feature_reached: True
#   id: cf84f533
#   policy: llm:openrouter/anthropic/claude-sonnet-4.6
#   steps: 4 · href_jumps: 1 · max_jumps: ∞ · allow_external: False
#   score: 0.811 (cov=1.00 rob=0.60 eff=0.78 cost=0.42 qual=0.82)
#   tokens: 3468 (input: 3026 · output: 442 · calls: 1) · representation_path: explore→plan
#   estimated_cost: n/a — no price for 'anthropic/claude-sonnet-4.6'

metadata:
  title: Demo
  version: 2.0.0
voice: {engine: gtts, voice_id: en, speed: 1.0}
scenarios:
- name: d
  url: https://capycms.com/
  steps:
  - {action: navigate, url: 'https://capycms.com/', narration: Start here on the homepage., wait: 3.0}
  - action: click
    locator: {type: css, value: 'body > a'}
    narration: Jump to pricing.
  - {action: scroll, direction: down, pixels: 800, narration: Review the tiers in detail.}
  - {action: scroll, direction: down, pixels: 600, narration: Continue through the plans.}
pipeline: [{generate_narration: {}}]
output: {filename: d.mp4, directory: output/}
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_extracts_report_and_steps(tmp_path: Path) -> None:
    info = parse_config(_write(tmp_path, "a.yaml", _GPT4O))
    assert info.model == "openai/gpt-4o"
    assert info.query == "navigate and review the pricing page"
    assert info.feature_reached is True
    assert info.score == 0.859
    assert info.score_breakdown["robustness"] == 0.70
    assert (info.tokens_input, info.tokens_output, info.calls) == (2671, 275, 1)
    assert info.cost_usd == 0.009428
    assert info.action_sequence == ["navigate", "click", "scroll"]
    assert info.steps[1].effects == ["spotlight"]


def test_cost_na_parses_as_none(tmp_path: Path) -> None:
    info = parse_config(_write(tmp_path, "c.yaml", _CLAUDE))
    assert info.cost_usd is None
    assert info.model == "anthropic/claude-sonnet-4.6"


def test_compare_highlights_and_markdown(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.yaml", _GPT4O)
    c = _write(tmp_path, "c.yaml", _CLAUDE)
    report = compare_configs([a, c])
    data = report.to_dict()

    assert data["query"] == "navigate and review the pricing page"
    assert data["highlights"]["highest_score"]["label"] == "openai/gpt-4o"
    # Only gpt-4o has a price → it's the cheapest priced one.
    assert data["highlights"]["cheapest"]["label"] == "openai/gpt-4o"
    assert data["highlights"]["most_steps"]["label"] == "anthropic/claude-sonnet-4.6"

    md = report.to_markdown()
    assert "Configuration comparison (2 configs)" in md
    assert "openai/gpt-4o" in md
    assert "Score breakdown" in md
    assert "Walkthroughs" in md
    # robust-locator share: gpt-4o uses text (robust), claude uses css (not).
    gpt = next(c for c in report.configs if c.model == "openai/gpt-4o")
    cld = next(c for c in report.configs if c.model == "anthropic/claude-sonnet-4.6")
    assert gpt.robust_locator_share == 1.0
    assert cld.robust_locator_share == 0.0


def test_detects_rendered_video_next_to_config(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "a.yaml", _GPT4O)
    # The config's output.filename is d.mp4 — drop a stand-in in a render/ subdir.
    render = tmp_path / "render"
    render.mkdir()
    video = render / "d.mp4"
    video.write_bytes(b"\x00" * 2048)

    info = parse_config(cfg)
    assert info.video is not None
    assert info.video.path == video
    assert info.video.size_bytes == 2048  # stat works without ffprobe
    assert info.video.size_mb is not None


def test_to_html_is_self_contained(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.yaml", _GPT4O)
    c = _write(tmp_path, "c.yaml", _CLAUDE)
    # Give one config a rendered video so the player + metrics appear.
    (tmp_path / "d.mp4").write_bytes(b"\x00" * 1024)

    report = compare_configs([a, c])
    out = tmp_path / "comparison.html"
    html = report.to_html(out_path=out)
    out.write_text(html, encoding="utf-8")

    assert html.startswith("<!doctype html>")
    assert "Configuration comparison" in html
    assert "openai/gpt-4o" in html
    assert "<video" in html  # video player embedded
    assert "Highlights" in html
    # video src is relative to the html location.
    assert 'src="d.mp4"' in html or "d.mp4" in html
