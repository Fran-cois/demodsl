"""Magnifier — circular lens following the cursor that magnifies content."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class MagnifierEffect(BrowserEffect):
    effect_id = "magnifier"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        scale = sanitize_number(
            params.get("scale", 2.0), default=2.0, min_val=1.2, max_val=5.0
        )
        radius = int(
            sanitize_number(
                params.get("radius", 80), default=80, min_val=30, max_val=200
            )
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)
        diameter = radius * 2

        css = (
            "#__demodsl_magnifier {\n"
            f"  position: fixed; width: {diameter}px; height: {diameter}px;\n"
            f"  border: 3px solid {color}; border-radius: 50%;\n"
            "  overflow: hidden; pointer-events: none; z-index: 99999;\n"
            f"  box-shadow: 0 0 20px {color}44, 0 4px 12px rgba(0,0,0,0.3);\n"
            "  opacity: 0; transition: opacity 0.3s ease;\n"
            "  will-change: left, top;\n"
            "}\n"
            "#__demodsl_magnifier_inner {\n"
            "  position: absolute; top: 0; left: 0;\n"
            f"  width: {diameter}px; height: {diameter}px;\n"
            "  overflow: hidden;\n"
            "}\n"
            "#__demodsl_magnifier_clone {\n"
            f"  transform-origin: 0 0;\n"
            f"  transform: scale({scale});\n"
            "  position: absolute;\n"
            "  pointer-events: none;\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_magnifier_style", css)
            + "const lens = document.createElement('div');\n"
            "lens.id = '__demodsl_magnifier';\n"
            "const inner = document.createElement('div');\n"
            "inner.id = '__demodsl_magnifier_inner';\n"
            "lens.appendChild(inner);\n"
            "document.body.appendChild(lens);\n"
            # Use a cloned snapshot of the body for magnification
            f"const RADIUS = {radius};\n"
            f"const SCALE = {scale};\n"
            "function updateLens(mx, my) {\n"
            "    lens.style.left = (mx - RADIUS) + 'px';\n"
            "    lens.style.top = (my - RADIUS) + 'px';\n"
            "    lens.style.opacity = '1';\n"
            # Use background-image approach with element() not supported everywhere;
            # Instead use clip + transform on a full-page screenshot-like clone
            # Simplest: use the page itself via an offset trick
            "    inner.innerHTML = '';\n"
            "    const clone = document.createElement('div');\n"
            "    clone.id = '__demodsl_magnifier_clone';\n"
            "    clone.style.width = document.documentElement.scrollWidth + 'px';\n"
            "    clone.style.height = document.documentElement.scrollHeight + 'px';\n"
            # Copy the page HTML into the clone
            "    clone.innerHTML = document.body.innerHTML;\n"
            # Remove the magnifier itself from clone to avoid recursion
            "    const selfClone = clone.querySelector('#__demodsl_magnifier');\n"
            "    if (selfClone) selfClone.remove();\n"
            # Position the clone so the mouse area is centered in the lens
            "    const sx = window.scrollX;\n"
            "    const sy = window.scrollY;\n"
            "    clone.style.left = -(mx + sx) * SCALE + RADIUS + 'px';\n"
            "    clone.style.top = -(my + sy) * SCALE + RADIUS + 'px';\n"
            "    inner.appendChild(clone);\n"
            "}\n"
            # Throttled mousemove
            "let lastMove = 0;\n"
            "document.addEventListener('mousemove', (e) => {\n"
            "    const now = performance.now();\n"
            "    if (now - lastMove < 50) return;\n"
            "    lastMove = now;\n"
            "    updateLens(e.clientX, e.clientY);\n"
            "});\n"
            # Auto-demo path
            + simulate_mouse_path(duration_s=min(duration - 0.5, 3.0), steps=60)
            # Cleanup
            + f"setTimeout(() => {{\n"
            "    lens.remove();\n"
            "    document.getElementById('__demodsl_magnifier_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
