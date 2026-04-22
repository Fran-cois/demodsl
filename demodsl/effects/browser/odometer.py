"""Odometer — rolling digit counter animation."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class OdometerEffect(BrowserEffect):
    effect_id = "odometer"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 3.5), default=3.5, min_val=1.0, max_val=10.0
        )
        target_val = int(
            sanitize_number(
                params.get("scale", 42857), default=42857, min_val=0, max_val=9999999
            )
        )
        lifetime = int(duration * 1000)
        roll_time = int(lifetime * 0.65)
        digits = list(str(target_val))
        digit_h = 48

        css = (
            ".__demodsl_odo_digit {\n"
            "  display: inline-block; overflow: hidden;\n"
            f"  width: 36px; height: {digit_h}px; margin: 0 2px;\n"
            "  background: rgba(20,20,30,0.95); border-radius: 6px;\n"
            f"  box-shadow: 0 2px 8px rgba(0,0,0,0.3), inset 0 0 0 1px {color}22;\n"
            "  position: relative;\n"
            "}\n"
            ".__demodsl_odo_strip {\n"
            "  position: absolute; left: 0; width: 100%;\n"
            f"  transition: top {round(roll_time / 1000, 1)}s cubic-bezier(0.22, 1, 0.36, 1);\n"
            "}\n"
            ".__demodsl_odo_num {\n"
            f"  height: {digit_h}px; line-height: {digit_h}px;\n"
            f"  font-size: 32px; font-weight: 700; color: {color};\n"
            "  text-align: center;\n"
            "  font-variant-numeric: tabular-nums;\n"
            "  font-family: -apple-system, BlinkMacSystemFont, monospace;\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_odo_style", css)
            + "const container = document.createElement('div');\n"
            "container.id = '__demodsl_odometer';\n"
            "container.style.cssText = `\n"
            "    position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);\n"
            "    z-index:99999; pointer-events:none;\n"
            "    display:flex; align-items:center; gap:0;\n"
            "    padding:16px 20px; border-radius:16px;\n"
            "    background:rgba(10,10,20,0.9);\n"
            f"    box-shadow:0 8px 32px {color}22;\n"
            "`;\n"
            "document.body.appendChild(container);\n"
            f"const DIGITS = {digits};\n"
            f"const DIGIT_H = {digit_h};\n"
            "const strips = [];\n"
            "DIGITS.forEach((d, i) => {\n"
            "    const box = document.createElement('div');\n"
            "    box.className = '__demodsl_odo_digit';\n"
            "    const strip = document.createElement('div');\n"
            "    strip.className = '__demodsl_odo_strip';\n"
            # Build digit strip 0-9
            "    for (let n = 0; n <= 9; n++) {\n"
            "        const cell = document.createElement('div');\n"
            "        cell.className = '__demodsl_odo_num';\n"
            "        cell.textContent = n;\n"
            "        strip.appendChild(cell);\n"
            "    }\n"
            # Start at 0
            "    strip.style.top = '0px';\n"
            "    box.appendChild(strip);\n"
            "    container.appendChild(box);\n"
            "    strips.push({strip, target: parseInt(d)});\n"
            "});\n"
            # Trigger roll after paint
            "requestAnimationFrame(() => {\n"
            "    strips.forEach((s, i) => {\n"
            "        setTimeout(() => {\n"
            "            s.strip.style.top = -(s.target * DIGIT_H) + 'px';\n"
            "        }, i * 80);\n"
            "    });\n"
            "});\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    container.style.transition = 'opacity 0.4s ease';\n"
            "    container.style.opacity = '0';\n"
            "    setTimeout(() => {\n"
            "        container.remove();\n"
            "        document.getElementById('__demodsl_odo_style')?.remove();\n"
            f"    }}, 500);\n"
            f"}}, {lifetime - 500});\n"
        )
        evaluate_js(iife(js))
