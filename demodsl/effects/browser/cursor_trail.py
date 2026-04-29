"""Cursor trail effect — fading blue dots following the cursor."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, on_mousemove, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class CursorTrailEffect(BrowserEffect):
    effect_id = "cursor_trail"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "rgba(80,130,255,1.0)"))
        size = sanitize_number(params.get("size", 30), default=30, min_val=4, max_val=60)
        glow = sanitize_number(params.get("glow", 20), default=20, min_val=0, max_val=40)
        fade_duration = sanitize_number(
            params.get("fade_duration", 1.5), default=1.5, min_val=0.2, max_val=5.0
        )
        max_dots = sanitize_number(params.get("max_dots", 80), default=80, min_val=10, max_val=200)

        offset = size // 2
        body = (
            "const dot = document.createElement('div');\n"
            "dot.style.cssText = `\n"
            f"    position:fixed; left:${{e.clientX - {offset}}}px; top:${{e.clientY - {offset}}}px;\n"
            f"    width:{size}px; height:{size}px; border-radius:50%;\n"
            f"    background:{color}; pointer-events:none;\n"
            f"    box-shadow: 0 0 {glow}px {color};\n"
            f"    z-index:99999; transition: all {fade_duration}s ease;\n"
            "`;\n"
            "document.body.appendChild(dot);\n"
            "trail.push(dot);\n"
            "setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0.3)'; }, 600);\n"
            "setTimeout(() => dot.remove(), 1800);\n"
            f"if (trail.length > {int(max_dots)}) trail.shift()?.remove();\n"
        )
        evaluate_js(iife("const trail = [];\n" + on_mousemove(body)))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
