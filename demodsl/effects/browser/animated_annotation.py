"""Animated annotation — self-drawing SVG circle with pulse effect."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class AnimatedAnnotationEffect(BrowserEffect):
    effect_id = "animated_annotation"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        color = sanitize_css_color(params.get("color", "#ef4444"))
        r = int(
            sanitize_number(
                params.get("radius", 60), default=60, min_val=20, max_val=200
            )
        )
        duration = sanitize_number(
            params.get("duration", 2.5), default=2.5, min_val=0.5, max_val=10.0
        )
        text_raw = params.get("text") or ""

        circ = int(2 * 3.14159 * r)
        lifetime = int(duration * 1000)
        draw_ms = int(duration * 600)

        # Optional label (JS-safe escaping)
        label_js = ""
        if text_raw:
            safe = (
                str(text_raw)
                .replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\n", "\\n")
            )
            label_js = (
                "const label = document.createElement('div');\n"
                "label.style.cssText = `\n"
                "    position:fixed; pointer-events:none; z-index:99999;\n"
                f"    color:{color}; font-size:14px; font-weight:600;\n"
                "    font-family:-apple-system,system-ui,sans-serif;\n"
                "    white-space:nowrap; text-shadow:0 1px 4px rgba(0,0,0,0.5);\n"
                "    transform:translateX(-50%); opacity:0;\n"
                "    transition:opacity 0.4s ease 0.6s;\n"
                "`;\n"
                f"label.textContent = '{safe}';\n"
                "label.style.left = cx + 'px';\n"
                f"label.style.top = (cy + {r} + 16) + 'px';\n"
                "document.body.appendChild(label);\n"
                "requestAnimationFrame(() => { label.style.opacity = '1'; });\n"
                f"setTimeout(() => label.remove(), {lifetime});\n"
            )

        js = (
            "const NS = 'http://www.w3.org/2000/svg';\n"
            "const svg = document.createElementNS(NS, 'svg');\n"
            "svg.id = '__demodsl_annotation';\n"
            "svg.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;overflow:visible;';\n"
            f"const cx = window.innerWidth * {target_x};\n"
            f"const cy = window.innerHeight * {target_y};\n"
            # Main circle
            "const c = document.createElementNS(NS, 'circle');\n"
            "c.setAttribute('cx', cx);\n"
            "c.setAttribute('cy', cy);\n"
            f"c.setAttribute('r', {r});\n"
            "c.setAttribute('fill', 'none');\n"
            f"c.setAttribute('stroke', '{color}');\n"
            "c.setAttribute('stroke-width', '3');\n"
            "c.setAttribute('stroke-linecap', 'round');\n"
            f"c.setAttribute('stroke-dasharray', '{circ}');\n"
            f"c.setAttribute('stroke-dashoffset', '{circ}');\n"
            "svg.appendChild(c);\n"
            # Pulse ring
            "const p = document.createElementNS(NS, 'circle');\n"
            "p.setAttribute('cx', cx);\n"
            "p.setAttribute('cy', cy);\n"
            f"p.setAttribute('r', {r});\n"
            "p.setAttribute('fill', 'none');\n"
            f"p.setAttribute('stroke', '{color}');\n"
            "p.setAttribute('stroke-width', '1.5');\n"
            "p.setAttribute('opacity', '0');\n"
            "svg.appendChild(p);\n"
            "document.body.appendChild(svg);\n"
            # Animate drawing with easeInOutQuad
            "let t0 = null;\n"
            f"const drawDur = {draw_ms};\n"
            "function draw(ts) {\n"
            "    if (!t0) t0 = ts;\n"
            "    const prog = Math.min((ts - t0) / drawDur, 1);\n"
            "    const ease = prog < 0.5 ? 2*prog*prog : 1 - Math.pow(-2*prog+2,2)/2;\n"
            f"    c.setAttribute('stroke-dashoffset', {circ} * (1 - ease));\n"
            "    if (prog >= 0.7) {\n"
            "        const pp = (prog - 0.7) / 0.3;\n"
            f"        p.setAttribute('r', {r} + pp * 15);\n"
            "        p.setAttribute('opacity', String(0.6 * (1 - pp)));\n"
            "    }\n"
            "    if (prog < 1) requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
            + label_js
            + f"setTimeout(() => svg.remove(), {lifetime});\n"
        )
        evaluate_js(iife(js))
