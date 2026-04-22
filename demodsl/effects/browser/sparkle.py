"""Sparkle effect — animated golden sparkles on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class SparkleEffect(BrowserEffect):
    effect_id = "sparkle"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        count = int(
            sanitize_number(
                params.get("count", 80), default=80, min_val=10, max_val=300
            )
        )
        color = sanitize_css_color(params.get("color", "#FFD700"))
        min_size = sanitize_number(
            params.get("min_size", 2), default=2, min_val=1, max_val=10
        )
        max_size = sanitize_number(
            params.get("max_size", 8), default=8, min_val=2, max_val=20
        )

        max_frames = int(duration * 60)
        size_range = max_size - min_size

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "sparkles.forEach(s => {\n"
            "    s.alpha = 0.5 + 0.5*Math.sin(frame*0.1 + s.x);\n"
            "    ctx.globalAlpha = s.alpha;\n"
            f"    ctx.fillStyle = '{color}';\n"
            "    ctx.beginPath(); ctx.arc(s.x,s.y,s.size,0,Math.PI*2); ctx.fill();\n"
            "});\n"
        )
        setup = (
            f"const sparkles = Array.from({{length: {count}}}, () => ({{\n"
            "    x: Math.random()*canvas.width, y: Math.random()*canvas.height,\n"
            f"    size: Math.random()*{size_range}+{min_size}, alpha: Math.random()\n"
            "}));\n" + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_sparkle", setup, max_frames)))
