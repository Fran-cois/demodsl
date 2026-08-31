"""Curl noise effect — flowing organic 2D texture (smoke/water/ink-like swirls).

Analytic pseudo-noise (a sum of a few phase-shifted sines), same cheap
deterministic approach as the repo's other procedural motion (wiggle paths,
aurora ribbons) — no real Perlin/Simplex library needed for a convincing
swirl at this scale.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class CurlNoiseEffect(BrowserEffect):
    effect_id = "curl_noise"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#8A5CFF"))
        density = sanitize_number(params.get("density", 1.0), default=1.0, min_val=0.2, max_val=3.0)
        speed = sanitize_number(params.get("speed", 1.0), default=1.0, min_val=0.1, max_val=3.0)
        opacity = sanitize_number(
            params.get("opacity", 0.25), default=0.25, min_val=0.05, max_val=0.8
        )
        max_frames = int(
            sanitize_number(params.get("duration", 6), default=6, min_val=0.5, max_val=60) * 60
        )
        setup = (
            f"const n = Math.floor(36 * {density});\n"
            "const particles = Array.from({length: n}, () => ({\n"
            "    x: Math.random() * canvas.width,\n"
            "    y: Math.random() * canvas.height,\n"
            "    life: Math.random() * 100,\n"
            "}));\n"
            "function draw() {\n"
            "    ctx.globalCompositeOperation = 'destination-out';\n"
            "    ctx.fillStyle = 'rgba(0,0,0,0.035)';\n"
            "    ctx.fillRect(0, 0, canvas.width, canvas.height);\n"
            "    ctx.globalCompositeOperation = 'source-over';\n"
            f"    const t = frame * 0.016 * {speed};\n"
            f"    ctx.fillStyle = '{color}';\n"
            f"    ctx.globalAlpha = {opacity};\n"
            "    for (const p of particles) {\n"
            "        // Fake curl: a swirling direction field from phase-shifted sines,\n"
            "        // not a real gradient curl, but reads the same at this scale.\n"
            "        const angle = (Math.sin(p.x * 0.006 + t * 0.6)\n"
            "            + Math.cos(p.y * 0.008 - t * 0.5)\n"
            "            + Math.sin((p.x - p.y) * 0.004 + t * 0.3)) * Math.PI;\n"
            "        p.x += Math.cos(angle) * 1.6;\n"
            "        p.y += Math.sin(angle) * 1.6;\n"
            "        p.life -= 1;\n"
            "        if (p.life <= 0 || p.x < 0 || p.x > canvas.width || p.y < 0 || p.y > canvas.height) {\n"
            "            p.x = Math.random() * canvas.width;\n"
            "            p.y = Math.random() * canvas.height;\n"
            "            p.life = 80 + Math.random() * 60;\n"
            "        }\n"
            "        ctx.beginPath();\n"
            "        ctx.arc(p.x, p.y, 10, 0, Math.PI * 2);\n"
            "        ctx.fill();\n"
            "    }\n"
            "    ctx.globalAlpha = 1;\n"
            "    if (++frame < maxF) requestAnimationFrame(draw);\n"
            "    else canvas.remove();\n"
            "}\n"
        )
        evaluate_js(iife(create_canvas("__demodsl_curl_noise", setup, max_frames)))
