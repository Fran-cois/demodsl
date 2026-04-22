"""Heatmap — animated heat overlay showing activity zones."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class HeatmapEffect(BrowserEffect):
    effect_id = "heatmap"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.5, max_val=15.0
        )
        lifetime = int(duration * 1000)
        max_alpha = round(0.3 + intensity * 0.4, 2)

        js = (
            "const canvas = document.createElement('canvas');\n"
            "canvas.id = '__demodsl_heatmap';\n"
            "canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;';\n"
            "document.body.appendChild(canvas);\n"
            "const W = canvas.width = window.innerWidth;\n"
            "const H = canvas.height = window.innerHeight;\n"
            "const ctx = canvas.getContext('2d');\n"
            # Generate heat points (simulated user activity)
            "const points = [\n"
            "    {x:0.3, y:0.25, r:90, heat:0.9},\n"
            "    {x:0.5, y:0.15, r:120, heat:1.0},\n"
            "    {x:0.7, y:0.35, r:80, heat:0.7},\n"
            "    {x:0.2, y:0.5, r:70, heat:0.5},\n"
            "    {x:0.6, y:0.55, r:100, heat:0.85},\n"
            "    {x:0.4, y:0.7, r:60, heat:0.4},\n"
            "    {x:0.8, y:0.6, r:90, heat:0.65},\n"
            "    {x:0.15, y:0.8, r:50, heat:0.3},\n"
            "    {x:0.5, y:0.4, r:110, heat:0.75},\n"
            "];\n"
            # Draw single heat point with radial gradient
            "function drawHeat(x, y, r, heat, alpha) {\n"
            "    const grd = ctx.createRadialGradient(x, y, 0, x, y, r);\n"
            "    const a = (heat * alpha).toFixed(2);\n"
            "    grd.addColorStop(0, `rgba(255,80,0,${a})`);\n"
            "    grd.addColorStop(0.3, `rgba(255,160,0,${(a*0.7).toFixed(2)})`);\n"
            "    grd.addColorStop(0.6, `rgba(255,220,0,${(a*0.3).toFixed(2)})`);\n"
            "    grd.addColorStop(1, 'rgba(255,255,0,0)');\n"
            "    ctx.fillStyle = grd;\n"
            "    ctx.fillRect(x - r, y - r, r * 2, r * 2);\n"
            "}\n"
            f"const MAX_ALPHA = {max_alpha};\n"
            "const t0 = performance.now();\n"
            "function draw() {\n"
            "    const elapsed = performance.now() - t0;\n"
            f"    if (elapsed > {lifetime}) {{ canvas.remove(); return; }}\n"
            f"    const fadeIn = Math.min(1, elapsed / 800);\n"
            f"    const fadeOut = elapsed > {lifetime - 600} ? "
            f"1 - (elapsed - {lifetime - 600}) / 600 : 1;\n"
            "    const alpha = MAX_ALPHA * fadeIn * fadeOut;\n"
            "    ctx.clearRect(0, 0, W, H);\n"
            "    ctx.globalCompositeOperation = 'lighter';\n"
            "    points.forEach((p, i) => {\n"
            "        const pulse = 1 + Math.sin(elapsed / 500 + i) * 0.15;\n"
            "        drawHeat(W * p.x, H * p.y, p.r * pulse, p.heat, alpha);\n"
            "    });\n"
            "    ctx.globalCompositeOperation = 'source-over';\n"
            "    requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
        )
        evaluate_js(iife(js))
