"""Chart draw — progressive line chart drawing animation."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class ChartDrawEffect(BrowserEffect):
    effect_id = "chart_draw"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.5, max_val=15.0
        )
        lifetime = int(duration * 1000)
        draw_time = int(lifetime * 0.6)

        js = (
            "const canvas = document.createElement('canvas');\n"
            "canvas.id = '__demodsl_chart_draw';\n"
            "canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;';\n"
            "document.body.appendChild(canvas);\n"
            "const W = canvas.width = window.innerWidth;\n"
            "const H = canvas.height = window.innerHeight;\n"
            "const ctx = canvas.getContext('2d');\n"
            f"const COLOR = '{color}';\n"
            # Chart area (centered panel)
            "const pad = {l: W*0.15, r: W*0.85, t: H*0.2, b: H*0.75};\n"
            "const cw = pad.r - pad.l, ch = pad.b - pad.t;\n"
            # Generate chart data points
            "const N = 24;\n"
            "const data = [];\n"
            "let v = 0.3;\n"
            "for (let i = 0; i < N; i++) {\n"
            "    v += (Math.random() - 0.35) * 0.12;\n"
            "    v = Math.max(0.05, Math.min(0.95, v));\n"
            "    data.push(v);\n"
            "}\n"
            # Bar chart data
            "const bars = [0.4, 0.6, 0.35, 0.8, 0.55, 0.7, 0.45, 0.9];\n"
            f"const DRAW_TIME = {draw_time};\n"
            "const t0 = performance.now();\n"
            "function draw() {\n"
            "    const elapsed = performance.now() - t0;\n"
            f"    if (elapsed > {lifetime}) {{ canvas.remove(); return; }}\n"
            "    const t = Math.min(1, elapsed / DRAW_TIME);\n"
            "    const ease = 1 - Math.pow(1 - t, 3);\n"
            "    ctx.clearRect(0, 0, W, H);\n"
            # Background panel
            "    ctx.fillStyle = 'rgba(15,15,25,0.88)';\n"
            "    ctx.beginPath();\n"
            "    const r = 16;\n"
            "    ctx.moveTo(pad.l - 30 + r, pad.t - 40);\n"
            "    ctx.arcTo(pad.r + 30, pad.t - 40, pad.r + 30, pad.b + 30, r);\n"
            "    ctx.arcTo(pad.r + 30, pad.b + 30, pad.l - 30, pad.b + 30, r);\n"
            "    ctx.arcTo(pad.l - 30, pad.b + 30, pad.l - 30, pad.t - 40, r);\n"
            "    ctx.arcTo(pad.l - 30, pad.t - 40, pad.r + 30, pad.t - 40, r);\n"
            "    ctx.fill();\n"
            # Grid lines
            "    ctx.strokeStyle = 'rgba(255,255,255,0.06)';\n"
            "    ctx.lineWidth = 1;\n"
            "    for (let i = 0; i <= 4; i++) {\n"
            "        const y = pad.t + ch * i / 4;\n"
            "        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.r, y); ctx.stroke();\n"
            "    }\n"
            # Draw bars (left half)
            "    const barW = cw * 0.04;\n"
            "    const barGap = cw * 0.055;\n"
            "    const barStart = pad.l + 10;\n"
            "    bars.forEach((bv, i) => {\n"
            "        const h = ch * bv * ease;\n"
            "        const x = barStart + i * barGap;\n"
            "        ctx.fillStyle = COLOR + '88';\n"
            "        ctx.fillRect(x, pad.b - h, barW, h);\n"
            "        ctx.fillStyle = COLOR;\n"
            "        ctx.fillRect(x, pad.b - h, barW, 3);\n"
            "    });\n"
            # Draw line chart (right half)
            "    const lineStart = pad.l + cw * 0.45;\n"
            "    const lineW = cw * 0.5;\n"
            "    const pts = Math.floor(ease * N);\n"
            "    if (pts > 1) {\n"
            # Fill area
            "        ctx.beginPath();\n"
            "        ctx.moveTo(lineStart, pad.b);\n"
            "        for (let i = 0; i < pts; i++) {\n"
            "            ctx.lineTo(lineStart + lineW * i / (N-1), pad.b - ch * data[i]);\n"
            "        }\n"
            "        ctx.lineTo(lineStart + lineW * (pts-1) / (N-1), pad.b);\n"
            "        ctx.closePath();\n"
            "        const grd = ctx.createLinearGradient(0, pad.t, 0, pad.b);\n"
            "        grd.addColorStop(0, COLOR + '33');\n"
            "        grd.addColorStop(1, COLOR + '05');\n"
            "        ctx.fillStyle = grd;\n"
            "        ctx.fill();\n"
            # Line
            "        ctx.beginPath();\n"
            "        for (let i = 0; i < pts; i++) {\n"
            "            const x = lineStart + lineW * i / (N-1);\n"
            "            const y = pad.b - ch * data[i];\n"
            "            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);\n"
            "        }\n"
            "        ctx.strokeStyle = COLOR;\n"
            "        ctx.lineWidth = 2.5;\n"
            "        ctx.shadowColor = COLOR;\n"
            "        ctx.shadowBlur = 8;\n"
            "        ctx.stroke();\n"
            "        ctx.shadowBlur = 0;\n"
            # Dot at current endpoint
            "        const lastX = lineStart + lineW * (pts-1) / (N-1);\n"
            "        const lastY = pad.b - ch * data[pts-1];\n"
            "        ctx.beginPath();\n"
            "        ctx.arc(lastX, lastY, 5, 0, Math.PI*2);\n"
            "        ctx.fillStyle = COLOR;\n"
            "        ctx.fill();\n"
            "    }\n"
            "    requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
        )
        evaluate_js(iife(js))
