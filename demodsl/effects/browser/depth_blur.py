"""Depth blur (tilt-shift) — blurs top and bottom edges, keeps center sharp."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class DepthBlurEffect(BrowserEffect):
    effect_id = "depth_blur"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.5), default=0.5, min_val=0.1, max_val=1.0
        )
        focus_y = sanitize_number(
            params.get("focus_position", 0.5),
            default=0.5,
            min_val=0.1,
            max_val=0.9,
        )
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=0.5, max_val=15.0
        )

        blur_px = int(intensity * 12)
        lifetime = int(duration * 1000)
        clear_start = max(0, int((focus_y - 0.15) * 100))
        clear_end = min(100, int((focus_y + 0.15) * 100))

        js = (
            "const overlay = document.createElement('div');\n"
            "overlay.id = '__demodsl_depth_blur';\n"
            "overlay.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99998; pointer-events:none;\n"
            f"    backdrop-filter: blur({blur_px}px);\n"
            f"    -webkit-backdrop-filter: blur({blur_px}px);\n"
            f"    -webkit-mask-image: linear-gradient(to bottom, "
            f"black 0%, transparent {clear_start}%, "
            f"transparent {clear_end}%, black 100%);\n"
            f"    mask-image: linear-gradient(to bottom, "
            f"black 0%, transparent {clear_start}%, "
            f"transparent {clear_end}%, black 100%);\n"
            "    opacity:0; transition:opacity 0.5s ease;\n"
            "`;\n"
            "document.body.appendChild(overlay);\n"
            "requestAnimationFrame(() => { overlay.style.opacity = '1'; });\n"
            f"setTimeout(() => {{\n"
            "    overlay.style.opacity = '0';\n"
            "    setTimeout(() => overlay.remove(), 600);\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
