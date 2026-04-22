"""Matrix rain effect — falling characters Matrix-style on canvas."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_canvas, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class MatrixRainEffect(BrowserEffect):
    effect_id = "matrix_rain"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#00FF41"))
        density = sanitize_number(
            params.get("density", 0.6), default=0.6, min_val=0.1, max_val=2.0
        )
        speed = sanitize_number(
            params.get("speed", 1.0), default=1.0, min_val=0.1, max_val=5.0
        )
        max_frames = int(
            sanitize_number(
                params.get("duration", 5), default=5, min_val=0.5, max_val=30
            )
            * 60
        )
        setup = (
            "const fontSize = 14;\n"
            f"const cols = Math.floor(canvas.width / fontSize * {density});\n"
            "const drops = Array.from({length: cols}, () => Math.random() * -100);\n"
            "const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZアイウエオカキクケコ0123456789@#$%^&*';\n"
            "function draw() {\n"
            "    ctx.fillStyle = 'rgba(0,0,0,0.05)';\n"
            "    ctx.fillRect(0, 0, canvas.width, canvas.height);\n"
            f"    ctx.fillStyle = '{color}';\n"
            "    ctx.font = fontSize + 'px monospace';\n"
            "    for (let i = 0; i < cols; i++) {\n"
            "        const ch = chars[Math.floor(Math.random() * chars.length)];\n"
            f"        const x = (i / {density}) * fontSize;\n"
            "        ctx.fillText(ch, x, drops[i] * fontSize);\n"
            "        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975)\n"
            "            drops[i] = 0;\n"
            f"        drops[i] += {speed};\n"
            "    }\n"
            "    if (++frame < maxF) requestAnimationFrame(draw);\n"
            "    else canvas.remove();\n"
            "}\n"
        )
        evaluate_js(iife(create_canvas("__demodsl_matrix_rain", setup, max_frames)))
