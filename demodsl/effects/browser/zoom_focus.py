"""Zoom focus (punch-in) — dynamic zoom into a specific area with smooth easing."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class ZoomFocusEffect(BrowserEffect):
    effect_id = "zoom_focus"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        scale = sanitize_number(
            params.get("scale", 1.8), default=1.8, min_val=1.1, max_val=5.0
        )
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.4), default=0.4, min_val=0.0, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 2.0), default=2.0, min_val=0.5, max_val=10.0
        )

        zoom_in_ms = 500
        zoom_out_ms = 500
        hold_ms = max(100, int(duration * 1000) - zoom_in_ms - zoom_out_ms)
        origin_x = int(target_x * 100)
        origin_y = int(target_y * 100)

        js = (
            "history.scrollRestoration = 'manual';\n"
            "const el = document.body;\n"
            f"el.style.transformOrigin = '{origin_x}% {origin_y}%';\n"
            f"el.style.transition = 'transform {zoom_in_ms}ms cubic-bezier(0.25,0.46,0.45,0.94),"
            f" filter {zoom_in_ms}ms ease';\n"
            "requestAnimationFrame(() => {\n"
            f"    el.style.transform = 'scale({scale})';\n"
            "    el.style.filter = 'blur(1.5px)';\n"
            "    setTimeout(() => { el.style.filter = ''; }, 250);\n"
            "});\n"
            f"setTimeout(() => {{\n"
            f"    el.style.transition = 'transform {zoom_out_ms}ms cubic-bezier(0.25,0.46,0.45,0.94),"
            f" filter {zoom_out_ms}ms ease';\n"
            "    el.style.filter = 'blur(1px)';\n"
            "    el.style.transform = '';\n"
            "    setTimeout(() => {\n"
            "        el.style.filter = '';\n"
            "        el.style.transformOrigin = '';\n"
            "        el.style.transition = '';\n"
            f"    }}, {zoom_out_ms});\n"
            f"}}, {zoom_in_ms + hold_ms});\n"
        )
        evaluate_js(iife(js))
