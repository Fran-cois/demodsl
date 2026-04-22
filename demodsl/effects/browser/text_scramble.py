"""Text scramble effect — hacker-terminal style text convergence."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class TextScrambleEffect(BrowserEffect):
    effect_id = "text_scramble"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        speed = sanitize_number(
            params.get("speed", 50), default=50, min_val=10, max_val=500
        )
        js = (
            "const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*';\n"
            "document.querySelectorAll('h1,h2,h3,p,a,span,button,label').forEach(el => {\n"
            "    if (el.children.length > 0 || el.textContent.trim().length === 0) return;\n"
            "    const original = el.textContent;\n"
            "    let iteration = 0;\n"
            "    const interval = setInterval(() => {\n"
            "        el.textContent = original.split('').map((c, i) => {\n"
            "            if (i < iteration) return original[i];\n"
            "            return chars[Math.floor(Math.random() * chars.length)];\n"
            "        }).join('');\n"
            "        if (iteration >= original.length) clearInterval(interval);\n"
            "        iteration += 1 / 3;\n"
            f"    }}, {speed});\n"
            "});\n"
        )
        evaluate_js(iife(js))
