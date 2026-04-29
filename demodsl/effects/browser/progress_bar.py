"""Progress bar effect — animated progress bar overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_css_position,
    sanitize_number,
)


class ProgressBarEffect(BrowserEffect):
    effect_id = "progress_bar"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        position = sanitize_css_position(
            params.get("position", "top"), allowed=frozenset({"top", "bottom"})
        )
        height = sanitize_number(params.get("intensity", 6), default=6, min_val=2, max_val=20)
        duration = sanitize_number(
            params.get("duration", 2.5), default=2.5, min_val=0.1, max_val=30
        )
        pos_css = "top:0" if position == "top" else "bottom:0"
        duration_ms = int(duration * 1000)
        js = (
            "const bar = document.createElement('div');\n"
            "bar.id = '__demodsl_progress_bar';\n"
            f"bar.style.cssText = `\n"
            f"    position:fixed; left:0; {pos_css};\n"
            f"    width:0%; height:{height}px;\n"
            f"    background: linear-gradient(90deg, {color}, {color}cc);\n"
            f"    z-index:99999; pointer-events:none;\n"
            f"    box-shadow: 0 0 12px {color}88, 0 0 4px {color}44;\n"
            f"`;\n"
            "document.body.appendChild(bar);\n"
            "window.__demodsl_progress_set = (pct) => {\n"
            "    bar.style.width = Math.min(100, Math.max(0, pct)) + '%';\n"
            "};\n"
            "// Auto-animate from 0% to 100%\n"
            f"const dur = {duration_ms};\n"
            "const t0 = performance.now();\n"
            "function tick(now) {\n"
            "    const p = Math.min(1, (now - t0) / dur);\n"
            "    bar.style.width = (p * 100).toFixed(1) + '%';\n"
            "    if (p < 1) requestAnimationFrame(tick);\n"
            "}\n"
            "requestAnimationFrame(tick);\n"
        )
        evaluate_js(iife(js))
