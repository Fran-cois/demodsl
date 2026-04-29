"""Emoji rain effect — falling characters on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class EmojiRainEffect(BrowserEffect):
    effect_id = "emoji_rain"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 3), default=3, min_val=0.5, max_val=30)
        count = int(sanitize_number(params.get("count", 60), default=60, min_val=10, max_val=200))
        min_size = sanitize_number(params.get("min_size", 22), default=22, min_val=10, max_val=60)
        size_range = sanitize_number(
            params.get("size_range", 20), default=20, min_val=5, max_val=40
        )
        speed_min = sanitize_number(
            params.get("speed_min", 1.5), default=1.5, min_val=0.5, max_val=10.0
        )
        speed_range = sanitize_number(
            params.get("speed_range", 2.5), default=2.5, min_val=0.5, max_val=10.0
        )

        custom = params.get("emojis")
        if custom:
            emojis_js = "[" + ",".join(f"'{e}'" for e in custom) + "]"
        else:
            # Use geometric/decorative BMP symbols — safe for Canvas in headless Chrome
            # Avoid characters that trigger emoji presentation (U+2764, U+263A, etc.)
            emojis_js = (
                "["
                "'\\u2605','\\u2606','\\u2666','\\u2660','\\u2663',"  # ★☆♦♠♣
                "'\\u266A','\\u266B','\\u2736','\\u273A','\\u2756',"  # ♪♫✶✺❖
                "'\\u25C6','\\u25B2','\\u25CF','\\u25CB','\\u25A0',"  # ◆▲●○■
                "'\\u2726','\\u2727','\\u25B6','\\u25C0','\\u2022'"  # ✦✧▶◀•
                "]"
            )

        max_frames = int(duration * 60)

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            "items.forEach(p => {\n"
            "    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);\n"
            "    ctx.font = 'bold '+p.size+'px sans-serif'; ctx.textAlign='center'; ctx.textBaseline='middle';\n"
            "    ctx.fillStyle=p.color; ctx.fillText(p.emoji,0,0); ctx.restore();\n"
            "    p.y+=p.vy; p.x+=p.vx; p.rot+=p.vr;\n"
            "    if (p.y > canvas.height + 50) Object.assign(p, makeItem());\n"
            "});\n"
        )
        setup = (
            f"const emojis = {emojis_js};\n"
            "function makeItem() {\n"
            "    return {\n"
            "        x: Math.random()*canvas.width, y: -40 - Math.random()*200,\n"
            "        emoji: emojis[Math.floor(Math.random()*emojis.length)],\n"
            f"        vy: Math.random()*{speed_range}+{speed_min}, vx: Math.random()*2-1,\n"
            f"        size: Math.random()*{size_range}+{min_size}, rot: Math.random()*360, vr: Math.random()*4-2,\n"
            "        color: 'hsl(' + Math.floor(Math.random()*360) + ',80%,65%)'\n"
            "    };\n"
            "}\n"
            f"const items = Array.from({{length: {count}}}, makeItem);\n"
            + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_emoji_rain", setup, max_frames)))
