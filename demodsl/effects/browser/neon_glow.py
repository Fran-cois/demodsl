"""Neon glow effect — colored inward box-shadow overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_overlay, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color


class NeonGlowEffect(BrowserEffect):
    effect_id = "neon_glow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#FF00FF"))
        evaluate_js(
            iife(
                create_overlay(
                    "__demodsl_neon",
                    f"box-shadow: inset 0 0 60px {color}50, inset 0 0 120px {color}20;",
                    z_index=40,
                )
            )
        )
