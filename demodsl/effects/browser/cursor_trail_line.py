"""Cursor trail line — SVG polyline following cursor movement."""

from __future__ import annotations

import re
from typing import Any

from demodsl.effects.js_builder import iife, on_mousemove, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number

_RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def _extract_rgb(color: str) -> str:
    """Extract 'R,G,B' from an rgba/rgb CSS colour string."""
    m = _RGBA_RE.match(color)
    if m:
        return f"{m.group(1)},{m.group(2)},{m.group(3)}"
    return "80,180,255"


class CursorTrailLineEffect(BrowserEffect):
    effect_id = "cursor_trail_line"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "rgba(80,180,255,1)"))
        max_points = int(
            sanitize_number(
                params.get("max_points", 60), default=60, min_val=10, max_val=200
            )
        )
        min_width = sanitize_number(
            params.get("min_width", 2), default=2, min_val=0.5, max_val=10
        )
        max_width = sanitize_number(
            params.get("max_width", 7), default=7, min_val=1, max_val=20
        )

        width_range = max_width - min_width
        color_rgb = _extract_rgb(color)

        body = (
            "points.push({x:e.clientX,y:e.clientY});\n"
            f"if (points.length > {max_points}) points.shift();\n"
            "while (svg.firstChild) svg.removeChild(svg.firstChild);\n"
            "if (points.length < 2) return;\n"
            "for (let i = 1; i < points.length; i++) {\n"
            "    const line = document.createElementNS('http://www.w3.org/2000/svg','line');\n"
            "    const alpha = i / points.length;\n"
            "    line.setAttribute('x1', points[i-1].x);\n"
            "    line.setAttribute('y1', points[i-1].y);\n"
            "    line.setAttribute('x2', points[i].x);\n"
            "    line.setAttribute('y2', points[i].y);\n"
            f"    line.setAttribute('stroke', `rgba({color_rgb},${{alpha}})`);\n"
            f"    line.setAttribute('stroke-width', `${{{min_width} + alpha * {width_range}}}`);\n"
            "    line.setAttribute('stroke-linecap', 'round');\n"
            "    svg.appendChild(line);\n"
            "}\n"
        )
        setup = (
            "const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');\n"
            "svg.id = '__demodsl_trail_line';\n"
            "svg.setAttribute('style','position:fixed;top:0;left:0;width:100%;height:100%;"
            "z-index:99999;pointer-events:none;');\n"
            "document.body.appendChild(svg);\n"
            "const points = [];\n" + on_mousemove(body)
        )
        evaluate_js(iife(setup))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
