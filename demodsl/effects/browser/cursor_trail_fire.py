"""Cursor trail fire — flickering sparks following the cursor."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, on_mousemove, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class CursorTrailFireEffect(BrowserEffect):
    effect_id = "cursor_trail_fire"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        sparks_per_move = int(
            sanitize_number(params.get("sparks", 5), default=5, min_val=1, max_val=15)
        )
        min_size = sanitize_number(params.get("min_size", 10), default=10, min_val=4, max_val=30)
        size_range = sanitize_number(
            params.get("size_range", 12), default=12, min_val=4, max_val=30
        )
        glow_size = sanitize_number(params.get("glow", 10), default=10, min_val=0, max_val=30)
        hue_base = sanitize_number(params.get("hue_base", 10), default=10, min_val=0, max_val=360)
        hue_range = sanitize_number(params.get("hue_range", 40), default=40, min_val=0, max_val=180)
        fade_delay = int(
            sanitize_number(params.get("fade_delay", 300), default=300, min_val=50, max_val=1000)
        )
        lifetime = int(
            sanitize_number(params.get("lifetime", 1500), default=1500, min_val=500, max_val=5000)
        )

        body = (
            f"for (let i = 0; i < {sparks_per_move}; i++) {{\n"
            "    const spark = document.createElement('div');\n"
            "    spark.className = '__demodsl_trail_fire';\n"
            f"    const size = Math.random() * {size_range} + {min_size};\n"
            f"    const hue = Math.random() * {hue_range} + {hue_base};\n"
            "    spark.style.cssText = `\n"
            "        position:fixed; left:${e.clientX + (Math.random()-0.5)*12}px;\n"
            "        top:${e.clientY + (Math.random()-0.5)*12}px;\n"
            "        width:${size}px; height:${size}px; border-radius:50%;\n"
            "        background:hsl(${hue},100%,55%);\n"
            f"        box-shadow: 0 0 {glow_size}px hsl(${{hue}},100%,50%), 0 0 {glow_size * 2}px rgba(255,100,0,0.5);\n"
            "        pointer-events:none; z-index:99999;\n"
            "        transition: all 1.0s ease-out;\n"
            "    `;\n"
            "    document.body.appendChild(spark);\n"
            "    setTimeout(() => {\n"
            "        spark.style.transform = `translateY(-${25 + Math.random()*30}px) scale(0)`;\n"
            "        spark.style.opacity = '0';\n"
            f"    }}, {fade_delay});\n"
            f"    setTimeout(() => spark.remove(), {lifetime});\n"
            "}\n"
        )
        evaluate_js(iife(on_mousemove(body)))
        if params.get("simulate_mouse"):
            duration = sanitize_number(
                params.get("duration", 3), default=3, min_val=0.5, max_val=30
            )
            evaluate_js(simulate_mouse_path(duration))
