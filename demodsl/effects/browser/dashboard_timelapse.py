"""Dashboard timelapse — fast-rolling counter numbers and animated metrics."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class DashboardTimelapseEffect(BrowserEffect):
    effect_id = "dashboard_timelapse"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.5, max_val=15.0
        )
        speed = sanitize_number(params.get("speed", 1.0), default=1.0, min_val=0.2, max_val=5.0)
        lifetime = int(duration * 1000)
        roll_speed = round(speed, 2)

        css = (
            "@keyframes __demodsl_dash_fadein {\n"
            "  0%   { opacity: 0; transform: translateY(10px); }\n"
            "  100% { opacity: 1; transform: translateY(0); }\n"
            "}\n"
            ".__demodsl_dash_card {\n"
            "  background: rgba(30,30,40,0.92); border-radius: 12px;\n"
            "  padding: 16px 20px; min-width: 160px;\n"
            "  box-shadow: 0 4px 16px rgba(0,0,0,0.3);\n"
            "  animation: __demodsl_dash_fadein 0.4s ease forwards;\n"
            "  font-family: -apple-system, BlinkMacSystemFont, monospace;\n"
            "}\n"
            ".__demodsl_dash_label {\n"
            "  font-size: 11px; color: #94a3b8; text-transform: uppercase;\n"
            "  letter-spacing: 1px; margin-bottom: 6px;\n"
            "}\n"
            ".__demodsl_dash_value {\n"
            f"  font-size: 32px; font-weight: 700; color: {color};\n"
            "  font-variant-numeric: tabular-nums;\n"
            "}\n"
            ".__demodsl_dash_delta {\n"
            "  font-size: 12px; margin-top: 4px;\n"
            "}\n"
        )

        # Dashboard metric definitions
        metrics_js = (
            "const metrics = [\n"
            "  {label:'Revenue', target:148750, prefix:'$', suffix:'', decimals:0, delta:'+23.4%', deltaColor:'#34d399'},\n"
            "  {label:'Users', target:28493, prefix:'', suffix:'', decimals:0, delta:'+12.1%', deltaColor:'#34d399'},\n"
            "  {label:'Conversion', target:4.82, prefix:'', suffix:'%', decimals:2, delta:'+0.8%', deltaColor:'#34d399'},\n"
            "  {label:'Latency', target:42, prefix:'', suffix:'ms', decimals:0, delta:'-18.2%', deltaColor:'#fbbf24'},\n"
            "];\n"
        )

        js = (
            inject_style("__demodsl_dash_style", css)
            + "const panel = document.createElement('div');\n"
            "panel.id = '__demodsl_dashboard_timelapse';\n"
            "panel.style.cssText = `\n"
            "    position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);\n"
            "    z-index:99999; pointer-events:none;\n"
            "    display:grid; grid-template-columns:1fr 1fr; gap:12px;\n"
            "`;\n"
            "document.body.appendChild(panel);\n" + metrics_js + "const cards = [];\n"
            "metrics.forEach((m, i) => {\n"
            "    const card = document.createElement('div');\n"
            "    card.className = '__demodsl_dash_card';\n"
            "    card.style.animationDelay = (i * 0.1) + 's';\n"
            "    card.style.opacity = '0';\n"
            "    const label = document.createElement('div');\n"
            "    label.className = '__demodsl_dash_label';\n"
            "    label.textContent = m.label;\n"
            "    const value = document.createElement('div');\n"
            "    value.className = '__demodsl_dash_value';\n"
            "    value.textContent = m.prefix + '0' + m.suffix;\n"
            "    const delta = document.createElement('div');\n"
            "    delta.className = '__demodsl_dash_delta';\n"
            "    delta.style.color = m.deltaColor;\n"
            "    delta.style.opacity = '0';\n"
            "    delta.textContent = m.delta;\n"
            "    card.appendChild(label);\n"
            "    card.appendChild(value);\n"
            "    card.appendChild(delta);\n"
            "    panel.appendChild(card);\n"
            "    cards.push({el: value, deltaEl: delta, meta: m, current: 0});\n"
            "});\n"
            # Animate counters
            f"const ROLL_SPEED = {roll_speed};\n"
            f"const ROLL_TIME = {int(lifetime * 0.65)};\n"
            "const t0 = performance.now();\n"
            "function animCounters() {\n"
            "    const elapsed = performance.now() - t0;\n"
            "    const t = Math.min(1, elapsed / ROLL_TIME * ROLL_SPEED);\n"
            # Ease out cubic
            "    const ease = 1 - Math.pow(1 - Math.min(1, t), 3);\n"
            "    cards.forEach(c => {\n"
            "        const val = c.meta.target * ease;\n"
            "        let display;\n"
            "        if (c.meta.decimals > 0) {\n"
            "            display = val.toFixed(c.meta.decimals);\n"
            "        } else {\n"
            "            display = Math.floor(val).toLocaleString('en-US');\n"
            "        }\n"
            "        c.el.textContent = c.meta.prefix + display + c.meta.suffix;\n"
            # Show delta when counter reaches ~80%
            "        if (ease > 0.8) c.deltaEl.style.opacity = '1';\n"
            "    });\n"
            "    if (t < 1) requestAnimationFrame(animCounters);\n"
            "}\n"
            "requestAnimationFrame(animCounters);\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    panel.style.transition = 'opacity 0.4s ease';\n"
            "    panel.style.opacity = '0';\n"
            "    setTimeout(() => {\n"
            "        panel.remove();\n"
            "        document.getElementById('__demodsl_dash_style')?.remove();\n"
            f"    }}, 500);\n"
            f"}}, {lifetime - 500});\n"
        )
        evaluate_js(iife(js))
