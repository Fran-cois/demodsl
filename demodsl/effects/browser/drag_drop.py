"""Drag-and-drop accentuated — massive shadow + rotation on a dragged element."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class DragDropEffect(BrowserEffect):
    effect_id = "drag_drop"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        intensity = sanitize_number(
            params.get("intensity", 0.7), default=0.7, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)
        shadow_blur = int(20 + intensity * 40)
        rotation = round(2 + intensity * 4, 1)
        scale_lift = round(1.02 + intensity * 0.06, 2)

        css = (
            "@keyframes __demodsl_dd_float {\n"
            f"  0%   {{ transform: scale(1) rotate(0deg); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}\n"
            f"  30%  {{ transform: scale({scale_lift}) rotate({rotation}deg);\n"
            f"          box-shadow: 0 {shadow_blur}px {shadow_blur * 2}px {color}44; }}\n"
            f"  70%  {{ transform: scale({scale_lift}) rotate(-{rotation * 0.5}deg);\n"
            f"          box-shadow: 0 {shadow_blur}px {shadow_blur * 2}px {color}44; }}\n"
            f"  100% {{ transform: scale(1) rotate(0deg); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}\n"
            "}\n"
            ".__demodsl_dd_ghost {\n"
            "  position: fixed; z-index: 99998; pointer-events: none;\n"
            "  border-radius: 12px; overflow: hidden;\n"
            f"  border: 2px solid {color}55;\n"
            "}\n"
            ".__demodsl_dd_dropzone {\n"
            "  position: fixed; z-index: 99997; pointer-events: none;\n"
            "  border-radius: 12px;\n"
            f"  border: 2px dashed {color}88;\n"
            f"  background: {color}11;\n"
            "  transition: all 0.3s ease;\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_dd_style", css)
            # Create a card-like element to "drag"
            + "const card = document.createElement('div');\n"
            "card.id = '__demodsl_drag_drop';\n"
            "card.className = '__demodsl_dd_ghost';\n"
            "card.style.cssText = `\n"
            "    left: 15%; top: 30%; width: 220px; height: 140px;\n"
            f"    background: linear-gradient(135deg, {color}22, {color}44);\n"
            "    backdrop-filter: blur(4px);\n"
            f"    box-shadow: 0 4px 12px {color}33;\n"
            "`;\n"
            # Inner content SVG (file icon)
            'card.innerHTML = \'<svg width="40" height="40" viewBox="0 0 24 24" '
            'style="margin:50px auto;display:block;opacity:0.6" '
            f'fill="{color}">'
            '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"/>'
            '<path d="M14 2v6h6" fill="none" stroke="white" stroke-width="1"/>'
            "</svg>';\n"
            "document.body.appendChild(card);\n"
            # Drop zone
            "const zone = document.createElement('div');\n"
            "zone.className = '__demodsl_dd_dropzone';\n"
            "zone.style.cssText = 'left:60%; top:25%; width:250px; height:180px;';\n"
            "zone.innerHTML = '<div style=\"text-align:center;padding-top:70px;font-size:14px;"
            f"color:{color};opacity:0.6\">Drop here</div>';\n"
            "document.body.appendChild(zone);\n"
            # Animated drag path
            "const startX = window.innerWidth * 0.15;\n"
            "const startY = window.innerHeight * 0.3;\n"
            "const endX = window.innerWidth * 0.6 + 15;\n"
            "const endY = window.innerHeight * 0.25 + 20;\n"
            f"const moveTime = {int(lifetime * 0.5)};\n"
            "const t0 = performance.now();\n"
            "function animDrag() {\n"
            "    const elapsed = performance.now() - t0;\n"
            "    const t = Math.min(1, elapsed / moveTime);\n"
            # Eased movement
            "    const ease = t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t+2, 2)/2;\n"
            "    const cx = startX + (endX - startX) * ease;\n"
            "    const cy = startY + (endY - startY) * ease;\n"
            # Rotation and shadow during drag
            f"    const rot = Math.sin(t * Math.PI) * {rotation};\n"
            f"    const sc = 1 + Math.sin(t * Math.PI) * {round(scale_lift - 1, 2)};\n"
            f"    const sh = Math.sin(t * Math.PI) * {shadow_blur};\n"
            "    card.style.left = cx + 'px';\n"
            "    card.style.top = cy + 'px';\n"
            "    card.style.transform = `scale(${sc}) rotate(${rot}deg)`;\n"
            f"    card.style.boxShadow = `0 ${{sh}}px ${{sh*2}}px {color}44`;\n"
            # Dropzone glow when near
            "    if (t > 0.6) {\n"
            f"        zone.style.borderColor = '{color}';\n"
            f"        zone.style.background = '{color}22';\n"
            f"        zone.style.boxShadow = '0 0 20px {color}44';\n"
            "    }\n"
            "    if (t < 1) requestAnimationFrame(animDrag);\n"
            "    else {\n"
            # Drop animation
            "        card.style.transform = 'scale(0.95) rotate(0deg)';\n"
            "        card.style.transition = 'all 0.3s ease';\n"
            "        card.style.opacity = '0.7';\n"
            f"        zone.style.borderColor = '#22c55e';\n"
            f"        zone.style.background = '#22c55e22';\n"
            "    }\n"
            "}\n"
            "requestAnimationFrame(animDrag);\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    card.remove(); zone.remove();\n"
            "    document.getElementById('__demodsl_dd_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
