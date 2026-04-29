"""Progress ring — SVG circular loading ring that transforms into a checkmark."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class ProgressRingEffect(BrowserEffect):
    effect_id = "progress_ring"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#22c55e"))
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=1.0, max_val=10.0
        )
        size = int(sanitize_number(params.get("scale", 120), default=120, min_val=60, max_val=300))
        lifetime = int(duration * 1000)
        fill_time = int(lifetime * 0.6)
        stroke_w = max(4, size // 15)
        r = (size - stroke_w) // 2
        circumference = round(2 * 3.14159 * r, 1)

        js = (
            "const container = document.createElement('div');\n"
            "container.id = '__demodsl_progress_ring';\n"
            "container.style.cssText = `\n"
            f"    position:fixed; top:50%; left:50%; width:{size}px; height:{size}px;\n"
            f"    transform:translate(-50%,-50%); z-index:99999; pointer-events:none;\n"
            "`;\n"
            f"const svgNS = 'http://www.w3.org/2000/svg';\n"
            f"const svg = document.createElementNS(svgNS, 'svg');\n"
            f"svg.setAttribute('width', '{size}');\n"
            f"svg.setAttribute('height', '{size}');\n"
            f"svg.setAttribute('viewBox', '0 0 {size} {size}');\n"
            # Background circle (track)
            "const track = document.createElementNS(svgNS, 'circle');\n"
            f"track.setAttribute('cx', '{size // 2}');\n"
            f"track.setAttribute('cy', '{size // 2}');\n"
            f"track.setAttribute('r', '{r}');\n"
            f"track.setAttribute('fill', 'none');\n"
            f"track.setAttribute('stroke', '{color}33');\n"
            f"track.setAttribute('stroke-width', '{stroke_w}');\n"
            "svg.appendChild(track);\n"
            # Progress circle
            "const prog = document.createElementNS(svgNS, 'circle');\n"
            f"prog.setAttribute('cx', '{size // 2}');\n"
            f"prog.setAttribute('cy', '{size // 2}');\n"
            f"prog.setAttribute('r', '{r}');\n"
            "prog.setAttribute('fill', 'none');\n"
            f"prog.setAttribute('stroke', '{color}');\n"
            f"prog.setAttribute('stroke-width', '{stroke_w}');\n"
            f"prog.setAttribute('stroke-dasharray', '{circumference}');\n"
            f"prog.setAttribute('stroke-dashoffset', '{circumference}');\n"
            "prog.setAttribute('stroke-linecap', 'round');\n"
            f"prog.style.transform = 'rotate(-90deg)';\n"
            f"prog.style.transformOrigin = '{size // 2}px {size // 2}px';\n"
            "svg.appendChild(prog);\n"
            # Checkmark path (hidden initially)
            "const check = document.createElementNS(svgNS, 'path');\n"
            f"const cx = {size // 2}, cy = {size // 2}, cs = {size // 5};\n"
            "check.setAttribute('d', `M${cx-cs} ${cy} L${cx-cs/3} ${cy+cs*0.7} L${cx+cs} ${cy-cs*0.6}`);\n"
            "check.setAttribute('fill', 'none');\n"
            f"check.setAttribute('stroke', '{color}');\n"
            f"check.setAttribute('stroke-width', '{stroke_w + 1}');\n"
            "check.setAttribute('stroke-linecap', 'round');\n"
            "check.setAttribute('stroke-linejoin', 'round');\n"
            "check.style.opacity = '0';\n"
            "const checkLen = check.getTotalLength ? 100 : 100;\n"
            "svg.appendChild(check);\n"
            "container.appendChild(svg);\n"
            "document.body.appendChild(container);\n"
            # Animate progress fill
            f"const CIRC = {circumference};\n"
            f"const FILL_TIME = {fill_time};\n"
            "const t0 = performance.now();\n"
            "function animate() {\n"
            "    const elapsed = performance.now() - t0;\n"
            "    const t = Math.min(1, elapsed / FILL_TIME);\n"
            # Eased progress
            "    const ease = 1 - Math.pow(1 - t, 3);\n"
            "    prog.setAttribute('stroke-dashoffset', (CIRC * (1 - ease)).toFixed(1));\n"
            "    if (t < 1) {\n"
            "        requestAnimationFrame(animate);\n"
            "    } else {\n"
            # Show checkmark with animation
            "        prog.style.transition = 'opacity 0.3s ease';\n"
            "        prog.style.opacity = '0.3';\n"
            "        check.style.transition = 'opacity 0.3s ease';\n"
            "        check.style.opacity = '1';\n"
            # Pulse effect
            "        container.style.transition = 'transform 0.3s ease';\n"
            "        container.style.transform = 'translate(-50%,-50%) scale(1.15)';\n"
            "        setTimeout(() => {\n"
            "            container.style.transform = 'translate(-50%,-50%) scale(1)';\n"
            "        }, 300);\n"
            "    }\n"
            "}\n"
            "requestAnimationFrame(animate);\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    container.style.transition = 'opacity 0.3s ease';\n"
            "    container.style.opacity = '0';\n"
            "    setTimeout(() => container.remove(), 400);\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
