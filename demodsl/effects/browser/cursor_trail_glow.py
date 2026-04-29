"""Cursor trail glow — radial gradient halos following the cursor."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, on_mousemove, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class CursorTrailGlowEffect(BrowserEffect):
    effect_id = "cursor_trail_glow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#00BFFF"))
        size = int(sanitize_number(params.get("size", 36), default=36, min_val=10, max_val=100))
        glow_inner = int(
            sanitize_number(params.get("glow_inner", 24), default=24, min_val=0, max_val=60)
        )
        glow_outer = int(
            sanitize_number(params.get("glow_outer", 48), default=48, min_val=0, max_val=100)
        )
        fade_duration = sanitize_number(
            params.get("fade_duration", 1.5), default=1.5, min_val=0.3, max_val=5.0
        )
        lifetime = int(
            sanitize_number(params.get("lifetime", 2000), default=2000, min_val=500, max_val=5000)
        )
        scale_end = sanitize_number(
            params.get("scale_end", 2.5), default=2.5, min_val=1.0, max_val=5.0
        )

        body = (
            "const dot = document.createElement('div');\n"
            "dot.className = '__demodsl_trail_glow';\n"
            "dot.style.cssText = `\n"
            f"    position:fixed; left:${{e.clientX}}px; top:${{e.clientY}}px;\n"
            f"    width:{size}px; height:{size}px; border-radius:50%;\n"
            f"    background:radial-gradient(circle, {color}cc, {color}44, transparent);\n"
            f"    box-shadow: 0 0 {glow_inner}px {color}aa, 0 0 {glow_outer}px {color}55;\n"
            f"    pointer-events:none; z-index:99999; transition: all {fade_duration}s ease;\n"
            "    transform:translate(-50%,-50%);\n"
            "`;\n"
            "document.body.appendChild(dot);\n"
            f"setTimeout(() => {{ dot.style.opacity='0'; dot.style.transform='translate(-50%,-50%) scale({scale_end})'; }}, 600);\n"
            f"setTimeout(() => dot.remove(), {lifetime});\n"
        )
        evaluate_js(iife(on_mousemove(body)))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
