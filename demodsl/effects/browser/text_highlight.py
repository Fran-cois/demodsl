"""Text highlight effect — animated progressive text highlight."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color


class TextHighlightEffect(BrowserEffect):
    effect_id = "text_highlight"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#FFD700"))
        css = (
            f"::selection {{\n"
            f"    background: {color}80;\n"
            f"}}\n"
            f".__demodsl_hl {{\n"
            f"    background: linear-gradient(90deg, {color}60 0%, transparent 100%);\n"
            f"    background-size: 200% 100%;\n"
            f"    background-position: 100% 0;\n"
            f"    animation: demodsl_hl_sweep 1.2s ease forwards;\n"
            f"}}\n"
            f"@keyframes demodsl_hl_sweep {{\n"
            f"    to {{ background-position: 0 0; }}\n"
            f"}}"
        )
        js = (
            inject_style("__demodsl_text_highlight", css)
            + "document.querySelectorAll('p, h1, h2, h3, li, span, a').forEach(el => {\n"
            + "    el.classList.add('__demodsl_hl');\n"
            + "});\n"
        )
        evaluate_js(iife(js))
