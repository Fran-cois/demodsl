"""`demodsl probe` — resolve every locator against the live page (issue #16).

The dominant failure mode of a programmatically authored config is a **locator
miss**: the element doesn't exist, isn't visible, resolves to a hidden footer
node, or matches five things at once. Today the only way to find out is a full
render (browser + TTS + composition) that dies at step 7.

:func:`probe_config` opens the page(s) once, resolves every locator the config
references — step locators, drag targets and camera targets — and reports for
each one whether it resolved, how many elements it matched, its bbox, whether
it is visible and whether it can be brought into the viewport. On a miss it
mines the page for near-matches and proposes concrete replacement locators.

Seconds instead of a ten-minute render, and the output is JSON so an agent can
repair its own config before spending a single TTS call.
"""

from __future__ import annotations

import difflib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from demodsl.models import DemoConfig, Locator
    from demodsl.providers.base import BrowserProvider

logger = logging.getLogger(__name__)

__all__ = ["probe_config", "collect_targets", "suggest", "ProbeTarget"]

#: Max suggestions returned per unresolved locator.
_MAX_SUGGESTIONS = 3
#: Below this similarity ratio a page element is not a plausible near-match.
_MIN_RATIO = 0.55


class ProbeTarget:
    """One locator referenced by the config, with where it came from."""

    __slots__ = ("index", "action", "kind", "locator", "url")

    def __init__(self, index: int, action: str, kind: str, locator: Locator, url: str | None):
        self.index = index
        self.action = action
        self.kind = kind  # "locator" | "target_locator" | "camera.target"
        self.locator = locator
        self.url = url

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "kind": self.kind,
            "locator": {"type": self.locator.type, "value": self.locator.value},
            "url": self.url,
        }


def collect_targets(config: DemoConfig) -> list[ProbeTarget]:
    """Every locator the config resolves at runtime, in execution order.

    The URL carried by each target is the page in effect at that point in the
    scenario (the last ``navigate``, or the scenario's ``url``), so a
    multi-page tour is probed page by page instead of all against the home.
    """
    targets: list[ProbeTarget] = []
    index = 0
    for scenario in config.scenarios:
        if scenario.mobile is not None:
            index += len(scenario.steps or [])
            continue  # a mobile scenario has no page to probe
        current = scenario.url
        for step in scenario.steps or []:
            if step.action == "navigate" and step.url:
                current = step.url
            if step.locator is not None:
                targets.append(ProbeTarget(index, step.action, "locator", step.locator, current))
            if step.target_locator is not None:
                targets.append(
                    ProbeTarget(index, step.action, "target_locator", step.target_locator, current)
                )
            camera = step.camera
            if camera is not None and getattr(camera, "target", None) is not None:
                targets.append(
                    ProbeTarget(index, step.action, "camera.target", camera.target, current)
                )
            index += 1
    return targets


# Resolves a locator with the same semantics as the browser provider and
# reports match count, bbox and visibility in one round-trip.
_RESOLVE_JS = r"""
(spec) => {
  const norm = (s) => (s || '').replace(/[\u2010-\u2015\u2212]/g, '-')
    .replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"')
    .replace(/\s+/g, ' ').trim().toLowerCase();
  let nodes = [];
  try {
    if (spec.type === 'css') nodes = Array.from(document.querySelectorAll(spec.value));
    else if (spec.type === 'id') {
      const el = document.getElementById(spec.value);
      nodes = el ? [el] : [];
    } else if (spec.type === 'xpath') {
      const it = document.evaluate(spec.value, document, null, 7, null);
      for (let i = 0; i < it.snapshotLength; i++) nodes.push(it.snapshotItem(i));
    } else if (spec.type === 'text') {
      const needle = norm(spec.value);
      const all = document.querySelectorAll('body *');
      for (const el of all) {
        if (el.children.length > 2) continue;          // prefer leaf-ish nodes
        if (norm(el.textContent).includes(needle)) nodes.push(el);
      }
      // Drop ancestors that only match through a matching descendant.
      nodes = nodes.filter((el) => !nodes.some((o) => o !== el && el.contains(o)));
    }
  } catch (err) {
    return { error: String(err && err.message || err), matches: 0 };
  }
  if (!nodes.length) return { matches: 0 };
  const el = nodes[0];
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  const hidden = cs.visibility === 'hidden' || cs.display === 'none'
    || parseFloat(cs.opacity) < 0.05 || (r.width < 2 && r.height < 2);
  return {
    matches: nodes.length,
    bbox: { x: r.left, y: r.top, w: r.width, h: r.height },
    page_y: r.top + window.scrollY,
    visible: !hidden,
    in_viewport: r.top < window.innerHeight && r.bottom > 0 && !hidden,
    page_height: document.documentElement.scrollHeight,
    viewport_h: window.innerHeight,
    tag: el.tagName.toLowerCase(),
    text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80),
  };
}
"""


