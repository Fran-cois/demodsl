"""Infinite canvas — zoom out to show ecosystem then zoom back in."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class InfiniteCanvasEffect(BrowserEffect):
    effect_id = "infinite_canvas"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=2.0, max_val=12.0
        )
        target_scale = sanitize_number(
            params.get("scale", 0.45), default=0.45, min_val=0.15, max_val=0.8
        )
        lifetime = int(duration * 1000)
        zoom_out_ms = int(lifetime * 0.3)
        hold_ms = int(lifetime * 0.4)
        zoom_in_ms = int(lifetime * 0.3)

        js = (
            "history.scrollRestoration = 'manual';\n"
            "const el = document.body;\n"
            # Create surrounding context cards (ecosystem)
            "const bg = document.createElement('div');\n"
            "bg.id = '__demodsl_infinite_canvas';\n"
            "bg.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:-1; pointer-events:none;\n"
            "    background: radial-gradient(ellipse at center,\n"
            "        rgba(20,20,35,0.95) 0%, rgba(10,10,20,0.98) 100%);\n"
            "    opacity:0; transition:opacity 0.4s ease;\n"
            "`;\n"
            # Add ecosystem cards around the "main" app
            "const cards = [\n"
            "    {x:'-55%', y:'-10%', label:'API Gateway', icon:'M13 10V3L4 14h7v7l9-11h-7z'},\n"
            "    {x:'55%',  y:'-10%', label:'Database', icon:'M12 2C6.48 2 2 4.02 2 6.5v11C2 19.98 6.48 22 12 22s10-2.02 10-4.5v-11C22 4.02 17.52 2 12 2z'},\n"
            "    {x:'-55%', y:'50%',  label:'Auth Service', icon:'M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2z'},\n"
            "    {x:'55%',  y:'50%',  label:'CDN / Assets', icon:'M19.35 10.04A7.49 7.49 0 0012 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 000 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z'},\n"
            "];\n"
            "cards.forEach(c => {\n"
            "    const card = document.createElement('div');\n"
            "    card.style.cssText = `\n"
            "        position:fixed; left:calc(50% + ${c.x}); top:calc(50% + ${c.y});\n"
            "        transform:translate(-50%,-50%) scale(0.8); opacity:0;\n"
            "        width:140px; padding:16px; border-radius:12px;\n"
            f"        background:rgba(30,30,50,0.9); border:1px solid {color}33;\n"
            "        text-align:center; font-family:-apple-system,sans-serif;\n"
            "        transition:opacity 0.5s ease, transform 0.5s ease;\n"
            "    `;\n"
            "    card.innerHTML = `<svg width='28' height='28' viewBox='0 0 24 24' "
            f"fill='{color}' style='margin-bottom:8px'><path d='${{c.icon}}'/></svg>"
            "<div style='color:#94a3b8;font-size:12px;font-weight:600'>${c.label}</div>`;\n"
            "    bg.appendChild(card);\n"
            "});\n"
            # Connection lines
            "const linesSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');\n"
            "linesSvg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;';\n"
            "linesSvg.setAttribute('viewBox', '0 0 100 100');\n"
            "linesSvg.setAttribute('preserveAspectRatio', 'none');\n"
            "const lines = [[25,40,50,50],[75,40,50,50],[25,75,50,50],[75,75,50,50]];\n"
            "lines.forEach(l => {\n"
            "    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');\n"
            "    line.setAttribute('x1', l[0]+'%'); line.setAttribute('y1', l[1]+'%');\n"
            "    line.setAttribute('x2', l[2]+'%'); line.setAttribute('y2', l[3]+'%');\n"
            f"    line.setAttribute('stroke', '{color}44');\n"
            "    line.setAttribute('stroke-width', '0.15');\n"
            "    line.setAttribute('stroke-dasharray', '1,0.5');\n"
            "    line.style.opacity = '0';\n"
            "    line.style.transition = 'opacity 0.5s ease';\n"
            "    linesSvg.appendChild(line);\n"
            "});\n"
            "bg.appendChild(linesSvg);\n"
            "document.body.appendChild(bg);\n"
            # Phase 1: zoom out
            f"el.style.transition = 'transform {zoom_out_ms}ms cubic-bezier(0.4, 0, 0.2, 1)';\n"
            "el.style.transformOrigin = '50% 50%';\n"
            "requestAnimationFrame(() => {\n"
            "    bg.style.opacity = '1';\n"
            f"    el.style.transform = 'scale({target_scale})';\n"
            f"    el.style.boxShadow = '0 0 40px {color}22';\n"
            "    el.style.borderRadius = '8px';\n"
            "});\n"
            # Show ecosystem cards and lines
            f"setTimeout(() => {{\n"
            "    bg.querySelectorAll('div').forEach((c, i) => {\n"
            "        setTimeout(() => {\n"
            "            c.style.opacity = '1';\n"
            "            c.style.transform = 'translate(-50%,-50%) scale(1)';\n"
            "        }, i * 100);\n"
            "    });\n"
            "    linesSvg.querySelectorAll('line').forEach((l, i) => {\n"
            "        setTimeout(() => { l.style.opacity = '1'; }, i * 150);\n"
            "    });\n"
            f"}}, {zoom_out_ms - 200});\n"
            # Phase 2: zoom back in
            f"setTimeout(() => {{\n"
            f"    el.style.transition = 'transform {zoom_in_ms}ms cubic-bezier(0.4, 0, 0.2, 1),"
            f" box-shadow {zoom_in_ms}ms ease, border-radius {zoom_in_ms}ms ease';\n"
            "    el.style.transform = '';\n"
            "    el.style.boxShadow = '';\n"
            "    el.style.borderRadius = '';\n"
            "    bg.style.opacity = '0';\n"
            f"    setTimeout(() => {{\n"
            "        el.style.transition = '';\n"
            "        el.style.transformOrigin = '';\n"
            "        bg.remove();\n"
            f"    }}, {zoom_in_ms});\n"
            f"}}, {zoom_out_ms + hold_ms});\n"
        )
        evaluate_js(iife(js))
