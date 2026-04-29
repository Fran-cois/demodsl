"""UI shimmer — shiny highlight sweep across interactive elements."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class UiShimmerEffect(BrowserEffect):
    effect_id = "ui_shimmer"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.5), default=0.5, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 3.5), default=3.5, min_val=1.0, max_val=10.0
        )
        lifetime = int(duration * 1000)
        shimmer_alpha = round(0.15 + intensity * 0.35, 2)
        sweep_duration = round(0.8 + (1 - intensity) * 0.8, 1)

        css = (
            "@keyframes __demodsl_ui_shimmer {\n"
            "  0%   { left: -60%; }\n"
            "  100% { left: 160%; }\n"
            "}\n"
            ".__demodsl_shimmer_target {\n"
            "  position: relative !important;\n"
            "  overflow: hidden !important;\n"
            "}\n"
            ".__demodsl_shimmer_bar {\n"
            "  position: absolute; top: 0; left: -60%; width: 50%; height: 100%;\n"
            "  pointer-events: none; z-index: 99999;\n"
            f"  background: linear-gradient(105deg, transparent 30%,\n"
            f"      rgba(255,255,255,{shimmer_alpha}) 50%, transparent 70%);\n"
            f"  animation: __demodsl_ui_shimmer {sweep_duration}s ease-in-out;\n"
            "  animation-fill-mode: forwards;\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_shimmer_style", css)
            # Find interactive elements to shimmer
            + "const targets = document.querySelectorAll(\n"
            '    \'button, a.btn, [role="button"], input[type="submit"],'
            " .cta, .primary-btn, a[href]'\n"
            ");\n"
            "const els = Array.from(targets).filter(el => {\n"
            "    const r = el.getBoundingClientRect();\n"
            "    return r.width > 30 && r.height > 20 && r.top > 0 && r.top < window.innerHeight;\n"
            "}).slice(0, 8);\n"
            "const bars = [];\n"
            "els.forEach((el, i) => {\n"
            "    el.classList.add('__demodsl_shimmer_target');\n"
            "    const bar = document.createElement('div');\n"
            "    bar.className = '__demodsl_shimmer_bar';\n"
            f"    bar.style.animationDelay = (i * 0.25) + 's';\n"
            "    el.appendChild(bar);\n"
            "    bars.push({el, bar});\n"
            "});\n"
            # Secondary wave
            f"setTimeout(() => {{\n"
            "    els.forEach((el, i) => {\n"
            "        const bar = document.createElement('div');\n"
            "        bar.className = '__demodsl_shimmer_bar';\n"
            f"        bar.style.animationDelay = (i * 0.2) + 's';\n"
            "        el.appendChild(bar);\n"
            "        bars.push({el, bar});\n"
            "    });\n"
            f"}}, {int(lifetime * 0.4)});\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    bars.forEach(b => {\n"
            "        b.bar.remove();\n"
            "        b.el.classList.remove('__demodsl_shimmer_target');\n"
            "    });\n"
            "    document.getElementById('__demodsl_shimmer_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
