"""Typewriter effect — blinking caret on input/textarea elements."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class TypewriterEffect(BrowserEffect):
    effect_id = "typewriter"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        caret_color = sanitize_css_color(params.get("caret_color", "#333"))
        blink_speed = sanitize_number(
            params.get("blink_speed", 0.7), default=0.7, min_val=0.2, max_val=3.0
        )
        bg_color = sanitize_css_color(params.get("bg_color", "rgba(0,0,0,0.75)"))
        text_color = sanitize_css_color(params.get("text_color", "#fff"))
        font_size = int(
            sanitize_number(params.get("font_size", 18), default=18, min_val=10, max_val=48)
        )
        label = params.get("label", "demodsl run demo.yaml — generating video...")

        evaluate_js(
            iife(
                inject_style(
                    "__demodsl_typewriter",
                    f"input, textarea {{\n"
                    f"    caret-color: {caret_color};\n"
                    f"    animation: demodsl-blink {blink_speed}s step-end infinite;\n"
                    f"}}\n"
                    f"@keyframes demodsl-blink {{ 50% {{ caret-color: transparent; }} }}",
                )
                + "// Fallback: if no input/textarea on page, show a visual typing indicator\n"
                + "if (!document.querySelector('input, textarea')) {\n"
                + "    const ind = document.createElement('div');\n"
                + "    ind.id = '__demodsl_typewriter_indicator';\n"
                + "    ind.style.cssText = 'position:fixed; bottom:40px; left:50%; "
                + f"transform:translateX(-50%); background:{bg_color}; color:{text_color}; "
                + f"padding:12px 24px; border-radius:8px; font-family:monospace; font-size:{font_size}px; "
                + "z-index:99999; pointer-events:none; display:flex; align-items:center; gap:2px; "
                + "min-width:300px;';\n"
                + "    const textSpan = document.createElement('span');\n"
                + "    const caret = document.createElement('span');\n"
                + f"    caret.style.cssText = 'display:inline-block;width:2px;height:20px;background:{text_color};"
                + f"animation:demodsl-blink-bar {blink_speed}s step-end infinite;';\n"
                + "    ind.appendChild(textSpan);\n"
                + "    ind.appendChild(caret);\n"
                + "    const s2 = document.createElement('style');\n"
                + "    s2.textContent = '@keyframes demodsl-blink-bar { 50% { opacity:0; } }';\n"
                + "    document.head.appendChild(s2);\n"
                + "    document.body.appendChild(ind);\n"
                + f"    const fullText = '{label}';\n"
                + "    let ci = 0;\n"
                + "    function typeNext() {\n"
                + "        if (ci < fullText.length) {\n"
                + "            textSpan.textContent += fullText[ci];\n"
                + "            ci++;\n"
                + "            setTimeout(typeNext, 50 + Math.random() * 60);\n"
                + "        }\n"
                + "    }\n"
                + "    typeNext();\n"
                + "}\n"
            )
        )
