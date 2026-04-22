"""Shockwave effect — expanding ring animation."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import (
    auto_remove_multi,
    create_element,
    inject_style,
    iife,
)
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class ShockwaveEffect(BrowserEffect):
    effect_id = "shockwave"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "rgba(100,200,255,1.0)"))
        glow_color = sanitize_css_color(
            params.get("glow_color", "rgba(100,200,255,0.6)")
        )
        border_width = sanitize_number(
            params.get("border_width", 4), default=4, min_val=1, max_val=10
        )
        max_size = int(
            sanitize_number(
                params.get("max_size", 600), default=600, min_val=100, max_val=1200
            )
        )
        duration = sanitize_number(
            params.get("duration", 0.8), default=0.8, min_val=0.2, max_val=3.0
        )
        glow_size = sanitize_number(
            params.get("glow", 15), default=15, min_val=0, max_val=40
        )
        lifetime = int(duration * 1000) + 100

        css = (
            f"position:fixed; top:50%; left:50%; width:10px; height:10px;"
            f"border-radius:50%; border:{border_width}px solid {color};"
            f"box-shadow: 0 0 {glow_size}px {glow_color}, inset 0 0 {glow_size * 0.66:.0f}px {glow_color};"
            f"transform:translate(-50%,-50%); z-index:99999; pointer-events:none;"
            f"animation: demodsl-shock {duration}s ease-out forwards;"
        )
        keyframes = (
            "@keyframes demodsl-shock {\n"
            f"    to {{ width:{max_size}px; height:{max_size}px; opacity:0; border-width:1px; box-shadow:none; }}\n"
            "}"
        )
        js = (
            create_element("div", "__demodsl_shockwave", css)
            + inject_style("__demodsl_shockwave_style", keyframes)
            + auto_remove_multi([("el", lifetime), ("style", lifetime)])
        )
        evaluate_js(iife(js))
