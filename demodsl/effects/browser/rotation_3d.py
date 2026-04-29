"""Rotation 3D — rotate the page on the Z/depth axis to reveal layer stacking."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class Rotation3DEffect(BrowserEffect):
    effect_id = "rotation_3d"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        angle = sanitize_number(params.get("angle", 25), default=25, min_val=5, max_val=60)
        duration = sanitize_number(
            params.get("duration", 3.5), default=3.5, min_val=1.0, max_val=10.0
        )
        depth = sanitize_number(params.get("depth", 3), default=3, min_val=1, max_val=6)

        tilt_ms = 800
        hold_ms = max(200, int(duration * 1000) - tilt_ms * 2)
        layer_count = int(depth)

        # We create exploded-view "layer" clones as semi-transparent planes
        # behind the page to show depth stacking
        js = (
            "history.scrollRestoration = 'manual';\n"
            "const el = document.body;\n"
            # Create ghost layers behind
            f"const layers = [];\n"
            f"for (let i = 1; i <= {layer_count}; i++) {{\n"
            "    const layer = document.createElement('div');\n"
            "    layer.className = '__demodsl_3d_layer';\n"
            "    layer.style.cssText = `\n"
            "        position:fixed; top:4%; left:4%; width:92%; height:92%;\n"
            "        border:1px solid rgba(100,100,255,0.15);\n"
            "        background:rgba(100,100,255,0.03);\n"
            "        border-radius:8px; pointer-events:none;\n"
            "        z-index:${99990 - i};\n"
            "        transform: translateZ(${-i * 40}px);\n"
            "        transition: transform 0.8s ease, opacity 0.8s ease;\n"
            "        opacity:0;\n"
            "    `;\n"
            "    document.body.appendChild(layer);\n"
            "    layers.push(layer);\n"
            "}\n"
            # Apply 3D perspective to body
            f"el.style.transition = 'transform {tilt_ms}ms cubic-bezier(0.25,0.46,0.45,0.94)';\n"
            "el.style.transformStyle = 'preserve-3d';\n"
            "requestAnimationFrame(() => {\n"
            f"    el.style.transform = 'perspective(1000px) rotateY({angle}deg)"
            f" rotateX(8deg) scale(0.85)';\n"
            # Show layers with depth offset
            "    layers.forEach((l, i) => {\n"
            "        l.style.opacity = (0.6 - i * 0.1).toFixed(1);\n"
            "        l.style.transform = `translateZ(${-(i+1) * 50}px)`;\n"
            "    });\n"
            "});\n"
            # Hold then revert
            f"setTimeout(() => {{\n"
            f"    el.style.transition = 'transform {tilt_ms}ms cubic-bezier(0.25,0.46,0.45,0.94)';\n"
            "    el.style.transform = '';\n"
            "    el.style.transformStyle = '';\n"
            "    layers.forEach(l => {\n"
            "        l.style.opacity = '0';\n"
            "        l.style.transform = 'translateZ(0)';\n"
            "    });\n"
            f"    setTimeout(() => {{\n"
            "        el.style.transition = '';\n"
            "        layers.forEach(l => l.remove());\n"
            f"    }}, {tilt_ms});\n"
            f"}}, {tilt_ms + hold_ms});\n"
        )
        evaluate_js(iife(js))
