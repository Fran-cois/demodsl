"""Cursor trail particles — radial particle burst on each mouse move."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, on_mousemove, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class CursorTrailParticlesEffect(BrowserEffect):
    effect_id = "cursor_trail_particles"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        count = int(sanitize_number(params.get("count", 6), default=6, min_val=2, max_val=20))
        min_size = sanitize_number(params.get("min_size", 8), default=8, min_val=2, max_val=30)
        size_range = sanitize_number(params.get("size_range", 6), default=6, min_val=2, max_val=20)
        spread = sanitize_number(params.get("spread", 35), default=35, min_val=10, max_val=100)
        hue_base = sanitize_number(params.get("hue_base", 180), default=180, min_val=0, max_val=360)
        hue_range = sanitize_number(params.get("hue_range", 60), default=60, min_val=0, max_val=180)
        glow = sanitize_number(params.get("glow", 8), default=8, min_val=0, max_val=30)
        fade_delay = int(
            sanitize_number(params.get("fade_delay", 200), default=200, min_val=50, max_val=1000)
        )
        lifetime = int(
            sanitize_number(params.get("lifetime", 1400), default=1400, min_val=500, max_val=5000)
        )

        body = (
            f"for (let i = 0; i < {count}; i++) {{\n"
            "    const p = document.createElement('div');\n"
            "    p.className = '__demodsl_trail_particles';\n"
            "    const angle = Math.random() * Math.PI * 2;\n"
            f"    const dist = Math.random() * {spread} + 10;\n"
            "    const dx = Math.cos(angle) * dist;\n"
            "    const dy = Math.sin(angle) * dist;\n"
            f"    const size = Math.random() * {size_range} + {min_size};\n"
            "    p.style.cssText = `\n"
            "        position:fixed; left:${e.clientX - size/2}px; top:${e.clientY - size/2}px;\n"
            "        width:${size}px; height:${size}px; border-radius:50%;\n"
            f"        background:hsl(${{Math.random()*{hue_range}+{hue_base}}},90%,65%);\n"
            f"        box-shadow: 0 0 {glow}px hsl(${{Math.random()*{hue_range}+{hue_base}}},80%,50%);\n"
            "        pointer-events:none; z-index:99999;\n"
            "        transition: all 1.0s ease-out;\n"
            "    `;\n"
            "    document.body.appendChild(p);\n"
            "    setTimeout(() => {\n"
            "        p.style.transform = `translate(${dx}px, ${dy}px)`;\n"
            "        p.style.opacity = '0';\n"
            f"    }}, {fade_delay});\n"
            f"    setTimeout(() => p.remove(), {lifetime});\n"
            "}\n"
        )
        evaluate_js(iife(on_mousemove(body)))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
