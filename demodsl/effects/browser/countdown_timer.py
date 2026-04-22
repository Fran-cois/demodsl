"""Countdown timer effect — animated countdown overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_css_position,
    sanitize_number,
)


class CountdownTimerEffect(BrowserEffect):
    effect_id = "countdown_timer"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 10), default=10, min_val=1, max_val=3600
        )
        color = sanitize_css_color(params.get("color", "#FFFFFF"))
        position = sanitize_css_position(
            params.get("position", "top-right"),
            allowed=frozenset({"top-right", "top-left", "bottom-right", "bottom-left"}),
        )
        pos_map = {
            "top-right": "top:20px;right:20px",
            "top-left": "top:20px;left:20px",
            "bottom-right": "bottom:20px;right:20px",
            "bottom-left": "bottom:20px;left:20px",
        }
        pos_css = pos_map.get(position, pos_map["top-right"])
        js = (
            "const timer = document.createElement('div');\n"
            "timer.id = '__demodsl_countdown';\n"
            f"timer.style.cssText = `\n"
            f"    position:fixed; {pos_css};\n"
            f"    font-size:42px; font-weight:bold; font-family:monospace;\n"
            f"    color:{color}; z-index:99999; pointer-events:none;\n"
            f"    background:rgba(0,0,0,0.7); padding:10px 20px;\n"
            f"    border-radius:8px; min-width:70px; text-align:center;\n"
            f"`;\n"
            "document.body.appendChild(timer);\n"
            f"let remaining = {duration};\n"
            "function tick() {\n"
            "    const m = Math.floor(remaining / 60);\n"
            "    const s = Math.floor(remaining % 60);\n"
            "    timer.textContent = (m > 0 ? m + ':' : '') + String(s).padStart(2, '0');\n"
            "    if (remaining <= 0) { timer.remove(); return; }\n"
            "    remaining -= 1;\n"
            "    setTimeout(tick, 1000);\n"
            "}\n"
            "tick();\n"
        )
        evaluate_js(iife(js))
