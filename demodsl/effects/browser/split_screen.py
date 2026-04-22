"""Split screen — dynamic before/after split view with draggable divider."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class SplitScreenEffect(BrowserEffect):
    effect_id = "split_screen"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        direction = params.get("direction", "vertical")
        if direction not in ("vertical", "horizontal"):
            direction = "vertical"
        lifetime = int(duration * 1000)

        is_v = direction == "vertical"

        css = (
            "@keyframes __demodsl_split_reveal {\n"
            "  0%   { opacity: 0; }\n"
            "  100% { opacity: 1; }\n"
            "}\n"
        )

        # Build labels
        left_label = params.get("text", "Before / After")
        parts = left_label.split("/") if "/" in str(left_label) else ["Before", "After"]
        label_a = parts[0].strip()[:20]
        label_b = parts[1].strip()[:20] if len(parts) > 1 else "After"

        js = (
            inject_style("__demodsl_split_style", css)
            + "const container = document.createElement('div');\n"
            "container.id = '__demodsl_split_screen';\n"
            "container.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99999; pointer-events:none;\n"
            "    animation: __demodsl_split_reveal 0.5s ease;\n"
            "`;\n"
        )

        if is_v:
            # Vertical split: dark overlay on right half
            js += (
                "const overlay = document.createElement('div');\n"
                "overlay.style.cssText = `\n"
                "    position:absolute; top:0; right:0; width:50%; height:100%;\n"
                "    background:rgba(0,0,0,0.08);\n"
                f"    border-left:3px solid {color};\n"
                "`;\n"
                "container.appendChild(overlay);\n"
                # Divider line with handle
                "const handle = document.createElement('div');\n"
                f"handle.style.cssText = 'position:absolute; top:50%; left:-16px;"
                f" width:32px; height:32px; border-radius:50%; background:{color};"
                " transform:translateY(-50%); pointer-events:auto; cursor:ew-resize;"
                f" box-shadow:0 0 12px {color}66; display:flex; align-items:center;"
                " justify-content:center;';\n"
                'handle.innerHTML = \'<svg width="16" height="16" viewBox="0 0 24 24" '
                'fill="white"><path d="M8 5v14l-4-7zM16 5v14l4-7z"/></svg>\';\n'
                "overlay.appendChild(handle);\n"
                # Labels
                f"const labelA = document.createElement('div');\n"
                f"labelA.textContent = '{label_a}';\n"
                f"labelA.style.cssText = `position:absolute; top:12px; left:20px; padding:4px 12px;"
                f" background:{color}; color:#fff; border-radius:4px; font-size:13px;"
                " font-weight:600;`;\n"
                "container.appendChild(labelA);\n"
                f"const labelB = document.createElement('div');\n"
                f"labelB.textContent = '{label_b}';\n"
                f"labelB.style.cssText = `position:absolute; top:12px; right:20px; padding:4px 12px;"
                f" background:{color}cc; color:#fff; border-radius:4px; font-size:13px;"
                " font-weight:600;`;\n"
                "container.appendChild(labelB);\n"
            )
        else:
            # Horizontal split
            js += (
                "const overlay = document.createElement('div');\n"
                "overlay.style.cssText = `\n"
                "    position:absolute; bottom:0; left:0; width:100%; height:50%;\n"
                "    background:rgba(0,0,0,0.08);\n"
                f"    border-top:3px solid {color};\n"
                "`;\n"
                "container.appendChild(overlay);\n"
                "const handle = document.createElement('div');\n"
                f"handle.style.cssText = 'position:absolute; top:-16px; left:50%;"
                f" width:32px; height:32px; border-radius:50%; background:{color};"
                " transform:translateX(-50%); pointer-events:auto; cursor:ns-resize;"
                f" box-shadow:0 0 12px {color}66;';\n"
                "overlay.appendChild(handle);\n"
                f"const labelA = document.createElement('div');\n"
                f"labelA.textContent = '{label_a}';\n"
                f"labelA.style.cssText = `position:absolute; top:12px; left:50%; transform:translateX(-50%);"
                f" padding:4px 12px; background:{color}; color:#fff; border-radius:4px;"
                " font-size:13px; font-weight:600;`;\n"
                "container.appendChild(labelA);\n"
                f"const labelB = document.createElement('div');\n"
                f"labelB.textContent = '{label_b}';\n"
                f"labelB.style.cssText = `position:absolute; bottom:12px; left:50%; transform:translateX(-50%);"
                f" padding:4px 12px; background:{color}cc; color:#fff; border-radius:4px;"
                " font-size:13px; font-weight:600;`;\n"
                "container.appendChild(labelB);\n"
            )

        # Animated divider sweep
        js += (
            "document.body.appendChild(container);\n"
            # Auto-animate: sweep divider from 30% to 70% and back
            "const overlay_ = container.querySelector('div');\n"
            f"const sweepTime = {int(lifetime * 0.6)};\n"
            "const t0 = performance.now();\n"
            "function animSweep() {\n"
            "    const elapsed = performance.now() - t0;\n"
            "    const t = Math.min(1, elapsed / sweepTime);\n"
            "    const pct = 30 + 40 * Math.sin(t * Math.PI);\n"
        )

        if is_v:
            js += "    overlay_.style.width = (100 - pct) + '%';\n"
        else:
            js += "    overlay_.style.height = (100 - pct) + '%';\n"

        js += (
            "    if (t < 1) requestAnimationFrame(animSweep);\n"
            "}\n"
            "requestAnimationFrame(animSweep);\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    container.style.transition = 'opacity 0.4s ease';\n"
            "    container.style.opacity = '0';\n"
            "    setTimeout(() => {\n"
            "        container.remove();\n"
            "        document.getElementById('__demodsl_split_style')?.remove();\n"
            f"    }}, 500);\n"
            f"}}, {lifetime - 500});\n"
        )
        evaluate_js(iife(js))
