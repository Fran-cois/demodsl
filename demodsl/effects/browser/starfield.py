"""Starfield effect — warp-speed stars radiating from the screen center."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class StarfieldEffect(BrowserEffect):
    effect_id = "starfield"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 5), default=5, min_val=0.5, max_val=30)
        count = int(sanitize_number(params.get("count", 250), default=250, min_val=20, max_val=800))
        color = sanitize_css_color(params.get("color", "#FFFFFF"))
        speed = sanitize_number(params.get("speed", 1.0), default=1.0, min_val=0.1, max_val=5.0)

        max_frames = int(duration * 60)

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            f"ctx.fillStyle='{color}';\n"
            "const cx=canvas.width/2, cy=canvas.height/2;\n"
            "stars.forEach(s=>{\n"
            f"    s.z -= 10*{speed};\n"
            "    if(s.z<=1){s.z=canvas.width;s.x=Math.random()*canvas.width-cx;"
            "s.y=Math.random()*canvas.height-cy;}\n"
            "    const px=cx+(s.x/s.z)*cx, py=cy+(s.y/s.z)*cy;\n"
            "    if(px>=0&&px<=canvas.width&&py>=0&&py<=canvas.height){\n"
            "        const d=1-s.z/canvas.width;\n"
            "        ctx.globalAlpha=Math.min(1,d*1.2+0.15);\n"
            "        ctx.beginPath(); ctx.arc(px,py,Math.max(0.4,d*2.4),0,Math.PI*2); ctx.fill();\n"
            "    }\n"
            "});\n"
            "ctx.globalAlpha=1;\n"
        )
        setup = (
            "const cx0=canvas.width/2, cy0=canvas.height/2;\n"
            f"const stars = Array.from({{length:{count}}},()=>({{\n"
            "    x:Math.random()*canvas.width-cx0, y:Math.random()*canvas.height-cy0,\n"
            "    z:Math.random()*canvas.width+1\n"
            "}));\n" + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_starfield", setup, max_frames)))
