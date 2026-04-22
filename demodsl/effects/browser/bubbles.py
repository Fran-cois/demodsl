"""Bubbles effect — floating wobbling bubbles on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class BubblesEffect(BrowserEffect):
    effect_id = "bubbles"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        count = int(
            sanitize_number(params.get("count", 45), default=45, min_val=5, max_val=200)
        )
        min_radius = sanitize_number(
            params.get("min_radius", 10), default=10, min_val=3, max_val=30
        )
        max_radius = sanitize_number(
            params.get("max_radius", 35), default=35, min_val=10, max_val=80
        )
        speed_min = sanitize_number(
            params.get("speed_min", 0.5), default=0.5, min_val=0.1, max_val=5.0
        )
        speed_range = sanitize_number(
            params.get("speed_range", 1.5), default=1.5, min_val=0.5, max_val=5.0
        )
        hue_base = sanitize_number(
            params.get("hue_base", 180), default=180, min_val=0, max_val=360
        )
        hue_range = sanitize_number(
            params.get("hue_range", 60), default=60, min_val=0, max_val=180
        )

        max_frames = int(duration * 60)
        radius_range = max_radius - min_radius

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "bubbles.forEach(b=>{\n"
            "    b.wobble+=0.03;\n"
            "    const wx=Math.sin(b.wobble)*15;\n"
            "    ctx.beginPath(); ctx.arc(b.x+wx,b.y,b.r,0,Math.PI*2);\n"
            "    ctx.fillStyle='hsla('+b.hue+',70%,70%,0.25)';\n"
            "    ctx.fill();\n"
            "    ctx.strokeStyle='hsla('+b.hue+',80%,80%,0.5)';\n"
            "    ctx.lineWidth=1.5; ctx.stroke();\n"
            "    ctx.beginPath(); ctx.arc(b.x+wx-b.r*0.3,b.y-b.r*0.3,b.r*0.2,0,Math.PI*2);\n"
            "    ctx.fillStyle='rgba(255,255,255,0.6)'; ctx.fill();\n"
            "    b.y+=b.vy; b.x+=b.vx;\n"
            "    if (b.y < -b.r*2) Object.assign(b, makeBubble());\n"
            "});\n"
        )
        setup = (
            "function makeBubble() {\n"
            "    return {\n"
            f"        x:Math.random()*canvas.width, y:canvas.height+Math.random()*100,\n"
            f"        r:Math.random()*{radius_range}+{min_radius}, vy:-(Math.random()*{speed_range}+{speed_min}),\n"
            f"        vx:Math.random()*0.6-0.3, wobble:Math.random()*Math.PI*2,\n"
            f"        hue:Math.random()*{hue_range}+{hue_base}\n"
            "    };\n"
            "}\n"
            f"const bubbles = Array.from({{length:{count}}}, makeBubble);\n"
            + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_bubbles", setup, max_frames)))
