"""Scroll parallax — controlled multi-layer parallax on existing page elements."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class ScrollParallaxEffect(BrowserEffect):
    effect_id = "scroll_parallax"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.5), default=0.5, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        depth = int(sanitize_number(params.get("depth", 3), default=3, min_val=2, max_val=6))

        lifetime = int(duration * 1000)
        max_offset = int(intensity * 60)

        # Create floating parallax layers as overlay
        layers_js = ""
        for i in range(depth):
            opacity = 0.06 + (i * 0.03)
            size = 80 + i * 40
            layers_js += (
                f"const l{i} = document.createElement('div');\n"
                f"l{i}.className = '__demodsl_parallax_layer';\n"
                f"l{i}.style.cssText = `\n"
                f"    position:fixed; pointer-events:none; z-index:99998;\n"
                f"    width:{size}px; height:{size}px; border-radius:50%;\n"
                f"    background: radial-gradient(circle, rgba(99,102,241,{opacity}), transparent 70%);\n"
                f"    top:{20 + i * 15}%; left:{10 + i * 20}%;\n"
                f"    transition: transform 0.1s linear;\n"
                f"`;\n"
                f"container.appendChild(l{i});\n"
            )

        js = (
            "const container = document.createElement('div');\n"
            "container.id = '__demodsl_scroll_parallax';\n"
            "container.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;"
            "z-index:99998;pointer-events:none;overflow:hidden;';\n"
            "document.body.appendChild(container);\n"
            + layers_js
            + "let scrollY0 = window.scrollY;\n"
            "const layers = container.querySelectorAll('.__demodsl_parallax_layer');\n"
            "function updateParallax() {\n"
            "    const dy = window.scrollY - scrollY0;\n"
            "    layers.forEach((layer, i) => {\n"
            f"        const speed = (i + 1) / {depth};\n"
            f"        const offset = dy * speed * {intensity} * -0.5;\n"
            "        const sway = Math.sin(performance.now() / 2000 + i) * 10;\n"
            "        layer.style.transform = `translateY(${offset}px) translateX(${sway}px)`;\n"
            "    });\n"
            "}\n"
            # Also auto-animate if no scroll happens (for demo purposes)
            "let animFrame;\n"
            "let t0 = performance.now();\n"
            "function autoAnimate() {\n"
            f"    const elapsed = performance.now() - t0;\n"
            f"    if (elapsed > {lifetime}) return;\n"
            "    const progress = elapsed / 1000;\n"
            "    layers.forEach((layer, i) => {\n"
            f"        const speed = (i + 1) / {depth};\n"
            f"        const wave = Math.sin(progress * 0.8 + i * 1.2) * {max_offset} * speed;\n"
            "        const sway = Math.cos(progress * 0.5 + i * 0.8) * 15 * speed;\n"
            "        layer.style.transform = `translateY(${wave}px) translateX(${sway}px)`;\n"
            "    });\n"
            "    animFrame = requestAnimationFrame(autoAnimate);\n"
            "}\n"
            "window.addEventListener('scroll', updateParallax);\n"
            "autoAnimate();\n"
            # Fade in
            "container.style.opacity = '0';\n"
            "container.style.transition = 'opacity 0.5s ease';\n"
            "requestAnimationFrame(() => { container.style.opacity = '1'; });\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    container.style.opacity = '0';\n"
            "    window.removeEventListener('scroll', updateParallax);\n"
            "    cancelAnimationFrame(animFrame);\n"
            "    setTimeout(() => container.remove(), 600);\n"
            f"}}, {lifetime - 600});\n"
        )
        evaluate_js(iife(js))
