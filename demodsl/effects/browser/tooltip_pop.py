"""Tooltip pop — bouncing tooltip bubbles on element hover."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_js_string,
    sanitize_number,
)


class TooltipPopEffect(BrowserEffect):
    effect_id = "tooltip_pop"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        text = sanitize_js_string(params.get("text", "Hover me!"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)

        css = (
            "@keyframes __demodsl_tpop_bounce {\n"
            "  0%   { transform: translateX(-50%) scale(0); opacity: 0; }\n"
            "  50%  { transform: translateX(-50%) scale(1.15); opacity: 1; }\n"
            "  70%  { transform: translateX(-50%) scale(0.95); }\n"
            "  85%  { transform: translateX(-50%) scale(1.05); }\n"
            "  100% { transform: translateX(-50%) scale(1); opacity: 1; }\n"
            "}\n"
            ".__demodsl_tpop {\n"
            f"  position: absolute; padding: 8px 16px; background: {color};\n"
            "  color: #fff; border-radius: 8px; font-size: 14px; font-weight: 600;\n"
            "  pointer-events: none; z-index: 99999; white-space: nowrap;\n"
            "  transform-origin: bottom center;\n"
            "  animation: __demodsl_tpop_bounce 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;\n"
            f"  box-shadow: 0 4px 16px {color}66;\n"
            "}\n"
            ".__demodsl_tpop::after {\n"
            "  content: ''; position: absolute; bottom: -6px; left: 50%;\n"
            "  transform: translateX(-50%);\n"
            "  border-left: 6px solid transparent;\n"
            "  border-right: 6px solid transparent;\n"
            f"  border-top: 6px solid {color};\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_tpop_style", css) + "let activeTip = null;\n"
            "function showTip(el) {\n"
            "    if (activeTip) activeTip.remove();\n"
            "    const tip = document.createElement('div');\n"
            "    tip.className = '__demodsl_tpop';\n"
            f"    tip.textContent = '{text}';\n"
            "    document.body.appendChild(tip);\n"
            "    const rect = el.getBoundingClientRect();\n"
            "    tip.style.left = (rect.left + rect.width / 2 + window.scrollX) + 'px';\n"
            "    tip.style.top = (rect.top - tip.offsetHeight - 10 + window.scrollY) + 'px';\n"
            "    activeTip = tip;\n"
            "}\n"
            "function hideTip() {\n"
            "    if (activeTip) { activeTip.remove(); activeTip = null; }\n"
            "}\n"
            # Mouseover handler
            "document.addEventListener('mouseover', (e) => {\n"
            '    const el = e.target.closest(\'button, a, [role="button"], .btn, input[type="submit"]\');\n'
            "    if (el) showTip(el); else hideTip();\n"
            "});\n"
            # Auto-demo: cycle through first few interactive elements
            "const demoEls = document.querySelectorAll('button, a[href], [role=\"button\"]');\n"
            "const targets = Array.from(demoEls).slice(0, 4);\n"
            "targets.forEach((el, i) => {\n"
            "    setTimeout(() => showTip(el), 400 + i * 600);\n"
            "});\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    hideTip();\n"
            "    document.getElementById('__demodsl_tpop_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
