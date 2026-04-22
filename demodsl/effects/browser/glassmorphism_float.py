"""Glassmorphism float — translucent floating panel with blur and light refraction."""

from __future__ import annotations

import html
from typing import Any

from demodsl.effects.js_builder import auto_remove_multi, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_css_position,
    sanitize_number,
)


class GlassmorphismFloatEffect(BrowserEffect):
    effect_id = "glassmorphism_float"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        position = sanitize_css_position(
            params.get("position", "center"),
            allowed=frozenset(
                {
                    "center",
                    "top",
                    "bottom",
                    "top-right",
                    "top-left",
                    "bottom-right",
                    "bottom-left",
                }
            ),
        )
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=0.5, max_val=15.0
        )
        text_raw = params.get("text") or ""
        safe_text = html.escape(str(text_raw)) if text_raw else ""
        lifetime = int(duration * 1000)
        blur_px = int(intensity * 24)

        pos_map = {
            "center": "top:50%;left:50%;transform:translate(-50%,-50%) scale(0.8)",
            "top": "top:60px;left:50%;transform:translateX(-50%) scale(0.8)",
            "bottom": "bottom:60px;left:50%;transform:translateX(-50%) scale(0.8)",
            "top-right": "top:40px;right:40px;transform:scale(0.8)",
            "top-left": "top:40px;left:40px;transform:scale(0.8)",
            "bottom-right": "bottom:40px;right:40px;transform:scale(0.8)",
            "bottom-left": "bottom:40px;left:40px;transform:scale(0.8)",
        }
        pos_css = pos_map.get(position, pos_map["center"])

        text_el = ""
        if safe_text:
            text_el = (
                f"panel.innerHTML = '<div style=\"color:#fff;font-size:16px;"
                f"font-weight:500;font-family:-apple-system,system-ui,sans-serif;"
                f'text-align:center;text-shadow:0 1px 4px rgba(0,0,0,0.3);">'
                f"{safe_text}</div>';\n"
            )

        js = (
            "const panel = document.createElement('div');\n"
            "panel.id = '__demodsl_glassmorphism_float';\n"
            f"panel.style.cssText = `\n"
            f"    position:fixed; {pos_css};\n"
            f"    width:320px; min-height:120px;\n"
            f"    padding:28px 32px;\n"
            f"    border-radius:20px;\n"
            f"    background: rgba(255,255,255,0.08);\n"
            f"    backdrop-filter: blur({blur_px}px) saturate(180%);\n"
            f"    -webkit-backdrop-filter: blur({blur_px}px) saturate(180%);\n"
            f"    border: 1px solid rgba(255,255,255,0.18);\n"
            f"    box-shadow: 0 8px 32px rgba(0,0,0,0.15),\n"
            f"                inset 0 1px 0 rgba(255,255,255,0.25),\n"
            f"                0 0 60px {color}22;\n"
            f"    z-index:99999; pointer-events:none;\n"
            f"    opacity:0;\n"
            f"    transition: opacity 0.5s ease, transform 0.6s cubic-bezier(0.34,1.56,0.64,1);\n"
            "`;\n" + text_el + "document.body.appendChild(panel);\n"
            # Light refraction shimmer
            "const shimmer = document.createElement('div');\n"
            "shimmer.style.cssText = `\n"
            "    position:absolute; top:0; left:0; width:100%; height:100%;\n"
            "    border-radius:20px; overflow:hidden; pointer-events:none;\n"
            "`;\n"
            "const grad = document.createElement('div');\n"
            "grad.style.cssText = `\n"
            "    position:absolute; top:-50%; left:-50%; width:200%; height:200%;\n"
            f"    background: conic-gradient(from 0deg, transparent, {color}15, transparent, {color}10, transparent);\n"
            "    animation: __demodsl_glass_spin 4s linear infinite;\n"
            "`;\n"
            "shimmer.appendChild(grad);\n"
            "panel.appendChild(shimmer);\n"
            # Keyframes for the spinning refraction
            "const style = document.createElement('style');\n"
            "style.id = '__demodsl_glassmorphism_float_style';\n"
            "style.textContent = `\n"
            "    @keyframes __demodsl_glass_spin {\n"
            "        from { transform: rotate(0deg); }\n"
            "        to { transform: rotate(360deg); }\n"
            "    }\n"
            "    @keyframes __demodsl_glass_float {\n"
            "        0%, 100% { transform: translateY(0px); }\n"
            "        50% { transform: translateY(-8px); }\n"
            "    }\n"
            "`;\n"
            "document.head.appendChild(style);\n"
            # Animate in — just update opacity + scale via transform
            "requestAnimationFrame(() => {\n"
            "    panel.style.opacity = '1';\n"
            "    panel.style.transform = panel.style.transform.replace('scale(0.8)', 'scale(1)');\n"
            "});\n"
            # Fade out before removal
            f"setTimeout(() => {{\n"
            "    panel.style.opacity = '0';\n"
            "    panel.style.transform += ' scale(0.9)';\n"
            f"}}, {lifetime - 500});\n"
            + auto_remove_multi(
                [
                    ("panel", lifetime),
                    ("style", lifetime),
                ]
            )
        )
        evaluate_js(iife(js))
