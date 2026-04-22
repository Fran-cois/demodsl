"""Zoom through — dive into an element as a transition effect."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class ZoomThroughEffect(BrowserEffect):
    effect_id = "zoom_through"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.4), default=0.4, min_val=0.0, max_val=1.0
        )
        scale = sanitize_number(
            params.get("scale", 8), default=8, min_val=2, max_val=30
        )
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=0.5, max_val=10.0
        )
        zoom_in_ms = int(duration * 1000 * 0.4)
        hold_ms = int(duration * 1000 * 0.2)
        zoom_out_ms = int(duration * 1000 * 0.4)

        # Use document.body transform (same pattern as zoom_focus/perspective_tilt)
        js = (
            "history.scrollRestoration = 'manual';\n"
            "const el = document.body;\n"
            f"const originX = {round(target_x * 100, 1)};\n"
            f"const originY = {round(target_y * 100, 1)};\n"
            "el.style.transformOrigin = originX + '% ' + originY + '%';\n"
            # Phase 1: zoom in
            f"el.style.transition = 'transform {zoom_in_ms}ms cubic-bezier(0.4, 0, 0.2, 1)';\n"
            "requestAnimationFrame(() => {\n"
            f"    el.style.transform = 'scale({scale})';\n"
            "});\n"
            # Phase 2: white flash at peak zoom
            f"setTimeout(() => {{\n"
            "    const flash = document.createElement('div');\n"
            "    flash.id = '__demodsl_zoom_through_flash';\n"
            "    flash.style.cssText = `\n"
            "        position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "        background:white; z-index:99999; pointer-events:none;\n"
            "        opacity:0; transition:opacity 200ms ease;\n"
            "    `;\n"
            "    document.body.appendChild(flash);\n"
            "    requestAnimationFrame(() => { flash.style.opacity = '0.85'; });\n"
            "    setTimeout(() => {\n"
            "        flash.style.opacity = '0';\n"
            "        setTimeout(() => flash.remove(), 300);\n"
            "    }, 300);\n"
            f"}}, {zoom_in_ms - 100});\n"
            # Phase 3: zoom out
            f"setTimeout(() => {{\n"
            f"    el.style.transition = 'transform {zoom_out_ms}ms cubic-bezier(0.4, 0, 0.2, 1)';\n"
            "    el.style.transform = '';\n"
            f"    setTimeout(() => {{\n"
            "        el.style.transition = '';\n"
            "        el.style.transformOrigin = '';\n"
            f"    }}, {zoom_out_ms});\n"
            f"}}, {zoom_in_ms + hold_ms});\n"
        )
        evaluate_js(iife(js))
