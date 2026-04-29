"""Confetti effect — animated falling confetti pieces on a canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_colors_list, sanitize_number


class ConfettiEffect(BrowserEffect):
    effect_id = "confetti"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 3), default=3, min_val=0.5, max_val=30)
        count = int(sanitize_number(params.get("count", 150), default=150, min_val=20, max_val=500))
        colors = params.get(
            "colors",
            [
                "#f44336",
                "#e91e63",
                "#9c27b0",
                "#2196f3",
                "#4caf50",
                "#ff9800",
                "#FFEB3B",
                "#00BCD4",
            ],
        )
        safe_colors = (
            sanitize_css_colors_list(colors)
            if isinstance(colors, list)
            else ["#f44336", "#e91e63", "#9c27b0"]
        )
        speed_min = sanitize_number(
            params.get("speed_min", 1.5), default=1.5, min_val=0.5, max_val=10.0
        )
        speed_range = sanitize_number(
            params.get("speed_range", 3.0), default=3.0, min_val=0.5, max_val=10.0
        )

        max_frames = int(duration * 60)
        colors_js = ",".join(f"'{c}'" for c in safe_colors)

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "pieces.forEach(p => {\n"
            "    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);\n"
            "    ctx.fillStyle=p.color; ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);\n"
            "    ctx.restore();\n"
            "    p.y+=p.vy; p.x+=p.vx; p.rot+=3;\n"
            "    if (p.y > canvas.height + 30) Object.assign(p, makePiece());\n"
            "});\n"
        )
        setup = (
            f"const colors = [{colors_js}];\n"
            "function makePiece() {\n"
            "    return {\n"
            "        x: Math.random()*canvas.width, y: -20 - Math.random()*40,\n"
            "        w: Math.random()*12+8, h: Math.random()*8+5,\n"
            "        color: colors[Math.floor(Math.random()*colors.length)],\n"
            f"        vy: Math.random()*{speed_range}+{speed_min}, vx: Math.random()*4-2, rot: Math.random()*360\n"
            "    };\n"
            "}\n"
            f"const pieces = Array.from({{length: {count}}}, makePiece);\n"
            + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_confetti", setup, max_frames)))
