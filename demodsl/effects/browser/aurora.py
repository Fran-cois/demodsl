"""Aurora effect — drifting northern-light ribbons overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import (
    auto_remove_multi,
    create_overlay,
    iife,
    inject_style,
)
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_css_colors_list, sanitize_number


class AuroraEffect(BrowserEffect):
    effect_id = "aurora"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(params.get("duration", 8), default=8, min_val=1.0, max_val=60)
        colors = params.get("colors", ["#00FFA3", "#00C2FF", "#8A5CFF"])
        safe_colors = (
            sanitize_css_colors_list(colors)
            if isinstance(colors, list)
            else [sanitize_css_color(colors)]
        )
        # Always three ribbons — cycle the palette if fewer colors given
        c1, c2, c3 = (safe_colors * 3)[:3]
        intensity = sanitize_number(
            params.get("intensity", 0.5), default=0.5, min_val=0.1, max_val=1.0
        )

        opacity = round(0.25 + intensity * 0.45, 2)
        lifetime_ms = int(duration * 1000)
        drift_s = round(max(4.0, duration / 2), 1)

        css = (
            "#__demodsl_aurora {\n"
            f"    opacity: {opacity};\n"
            "    background:\n"
            f"        radial-gradient(ellipse 80% 40% at 20% 8%, {c1}, transparent 60%),\n"
            f"        radial-gradient(ellipse 70% 35% at 72% 4%, {c2}, transparent 60%),\n"
            f"        radial-gradient(ellipse 95% 45% at 48% 0%, {c3}, transparent 65%);\n"
            "    filter: blur(34px) saturate(1.3);\n"
            f"    animation: __demodsl_aurora_drift {drift_s}s ease-in-out infinite alternate;\n"
            "}\n"
            "@keyframes __demodsl_aurora_drift {\n"
            "    0%   { transform: translateX(-6%) scaleY(1.0); }\n"
            "    50%  { transform: translateX(4%)  scaleY(1.18); }\n"
            "    100% { transform: translateX(6%)  scaleY(0.92); }\n"
            "}"
        )
        js = (
            inject_style("__demodsl_aurora_style", css)
            + create_overlay("__demodsl_aurora")
            + auto_remove_multi([("style", lifetime_ms), ("overlay", lifetime_ms)])
        )
        evaluate_js(iife(js))
