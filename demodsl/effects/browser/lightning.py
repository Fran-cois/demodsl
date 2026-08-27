"""Lightning effect — periodic branched lightning bolts with a screen flash."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import canvas_animation_loop, create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class LightningEffect(BrowserEffect):
    effect_id = "lightning"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 6), default=6, min_val=1.0, max_val=30)
        color = sanitize_css_color(params.get("color", "#CFE2FF"))
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        interval = sanitize_number(
            params.get("interval", 1.4), default=1.4, min_val=0.4, max_val=10.0
        )

        max_frames = int(duration * 60)
        interval_frames = max(1, int(interval * 60))
        flash_alpha = round(intensity * 0.35, 3)

        draw_body = (
            "ctx.clearRect(0,0,canvas.width,canvas.height);\n"
            f"if(frame % {interval_frames} === 0){{ bolt = makeBolt(); boltAge = 0; }}\n"
            "if(bolt){\n"
            "    boltAge++;\n"
            "    const a = Math.max(0, 1 - boltAge/18);\n"
            "    if(a > 0){\n"
            f"        ctx.fillStyle = 'rgba(255,255,255,' + ({flash_alpha}*a).toFixed(3) + ')';\n"
            "        ctx.fillRect(0,0,canvas.width,canvas.height);\n"
            f"        ctx.strokeStyle='{color}'; ctx.lineWidth=2.5;\n"
            f"        ctx.shadowColor='{color}'; ctx.shadowBlur=18; ctx.globalAlpha=a;\n"
            "        ctx.beginPath(); ctx.moveTo(bolt[0][0], bolt[0][1]);\n"
            "        for(let i=1;i<bolt.length;i++) ctx.lineTo(bolt[i][0], bolt[i][1]);\n"
            "        ctx.stroke();\n"
            "        ctx.globalAlpha=1; ctx.shadowBlur=0;\n"
            "    } else { bolt = null; }\n"
            "}\n"
        )
        setup = (
            "let bolt = null, boltAge = 0;\n"
            "function makeBolt(){\n"
            "    const segs=[];\n"
            "    let x=Math.random()*canvas.width*0.8+canvas.width*0.1, y=0;\n"
            "    segs.push([x,y]);\n"
            "    while(y < canvas.height*0.75){\n"
            "        x += (Math.random()-0.5)*80;\n"
            "        y += Math.random()*40+20;\n"
            "        segs.push([x,y]);\n"
            "    }\n"
            "    return segs;\n"
            "}\n" + canvas_animation_loop(draw_body)
        )
        evaluate_js(iife(create_canvas("__demodsl_lightning", setup, max_frames)))
