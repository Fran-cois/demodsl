"""Perspective tilt — 3D isometric view of the page with depth shadow."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class PerspectiveTiltEffect(BrowserEffect):
    effect_id = "perspective_tilt"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        angle = sanitize_number(
            params.get("angle", 12), default=12, min_val=2, max_val=45
        )
        direction = params.get("direction", "left")
        if direction not in ("left", "right", "top", "bottom"):
            direction = "left"
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=0.5, max_val=10.0
        )

        if direction in ("left", "right"):
            ry = angle if direction == "left" else -angle
            rx = 3
            shadow_x = 20 if ry >= 0 else -20
        else:
            rx = angle if direction == "top" else -angle
            ry = 0
            shadow_x = 0

        tilt_in_ms = 600
        hold_ms = max(100, int(duration * 1000) - tilt_in_ms * 2)

        js = (
            "history.scrollRestoration = 'manual';\n"
            "const el = document.body;\n"
            f"el.style.transition = 'transform {tilt_in_ms}ms cubic-bezier(0.25,0.46,0.45,0.94),"
            f" box-shadow {tilt_in_ms}ms ease';\n"
            "requestAnimationFrame(() => {\n"
            f"    el.style.transform = 'perspective(1200px) rotateY({ry}deg)"
            f" rotateX({rx}deg) scale(0.92)';\n"
            f"    el.style.boxShadow = '{shadow_x}px 15px 50px rgba(0,0,0,0.35)';\n"
            "});\n"
            f"setTimeout(() => {{\n"
            f"    el.style.transition = 'transform {tilt_in_ms}ms cubic-bezier(0.25,0.46,0.45,0.94),"
            f" box-shadow {tilt_in_ms}ms ease';\n"
            "    el.style.transform = '';\n"
            "    el.style.boxShadow = '';\n"
            f"    setTimeout(() => {{\n"
            "        el.style.transition = '';\n"
            f"    }}, {tilt_in_ms});\n"
            f"}}, {tilt_in_ms + hold_ms});\n"
        )
        evaluate_js(iife(js))
