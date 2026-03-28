"""Tests for demodsl.effects.browser_effects — 33 browser effects."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.effects.browser_effects import (
    BubblesEffect,
    CalloutArrowEffect,
    ConfettiEffect,
    CountdownTimerEffect,
    CursorTrailEffect,
    CursorTrailCometEffect,
    CursorTrailFireEffect,
    CursorTrailGlowEffect,
    CursorTrailLineEffect,
    CursorTrailParticlesEffect,
    CursorTrailRainbowEffect,
    EmojiRainEffect,
    FireworksEffect,
    FrostedGlassEffect,
    GlowEffect,
    HighlightEffect,
    MagneticHoverEffect,
    MatrixRainEffect,
    MorphingBackgroundEffect,
    NeonGlowEffect,
    PartyPopperEffect,
    ProgressBarEffect,
    RippleEffect,
    ShockwaveEffect,
    SnowEffect,
    SparkleEffect,
    SpotlightEffect,
    StarBurstEffect,
    SuccessCheckmarkEffect,
    TextHighlightEffect,
    TextScrambleEffect,
    TooltipAnnotationEffect,
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
    ("cursor_trail_rainbow", CursorTrailRainbowEffect, None),
    ("cursor_trail_comet", CursorTrailCometEffect, None),
    ("cursor_trail_glow", CursorTrailGlowEffect, None),
    ("cursor_trail_line", CursorTrailLineEffect, "__demodsl_trail_line"),
    ("cursor_trail_particles", CursorTrailParticlesEffect, None),
    ("cursor_trail_fire", CursorTrailFireEffect, None),
    ("ripple", RippleEffect, None),  # no static id
    ("neon_glow", NeonGlowEffect, "__demodsl_neon"),
    ("success_checkmark", SuccessCheckmarkEffect, "__demodsl_checkmark"),
    ("emoji_rain", EmojiRainEffect, "__demodsl_emoji_rain"),
    ("fireworks", FireworksEffect, "__demodsl_fireworks"),
    ("bubbles", BubblesEffect, "__demodsl_bubbles"),
    ("snow", SnowEffect, "__demodsl_snow"),
    ("star_burst", StarBurstEffect, "__demodsl_star_burst"),
    ("party_popper", PartyPopperEffect, "__demodsl_party_popper"),
    # New text / interaction / visual effects
    ("text_highlight", TextHighlightEffect, "__demodsl_text_highlight"),
    ("text_scramble", TextScrambleEffect, None),
    ("magnetic_hover", MagneticHoverEffect, "__demodsl_magnetic_hover"),
    ("tooltip_annotation", TooltipAnnotationEffect, "__demodsl_tooltip"),
    ("morphing_background", MorphingBackgroundEffect, "__demodsl_morphing_bg"),
    ("matrix_rain", MatrixRainEffect, "__demodsl_matrix_rain"),
    ("frosted_glass", FrostedGlassEffect, "__demodsl_frosted_glass"),
    # New utility overlays
    ("progress_bar", ProgressBarEffect, "__demodsl_progress_bar"),
    ("countdown_timer", CountdownTimerEffect, "__demodsl_countdown"),
    ("callout_arrow", CalloutArrowEffect, "__demodsl_callout_arrow"),
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


class TestTextHighlightParams:
    def test_default_color(self) -> None:
        effect = TextHighlightEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#FFD700" in js

    def test_custom_color(self) -> None:
        effect = TextHighlightEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"color": "#FF0000"})
        js = mock_eval.call_args.args[0]
        assert "#FF0000" in js


class TestMatrixRainParams:
    def test_default_color(self) -> None:
        effect = MatrixRainEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#00FF41" in js

    def test_custom_params(self) -> None:
        effect = MatrixRainEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"color": "#FF0000", "density": 0.8, "speed": 2.0})
        js = mock_eval.call_args.args[0]
        assert "#FF0000" in js


class TestProgressBarParams:
    def test_default_color(self) -> None:
        effect = ProgressBarEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#6366f1" in js
        assert "__demodsl_progress_set" in js

    def test_bottom_position(self) -> None:
        effect = ProgressBarEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"position": "bottom"})
        js = mock_eval.call_args.args[0]
        assert "bottom:0" in js


class TestCountdownTimerParams:
    def test_default_duration(self) -> None:
        effect = CountdownTimerEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_countdown" in js

    def test_custom_position(self) -> None:
        effect = CountdownTimerEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"position": "bottom-left"})
        js = mock_eval.call_args.args[0]
        assert "bottom:20px" in js


class TestCalloutArrowParams:
    def test_default_color(self) -> None:
        effect = CalloutArrowEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#ef4444" in js

    def test_custom_text(self) -> None:
        effect = CalloutArrowEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"text": "Important!", "color": "#0000FF"})
        js = mock_eval.call_args.args[0]
        assert "Important!" in js
        assert "#0000FF" in js


class TestRegisterAllBrowserEffects:
    def test_registers_all_33(self) -> None:
        registry = EffectRegistry()
        register_all_browser_effects(registry)
        assert len(registry.browser_effects) == 33

    def test_all_names_present(self) -> None:
        registry = EffectRegistry()
        register_all_browser_effects(registry)
        expected = {n for n, _, _ in ALL_EFFECTS}
        assert expected == set(registry.browser_effects)
