"""Visual page observation — Set-of-Marks + prominence ranking (issue #23).

The crawl graph an author works from is a *DOM listing*: headings and
interactive elements in document order. A landing page argues
*visually* — the hero is huge, the proof rail is a band of logos, the CTA
is the only saturated button on screen. This module produces the second
representation:

1. a **prominence-ranked element table**, each entry carrying the visual
   evidence that makes it important (font size, area ratio, contrast,
   above-the-fold, only-saturated-CTA, in-carousel, hoverable);
2. a **Set-of-Marks screenshot** — the same screenshot with numbered
   badges — so a multimodal model can point at "12" instead of guessing
   a selector;
3. a **derived page structure** (hero / features / proof / pricing /
   footer) plus a shortlist of candidate arguments.

Everything below the browser boundary is pure: :func:`rank_elements`,
:func:`derive_sections` and :func:`candidate_arguments` take plain dicts
so they can be unit-tested from a fixture.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from demodsl.color_utils import contrast_ratio, parse_css_color

logger = logging.getLogger(__name__)

__all__ = [
    "COLLECT_JS",
    "rank_elements",
    "derive_sections",
    "candidate_arguments",
    "draw_marks",
    "observe",
    "SECTION_KEYWORDS",
]

#: Section classification keywords, checked against the section's heading
#: and its text content (lower-cased).
SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pricing": ("pricing", "plans", "per month", "/mo", "tarif", "abonnement", "€", "$"),
    "proof": (
        "trusted by",
        "customers",
        "testimonial",
        "case study",
        "loved by",
        "used by",
        "ils nous font confiance",
    ),
    "features": ("features", "how it works", "why", "built for", "fonctionnalit"),
    "footer": ("privacy", "terms", "©", "all rights reserved", "mentions légales"),
}

_NUMERIC_TOKEN = re.compile(r"(?<![\w.])\d[\d\s.,]*\s*(?:%|x|×|k|m|bn|\+|€|\$|£)?", re.IGNORECASE)
_STRONG_NUMERIC = re.compile(r"\d[\d.,]*\s*(?:%|x|×|k|m|bn|\+)|[€$£]\s*\d", re.IGNORECASE)

#: Collected in the page. Returns the raw material :func:`rank_elements` scores.
COLLECT_JS = r"""
(() => {
  const SEL = 'h1,h2,h3,h4,p,a,button,[role=button],img,li,span,strong,div[class*=stat]';
  const out = [];
  const seen = new Set();
  const cssPath = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 5) {
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const sibs = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (sibs.length > 1) part += `:nth-of-type(${sibs.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      if (node.id) { parts[0] = '#' + CSS.escape(node.id); break; }
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  for (const el of document.querySelectorAll(SEL)) {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.05)
      continue;
    const text = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 160);
    if (!text && el.tagName !== 'IMG') continue;
    const key = el.tagName + '|' + text + '|' + Math.round(r.top);
    if (seen.has(key)) continue;
    seen.add(key);
    let bg = 'rgba(0, 0, 0, 0)';
    let node = el;
    while (node && bg === 'rgba(0, 0, 0, 0)') {
      bg = getComputedStyle(node).backgroundColor;
      node = node.parentElement;
    }
    const carousel = !!el.closest(
      '[class*=carousel],[class*=slider],[class*=swiper],[aria-roledescription=carousel]'
    );
    out.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      text: text,
      locator: { type: 'css', value: cssPath(el) },
      bbox: { x: r.left, y: r.top, w: r.width, h: r.height },
      page_y: r.top + window.scrollY,
      font_px: parseFloat(cs.fontSize) || 0,
      font_weight: parseInt(cs.fontWeight, 10) || 400,
      color: cs.color,
      background: bg,
      pointer_events: cs.pointerEvents,
      in_carousel: carousel,
      is_link: el.tagName === 'A' || el.tagName === 'BUTTON' || el.getAttribute('role') === 'button',
    });
  }
  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    page_height: document.documentElement.scrollHeight,
    scroll_y: window.scrollY,
    elements: out,
  };
})()
"""


# ── Prominence ranking ───────────────────────────────────────────────────────


def _saturation(color: str | None) -> float:
    parsed = parse_css_color(color)
    if parsed is None or parsed[3] == 0:
        return 0.0
    high, low = max(parsed[:3]), min(parsed[:3])
    return 0.0 if high == 0 else (high - low) / high


def _role_weight(element: dict[str, Any]) -> float:
    tag = (element.get("tag") or "").lower()
    if tag == "h1":
        return 1.0
    if tag == "h2":
        return 0.85
    if tag in ("h3", "h4"):
        return 0.7
    if element.get("is_link"):
        return 0.6
    if tag == "img":
        return 0.45
    return 0.35


def rank_elements(
    payload: dict[str, Any],
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Score, sort and number the observed elements.

    *payload* is the output of :data:`COLLECT_JS` (or an equivalent
    fixture). The returned entries carry a ``mark`` (1-based, stable for
    a given payload), a ``prominence`` score in 0..1 and a ``visual``
    sub-dict with the evidence behind the score.
    """
    viewport = payload.get("viewport") or {}
    vw = float(viewport.get("w") or 1) or 1.0
    vh = float(viewport.get("h") or 1) or 1.0
    viewport_area = vw * vh
    elements = list(payload.get("elements") or [])

    saturated_ctas = [
        el for el in elements if el.get("is_link") and _saturation(el.get("background")) >= 0.35
    ]
    only_cta_text = (saturated_ctas[0].get("text") or "") if len(saturated_ctas) == 1 else None

    max_font = max((float(el.get("font_px") or 0) for el in elements), default=1.0) or 1.0

    scored: list[dict[str, Any]] = []
    for el in elements:
        bbox = el.get("bbox") or {}
        area = float(bbox.get("w") or 0) * float(bbox.get("h") or 0)
        area_ratio = area / viewport_area if viewport_area else 0.0
        font_px = float(el.get("font_px") or 0)
        weight = int(el.get("font_weight") or 400)
        contrast = contrast_ratio(el.get("color") or "", el.get("background") or "#FFFFFF")
        above_fold = float(el.get("page_y") or 0) < vh
        is_only_cta = only_cta_text is not None and (el.get("text") or "") == only_cta_text
        hoverable = (
            not el.get("in_carousel", False)
            and (el.get("pointer_events") or "auto") != "none"
            and area > 0
        )

        score = (
            0.34 * min(1.0, font_px / max_font)
            + 0.24 * min(1.0, area_ratio * 6)
            + 0.14 * min(1.0, (weight - 300) / 500)
            + 0.10 * min(1.0, (contrast or 1.0) / 12.0)
            + 0.08 * (1.0 if above_fold else 0.0)
            + 0.10 * (1.0 if is_only_cta else 0.0)
        ) * _role_weight(el)

        scored.append(
            {
                "role": el.get("role") or el.get("tag"),
                "tag": el.get("tag"),
                "text": el.get("text") or "",
                "locator": el.get("locator") or {},
                "bbox": bbox,
                "page_y": el.get("page_y", bbox.get("y", 0)),
                "prominence": round(min(1.0, score), 4),
                "visual": {
                    "font_px": font_px,
                    "font_weight": weight,
                    "area_ratio": round(area_ratio, 4),
                    "contrast": round(contrast, 2) if contrast is not None else None,
                    "above_the_fold": above_fold,
                    "is_only_saturated_cta": is_only_cta,
                    "in_carousel": bool(el.get("in_carousel")),
                },
                "hoverable": hoverable,
            }
        )

    scored.sort(key=lambda e: (-e["prominence"], e["page_y"], e["text"]))
    scored = scored[:limit]
    for i, entry in enumerate(scored, start=1):
        entry["mark"] = i
    return scored


# ── Page structure ───────────────────────────────────────────────────────────


def _classify(heading: str, body: str) -> str:
    blob = f"{heading} {body}".lower()
    for name in ("pricing", "proof", "footer", "features"):
        if any(kw in blob for kw in SECTION_KEYWORDS[name]):
            return name
    return "content"


def derive_sections(
    elements: list[dict[str, Any]],
    *,
    page_height: float,
    viewport_height: float,
) -> list[dict[str, Any]]:
    """Group ranked elements into page sections the author can reason about.

    Sections start at each heading (in page order); the first one is the
    *hero* when it sits above the fold, and anything in the last 12% of
    the page is folded into a *footer*.
    """
    if not elements:
        return []
    ordered = sorted(elements, key=lambda e: (float(e.get("page_y") or 0), e.get("mark", 0)))
    footer_start = page_height * 0.88

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for position, el in enumerate(ordered):
        page_y = float(el.get("page_y") or 0)
        is_heading = str(el.get("tag") or "").startswith("h")
        in_footer = page_y >= footer_start
        starts_section = (
            current is None
            or (is_heading and position > 0)
            or (in_footer and not current["in_footer"])
        )
        if starts_section:
            current = {
                "heading": el.get("text", "") if is_heading else "",
                "start_y": page_y,
                "end_y": page_y,
                "marks": [],
                "kind": "content",
                "in_footer": in_footer,
            }
            sections.append(current)
        current["marks"].append(el.get("mark"))
        current["end_y"] = max(current["end_y"], page_y + float((el.get("bbox") or {}).get("h", 0)))

    by_mark = {e.get("mark"): e for e in ordered}
    for idx, section in enumerate(sections):
        body = " ".join(str(by_mark[m].get("text", "")) for m in section["marks"] if m in by_mark)
        if section.pop("in_footer"):
            section["kind"] = "footer"
        elif idx == 0 and section["start_y"] < viewport_height:
            section["kind"] = "hero"
        else:
            section["kind"] = _classify(section["heading"], body)
    return sections


def candidate_arguments(elements: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Shortlist the marks that are plausible *arguments*, by kind.

    * ``biggest_text`` — the largest type on the page (the claim);
    * ``metrics`` — numeric / percentage tokens (the evidence);
    * ``logo_rail`` — three or more images sharing a horizontal band;
    * ``primary_cta`` — the only saturated call to action.
    """
    result: dict[str, list[int]] = {
        "biggest_text": [],
        "metrics": [],
        "logo_rail": [],
        "primary_cta": [],
    }
    if not elements:
        return result

    max_font = max(float(e["visual"]["font_px"]) for e in elements)
    for el in elements:
        mark = el.get("mark")
        if mark is None:
            continue
        if float(el["visual"]["font_px"]) >= max_font * 0.9:
            result["biggest_text"].append(mark)
        if _STRONG_NUMERIC.search(el.get("text") or ""):
            result["metrics"].append(mark)
        if el["visual"].get("is_only_saturated_cta"):
            result["primary_cta"].append(mark)

    images = [e for e in elements if e.get("tag") == "img"]
    bands: dict[int, list[int]] = {}
    for img in images:
        band = int(float(img.get("page_y") or 0) // 80)
        bands.setdefault(band, []).append(img["mark"])
    for marks in bands.values():
        if len(marks) >= 3:
            result["logo_rail"].extend(sorted(marks))

    for key in result:
        result[key] = sorted(dict.fromkeys(result[key]))
    return result


# ── Set-of-Marks rendering ───────────────────────────────────────────────────


def draw_marks(
    screenshot: Path,
    elements: list[dict[str, Any]],
    output: Path,
    *,
    scroll_y: float = 0.0,
) -> Path:
    """Overlay numbered badges on *screenshot* for every visible element.

    Elements scrolled out of the captured viewport are skipped — a badge
    at a negative coordinate would be a lie, and this artefact doubles as
    a human debugging aid.
    """
    from PIL import Image, ImageDraw

    image = Image.open(screenshot).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size

    for el in elements:
        bbox = el.get("bbox") or {}
        x = float(bbox.get("x", 0))
        y = float(bbox.get("y", 0)) - scroll_y
        w = float(bbox.get("w", 0))
        h = float(bbox.get("h", 0))
        if y + h < 0 or y > height or x > width:
            continue
        draw.rectangle(
            [x, y, min(x + w, width - 1), min(y + h, height - 1)],
            outline=(99, 102, 241, 220),
            width=2,
        )
        label = str(el.get("mark", "?"))
        bx, by = max(0.0, x), max(0.0, y)
        pad = 6 + 7 * len(label)
        draw.rectangle([bx, by, bx + pad, by + 20], fill=(99, 102, 241, 235))
        draw.text((bx + 4, by + 4), label, fill=(255, 255, 255, 255))

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


# ── Browser-side entry point ─────────────────────────────────────────────────


def observe(
    url: str,
    *,
    output_dir: Path,
    marks: bool = True,
    limit: int = 40,
    viewport: tuple[int, int] = (1920, 1080),
    browser: str = "chrome",
) -> dict[str, Any]:
    """Open *url*, collect the visual observation and (optionally) draw marks."""
    import demodsl.providers.browser  # noqa: F401  (registers the provider)
    from demodsl.models import Viewport
    from demodsl.providers.base import BrowserProviderFactory

    output_dir.mkdir(parents=True, exist_ok=True)
    provider = BrowserProviderFactory.create("playwright")
    provider.launch_without_recording(
        browser_type=browser,
        viewport=Viewport(width=viewport[0], height=viewport[1]),
    )
    try:
        provider.navigate(url)
        payload = provider.evaluate_js(COLLECT_JS)
        shot = provider.screenshot(output_dir / "observe.png")
    finally:
        provider.close()

    elements = rank_elements(payload, limit=limit)
    report: dict[str, Any] = {
        "url": url,
        "viewport": payload.get("viewport"),
        "page_height": payload.get("page_height"),
        "screenshot": str(shot),
        "elements": elements,
        "sections": derive_sections(
            elements,
            page_height=float(payload.get("page_height") or viewport[1]),
            viewport_height=float((payload.get("viewport") or {}).get("h") or viewport[1]),
        ),
        "candidates": candidate_arguments(elements),
    }
    if marks:
        report["marks_screenshot"] = str(
            draw_marks(
                shot,
                elements,
                output_dir / "observe_marks.png",
                scroll_y=float(payload.get("scroll_y") or 0.0),
            )
        )
    return report
