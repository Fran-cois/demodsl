"""Highlight effect — hover box-shadow on all elements."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class HighlightEffect(BrowserEffect):
    effect_id = "highlight"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#FFD700"))
        intensity = sanitize_number(
            params.get("intensity", 0.9), default=0.9, min_val=0.0, max_val=1.0
        )
        spread = int(24 * intensity)
        # Paint bright background panels behind visible elements
        evaluate_js(
            iife(
                f"const style = document.createElement('style');\n"
                f"style.id = '__demodsl_highlight_style';\n"
                f"style.textContent = `\n"
                f"@keyframes __demodsl_hl_pulse {{\n"
                f"  0%, 100% {{ box-shadow: 0 0 {spread}px 4px {color}, 0 0 {spread * 3}px 2px {color}66; }}\n"
                f"  50% {{ box-shadow: 0 0 {spread * 2}px 8px {color}, 0 0 {spread * 4}px 4px {color}88; }}\n"
                f"}}\n"
                f".__demodsl_highlighted {{\n"
                f"  outline: 3px solid {color} !important;\n"
                f"  outline-offset: 6px !important;\n"
                f"  box-shadow: 0 0 {spread}px 4px {color}, 0 0 {spread * 3}px 2px {color}66 !important;\n"
                f"  animation: __demodsl_hl_pulse 1.2s ease-in-out infinite !important;\n"
                f"  background-color: {color}18 !important;\n"
                f"}}\n`;\n"
                f"document.head.appendChild(style);\n"
                f"const els = document.querySelectorAll("
                f"'h1,h2,h3,h4,p,a,button,img,section,article,nav,header,footer'"
                f");\n"
                f"let count = 0;\n"
                f"els.forEach(el => {{\n"
                f"  const rect = el.getBoundingClientRect();\n"
                f"  if (rect.width > 50 && rect.height > 15 && rect.top < window.innerHeight && rect.bottom > 0) {{\n"
                f"    el.classList.add('__demodsl_highlighted');\n"
                f"    count++;\n"
                f"    if (count > 30) return;\n"
                f"  }}\n"
                f"}});\n"
            )
        )
