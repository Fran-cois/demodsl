"""Click particles — burst of particles spawning at each click."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class ClickParticlesEffect(BrowserEffect):
    effect_id = "click_particles"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )

        count = int(8 + intensity * 16)
        lifetime = int(duration * 1000)

        js = (
            "const canvas = document.createElement('canvas');\n"
            "canvas.id = '__demodsl_click_particles';\n"
            "canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;';\n"
            "document.body.appendChild(canvas);\n"
            "canvas.width = window.innerWidth;\n"
            "canvas.height = window.innerHeight;\n"
            "const ctx = canvas.getContext('2d');\n"
            "const particles = [];\n"
            "const startTime = performance.now();\n"
            f"const LIFETIME = {lifetime};\n"
            f"const COLOR = '{color}';\n"
            f"const COUNT = {count};\n"
            # Particle class
            "function spawnBurst(x, y) {\n"
            "    for (let i = 0; i < COUNT; i++) {\n"
            "        const angle = (Math.PI * 2 * i) / COUNT + (Math.random() - 0.5) * 0.4;\n"
            "        const speed = 2 + Math.random() * 4;\n"
            "        particles.push({\n"
            "            x, y,\n"
            "            vx: Math.cos(angle) * speed,\n"
            "            vy: Math.sin(angle) * speed - 2,\n"
            "            size: 2 + Math.random() * 4,\n"
            "            life: 1.0,\n"
            "            decay: 0.015 + Math.random() * 0.02,\n"
            "            gravity: 0.08 + Math.random() * 0.04,\n"
            "            hueShift: Math.random() * 30 - 15,\n"
            "        });\n"
            "    }\n"
            "}\n"
            # Click handler — use capturing to get clicks even with pointer-events:none canvas
            "function onClick(e) {\n"
            "    spawnBurst(e.clientX, e.clientY);\n"
            "}\n"
            "document.addEventListener('click', onClick, true);\n"
            # Auto-fire demo clicks
            "const demoClicks = [\n"
            "    {t: 200,  x: 0.3, y: 0.4},\n"
            "    {t: 700,  x: 0.6, y: 0.5},\n"
            "    {t: 1200, x: 0.5, y: 0.3},\n"
            "    {t: 1800, x: 0.7, y: 0.6},\n"
            "];\n"
            "demoClicks.forEach(c => {\n"
            "    setTimeout(() => spawnBurst(\n"
            "        window.innerWidth * c.x,\n"
            "        window.innerHeight * c.y\n"
            "    ), c.t);\n"
            "});\n"
            # Animation loop
            "function draw() {\n"
            "    const elapsed = performance.now() - startTime;\n"
            "    if (elapsed > LIFETIME) {\n"
            "        document.removeEventListener('click', onClick, true);\n"
            "        canvas.remove();\n"
            "        return;\n"
            "    }\n"
            "    ctx.clearRect(0, 0, canvas.width, canvas.height);\n"
            "    for (let i = particles.length - 1; i >= 0; i--) {\n"
            "        const p = particles[i];\n"
            "        p.x += p.vx;\n"
            "        p.y += p.vy;\n"
            "        p.vy += p.gravity;\n"
            "        p.vx *= 0.98;\n"
            "        p.life -= p.decay;\n"
            "        if (p.life <= 0) { particles.splice(i, 1); continue; }\n"
            "        ctx.globalAlpha = p.life;\n"
            "        ctx.fillStyle = COLOR;\n"
            "        ctx.shadowColor = COLOR;\n"
            "        ctx.shadowBlur = 6;\n"
            "        ctx.beginPath();\n"
            "        ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);\n"
            "        ctx.fill();\n"
            "    }\n"
            "    ctx.shadowBlur = 0;\n"
            "    ctx.globalAlpha = 1;\n"
            "    requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
        )
        evaluate_js(iife(js))
