"""Glass reflection — subtle light reflection sweeping across screen."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class GlassReflectionEffect(BrowserEffect):
    effect_id = "glass_reflection"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.4), default=0.4, min_val=0.05, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=1.0, max_val=10.0
        )
        lifetime = int(duration * 1000)
        sweep_ms = int(lifetime * 0.7)
        alpha = round(0.04 + intensity * 0.08, 3)
        band_width = int(200 + intensity * 200)

        css = (
            "@keyframes __demodsl_glass_sweep {\n"
            f"  0%   {{ left: -{band_width}px; }}\n"
            "  100% { left: calc(100% + 100px); }\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_glass_style", css)
            + "const refl = document.createElement('div');\n"
            "refl.id = '__demodsl_glass_reflection';\n"
            "refl.style.cssText = `\n"
            f"    position:fixed; top:0; width:{band_width}px; height:100%;\n"
            "    z-index:99999; pointer-events:none;\n"
            "    background:linear-gradient(105deg,\n"
            f"        transparent 0%, rgba(255,255,255,{alpha}) 30%,\n"
            f"        rgba(255,255,255,{round(alpha * 2, 3)}) 50%,\n"
            f"        rgba(255,255,255,{alpha}) 70%, transparent 100%);\n"
            f"    animation:__demodsl_glass_sweep {sweep_ms}ms ease-in-out forwards;\n"
            "`;\n"
            "document.body.appendChild(refl);\n"
            # Second subtle pass
            f"setTimeout(() => {{\n"
            "    const r2 = refl.cloneNode();\n"
            "    r2.id = '__demodsl_glass_reflection2';\n"
            "    r2.style.opacity = '0.5';\n"
            f"    r2.style.animation = '__demodsl_glass_sweep {int(sweep_ms * 0.8)}ms ease-in-out forwards';\n"
            "    document.body.appendChild(r2);\n"
            f"    setTimeout(() => r2.remove(), {int(sweep_ms * 0.8) + 100});\n"
            f"}}, {int(sweep_ms * 0.5)});\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    refl.remove();\n"
            "    document.getElementById('__demodsl_glass_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
