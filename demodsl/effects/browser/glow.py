"""Glow effect — inward box-shadow overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import create_overlay, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color


class GlowEffect(BrowserEffect):
    effect_id = "glow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#00FF00"))
        evaluate_js(
            iife(
                create_overlay(
                    "__demodsl_glow",
                    f"box-shadow: inset 0 0 80px {color}40;",
                    z_index=40,
                )
            )
        )