def suggest(
    value: str, elements: list[dict[str, Any]], *, limit: int = _MAX_SUGGESTIONS
) -> list[dict[str, Any]]:
    """Propose replacement locators for the unresolved text *value*.

    *elements* are the ranked entries produced by :mod:`demodsl.observe`. The
    best textual near-matches come back as ready-to-paste locators; when the
    page contains nothing similar (the label was invented, or the copy
    changed entirely) the most prominent interactive elements are returned
    instead, flagged ``fallback`` — an agent still gets something real to
    re-target rather than a dead end.
    """
    needle = " ".join(value.split()).lower()
    needle_tokens = {t for t in needle.split() if len(t) > 2}
    scored: list[tuple[float, dict[str, Any]]] = []
    for el in elements:
        text = " ".join(str(el.get("text") or "").split())
        if not text:
            continue
        lowered = text.lower()
        ratio = difflib.SequenceMatcher(None, needle, lowered).ratio()
        tokens = {t for t in lowered.split() if len(t) > 2}
        if needle_tokens and tokens:
            ratio = max(ratio, len(needle_tokens & tokens) / len(needle_tokens | tokens))
        if needle and (needle in lowered or lowered in needle):
            ratio = max(ratio, 0.9)
        if ratio >= _MIN_RATIO:
            scored.append((ratio, el))
    scored.sort(key=lambda pair: (-pair[0], len(str(pair[1].get("text") or ""))))
    fallback = False

    if not scored:
        fallback = True
        clickable = [el for el in elements if el.get("is_link") or el.get("hoverable")]
        scored = [(0.0, el) for el in (clickable or elements)[:limit]]

    out: list[dict[str, Any]] = []
    for ratio, el in scored[:limit]:
        text = " ".join(str(el.get("text") or "").split())
        entry: dict[str, Any] = {
            "type": "text",
            "value": text[:60],
            "similarity": round(ratio, 2),
            "css": (el.get("locator") or {}).get("value"),
            "prominence": el.get("prominence"),
        }
        if fallback:
            entry["fallback"] = True
        out.append(entry)
    return out


