"""Connection trace — animated lines linking two page regions."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class ConnectionTraceEffect(BrowserEffect):
    effect_id = "connection_trace"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        from_x = sanitize_number(
            params.get("from_x", 0.2), default=0.2, min_val=0.0, max_val=1.0
        )
        from_y = sanitize_number(
            params.get("from_y", 0.4), default=0.4, min_val=0.0, max_val=1.0
        )
        to_x = sanitize_number(
            params.get("target_x", 0.8), default=0.8, min_val=0.0, max_val=1.0
        )
        to_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        lifetime = int(duration * 1000)
        draw_time = min(1200, int(lifetime * 0.4))

        js = (
            "const canvas = document.createElement('canvas');\n"
            "canvas.id = '__demodsl_connection_trace';\n"
            "canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;';\n"
            "document.body.appendChild(canvas);\n"
            "canvas.width = window.innerWidth;\n"
            "canvas.height = window.innerHeight;\n"
            "const ctx = canvas.getContext('2d');\n"
            f"const COLOR = '{color}';\n"
            f"const sx = canvas.width * {from_x}, sy = canvas.height * {from_y};\n"
            f"const ex = canvas.width * {to_x}, ey = canvas.height * {to_y};\n"
            # Cubic bezier control points for a nice curve
            "const cx1 = sx + (ex - sx) * 0.3, cy1 = sy - 60;\n"
            "const cx2 = sx + (ex - sx) * 0.7, cy2 = ey + 60;\n"
            # Draw endpoint dots
            "function drawDot(x, y, radius, pulse) {\n"
            "    ctx.beginPath();\n"
            "    ctx.arc(x, y, radius + pulse, 0, Math.PI * 2);\n"
            "    ctx.fillStyle = COLOR + '44';\n"
            "    ctx.fill();\n"
            "    ctx.beginPath();\n"
            "    ctx.arc(x, y, radius * 0.6, 0, Math.PI * 2);\n"
            "    ctx.fillStyle = COLOR;\n"
            "    ctx.fill();\n"
            "}\n"
            # Get point on cubic bezier at t
            "function bezierPt(t) {\n"
            "    const u = 1 - t;\n"
            "    return {\n"
            "        x: u*u*u*sx + 3*u*u*t*cx1 + 3*u*t*t*cx2 + t*t*t*ex,\n"
            "        y: u*u*u*sy + 3*u*u*t*cy1 + 3*u*t*t*cy2 + t*t*t*ey\n"
            "    };\n"
            "}\n"
            f"const DRAW_TIME = {draw_time};\n"
            "const t0 = performance.now();\n"
            "function draw() {\n"
            "    const elapsed = performance.now() - t0;\n"
            "    ctx.clearRect(0, 0, canvas.width, canvas.height);\n"
            "    const progress = Math.min(1, elapsed / DRAW_TIME);\n"
            "    const ease = 1 - Math.pow(1 - progress, 3);\n"
            "    const pulse = Math.sin(elapsed / 300) * 2;\n"
            # Draw the curve up to current progress
            "    ctx.beginPath();\n"
            "    ctx.moveTo(sx, sy);\n"
            "    const steps = Math.floor(ease * 60);\n"
            "    for (let i = 1; i <= steps; i++) {\n"
            "        const pt = bezierPt(i / 60);\n"
            "        ctx.lineTo(pt.x, pt.y);\n"
            "    }\n"
            "    ctx.strokeStyle = COLOR;\n"
            "    ctx.lineWidth = 2.5;\n"
            "    ctx.setLineDash([6, 3]);\n"
            "    ctx.lineDashOffset = -elapsed / 50;\n"
            "    ctx.shadowColor = COLOR;\n"
            "    ctx.shadowBlur = 8;\n"
            "    ctx.stroke();\n"
            "    ctx.setLineDash([]);\n"
            "    ctx.shadowBlur = 0;\n"
            # Draw dots
            "    drawDot(sx, sy, 8, pulse);\n"
            "    if (ease > 0.95) drawDot(ex, ey, 8, pulse);\n"
            # Traveling particle along curve
            "    if (ease > 0.1) {\n"
            "        const pp = bezierPt(Math.min(ease, 1) * ((elapsed / 600) % 1));\n"
            "        ctx.beginPath();\n"
            "        ctx.arc(pp.x, pp.y, 4, 0, Math.PI * 2);\n"
            "        ctx.fillStyle = COLOR;\n"
            "        ctx.shadowColor = COLOR;\n"
            "        ctx.shadowBlur = 10;\n"
            "        ctx.fill();\n"
            "        ctx.shadowBlur = 0;\n"
            "    }\n"
            f"    if (elapsed < {lifetime}) requestAnimationFrame(draw);\n"
            "    else canvas.remove();\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
        )
        evaluate_js(iife(js))
