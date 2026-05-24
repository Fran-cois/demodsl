"""Resolve `anchors:` blocks to concrete bounding boxes.

The ``anchors`` block lets users reference DOM elements by selector in the
YAML config; their pixel coordinates are computed once (via a lightweight
Playwright probe) and exposed as a templating namespace so library presets
can be positioned by selector instead of by hard-coded ``x``/``y``.

Example YAML::

    anchors:
      signup_btn:
        selector: "#signup"
        # Optional: scenario index (default 0) — picks the URL & viewport
        scenario: 0
      hero:
        # Manual override (no probing): give coords directly
        x: 100
        y: 200
        w: 400
        h: 80

    timeline:
      layers:
        - $use: callouts/circle_highlight
          $params:
            x: "{{ anchors.signup_btn.cx }}"
            y: "{{ anchors.signup_btn.cy }}"

Public functions:
    - ``extract_anchors_spec``: pop ``anchors:`` from raw config
    - ``resolve_anchors``: turn spec → namespace dict (probes if needed)
    - ``apply_anchor_templates``: walk config & interpolate ``{{ anchors.* }}``
"""

from __future__ import annotations

import logging
import re
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger(__name__)

# Match strings that contain at least one {{ ... }} referencing anchors.
_ANCHOR_TEMPLATE_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_ANCHOR_NAMESPACE_RE = re.compile(r"\banchors\.")

DEFAULT_VIEWPORT_W = 1920
DEFAULT_VIEWPORT_H = 1080
PROBE_TIMEOUT_MS = 10_000


class AnchorResolveError(Exception):
    """Raised when anchor probing or templating fails."""


# ── Spec extraction ──────────────────────────────────────────────────────────


def extract_anchors_spec(raw: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    """Pop ``anchors:`` from the raw config dict.

    Returns the spec (or None if absent). Mutates ``raw`` so that the
    DemoConfig Pydantic model doesn't reject the extra key.
    """
    spec = raw.pop("anchors", None)
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise AnchorResolveError("'anchors' must be a mapping of name → spec")
    return spec


# ── Probe & resolve ──────────────────────────────────────────────────────────


def resolve_anchors(
    spec: dict[str, dict[str, Any]],
    scenarios: list[dict[str, Any]] | None,
) -> dict[str, dict[str, float]]:
    """Resolve every anchor in *spec* to a coords dict.

    Each returned entry contains: ``x, y, w, h, cx, cy, left, top, right,
    bottom``. Anchors with manual ``x/y`` are returned as-is; anchors with
    ``selector`` are probed using Playwright.

    Failed probes log a warning and fall back to viewport-center coordinates
    so the demo can still render.
    """
    out: dict[str, dict[str, float]] = {}

    # Group selector-based anchors by scenario for batched probing.
    by_scenario: dict[int, list[tuple[str, dict[str, Any]]]] = {}
    for name, anchor in spec.items():
        if not isinstance(anchor, dict):
            raise AnchorResolveError(f"Anchor {name!r} must be a mapping")
        if "selector" in anchor:
            idx = int(anchor.get("scenario", 0))
            by_scenario.setdefault(idx, []).append((name, anchor))
        else:
            out[name] = _coords_from_manual(name, anchor)

    if by_scenario:
        if not scenarios:
            logger.warning(
                "anchors: selector-based anchors found but no scenarios defined; "
                "falling back to viewport center for all"
            )
            for batch in by_scenario.values():
                for name, _ in batch:
                    out[name] = _fallback_center()
        else:
            for idx, batch in by_scenario.items():
                if idx < 0 or idx >= len(scenarios):
                    logger.warning(
                        "anchors: scenario index %d out of range (have %d scenarios); "
                        "using fallback for %s",
                        idx,
                        len(scenarios),
                        [n for n, _ in batch],
                    )
                    for name, _ in batch:
                        out[name] = _fallback_center()
                    continue
                probed = _probe_scenario_anchors(scenarios[idx], batch)
                out.update(probed)

    return out


def _coords_from_manual(name: str, anchor: dict[str, Any]) -> dict[str, float]:
    """Build a coords dict from manual ``x, y, [w, h]`` keys."""
    try:
        x = float(anchor["x"])
        y = float(anchor["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AnchorResolveError(
            f"Anchor {name!r}: manual anchors require numeric 'x' and 'y'"
        ) from exc
    w = float(anchor.get("w", 0))
    h = float(anchor.get("h", 0))
    return _build_coords(x, y, w, h)


def _build_coords(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "cx": x + w / 2,
        "cy": y + h / 2,
        "left": x,
        "top": y,
        "right": x + w,
        "bottom": y + h,
    }


def _fallback_center() -> dict[str, float]:
    return _build_coords(
        (DEFAULT_VIEWPORT_W - 200) / 2,
        (DEFAULT_VIEWPORT_H - 60) / 2,
        200,
        60,
    )


def _probe_scenario_anchors(
    scenario: dict[str, Any],
    batch: list[tuple[str, dict[str, Any]]],
) -> dict[str, dict[str, float]]:
    """Launch a headless Playwright page once and capture every anchor's box."""
    url = scenario.get("url")
    if not url:
        logger.warning(
            "anchors: scenario has no URL; using fallback for %s",
            [n for n, _ in batch],
        )
        return {n: _fallback_center() for n, _ in batch}

    vp = scenario.get("viewport") or {}
    width = int(vp.get("width", DEFAULT_VIEWPORT_W))
    height = int(vp.get("height", DEFAULT_VIEWPORT_H))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("anchors: playwright not installed; using fallback")
        return {n: _fallback_center() for n, _ in batch}

    out: dict[str, dict[str, float]] = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(viewport={"width": width, "height": height})
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=PROBE_TIMEOUT_MS)
                # Allow the network/app to settle a bit (SPA hydration etc.)
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:  # noqa: BLE001
                    pass

                for name, anchor in batch:
                    sel = anchor["selector"]
                    try:
                        loc = page.locator(sel).first
                        box = loc.bounding_box(timeout=PROBE_TIMEOUT_MS)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "anchors: selector %r (%s) failed: %s — using fallback",
                            name,
                            sel,
                            exc,
                        )
                        out[name] = _fallback_center()
                        continue
                    if not box:
                        logger.warning(
                            "anchors: selector %r (%s) not found — using fallback",
                            name,
                            sel,
                        )
                        out[name] = _fallback_center()
                        continue
                    out[name] = _build_coords(
                        float(box["x"]),
                        float(box["y"]),
                        float(box["width"]),
                        float(box["height"]),
                    )
                    logger.info(
                        "anchors: %s → x=%.0f y=%.0f w=%.0f h=%.0f",
                        name,
                        out[name]["x"],
                        out[name]["y"],
                        out[name]["w"],
                        out[name]["h"],
                    )
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("anchors: probe failed (%s) — using fallback for all", exc)
        return {n: _fallback_center() for n, _ in batch}

    return out


