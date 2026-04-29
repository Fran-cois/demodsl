"""Cursor trail comet — multi-layer tail following the cursor."""

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
    return "255,200,50"


class CursorTrailCometEffect(BrowserEffect):
    effect_id = "cursor_trail_comet"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "rgba(255,200,50,1)"))
        glow_color = sanitize_css_color(params.get("glow_color", "rgba(255,180,0,1)"))
        layers = int(sanitize_number(params.get("layers", 4), default=4, min_val=2, max_val=8))
        head_size = sanitize_number(params.get("size", 28), default=28, min_val=8, max_val=50)
        size_step = sanitize_number(params.get("size_step", 3), default=3, min_val=1, max_val=10)
        fade_base = sanitize_number(
            params.get("fade_duration", 0.8), default=0.8, min_val=0.3, max_val=3.0
        )

        # Extract rgb values from rgba for dynamic alpha in JS template
        color_rgb = _extract_rgb(color)
        glow_rgb = _extract_rgb(glow_color)

        body = (
            f"for (let i = 0; i < {layers}; i++) {{\n"
            "    const dot = document.createElement('div');\n"
            "    dot.className = '__demodsl_trail_comet';\n"
            f"    const size = {head_size} - i * {size_step};\n"
            "    const alpha = 1.0 - i * 0.15;\n"
            "    dot.style.cssText = `\n"
            "        position:fixed; left:${e.clientX - size/2}px; top:${e.clientY - size/2 + i*3}px;\n"
            "        width:${size}px; height:${size}px; border-radius:50%;\n"
            f"        background:rgba({color_rgb},${{alpha}});\n"
            f"        box-shadow: 0 0 ${{12-i*2}}px rgba({glow_rgb},${{alpha*0.7}});\n"
            "        pointer-events:none; z-index:99999;\n"
            f"        transition: all ${{{fade_base} + i*0.3}}s ease-out;\n"
            "    `;\n"
            "    document.body.appendChild(dot);\n"
            "    setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0.1) translateY(20px)'; }, 500 + i*100);\n"
            "    setTimeout(() => dot.remove(), 1600 + i*300);\n"
            "}\n"
        )
        evaluate_js(iife(on_mousemove(body)))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
