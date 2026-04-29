"""Snow effect — falling snowflakes on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class SnowEffect(BrowserEffect):
    effect_id = "snow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 5), default=5, min_val=0.5, max_val=30)
        count = int(sanitize_number(params.get("count", 120), default=120, min_val=20, max_val=500))
        min_radius = sanitize_number(params.get("min_radius", 3), default=3, min_val=1, max_val=10)
        max_radius = sanitize_number(params.get("max_radius", 8), default=8, min_val=3, max_val=20)
        color = sanitize_css_color(params.get("color", "rgba(200,230,255,0.85)"))
        glow_color = sanitize_css_color(params.get("glow_color", "rgba(180,220,255,0.6)"))
        glow_blur = sanitize_number(params.get("glow", 4), default=4, min_val=0, max_val=20)
        speed_min = sanitize_number(
            params.get("speed_min", 0.8), default=0.8, min_val=0.1, max_val=5.0
        )
        speed_max = sanitize_number(
            params.get("speed_max", 2.8), default=2.8, min_val=0.5, max_val=10.0
        )

        max_frames = int(duration * 60)
        radius_range = max_radius - min_radius
        speed_range = speed_max - speed_min

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "flakes.forEach(f=>{\n"
            "    f.wobble+=0.02;\n"
            "    ctx.save();\n"
            f"    ctx.shadowColor='{glow_color}'; ctx.shadowBlur={glow_blur};\n"
            "    ctx.beginPath(); ctx.arc(f.x+Math.sin(f.wobble)*20,f.y,f.r,0,Math.PI*2);\n"
            f"    ctx.fillStyle='{color}';\n"
            "    ctx.fill();\n"
            "    ctx.restore();\n"
            "    f.y+=f.vy; f.x+=f.vx;\n"
            "    if(f.y>canvas.height+10){f.y=-10;f.x=Math.random()*canvas.width;}\n"
            "});\n"
        )
        setup = (
            f"const flakes = Array.from({{length:{count}}},()=>({{\n"
            f"    x:Math.random()*canvas.width, y:-10-Math.random()*canvas.height,\n"
            f"    r:Math.random()*{radius_range}+{min_radius}, vy:Math.random()*{speed_range}+{speed_min},\n"
            f"    vx:Math.random()*0.8-0.4, wobble:Math.random()*Math.PI*2\n"
            "}));\n" + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_snow", setup, max_frames)))
