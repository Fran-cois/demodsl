"""Ripple effect — expanding ring on click."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class RippleEffect(BrowserEffect):
    effect_id = "ripple"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "rgba(80,150,255,1.0)"))
        glow_color = sanitize_css_color(
            params.get("glow_color", "rgba(80,150,255,0.5)")
        )
        border_width = sanitize_number(
            params.get("border_width", 3), default=3, min_val=1, max_val=10
        )
        max_size = int(
            sanitize_number(
                params.get("max_size", 200), default=200, min_val=50, max_val=600
            )
        )
        duration = sanitize_number(
            params.get("duration", 0.6), default=0.6, min_val=0.2, max_val=3.0
        )
        glow_size = sanitize_number(
            params.get("glow", 12), default=12, min_val=0, max_val=40
        )

        start_size = 50
        start_offset = start_size // 2
        end_offset = max_size // 2

        spawn_fn = (
            "function spawnRipple(cx, cy) {\n"
            "    const ripple = document.createElement('div');\n"
            "    const id = '__drip_' + Math.random().toString(36).slice(2,8);\n"
            "    ripple.style.cssText = `\n"
            f"        position:fixed; left:${{cx-{start_offset}}}px; top:${{cy-{start_offset}}}px;\n"
            f"        width:{start_size}px; height:{start_size}px; border-radius:50%;\n"
            f"        border:{border_width}px solid {color};\n"
            f"        box-shadow: 0 0 {glow_size}px {glow_color};\n"
            "        z-index:99999; pointer-events:none;\n"
            f"        animation: ${{id}} {duration}s ease-out forwards;\n"
            "    `;\n"
            "    const style = document.createElement('style');\n"
            f"    style.textContent = `@keyframes ${{id}} {{ to {{ width:{max_size}px;height:{max_size}px;"
            f"left:${{cx-{end_offset}}}px;top:${{cy-{end_offset}}}px;opacity:0; }} }}`;\n"
            "    document.head.appendChild(style);\n"
            "    document.body.appendChild(ripple);\n"
            f"    setTimeout(() => {{ ripple.remove(); style.remove(); }}, {int(duration * 1000 + 100)});\n"
            "}\n"
        )

        click_handler = (
            "document.addEventListener('click', (e) => {\n"
            "    spawnRipple(e.clientX, e.clientY);\n"
            "});\n"
        )

        # Auto-spawn ripples at random positions for headless recording
        auto_anim = (
            "const vw = window.innerWidth, vh = window.innerHeight;\n"
            "let spawned = 0;\n"
            "function autoRipple() {\n"
            "    const cx = 100 + Math.random() * (vw - 200);\n"
            "    const cy = 100 + Math.random() * (vh - 200);\n"
            "    spawnRipple(cx, cy);\n"
            "    spawned++;\n"
            "    if (spawned < 12) setTimeout(autoRipple, 300 + Math.random() * 200);\n"
            "}\n"
            "autoRipple();\n"
        )

        evaluate_js(iife(spawn_fn + click_handler + auto_anim))
