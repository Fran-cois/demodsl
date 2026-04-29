"""Success checkmark — animated green checkmark overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import auto_remove_multi, iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class SuccessCheckmarkEffect(BrowserEffect):
    effect_id = "success_checkmark"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#4CAF50"))
        font_size = int(
            sanitize_number(params.get("size", 140), default=140, min_val=40, max_val=300)
        )
        glow_size = sanitize_number(params.get("glow", 20), default=20, min_val=0, max_val=60)
        duration = sanitize_number(
            params.get("duration", 1.2), default=1.2, min_val=0.3, max_val=5.0
        )
        symbol = params.get("symbol", "\u2713")
        lifetime = int(duration * 1000) + 300

        js = (
            "const el = document.createElement('div');\n"
            "el.id = '__demodsl_checkmark';\n"
            f"el.innerHTML = '{symbol}';\n"
            "el.style.cssText = `\n"
            "    position:fixed; top:50%; left:50%; transform:translate(-50%,-50%) scale(0);\n"
            f"    font-size:{font_size}px; color:{color}; z-index:99999; pointer-events:none;\n"
            f"    text-shadow: 0 0 {glow_size}px {color}99;\n"
            f"    animation: demodsl-check {duration}s ease-out forwards;\n"
            "`;\n"
            + inject_style(
                "__demodsl_checkmark_style",
                "@keyframes demodsl-check { 40% { transform:translate(-50%,-50%) scale(1.2); opacity:1; } "
                "85% { transform:translate(-50%,-50%) scale(1); opacity:1; } "
                "100% { transform:translate(-50%,-50%) scale(1); opacity:0; } }",
            )
            + "document.body.appendChild(el);\n"
            + auto_remove_multi([("el", lifetime), ("style", lifetime)])
        )
        evaluate_js(iife(js))
