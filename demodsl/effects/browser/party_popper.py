"""Party popper effect — multi-shape confetti from corners on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class PartyPopperEffect(BrowserEffect):
    effect_id = "party_popper"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 3), default=3, min_val=0.5, max_val=30)
        count = int(sanitize_number(params.get("count", 55), default=55, min_val=10, max_val=200))
        min_size = sanitize_number(params.get("min_size", 8), default=8, min_val=2, max_val=30)
        size_range = sanitize_number(
            params.get("size_range", 10), default=10, min_val=2, max_val=30
        )
        speed_min = sanitize_number(params.get("speed_min", 4), default=4, min_val=1, max_val=15)
        speed_range = sanitize_number(
            params.get("speed_range", 7), default=7, min_val=1, max_val=15
        )
        gravity = sanitize_number(
            params.get("gravity", 0.12), default=0.12, min_val=0.01, max_val=0.5
        )
        fade_rate = sanitize_number(
            params.get("fade_rate", 0.003), default=0.003, min_val=0.001, max_val=0.02
        )
        raw_colors = params.get(
            "colors",
            [
                "#FF6B6B",
                "#4ECDC4",
                "#45B7D1",
                "#FFA07A",
                "#98D8C8",
                "#F7DC6F",
                "#BB8FCE",
                "#FF69B4",
            ],
        )
        colors_js = ",".join(f"'{sanitize_css_color(c)}'" for c in raw_colors)

        max_frames = int(duration * 60)
        setup = (
            f"const colors=[{colors_js}];\n"
            "const shapes=['rect','circle','triangle'];\n"
            "const origins=[[0,canvas.height],[canvas.width,canvas.height]];\n"
            "const items=[];\n"
            "function makeItem(ox, oy) {\n"
            "    const a=-Math.PI/4-Math.random()*Math.PI/2;\n"
            f"    const sp=Math.random()*{speed_range}+{speed_min};\n"
            "    return {x:ox,y:oy,vx:Math.cos(a)*sp*(ox===0?1:-1),vy:Math.sin(a)*sp,\n"
            "        color:colors[Math.floor(Math.random()*colors.length)],\n"
            "        shape:shapes[Math.floor(Math.random()*shapes.length)],\n"
            f"        size:Math.random()*{size_range}+{min_size}, rot:Math.random()*360, vr:Math.random()*8-4, life:1}};\n"
            "}\n"
            "origins.forEach(([ox,oy])=>{\n"
            f"    for(let i=0;i<{count};i++) items.push(makeItem(ox,oy));\n"
            "});\n"
            "function draw(){\n"
            "    ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "    items.forEach(p=>{\n"
            "        ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);\n"
            "        ctx.globalAlpha=Math.max(0,p.life); ctx.fillStyle=p.color;\n"
            "        if(p.shape==='rect'){ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*0.6);}\n"
            "        else if(p.shape==='circle'){ctx.beginPath();ctx.arc(0,0,p.size/2,0,Math.PI*2);ctx.fill();}\n"
            "        else{ctx.beginPath();ctx.moveTo(0,-p.size/2);ctx.lineTo(p.size/2,p.size/2);ctx.lineTo(-p.size/2,p.size/2);ctx.closePath();ctx.fill();}\n"
            "        ctx.restore();\n"
            f"        p.x+=p.vx; p.y+=p.vy; p.vy+={gravity}; p.rot+=p.vr; p.life-={fade_rate};\n"
            "    });\n"
            "    if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();\n"
            "}\n"
        )
        evaluate_js(iife(create_canvas("__demodsl_party_popper", setup, max_frames)))
