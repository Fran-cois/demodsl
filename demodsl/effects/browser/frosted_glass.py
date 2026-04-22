"""Frosted glass effect — full-screen backdrop-filter blur overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_overlay, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class FrostedGlassEffect(BrowserEffect):
    effect_id = "frosted_glass"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        raw_intensity = sanitize_number(
            params.get("intensity", 0.5), default=0.5, min_val=0, max_val=1.0
        )
        blur_px = int(raw_intensity * 20)
        evaluate_js(
            iife(
                create_overlay(
                    "__demodsl_frosted_glass",
                    f"backdrop-filter: blur({blur_px}px) saturate(180%);\n"
                    f"    -webkit-backdrop-filter: blur({blur_px}px) saturate(180%);",
                )
            )
        )
