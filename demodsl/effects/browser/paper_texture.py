"""Paper texture — subtle grain overlay on the page."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class PaperTextureEffect(BrowserEffect):
    effect_id = "paper_texture"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.3), default=0.3, min_val=0.05, max_val=1.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)
        alpha = round(0.02 + intensity * 0.06, 3)

        # Generate noise pattern via canvas, convert to data URL
        js = (
            "const noiseCanvas = document.createElement('canvas');\n"
            "noiseCanvas.width = 256;\n"
            "noiseCanvas.height = 256;\n"
            "const nCtx = noiseCanvas.getContext('2d');\n"
            "const imgData = nCtx.createImageData(256, 256);\n"
            "for (let i = 0; i < imgData.data.length; i += 4) {\n"
            "    const v = Math.random() * 255;\n"
            "    imgData.data[i] = v;\n"
            "    imgData.data[i+1] = v;\n"
            "    imgData.data[i+2] = v;\n"
            f"    imgData.data[i+3] = {int(alpha * 255)};\n"
            "}\n"
            "nCtx.putImageData(imgData, 0, 0);\n"
            "const dataUrl = noiseCanvas.toDataURL();\n"
            "const overlay = document.createElement('div');\n"
            "overlay.id = '__demodsl_paper_texture';\n"
            "overlay.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99999; pointer-events:none;\n"
            "    background-image:url(${dataUrl});\n"
            "    background-repeat:repeat;\n"
            "    mix-blend-mode:multiply;\n"
            "    opacity:0; transition:opacity 0.5s ease;\n"
            "`;\n"
            "document.body.appendChild(overlay);\n"
            "requestAnimationFrame(() => { overlay.style.opacity = '1'; });\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    overlay.style.opacity = '0';\n"
            "    setTimeout(() => overlay.remove(), 600);\n"
            f"}}, {lifetime - 600});\n"
        )
        evaluate_js(iife(js))
