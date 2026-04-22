"""Morphing background effect — slowly morphing animated gradient."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_css_colors_list


class MorphingBackgroundEffect(BrowserEffect):
    effect_id = "morphing_background"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        colors = params.get("colors", ["#667eea", "#764ba2", "#f093fb", "#667eea"])
        safe_colors = (
            sanitize_css_colors_list(colors)
            if isinstance(colors, list)
            else [sanitize_css_color(colors)]
        )
        colors_css = ", ".join(safe_colors)
        css = (
            f"body::before {{\n"
            f"    content: ''; position: fixed; top: 0; left: 0;\n"
            f"    width: 100%; height: 100%; z-index: -1;\n"
            f"    background: linear-gradient(135deg, {colors_css});\n"
            f"    background-size: 400% 400%;\n"
            f"    animation: demodsl_morph 8s ease infinite;\n"
            f"}}\n"
            f"@keyframes demodsl_morph {{\n"
            f"    0%   {{ background-position: 0% 50%; }}\n"
            f"    50%  {{ background-position: 100% 50%; }}\n"
            f"    100% {{ background-position: 0% 50%; }}\n"
            f"}}"
        )
        evaluate_js(iife(inject_style("__demodsl_morphing_bg", css)))
