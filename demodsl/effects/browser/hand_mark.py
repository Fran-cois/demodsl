"""Hand mark — a hand-drawn ✓ or ✗ the reviewer drops next to an element.

Same felt-tip family as ``animated_annotation``: two wobbly marker strokes
(seeded, deterministic), ink-bleed under-stroke + soft shadow, an ease-out
draw-on with a little scale pop when the stroke lands, then a clean fade.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number

_GREEN = "#22C55E"
_RED = "#EF4444"


class HandMarkEffect(BrowserEffect):
    effect_id = "hand_mark"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        style = str(params.get("style") or "check").lower()
        if style not in ("check", "cross"):
            style = "check"
        color = sanitize_css_color(params.get("color") or (_GREEN if style == "check" else _RED))
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        r = int(sanitize_number(params.get("radius", 17), default=17, min_val=8, max_val=60))
        duration = sanitize_number(
            params.get("duration", 2.5), default=2.5, min_val=0.5, max_val=30.0
        )
        lifetime = int(duration * 1000)
        fade_ms = 260 if lifetime > 800 else 0

        if style == "check":
            # Two segments: short down-right, long up-right (with overshoot).
            strokes_js = (
                "const pts = [\n"
                "  [[-0.9, 0.05], [-0.25, 0.75]],\n"
                "  [[-0.25, 0.75], [1.0, -0.85]],\n"
                "];\n"
            )
        else:
            strokes_js = (
                "const pts = [\n"
                "  [[-0.85, -0.85], [0.9, 0.9]],\n"
                "  [[0.85, -0.9], [-0.9, 0.85]],\n"
                "];\n"
            )

        js = (
            "const NS = 'http://www.w3.org/2000/svg';\n"
            "const svg = document.createElementNS(NS, 'svg');\n"
            "svg.id = '__demodsl_hand_mark';\n"
            # absolute + page coords: rides scroll and the virtual camera.
            "svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;overflow:visible;';\n"
            f"const cx = window.innerWidth * {target_x} + window.scrollX;\n"
            f"const cy = window.innerHeight * {target_y} + window.scrollY;\n"
            f"const r = {r};\n"
            "let sd = (Math.floor(cx * 3 + cy * 7) + 23) >>> 0;\n"
            "const rnd = () => ((sd = (sd * 1664525 + 1013904223) >>> 0) / 4294967296);\n"
            "const ph = rnd() * 6.283;\n"
            + strokes_js
            + "const defs = document.createElementNS(NS, 'defs');\n"
            "defs.innerHTML = `<filter id='__dslMarkShadow' x='-40%' y='-40%'"
            " width='180%' height='180%'>"
            "<feDropShadow dx='0' dy='1.2' stdDeviation='1.3' flood-opacity='0.35'/>"
            "</filter>`;\n"
            "svg.appendChild(defs);\n"
            "const g = document.createElementNS(NS, 'g');\n"
            "g.setAttribute('filter', 'url(#__dslMarkShadow)');\n"
            "svg.appendChild(g);\n"
            # One path PER stroke: the reviewer draws them one after the other
            # with a visible pen lift in between — not both at once.
            "const paths = [];\n"
            "for (const seg of pts) {\n"
            "    let d = '';\n"
            "    for (let i = 0; i <= 12; i++) {\n"
            "        const u = i / 12;\n"
            "        const x = cx + (seg[0][0] + (seg[1][0] - seg[0][0]) * u) * r"
            " + 0.7 * Math.sin(u * 6 + ph);\n"
            "        const y = cy + (seg[0][1] + (seg[1][1] - seg[0][1]) * u) * r"
            " + 0.7 * Math.sin(u * 5 + ph * 1.3);\n"
            "        d += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);\n"
            "    }\n"
            "    const bleed = document.createElementNS(NS, 'path');\n"
            "    bleed.setAttribute('d', d);\n"
            "    bleed.setAttribute('fill', 'none');\n"
            f"    bleed.setAttribute('stroke', '{color}');\n"
            "    bleed.setAttribute('stroke-width', '8');\n"
            "    bleed.setAttribute('stroke-linecap', 'round');\n"
            "    bleed.setAttribute('opacity', '0.16');\n"
            "    g.appendChild(bleed);\n"
            "    const main = document.createElementNS(NS, 'path');\n"
            "    main.setAttribute('d', d);\n"
            "    main.setAttribute('fill', 'none');\n"
            f"    main.setAttribute('stroke', '{color}');\n"
            "    main.setAttribute('stroke-width', '4.5');\n"
            "    main.setAttribute('stroke-linecap', 'round');\n"
            "    main.setAttribute('stroke-linejoin', 'round');\n"
            "    g.appendChild(main);\n"
            "    paths.push([bleed, main]);\n"
            "}\n"
            "document.body.appendChild(svg);\n"
            "const lens = paths.map(([, m]) => m.getTotalLength());\n"
            "paths.forEach(([b, m], k) => {\n"
            "    b.style.strokeDasharray = lens[k]; b.style.strokeDashoffset = lens[k];\n"
            "    m.style.strokeDasharray = lens[k]; m.style.strokeDashoffset = lens[k];\n"
            "});\n"
            "g.style.transformOrigin = cx + 'px ' + cy + 'px';\n"
            # Timeline: stroke 1 (380ms, ease-out) → pen lift (120ms) →
            # stroke 2 (300ms) → landing pop.
            "const T1 = 380, LIFT = 120, T2 = 300;\n"
            "let t0 = null;\n"
            "function draw(ts) {\n"
            "    if (!t0) t0 = ts;\n"
            "    const el = ts - t0;\n"
            "    const p1 = Math.min(1, el / T1);\n"
            "    const e1 = 1 - Math.pow(1 - p1, 3);\n"
            "    paths[0][0].style.strokeDashoffset = lens[0] * (1 - e1);\n"
            "    paths[0][1].style.strokeDashoffset = lens[0] * (1 - e1);\n"
            "    if (paths.length > 1) {\n"
            "        const p2 = Math.min(1, Math.max(0, (el - T1 - LIFT) / T2));\n"
            "        const e2 = 1 - Math.pow(1 - p2, 3);\n"
            "        paths[1][0].style.strokeDashoffset = lens[1] * (1 - e2);\n"
            "        paths[1][1].style.strokeDashoffset = lens[1] * (1 - e2);\n"
            "    }\n"
            "    const total = T1 + LIFT + T2;\n"
            "    const pt = Math.min(1, el / total);\n"
            "    const pop = pt > 0.88 ? 1 + 0.12 * Math.sin((pt - 0.88) / 0.12 * 3.1416) : 1;\n"
            "    g.style.transform = 'scale(' + pop.toFixed(3) + ')';\n"
            "    if (el < total) requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
            + (
                f"setTimeout(() => {{ svg.style.transition = 'opacity .26s ease';"
                f" svg.style.opacity = '0'; }}, {lifetime - fade_ms});\n"
                if fade_ms
                else ""
            )
            + f"setTimeout(() => svg.remove(), {lifetime});\n"
        )
        evaluate_js(iife(js))
