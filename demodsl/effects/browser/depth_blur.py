"""Depth blur (tilt-shift) — blurs top and bottom edges, keeps center sharp.

With ``focus_position_to`` the sharp band travels across the page over the
effect's lifetime: a rack focus, the move an operator makes to hand the
viewer's eye from one part of the screen to another.
"""

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
        focus_to_raw = params.get("focus_position_to")
        focus_to = (
            sanitize_number(focus_to_raw, default=focus_y, min_val=0.1, max_val=0.9)
            if focus_to_raw is not None
            else None
        )

        blur_px = int(intensity * 12)
        lifetime = int(duration * 1000)
        clear_start = max(0, int((focus_y - 0.15) * 100))
        clear_end = min(100, int((focus_y + 0.15) * 100))

        # The mask travels only when a destination was asked for; otherwise the
        # band is written once and the effect stays the static tilt-shift.
        pull_js = ""
        if focus_to is not None and abs(focus_to - focus_y) > 0.01:
            # Hold the first framing briefly, pull, then let the tail breathe.
            pull_ms = max(400, int(lifetime * 0.45))
            pull_js = (
                f"const FROM = {focus_y}, TO = {focus_to}, PULL = {pull_ms};\n"
                f"const START = performance.now() + {int(lifetime * 0.2)};\n"
                "function band(y) {\n"
                "    const a = Math.max(0, (y - 0.15) * 100);\n"
                "    const b = Math.min(100, (y + 0.15) * 100);\n"
                "    const m = `linear-gradient(to bottom, black 0%, "
                "transparent ${a}%, transparent ${b}%, black 100%)`;\n"
                "    overlay.style.webkitMaskImage = m;\n"
                "    overlay.style.maskImage = m;\n"
                "}\n"
                "function pull(now) {\n"
                "    if (!overlay.isConnected) return;\n"
                "    const t = Math.min(Math.max((now - START) / PULL, 0), 1);\n"
                "    const e = t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2) / 2;\n"
                "    band(FROM + (TO - FROM) * e);\n"
                "    if (t < 1) requestAnimationFrame(pull);\n"
                "}\n"
                "requestAnimationFrame(pull);\n"
            )

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
            f"{pull_js}"
            f"setTimeout(() => {{\n"
            "    overlay.style.opacity = '0';\n"
            "    setTimeout(() => overlay.remove(), 600);\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
