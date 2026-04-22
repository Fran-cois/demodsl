"""Spotlight effect — radial light cone overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class SpotlightEffect(BrowserEffect):
    effect_id = "spotlight"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.8), default=0.8, min_val=0.0, max_val=1.0
        )
        # Light-cone spotlight: bright center that works on both dark and light pages
        alpha = round(0.35 * intensity, 2)
        evaluate_js(
            iife(
                f"const overlay = document.createElement('div');\n"
                f"overlay.id = '__demodsl_spotlight';\n"
                f"overlay.style.cssText = `\n"
                f"    position:fixed; top:0; left:0; width:100%; height:100%;\n"
                f"    z-index:99999; pointer-events:none;\n"
                f"    background: radial-gradient(ellipse 50% 50% at center,\n"
                f"        rgba(255,255,255,{alpha}) 0%,\n"
                f"        rgba(255,255,200,{round(alpha * 0.5, 2)}) 40%,\n"
                f"        transparent 70%);\n"
                f"    animation: __demodsl_spot_pulse 2s ease-in-out infinite;\n"
                f"`;\n"
                f"document.body.appendChild(overlay);\n"
                f"const style = document.createElement('style');\n"
                f"style.textContent = `\n"
                f"@keyframes __demodsl_spot_pulse {{\n"
                f"  0%, 100% {{ opacity: 1; }}\n"
                f"  50% {{ opacity: 0.5; }}\n"
                f"}}\n`;\n"
                f"document.head.appendChild(style);\n"
            )
        )
