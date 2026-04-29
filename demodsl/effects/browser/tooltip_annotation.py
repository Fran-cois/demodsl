"""Tooltip annotation effect — floating tooltip on hovered elements."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_js_string


class TooltipAnnotationEffect(BrowserEffect):
    effect_id = "tooltip_annotation"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        text = sanitize_js_string(params.get("text", "Click here"))
        color = sanitize_css_color(params.get("color", "#6C5CE7"))
        css = (
            f"@keyframes __demodsl_tip_pulse {{\n"
            f"  0%, 100% {{ box-shadow: 0 4px 20px {color}88, 0 0 30px {color}44; }}\n"
            f"  50% {{ box-shadow: 0 4px 30px {color}bb, 0 0 50px {color}66; }}\n"
            f"}}\n"
            f".__demodsl_tip {{\n"
            f"    position: absolute; padding: 10px 20px;\n"
            f"    background: {color}; color: #fff; border-radius: 8px;\n"
            f"    font-size: 16px; font-weight: 600; pointer-events: none; z-index: 99999;\n"
            f"    opacity: 0; transition: opacity 0.25s ease;\n"
            f"    white-space: nowrap;\n"
            f"    box-shadow: 0 4px 20px {color}88, 0 0 30px {color}44;\n"
            f"    animation: __demodsl_tip_pulse 1.5s ease-in-out infinite;\n"
            f"}}\n"
            f".__demodsl_tip--above::after {{\n"
            f"    content: ''; position: absolute; bottom: -8px; left: 50%;\n"
            f"    transform: translateX(-50%);\n"
            f"    border-left: 8px solid transparent;\n"
            f"    border-right: 8px solid transparent;\n"
            f"    border-top: 8px solid {color};\n"
            f"}}\n"
            f".__demodsl_tip--below::after {{\n"
            f"    content: ''; position: absolute; top: -8px; left: 50%;\n"
            f"    transform: translateX(-50%);\n"
            f"    border-left: 8px solid transparent;\n"
            f"    border-right: 8px solid transparent;\n"
            f"    border-bottom: 8px solid {color};\n"
            f"}}"
        )
        # Helper to position tooltip above or below element, with viewport clamping
        position_fn = (
            "function positionTip(tip, rect) {\n"
            "    const vw = document.documentElement.clientWidth;\n"
            "    let lx = rect.left + rect.width / 2 - tip.offsetWidth / 2 + window.scrollX;\n"
            "    lx = Math.max(8, Math.min(lx, vw - tip.offsetWidth - 8 + window.scrollX));\n"
            "    tip.style.left = lx + 'px';\n"
            "    const above = rect.top - tip.offsetHeight - 10 + window.scrollY;\n"
            "    if (above >= window.scrollY) {\n"
            "        tip.style.top = above + 'px';\n"
            "        tip.classList.remove('__demodsl_tip--below');\n"
            "        tip.classList.add('__demodsl_tip--above');\n"
            "    } else {\n"
            "        tip.style.top = (rect.bottom + 10 + window.scrollY) + 'px';\n"
            "        tip.classList.remove('__demodsl_tip--above');\n"
            "        tip.classList.add('__demodsl_tip--below');\n"
            "    }\n"
            "}\n"
        )
        js = (
            inject_style("__demodsl_tooltip", css)
            + position_fn
            + "const tip = document.createElement('div');\n"
            + "tip.className = '__demodsl_tip';\n"
            + f"tip.textContent = '{text}';\n"
            + "document.body.appendChild(tip);\n"
            + "const firstEl = document.querySelector('button, a, input, [role=\"button\"]');\n"
            + "if (firstEl) {\n"
            + "    const rect = firstEl.getBoundingClientRect();\n"
            + "    positionTip(tip, rect);\n"
            + "    tip.style.opacity = '1';\n"
            + "} else {\n"
            + "    tip.style.position = 'fixed';\n"
            + "    tip.style.top = '60px';\n"
            + "    tip.style.left = '50%';\n"
            + "    tip.style.transform = 'translateX(-50%)';\n"
            + "    tip.classList.add('__demodsl_tip--above');\n"
            + "    tip.style.opacity = '1';\n"
            + "}\n"
            + "document.addEventListener('mouseover', (e) => {\n"
            + "    const el = e.target.closest('button, a, input, [role=\"button\"]');\n"
            + "    if (!el) { tip.style.opacity = '0'; return; }\n"
            + "    const rect = el.getBoundingClientRect();\n"
            + "    tip.style.position = 'absolute';\n"
            + "    tip.style.transform = 'none';\n"
            + "    positionTip(tip, rect);\n"
            + "    tip.style.opacity = '1';\n"
            + "});\n"
        )
        evaluate_js(iife(js))
