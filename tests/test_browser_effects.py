"""Tests for demodsl.effects.browser_effects — 11 browser effects."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.effects.browser_effects import (
    ConfettiEffect,
    CursorTrailEffect,
    GlowEffect,
    HighlightEffect,
    NeonGlowEffect,
    RippleEffect,
    ShockwaveEffect,
    SparkleEffect,
    SpotlightEffect,
    SuccessCheckmarkEffect,
    TypewriterEffect,
    register_all_browser_effects,
)
from demodsl.effects.registry import EffectRegistry


ALL_EFFECTS = [
    ("spotlight", SpotlightEffect, "__demodsl_spotlight"),
    ("highlight", HighlightEffect, "__demodsl_highlight"),
    ("confetti", ConfettiEffect, "__demodsl_confetti"),
    ("typewriter", TypewriterEffect, "__demodsl_typewriter"),
    ("glow", GlowEffect, "__demodsl_glow"),
    ("shockwave", ShockwaveEffect, "__demodsl_shockwave"),
    ("sparkle", SparkleEffect, "__demodsl_sparkle"),
    ("cursor_trail", CursorTrailEffect, None),  # no static id
    ("ripple", RippleEffect, None),  # no static id
    ("neon_glow", NeonGlowEffect, "__demodsl_neon"),
    ("success_checkmark", SuccessCheckmarkEffect, "__demodsl_checkmark"),
]


class TestBrowserEffectInject:
    @pytest.mark.parametrize("name,cls,expected_id", ALL_EFFECTS)
    def test_inject_calls_evaluate_js(
        self, name: str, cls: type, expected_id: str | None
    ) -> None:
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert isinstance(js, str)
        assert len(js) > 10

    @pytest.mark.parametrize(
        "name,cls,expected_id",
        [(n, c, eid) for n, c, eid in ALL_EFFECTS if eid is not None],
    )
    def test_js_contains_dom_id(
        self, name: str, cls: type, expected_id: str
    ) -> None:
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert expected_id in js


class TestSpotlightParams:
    def test_default_intensity(self) -> None:
        effect = SpotlightEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "0.8" in js

    def test_custom_intensity(self) -> None:
        effect = SpotlightEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"intensity": 0.5})
        js = mock_eval.call_args.args[0]
        assert "0.5" in js


class TestHighlightParams:
    def test_default_color(self) -> None:
        effect = HighlightEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#FFD700" in js

    def test_custom_color(self) -> None:
        effect = HighlightEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"color": "#FF0000"})
        js = mock_eval.call_args.args[0]
        assert "#FF0000" in js


class TestGlowParams:
    def test_default_color(self) -> None:
        effect = GlowEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#00FF00" in js


class TestNeonGlowParams:
    def test_default_color(self) -> None:
        effect = NeonGlowEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#FF00FF" in js

    def test_custom_color(self) -> None:
        effect = NeonGlowEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"color": "#00FFFF"})
        js = mock_eval.call_args.args[0]
        assert "#00FFFF" in js


class TestRegisterAllBrowserEffects:
    def test_registers_all_11(self) -> None:
        registry = EffectRegistry()
        register_all_browser_effects(registry)
        assert len(registry.browser_effects) == 11

    def test_all_names_present(self) -> None:
        registry = EffectRegistry()
        register_all_browser_effects(registry)
        expected = {n for n, _, _ in ALL_EFFECTS}
        assert expected == set(registry.browser_effects)
