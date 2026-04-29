"""Fireworks effect — rockets + particle explosions on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class FireworksEffect(BrowserEffect):
    effect_id = "fireworks"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 3), default=3, min_val=0.5, max_val=30)
        initial_rockets = int(
            sanitize_number(params.get("initial_rockets", 8), default=8, min_val=1, max_val=30)
        )
        launch_interval = int(
            sanitize_number(
                params.get("launch_interval", 1200),
                default=1200,
                min_val=200,
                max_val=5000,
            )
        )
        particles_per_rocket = int(
            sanitize_number(
                params.get("particles_per_rocket", 50),
                default=50,
                min_val=10,
                max_val=200,
            )
        )
        particle_speed_min = sanitize_number(
            params.get("particle_speed_min", 1.5), default=1.5, min_val=0.5, max_val=8
        )
        particle_speed_range = sanitize_number(
            params.get("particle_speed_range", 4), default=4, min_val=1, max_val=10
        )
        gravity = sanitize_number(
            params.get("gravity", 0.05), default=0.05, min_val=0.01, max_val=0.2
        )
        fade_rate = sanitize_number(
            params.get("fade_rate", 0.012), default=0.012, min_val=0.005, max_val=0.05
        )

        max_frames = int(duration * 60)
        setup = (
            "const rockets = [];\n"
            "function launch() {\n"
            "    const x = Math.random()*canvas.width*0.6+canvas.width*0.2;\n"
            "    const targetY = Math.random()*canvas.height*0.4+50;\n"
            "    rockets.push({x, y:canvas.height, targetY, vy:-6-Math.random()*3, exploded:false, particles:[]});\n"
            "}\n"
            f"for (let i=0;i<{initial_rockets};i++) setTimeout(launch, i*300);\n"
            f"const intv = setInterval(launch, {launch_interval});\n"
            "function draw() {\n"
            "    ctx.fillStyle='rgba(0,0,0,0.15)'; ctx.fillRect(0,0,canvas.width,canvas.height);\n"
            "    rockets.forEach(r => {\n"
            "        if (!r.exploded) {\n"
            "            ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(r.x,r.y,3,0,Math.PI*2); ctx.fill();\n"
            "            r.y+=r.vy;\n"
            "            if (r.y<=r.targetY) {\n"
            "                r.exploded=true;\n"
            "                const hue=Math.random()*360;\n"
            f"                for(let i=0;i<{particles_per_rocket};i++){{\n"
            f"                    const a=Math.PI*2*i/{particles_per_rocket};\n"
            f"                    const sp=Math.random()*{particle_speed_range}+{particle_speed_min};\n"
            "                    r.particles.push({x:r.x,y:r.y,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,\n"
            "                        life:1,color:'hsl('+Math.round(hue+Math.random()*40)+',100%,60%)'});\n"
            "                }\n"
            "            }\n"
            "        }\n"
            "        r.particles.forEach(p=>{\n"
            "            ctx.globalAlpha=p.life; ctx.fillStyle=p.color;\n"
            "            ctx.beginPath(); ctx.arc(p.x,p.y,3,0,Math.PI*2); ctx.fill();\n"
            f"            p.x+=p.vx; p.y+=p.vy; p.vy+={gravity}; p.life-={fade_rate};\n"
            "        });\n"
            "        ctx.globalAlpha=1;\n"
            "    });\n"
            "    if(++frame<maxF) requestAnimationFrame(draw); else { clearInterval(intv); canvas.remove(); }\n"
            "}\n"
        )
        evaluate_js(iife(create_canvas("__demodsl_fireworks", setup, max_frames)))
