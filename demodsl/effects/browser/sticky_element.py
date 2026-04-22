"""Sticky element — an element that sticks to the cursor before release."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife, simulate_mouse_path
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class StickyElementEffect(BrowserEffect):
    effect_id = "sticky_element"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)
        pull_strength = round(0.05 + intensity * 0.15, 2)

        css = (
            "@keyframes __demodsl_sticky_snap {\n"
            "  0%   { transform: scale(1.08); }\n"
            "  50%  { transform: scale(0.95); }\n"
            "  100% { transform: scale(1); }\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_sticky_style", css)
            # Create a card element to demo the sticky behavior
            + "const card = document.createElement('div');\n"
            "card.id = '__demodsl_sticky_element';\n"
            "card.style.cssText = `\n"
            "    position:fixed; left:50%; top:50%; transform:translate(-50%,-50%);\n"
            "    width:180px; height:100px; border-radius:12px;\n"
            f"    background:linear-gradient(135deg, {color}22, {color}44);\n"
            f"    border:2px solid {color}55;\n"
            f"    box-shadow:0 4px 16px {color}33;\n"
            "    backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);\n"
            "    z-index:99999; pointer-events:none;\n"
            "    transition: box-shadow 0.2s ease;\n"
            "    display:flex; align-items:center; justify-content:center;\n"
            "`;\n"
            'card.innerHTML = \'<svg width="28" height="28" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2">'
            '<rect x="3" y="3" width="18" height="18" rx="2"/>'
            '<path d="M9 12h6M12 9v6"/></svg>\';\n'
            "document.body.appendChild(card);\n"
            # Sticky physics
            "let cardX = window.innerWidth / 2;\n"
            "let cardY = window.innerHeight / 2;\n"
            "let mouseX = cardX, mouseY = cardY;\n"
            "let stuck = false;\n"
            f"const PULL = {pull_strength};\n"
            "const SNAP_DIST = 120;\n"
            "document.addEventListener('mousemove', (e) => {\n"
            "    mouseX = e.clientX;\n"
            "    mouseY = e.clientY;\n"
            "});\n"
            # Animation loop: card follows mouse with elastic lag
            "const t0 = performance.now();\n"
            "function animate() {\n"
            "    const elapsed = performance.now() - t0;\n"
            f"    if (elapsed > {lifetime}) {{\n"
            "        card.remove();\n"
            "        document.getElementById('__demodsl_sticky_style')?.remove();\n"
            "        return;\n"
            "    }\n"
            "    const dx = mouseX - cardX;\n"
            "    const dy = mouseY - cardY;\n"
            "    const dist = Math.sqrt(dx*dx + dy*dy);\n"
            "    if (dist < SNAP_DIST) {\n"
            "        if (!stuck) {\n"
            "            stuck = true;\n"
            f"            card.style.borderColor = '{color}';\n"
            f"            card.style.boxShadow = '0 8px 32px {color}55';\n"
            "        }\n"
            "        cardX += dx * PULL;\n"
            "        cardY += dy * PULL;\n"
            "    } else if (stuck) {\n"
            "        stuck = false;\n"
            "        card.style.animation = '__demodsl_sticky_snap 0.3s ease';\n"
            f"        card.style.borderColor = '{color}55';\n"
            f"        card.style.boxShadow = '0 4px 16px {color}33';\n"
            "        setTimeout(() => { card.style.animation = ''; }, 300);\n"
            "    }\n"
            "    card.style.left = cardX + 'px';\n"
            "    card.style.top = cardY + 'px';\n"
            "    card.style.transform = 'translate(-50%,-50%)' + \n"
            "        (stuck ? ` rotate(${dx * 0.05}deg)` : '');\n"
            "    requestAnimationFrame(animate);\n"
            "}\n"
            "requestAnimationFrame(animate);\n"
            # Auto-demo mouse path
             + simulate_mouse_path(duration_s=min(duration - 0.5, 3.0), steps=80)
        )
        evaluate_js(iife(js))
