"""Click ripple — colored shockwave ring at each click."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class ClickRippleEffect(BrowserEffect):
    effect_id = "click_ripple"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        intensity = sanitize_number(
            params.get("intensity", 0.7), default=0.7, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)
        ring_size = int(100 + intensity * 200)
        ring_width = max(2, int(2 + intensity * 4))

        css = (
            "@keyframes __demodsl_clickrip {\n"
            f"  0%   {{ width:0; height:0; opacity:1; border-width:{ring_width}px; }}\n"
            f"  100% {{ width:{ring_size}px; height:{ring_size}px; opacity:0; border-width:1px; }}\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_click_ripple_style", css) + "function spawnRipple(x, y) {\n"
            "    const r = document.createElement('div');\n"
            "    r.style.cssText = `\n"
            "        position:fixed; border-radius:50%; pointer-events:none;\n"
            "        z-index:99999;\n"
            f"        border:{ring_width}px solid {color};\n"
            f"        box-shadow: 0 0 12px {color}66, inset 0 0 6px {color}33;\n"
            "        left:${x}px; top:${y}px;\n"
            "        transform:translate(-50%,-50%);\n"
            "        animation: __demodsl_clickrip 0.6s ease-out forwards;\n"
            "    `;\n"
            "    document.body.appendChild(r);\n"
            "    setTimeout(() => r.remove(), 700);\n"
            "}\n"
            "function onClick(e) { spawnRipple(e.clientX, e.clientY); }\n"
            "document.addEventListener('click', onClick, true);\n"
            # Auto-demo clicks
            "const demos = [\n"
            "    {t:300, x:0.3, y:0.4}, {t:800, x:0.6, y:0.3},\n"
            "    {t:1400, x:0.5, y:0.6}, {t:2000, x:0.7, y:0.5},\n"
            "];\n"
            "demos.forEach(d => {\n"
            "    setTimeout(() => spawnRipple(\n"
            "        window.innerWidth * d.x, window.innerHeight * d.y\n"
            "    ), d.t);\n"
            "});\n"
            f"setTimeout(() => {{\n"
            "    document.removeEventListener('click', onClick, true);\n"
            "    document.getElementById('__demodsl_click_ripple_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
