"""Magnetic hover effect — elements subtly follow the cursor."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class MagneticHoverEffect(BrowserEffect):
    effect_id = "magnetic_hover"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.3), default=0.3, min_val=0.0, max_val=2.0
        )
        css = (
            "@keyframes __demodsl_mag_pulse {\n"
            "    0%, 100% { transform: translate(0,0) scale(1); "
            "box-shadow: 0 0 8px rgba(99,102,241,0.3); }\n"
            "    25% { transform: translate(5px,-4px) scale(1.12); "
            "box-shadow: 0 0 28px rgba(99,102,241,0.7), 0 0 56px rgba(99,102,241,0.35); }\n"
            "    50% { transform: translate(-4px,3px) scale(1.08); "
            "box-shadow: 0 0 22px rgba(139,92,246,0.6), 0 0 44px rgba(139,92,246,0.3); }\n"
            "    75% { transform: translate(3px,5px) scale(1.15); "
            "box-shadow: 0 0 32px rgba(99,102,241,0.8), 0 0 64px rgba(99,102,241,0.4); }\n"
            "}\n"
            ".__demodsl_magnetic_active {\n"
            "    animation: __demodsl_mag_pulse 1.8s ease-in-out infinite !important;\n"
            "    outline: 2px solid rgba(99,102,241,0.5) !important;\n"
            "    outline-offset: 4px !important;\n"
            "}\n"
        )
        js = (
            inject_style("__demodsl_magnetic_hover", css)
            + f"const strength = {intensity} * 30;\n"
            + "const els = document.querySelectorAll('button, a, [role=\"button\"], .btn');\n"
            + "els.forEach(el => {\n"
            + "    el.addEventListener('mousemove', (e) => {\n"
            + "        const rect = el.getBoundingClientRect();\n"
            + "        const cx = rect.left + rect.width / 2;\n"
            + "        const cy = rect.top + rect.height / 2;\n"
            + "        const dx = (e.clientX - cx) / rect.width;\n"
            + "        const dy = (e.clientY - cy) / rect.height;\n"
            + "        el.style.transform = `translate(${dx * strength}px, ${dy * strength}px) scale(1.05)`;\n"
            + "    });\n"
            + "    el.addEventListener('mouseleave', () => {\n"
            + "        el.style.transform = 'translate(0, 0) scale(1)';\n"
            + "    });\n"
            + "});\n"
            + "// Auto-animate visible interactive elements for recording\n"
            + "const visible = [...els].filter(el => {\n"
            + "    const r = el.getBoundingClientRect();\n"
            + "    return r.width > 30 && r.height > 10 && r.top < window.innerHeight && r.bottom > 0;\n"
            + "}).slice(0, 10);\n"
            + "visible.forEach((el, i) => {\n"
            + "    el.style.animationDelay = (i * 0.2) + 's';\n"
            + "    el.classList.add('__demodsl_magnetic_active');\n"
            + "});\n"
        )
        evaluate_js(iife(js))
