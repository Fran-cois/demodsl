"""Cursor trail rainbow — HSL colour-cycling dots."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, on_mousemove, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class CursorTrailRainbowEffect(BrowserEffect):
    effect_id = "cursor_trail_rainbow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        size = sanitize_number(
            params.get("size", 18), default=18, min_val=6, max_val=50
        )
        hue_step = sanitize_number(
            params.get("hue_step", 12), default=12, min_val=1, max_val=60
        )
        glow = sanitize_number(
            params.get("glow", 12), default=12, min_val=0, max_val=40
        )
        fade_duration = sanitize_number(
            params.get("fade_duration", 1.4), default=1.4, min_val=0.3, max_val=5.0
        )
        lifetime = int(
            sanitize_number(
                params.get("lifetime", 2200), default=2200, min_val=500, max_val=5000
            )
        )

        offset = int(size) // 2
        body = (
            f"hue = (hue + {hue_step}) % 360;\n"
            "const dot = document.createElement('div');\n"
            "dot.className = '__demodsl_trail_rainbow';\n"
            "dot.style.cssText = `\n"
            f"    position:fixed; left:${{e.clientX - {offset}}}px; top:${{e.clientY - {offset}}}px;\n"
            f"    width:{int(size)}px; height:{int(size)}px; border-radius:50%;\n"
            "    background:hsl(${hue},100%,60%); pointer-events:none;\n"
            f"    box-shadow: 0 0 {glow}px hsl(${{hue}},100%,50%);\n"
            f"    z-index:99999; transition: all {fade_duration}s ease;\n"
            "`;\n"
            "document.body.appendChild(dot);\n"
            "setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0.2)'; }, 800);\n"
            f"setTimeout(() => dot.remove(), {lifetime});\n"
        )
        evaluate_js(iife("let hue = 0;\n" + on_mousemove(body)))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