def probe_config(
    config: DemoConfig,
    *,
    viewport: tuple[int, int] = (1920, 1080),
    browser: str = "chrome",
    suggestions: bool = True,
) -> dict[str, Any]:
    """Open every page the config visits and resolve all its locators."""
    import demodsl.providers.browser  # noqa: F401  (registers the provider)
    from demodsl.models import Viewport
    from demodsl.providers.base import BrowserProviderFactory

    targets = collect_targets(config)
    if not targets:
        return {"targets": 0, "resolved": 0, "steps": []}

    provider = BrowserProviderFactory.create("playwright")
    provider.launch_without_recording(
        browser_type=browser,
        viewport=Viewport(width=viewport[0], height=viewport[1]),
    )
    results: list[dict[str, Any]] = []
    page_elements: dict[str, list[dict[str, Any]]] = {}
    resolved_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
    current_url: str | None = None
    try:
        for target in targets:
            if target.url and target.url != current_url:
                provider.navigate(target.url)
                current_url = target.url
                page_elements.pop(current_url, None)
            key = (current_url or "", target.locator.type, target.locator.value)
            cached = resolved_cache.get(key)
            if cached is not None:
                entry = {**cached, **target.to_dict()}
            else:
                entry = _probe_one(
                    provider,
                    target,
                    page_elements if suggestions else None,
                    current_url,
                )
                resolved_cache[key] = {
                    k: v for k, v in entry.items() if k not in ("index", "action", "kind")
                }
            results.append(entry)
    finally:
        provider.close()

    resolved = sum(1 for r in results if r["resolved"])
    return {
        "targets": len(results),
        "resolved": resolved,
        "unresolved": len(results) - resolved,
        "ambiguous": sum(1 for r in results if r.get("matches", 0) > 1),
        "steps": results,
    }


def _probe_one(
    provider: BrowserProvider,
    target: ProbeTarget,
    page_elements: dict[str, list[dict[str, Any]]] | None,
    url: str | None,
) -> dict[str, Any]:
    spec = {"type": target.locator.type, "value": target.locator.value}
    entry: dict[str, Any] = target.to_dict()
    try:
        # evaluate_js takes an expression: an IIFE-style call of the resolver.
        raw = provider.evaluate_js(f"({_RESOLVE_JS})({json.dumps(spec)})")
    except Exception as exc:  # pragma: no cover - JS/page failure
        entry.update({"resolved": False, "reason": f"probe failed: {exc}"})
        return entry

    if not isinstance(raw, dict) or raw.get("error"):
        entry.update(
            {
                "resolved": False,
                "matches": 0,
                "reason": (raw or {}).get("error", "invalid selector")
                if isinstance(raw, dict)
                else "invalid selector",
            }
        )
        return entry

    matches = int(raw.get("matches") or 0)
    if matches == 0:
        entry.update({"resolved": False, "matches": 0, "reason": "no match"})
        if page_elements is not None and target.locator.type == "text":
            entry["suggestions"] = suggest(
                target.locator.value, _elements_for(provider, page_elements, url)
            )
        return entry

    entry.update(
        {
            "resolved": True,
            "matches": matches,
            "bbox": raw.get("bbox"),
            "visible": bool(raw.get("visible")),
            "in_viewport": bool(raw.get("in_viewport")),
            "in_viewport_after_scroll": bool(
                raw.get("visible")
                and float(raw.get("page_y") or 0) <= float(raw.get("page_height") or 0)
            ),
            "tag": raw.get("tag"),
            "text": raw.get("text"),
        }
    )
    if matches > 1:
        entry["reason"] = f"ambiguous — matches {matches} elements"
    elif not raw.get("visible"):
        entry["reason"] = "element resolves but is not visible"
    return entry


def _elements_for(
    provider: BrowserProvider,
    cache: dict[str, list[dict[str, Any]]],
    url: str | None,
) -> list[dict[str, Any]]:
    """Ranked page elements for *url*, collected once per page."""
    key = url or ""
    if key in cache:
        return cache[key]
    from demodsl.observe import COLLECT_JS, rank_elements

    try:
        payload = provider.evaluate_js(COLLECT_JS)
        cache[key] = rank_elements(payload, limit=80)
    except Exception as exc:  # pragma: no cover - page failure
        logger.warning("Cannot collect page elements for suggestions: %s", exc)
        cache[key] = []
    return cache[key]


def probe_file(
    path: Path,
    *,
    viewport: tuple[int, int] = (1920, 1080),
    browser: str = "chrome",
    suggestions: bool = True,
) -> dict[str, Any]:
    """Load a config file and probe it."""
    from demodsl.config_loader import load_config_with_library
    from demodsl.models import DemoConfig

    config = DemoConfig(**load_config_with_library(path))
    return probe_config(config, viewport=viewport, browser=browser, suggestions=suggestions)
