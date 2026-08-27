"""Rain effect — slanted rain streaks falling on canvas."""

from __future__ import annotations

import math
from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class RainEffect(BrowserEffect):
    effect_id = "rain"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 5), default=5, min_val=0.5, max_val=30)
        count = int(sanitize_number(params.get("count", 180), default=180, min_val=20, max_val=600))
        color = sanitize_css_color(params.get("color", "rgba(174,194,224,0.55)"))
        speed = sanitize_number(params.get("speed", 1.0), default=1.0, min_val=0.2, max_val=5.0)
        angle = sanitize_number(params.get("angle", 12), default=12, min_val=-45, max_val=45)

        max_frames = int(duration * 60)
        slant = round(math.tan(math.radians(angle)), 3)

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            f"ctx.strokeStyle='{color}'; ctx.lineWidth=1.3; ctx.lineCap='round';\n"
            "drops.forEach(d=>{\n"
            "    ctx.globalAlpha = d.a;\n"
            "    ctx.beginPath(); ctx.moveTo(d.x,d.y);\n"
            f"    ctx.lineTo(d.x+{slant}*d.len, d.y+d.len);\n"
            "    ctx.stroke();\n"
            f"    d.y+=d.vy; d.x+={slant}*d.vy;\n"
            "    if(d.y>canvas.height+30){d.y=-30;d.x=Math.random()*(canvas.width+200)-100;}\n"
            "    if(d.x>canvas.width+100){d.x=-100;} else if(d.x<-100){d.x=canvas.width+100;}\n"
            "});\n"
            "ctx.globalAlpha=1;\n"
        )
        setup = (
            f"const drops = Array.from({{length:{count}}},()=>({{\n"
            "    x:Math.random()*(canvas.width+200)-100, y:Math.random()*canvas.height,\n"
            f"    len:Math.random()*14+8, vy:(Math.random()*6+9)*{speed},\n"
            "    a:Math.random()*0.5+0.4\n"
            "}));\n" + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_rain", setup, max_frames)))
