"""Tests for the curl_noise browser effect (demodsl.effects.browser.curl_noise)."""

from __future__ import annotations

from unittest.mock import MagicMock

from demodsl.effects.browser import _BROWSER_EFFECTS, CurlNoiseEffect, register_all_browser_effects
from demodsl.effects.registry import EffectRegistry


class TestCurlNoiseEffect:
    def test_inject_calls_evaluate_js(self) -> None:
        effect = CurlNoiseEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert isinstance(js, str)
        assert "__demodsl_curl_noise" in js

    def test_default_color(self) -> None:
        effect = CurlNoiseEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "#8A5CFF" in js

    def test_custom_color(self) -> None:
        effect = CurlNoiseEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"color": "#00FFA3"})
        js = mock_eval.call_args.args[0]
        assert "#00FFA3" in js

    def test_density_scales_particle_count(self) -> None:
        effect = CurlNoiseEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {"density": 2.0})
        js = mock_eval.call_args.args[0]
        assert "Math.floor(36 * 2.0)" in js

    def test_uses_a_flow_field_not_a_random_walk(self) -> None:
        effect = CurlNoiseEffect()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "Math.cos(angle)" in js
        assert "Math.sin(angle)" in js

    def test_registered_in_browser_effects_map(self) -> None:
        assert _BROWSER_EFFECTS["curl_noise"] is CurlNoiseEffect

    def test_registers_into_effect_registry(self) -> None:
        registry = EffectRegistry()
        register_all_browser_effects(registry)
        assert registry.is_browser_effect("curl_noise")
