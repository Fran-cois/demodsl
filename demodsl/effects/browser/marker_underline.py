"""Marker underline — hand-drawn highlighter sweep under the target element.

The editor's gesture: a felt-tip underline swiped beneath a headline, with a
seeded organic waver, a shorter second pass, ease-out draw-on and a soft
highlighter transparency (multiply blend so text stays crisp above it).
"""

from __future__ import annotations

import math
from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class MarkerUnderlineEffect(BrowserEffect):
    effect_id = "marker_underline"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.55), default=0.55, min_val=0.0, max_val=1.0
        )
        color = sanitize_css_color(params.get("color", "#6366F1"))
        # radius carries the HALF-WIDTH of the swipe (anchored from the bbox).
        half_w = int(
            sanitize_number(params.get("radius", 140), default=140, min_val=30, max_val=700)
        )
        angle_deg = sanitize_number(
            params.get("angle", -0.8), default=-0.8, min_val=-10.0, max_val=10.0
        )
        rot = round(math.radians(angle_deg), 5)
        duration = sanitize_number(
            params.get("duration", 2.5), default=2.5, min_val=0.5, max_val=30.0
        )

        lifetime = int(duration * 1000)
        draw_ms = min(700, int(duration * 400))
        fade_ms = 280 if lifetime > 800 else 0

        js = (
            "const NS = 'http://www.w3.org/2000/svg';\n"
            "const svg = document.createElementNS(NS, 'svg');\n"
            "svg.id = '__demodsl_marker_underline';\n"
            # absolute + page coords: rides scroll and the virtual camera.
            "svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;"
            "height:100%;z-index:99998;pointer-events:none;overflow:visible;"
            "mix-blend-mode:multiply;';\n"
            f"const cx = window.innerWidth * {target_x} + window.scrollX;\n"
            f"const cy = window.innerHeight * {target_y} + window.scrollY;\n"
            f"const hw = {half_w}, rot = {rot};\n"
            "let sd = (Math.floor(cx * 5 + cy * 11) + 41) >>> 0;\n"
            "const rnd = () => ((sd = (sd * 1664525 + 1013904223) >>> 0) / 4294967296);\n"
            "const ph1 = rnd() * 6.283, ph2 = rnd() * 6.283;\n"
            "const cosR = Math.cos(rot), sinR = Math.sin(rot);\n"
            "function stroke(y0, x0, x1, amp) {\n"
            "    let d = '';\n"
            "    for (let i = 0; i <= 48; i++) {\n"
            "        const u = i / 48;\n"
            "        const ex = x0 + (x1 - x0) * u;\n"
            "        const ey = y0 + amp * Math.sin(u * 4.2 + ph1)"
            " + amp * 0.6 * Math.sin(u * 9.1 + ph2);\n"
            "        const x = cx + ex * cosR - ey * sinR;\n"
            "        const y = cy + ex * sinR + ey * cosR;\n"
            "        d += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);\n"
            "    }\n"
            "    const p = document.createElementNS(NS, 'path');\n"
            "    p.setAttribute('d', d);\n"
            "    p.setAttribute('fill', 'none');\n"
            f"    p.setAttribute('stroke', '{color}');\n"
            "    p.setAttribute('stroke-linecap', 'round');\n"
            "    svg.appendChild(p);\n"
            "    return p;\n"
            "}\n"
            # Main sweep slightly overshoots left/right; second pass shorter,
            # lower and offset — the classic double-underline of an editor.
            "const main = stroke(0, -hw - 8, hw + 12, 2.2);\n"
            "main.setAttribute('stroke-width', '9');\n"
            "main.setAttribute('opacity', '0.55');\n"
            "const second = stroke(9, -hw * 0.72, hw * 0.55, 1.6);\n"
            "second.setAttribute('stroke-width', '7');\n"
            "second.setAttribute('opacity', '0.4');\n"
            "document.body.appendChild(svg);\n"
            "const L1 = main.getTotalLength(), L2 = second.getTotalLength();\n"
            "main.style.strokeDasharray = L1; main.style.strokeDashoffset = L1;\n"
            "second.style.strokeDasharray = L2; second.style.strokeDashoffset = L2;\n"
            "let t0 = null;\n"
            f"const drawDur = {draw_ms};\n"
            "function draw(ts) {\n"
            "    if (!t0) t0 = ts;\n"
            "    const prog = Math.min((ts - t0) / drawDur, 1);\n"
            "    const ease = 1 - Math.pow(1 - prog, 3);\n"
            "    main.style.strokeDashoffset = L1 * (1 - ease);\n"
            # Second pass starts once the first is ~70% down.
            "    const p2 = Math.max(0, (prog - 0.55) / 0.45);\n"
            "    second.style.strokeDashoffset = L2 * (1 - (1 - Math.pow(1 - p2, 3)));\n"
            "    if (prog < 1) requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
            + (
                f"setTimeout(() => {{ svg.style.transition = 'opacity .28s ease';"
                f" svg.style.opacity = '0'; }}, {lifetime - fade_ms});\n"
                if fade_ms
                else ""
            )
            + f"setTimeout(() => svg.remove(), {lifetime});\n"
        )
        evaluate_js(iife(js))
