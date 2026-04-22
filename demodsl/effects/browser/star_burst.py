"""Star burst effect — exploding stars from center on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class StarBurstEffect(BrowserEffect):
    effect_id = "star_burst"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        count = int(
            sanitize_number(
                params.get("count", 80), default=80, min_val=10, max_val=300
            )
        )
        speed_min = sanitize_number(
            params.get("speed_min", 2), default=2, min_val=0.5, max_val=10.0
        )
        speed_range = sanitize_number(
            params.get("speed_range", 5), default=5, min_val=1, max_val=15.0
        )
        hue_base = sanitize_number(
            params.get("hue_base", 40), default=40, min_val=0, max_val=360
        )
        hue_range = sanitize_number(
            params.get("hue_range", 60), default=60, min_val=0, max_val=180
        )
        decay = sanitize_number(
            params.get("decay", 0.006), default=0.006, min_val=0.001, max_val=0.05
        )

        max_frames = int(duration * 60)
        setup = (
            "const cx=canvas.width/2, cy=canvas.height/2;\n"
            f"const stars=Array.from({{length:{count}}},()=>{{\n"
            "    const a=Math.random()*Math.PI*2;\n"
            f"    const sp=Math.random()*{speed_range}+{speed_min};\n"
            "    return {x:cx,y:cy,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,\n"
            f"        size:Math.random()*4+2,hue:Math.random()*{hue_range}+{hue_base},life:1}};\n"
            "});\n"
            "function drawStar(x,y,r){\n"
            "    ctx.beginPath();\n"
            "    for(let i=0;i<5;i++){\n"
            "        const a=Math.PI*2*i/5-Math.PI/2;\n"
            "        const ai=a+Math.PI/5;\n"
            "        ctx.lineTo(x+Math.cos(a)*r,y+Math.sin(a)*r);\n"
            "        ctx.lineTo(x+Math.cos(ai)*r*0.4,y+Math.sin(ai)*r*0.4);\n"
            "    }\n"
            "    ctx.closePath(); ctx.fill();\n"
            "}\n"
            "function draw(){\n"
            "    ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "    stars.forEach(s=>{\n"
            "        ctx.globalAlpha=Math.max(0,s.life);\n"
            "        ctx.fillStyle='hsl('+Math.round(s.hue)+',100%,65%)';\n"
            "        drawStar(s.x,s.y,s.size*4);\n"
            f"        s.x+=s.vx; s.y+=s.vy; s.vy+=0.04; s.life-={decay};\n"
            "    });\n"
            "    ctx.globalAlpha=1;\n"
            "    if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();\n"
            "}\n"
        )
        evaluate_js(iife(create_canvas("__demodsl_star_burst", setup, max_frames)))
