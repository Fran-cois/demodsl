"""Callout arrow effect — animated SVG arrow pointing at a target."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import auto_remove_multi, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_js_string,
    sanitize_number,
)


class CalloutArrowEffect(BrowserEffect):
    effect_id = "callout_arrow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        text = sanitize_js_string(params.get("text", "Look here!"))
        color = sanitize_css_color(params.get("color", "#ef4444"))
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        js = (
            "const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');\n"
            "svg.id = '__demodsl_callout_arrow';\n"
            "svg.setAttribute('style','position:fixed;top:0;left:0;width:100%;height:100%;"
            "z-index:99999;pointer-events:none;');\n"
            "svg.innerHTML = `\n"
            "    <defs>\n"
            '        <marker id="dsl-arrowhead" markerWidth="10" markerHeight="7"\n'
            '            refX="10" refY="3.5" orient="auto">\n'
            f'            <polygon points="0 0, 10 3.5, 0 7" fill="{color}"/>\n'
            "        </marker>\n"
            "    </defs>\n"
            "`;\n"
            "document.body.appendChild(svg);\n"
            f"const tx = window.innerWidth * {target_x};\n"
            f"const ty = window.innerHeight * {target_y};\n"
            "const sx = tx + (tx > window.innerWidth / 2 ? 120 : -120);\n"
            "const sy = ty - 80;\n"
            "const line = document.createElementNS('http://www.w3.org/2000/svg','line');\n"
            "line.setAttribute('x1', sx); line.setAttribute('y1', sy);\n"
            "line.setAttribute('x2', tx); line.setAttribute('y2', ty);\n"
            f"line.setAttribute('stroke', '{color}');\n"
            "line.setAttribute('stroke-width', '4');\n"
            "line.setAttribute('marker-end', 'url(#dsl-arrowhead)');\n"
            "line.setAttribute('stroke-dasharray', '200');\n"
            "line.setAttribute('stroke-dashoffset', '200');\n"
            "line.style.transition = 'stroke-dashoffset 0.6s ease';\n"
            "svg.appendChild(line);\n"
            "const label = document.createElement('div');\n"
            "label.id = '__demodsl_callout_label';\n"
            f"label.textContent = `{text}`;\n"
            "label.style.cssText = `\n"
            f"    position:fixed; left:${{sx - 60}}px; top:${{sy - 36}}px;\n"
            f"    background:{color}; color:#fff; padding:6px 14px;\n"
            f"    border-radius:6px; font-size:14px; font-weight:600;\n"
            f"    z-index:99999; pointer-events:none; opacity:0;\n"
            f"    transition: opacity 0.3s ease;\n"
            f"    box-shadow: 0 4px 12px rgba(0,0,0,0.2);\n"
            "`;\n"
            "document.body.appendChild(label);\n"
            "requestAnimationFrame(() => {\n"
            "    line.setAttribute('stroke-dashoffset', '0');\n"
            "    label.style.opacity = '1';\n"
            "});\n" + auto_remove_multi([("svg", 4000), ("label", 4000)])
        )
        evaluate_js(iife(js))
