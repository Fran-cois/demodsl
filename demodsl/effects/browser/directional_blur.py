"""Directional blur — motion blur on screen edges during scroll."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class DirectionalBlurEffect(BrowserEffect):
    effect_id = "directional_blur"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        direction = params.get("direction", "vertical")
        if direction not in ("vertical", "horizontal"):
            direction = "vertical"
        lifetime = int(duration * 1000)
        max_blur = round(4 + intensity * 12, 1)

        is_v = direction == "vertical"

        js = (
            "const overlay = document.createElement('div');\n"
            "overlay.id = '__demodsl_directional_blur';\n"
            "overlay.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99998; pointer-events:none;\n"
            "`;\n"
            "document.body.appendChild(overlay);\n"
            # Top/bottom or left/right gradient masks
        )

        if is_v:
            js += (
                "const topBlur = document.createElement('div');\n"
                "topBlur.style.cssText = `\n"
                "    position:absolute; top:0; left:0; width:100%; height:15%;\n"
                "    backdrop-filter:blur(0px); -webkit-backdrop-filter:blur(0px);\n"
                "    mask-image:linear-gradient(180deg, black, transparent);\n"
                "    -webkit-mask-image:linear-gradient(180deg, black, transparent);\n"
                "    transition:backdrop-filter 0.15s ease, -webkit-backdrop-filter 0.15s ease;\n"
                "`;\n"
                "overlay.appendChild(topBlur);\n"
                "const botBlur = document.createElement('div');\n"
                "botBlur.style.cssText = `\n"
                "    position:absolute; bottom:0; left:0; width:100%; height:15%;\n"
                "    backdrop-filter:blur(0px); -webkit-backdrop-filter:blur(0px);\n"
                "    mask-image:linear-gradient(0deg, black, transparent);\n"
                "    -webkit-mask-image:linear-gradient(0deg, black, transparent);\n"
                "    transition:backdrop-filter 0.15s ease, -webkit-backdrop-filter 0.15s ease;\n"
                "`;\n"
                "overlay.appendChild(botBlur);\n"
            )
        else:
            js += (
                "const topBlur = document.createElement('div');\n"
                "topBlur.style.cssText = `\n"
                "    position:absolute; top:0; left:0; width:15%; height:100%;\n"
                "    backdrop-filter:blur(0px); -webkit-backdrop-filter:blur(0px);\n"
                "    mask-image:linear-gradient(90deg, black, transparent);\n"
                "    -webkit-mask-image:linear-gradient(90deg, black, transparent);\n"
                "    transition:backdrop-filter 0.15s ease, -webkit-backdrop-filter 0.15s ease;\n"
                "`;\n"
                "overlay.appendChild(topBlur);\n"
                "const botBlur = document.createElement('div');\n"
                "botBlur.style.cssText = `\n"
                "    position:absolute; top:0; right:0; width:15%; height:100%;\n"
                "    backdrop-filter:blur(0px); -webkit-backdrop-filter:blur(0px);\n"
                "    mask-image:linear-gradient(270deg, black, transparent);\n"
                "    -webkit-mask-image:linear-gradient(270deg, black, transparent);\n"
                "    transition:backdrop-filter 0.15s ease, -webkit-backdrop-filter 0.15s ease;\n"
                "`;\n"
                "overlay.appendChild(botBlur);\n"
            )

        js += (
            # Scroll velocity detection
            f"const MAX_BLUR = {max_blur};\n"
            "let lastScrollY = window.scrollY;\n"
            "let lastTime = performance.now();\n"
            "let currentBlur = 0;\n"
            "function onScroll() {\n"
            "    const now = performance.now();\n"
            "    const dt = Math.max(1, now - lastTime);\n"
            "    const dy = Math.abs(window.scrollY - lastScrollY);\n"
            "    const velocity = dy / dt * 16;\n"  # px per frame
            "    lastScrollY = window.scrollY;\n"
            "    lastTime = now;\n"
            "    const targetBlur = Math.min(MAX_BLUR, velocity * 0.3);\n"
            "    currentBlur += (targetBlur - currentBlur) * 0.3;\n"
            "    const b = currentBlur.toFixed(1) + 'px';\n"
            "    topBlur.style.backdropFilter = `blur(${b})`;\n"
            "    topBlur.style.webkitBackdropFilter = `blur(${b})`;\n"
            "    botBlur.style.backdropFilter = `blur(${b})`;\n"
            "    botBlur.style.webkitBackdropFilter = `blur(${b})`;\n"
            "}\n"
            "window.addEventListener('scroll', onScroll, {passive: true});\n"
            # Auto-demo: trigger smooth scroll
            "const autoStart = performance.now();\n"
            "function autoScroll() {\n"
            "    const elapsed = performance.now() - autoStart;\n"
            f"    if (elapsed > {int(lifetime * 0.7)}) return;\n"
            "    const speed = 3 + Math.sin(elapsed / 500) * 4;\n"
            "    window.scrollBy(0, speed);\n"
            "    onScroll();\n"
            "    requestAnimationFrame(autoScroll);\n"
            "}\n"
            "requestAnimationFrame(autoScroll);\n"
            # Decay loop to smoothly reduce blur when not scrolling
            "function decayBlur() {\n"
            "    currentBlur *= 0.92;\n"
            "    if (currentBlur < 0.1) currentBlur = 0;\n"
            "    const b = currentBlur.toFixed(1) + 'px';\n"
            "    topBlur.style.backdropFilter = `blur(${b})`;\n"
            "    topBlur.style.webkitBackdropFilter = `blur(${b})`;\n"
            "    botBlur.style.backdropFilter = `blur(${b})`;\n"
            "    botBlur.style.webkitBackdropFilter = `blur(${b})`;\n"
            f"    if (performance.now() - autoStart < {lifetime}) requestAnimationFrame(decayBlur);\n"
            "}\n"
            "requestAnimationFrame(decayBlur);\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    window.removeEventListener('scroll', onScroll);\n"
            "    overlay.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
