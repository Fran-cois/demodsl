"""X-Ray view — scanner revealing code structure beneath the UI."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class XrayViewEffect(BrowserEffect):
    effect_id = "xray_view"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#22d3ee"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.5, max_val=15.0
        )
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        lifetime = int(duration * 1000)
        scan_speed = int(lifetime * 0.6)
        scan_width = int(60 + intensity * 80)

        css = (
            "@keyframes __demodsl_xray_scan {\n"
            f"  0%   {{ left: -{scan_width}px; }}\n"
            "  100% { left: 100%; }\n"
            "}\n"
        )

        # Generate fake code lines
        code_lines = [
            "&lt;div class=&quot;container&quot;&gt;",
            "  &lt;header class=&quot;navbar&quot;&gt;",
            "    &lt;nav role=&quot;navigation&quot;&gt;",
            "      &lt;a href=&quot;/&quot;&gt;Home&lt;/a&gt;",
            "    &lt;/nav&gt;",
            "  &lt;/header&gt;",
            "  &lt;main id=&quot;content&quot;&gt;",
            "    &lt;section class=&quot;hero&quot;&gt;",
            "      &lt;h1&gt;Welcome&lt;/h1&gt;",
            "      &lt;p&gt;Build amazing...&lt;/p&gt;",
            "    &lt;/section&gt;",
            "    &lt;div class=&quot;grid&quot;&gt;",
            "      &lt;Card data={items}/&gt;",
            "    &lt;/div&gt;",
            "  &lt;/main&gt;",
            "&lt;/div&gt;",
        ]
        code_html = "".join(
            f"<div style='opacity:0.7;white-space:pre'>{line}</div>" for line in code_lines
        )

        js = (
            inject_style("__demodsl_xray_style", css)
            # Code overlay (hidden by clip)
            + "const codePanel = document.createElement('div');\n"
            "codePanel.id = '__demodsl_xray_code';\n"
            "codePanel.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99998; pointer-events:none;\n"
            "    background:rgba(10,15,25,0.92);\n"
            "    padding:60px 40px;\n"
            f"    font-family:'SF Mono',Consolas,monospace; font-size:13px; color:{color};\n"
            "    line-height:1.8; overflow:hidden;\n"
            "    clip-path:inset(0 100% 0 0);\n"
            "`;\n"
            f"codePanel.innerHTML = `{code_html}`;\n"
            "document.body.appendChild(codePanel);\n"
            # Scanner line
            "const scanner = document.createElement('div');\n"
            "scanner.style.cssText = `\n"
            f"    position:fixed; top:0; width:{scan_width}px; height:100%;\n"
            "    z-index:99999; pointer-events:none;\n"
            f"    background:linear-gradient(90deg, transparent, {color}15, {color}30, {color}15, transparent);\n"
            f"    border-left:2px solid {color}88;\n"
            f"    border-right:2px solid {color}88;\n"
            f"    box-shadow:0 0 30px {color}33;\n"
            f"    animation:__demodsl_xray_scan {scan_speed}ms ease-in-out forwards;\n"
            "`;\n"
            "document.body.appendChild(scanner);\n"
            # Sync code reveal with scanner position
            f"const SCAN_TIME = {scan_speed};\n"
            "const t0 = performance.now();\n"
            "function syncClip() {\n"
            "    const elapsed = performance.now() - t0;\n"
            "    const t = Math.min(1, elapsed / SCAN_TIME);\n"
            "    const ease = t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t+2, 2)/2;\n"
            "    const pct = ease * 100;\n"
            "    codePanel.style.clipPath = `inset(0 ${(100 - pct).toFixed(1)}% 0 0)`;\n"
            "    if (t < 1) requestAnimationFrame(syncClip);\n"
            "}\n"
            "requestAnimationFrame(syncClip);\n"
            # Fade out and cleanup
            f"setTimeout(() => {{\n"
            "    codePanel.style.transition = 'opacity 0.5s ease';\n"
            "    codePanel.style.opacity = '0';\n"
            "    scanner.style.transition = 'opacity 0.3s ease';\n"
            "    scanner.style.opacity = '0';\n"
            "    setTimeout(() => {\n"
            "        codePanel.remove(); scanner.remove();\n"
            "        document.getElementById('__demodsl_xray_style')?.remove();\n"
            f"    }}, 600);\n"
            f"}}, {lifetime - 600});\n"
        )
        evaluate_js(iife(js))