# ── Template application ─────────────────────────────────────────────────────


def apply_anchor_templates(
    config: dict[str, Any],
    anchors: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Walk *config* and evaluate any ``{{ anchors.* }}`` template strings.

    Reuses the same safe-eval engine as the library resolver but only
    activates on strings whose templates reference ``anchors.``. Other
    ``{{ }}`` strings (e.g. unresolved library params) are left untouched.
    """
    # Convert anchors → SimpleNamespace for dotted access in expressions.
    ns = SimpleNamespace(**{name: SimpleNamespace(**coords) for name, coords in anchors.items()})

    return _walk(config, {"anchors": ns})


def _walk(obj: Any, env: dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return _eval_if_anchor(obj, env)
    if isinstance(obj, dict):
        return {k: _walk(v, env) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(item, env) for item in obj]
    return obj


def _eval_if_anchor(s: str, env: dict[str, Any]) -> Any:
    """Evaluate ``{{ anchors.* }}`` templates inside *s*.

    Templates not referencing ``anchors.`` are left as-is (the library
    resolver may handle them or they're just plain text).
    """
    if "anchors." not in s:
        return s
    # Whole-string template → return native value
    m = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", s)
    if m and _ANCHOR_NAMESPACE_RE.search(m.group(1)):
        return _safe_eval(m.group(1), env)

    # Multi-segment: replace each anchor-referencing template inline
    def _replace(match: re.Match[str]) -> str:
        expr = match.group(1)
        if not _ANCHOR_NAMESPACE_RE.search(expr):
            return match.group(0)  # leave untouched
        return str(_safe_eval(expr, env))

    return _ANCHOR_TEMPLATE_RE.sub(_replace, s)


def _safe_eval(expr: str, env: dict[str, Any]) -> Any:
    """Evaluate a template expression with only *env* names + safe builtins."""
    import builtins as _builtins_mod

    safe_names = ("True", "False", "None", "int", "float", "str", "abs", "min", "max", "round")
    allowed = {n: getattr(_builtins_mod, n) for n in safe_names if hasattr(_builtins_mod, n)}
    ns: dict[str, Any] = {"__builtins__": allowed}
    ns.update(env)
    try:
        return eval(expr, ns)  # noqa: S307
    except Exception as exc:
        raise AnchorResolveError(f"Anchor template expression error: {expr!r} — {exc}") from exc
