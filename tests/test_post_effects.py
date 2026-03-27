"""Tests for demodsl.effects.post_effects — 7 post-processing effects."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.effects.post_effects import (
    FadeInEffect,
    FadeOutEffect,
    GlitchEffect,
    ParallaxEffect,
    SlideInEffect,
    VignetteEffect,
    ZoomPulseEffect,
    register_all_post_effects,
)
from demodsl.effects.registry import EffectRegistry


class TestParallaxEffect:
    def test_default_depth(self) -> None:
        effect = ParallaxEffect()
        clip = MagicMock()
        clip.w = 1920
        clip.h = 1080
        resized = MagicMock()
        clip.resized.return_value = resized
        effect.apply(clip, {})
        clip.resized.assert_called_once_with(1.05)  # 1 + 5 * 0.01

    def test_custom_depth(self) -> None:
        effect = ParallaxEffect()
        clip = MagicMock()
        clip.w = 1920
        clip.h = 1080
        resized = MagicMock()
        clip.resized.return_value = resized
        effect.apply(clip, {"depth": 10})
        clip.resized.assert_called_once_with(1.10)


class TestZoomPulseEffect:
    def test_default_scale(self) -> None:
        effect = ZoomPulseEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_scale(self) -> None:
        effect = ZoomPulseEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"scale": 2.0})
        clip.transform.assert_called_once()


class TestFadeInEffect:
    def test_default_duration(self) -> None:
        effect = FadeInEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.with_effects.assert_called_once()

    def test_custom_duration(self) -> None:
        effect = FadeInEffect()
        clip = MagicMock()
        effect.apply(clip, {"duration": 2.5})
        clip.with_effects.assert_called_once()


class TestFadeOutEffect:
    def test_default_duration(self) -> None:
        effect = FadeOutEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.with_effects.assert_called_once()


class TestVignetteEffect:
    def test_returns_transform(self) -> None:
        effect = VignetteEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_intensity(self) -> None:
        effect = VignetteEffect()
        clip = MagicMock()
        effect.apply(clip, {"intensity": 0.9})
        clip.transform.assert_called_once()


class TestGlitchEffect:
    def test_returns_transform(self) -> None:
        effect = GlitchEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_num_slices_proportional(self) -> None:
        # intensity=0.5 → num_slices = int(10 * 0.5) = 5
        effect = GlitchEffect()
        clip = MagicMock()
        # Just ensure it doesn't raise
        effect.apply(clip, {"intensity": 0.5})
        clip.transform.assert_called_once()


class TestSlideInEffect:
    def test_default_duration(self) -> None:
        effect = SlideInEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.with_effects.assert_called_once()


class TestRegisterAllPostEffects:
    def test_registers_all_7(self) -> None:
        registry = EffectRegistry()
        register_all_post_effects(registry)
        assert len(registry.post_effects) == 7

    def test_all_names(self) -> None:
        registry = EffectRegistry()
        register_all_post_effects(registry)
        expected = {"parallax", "zoom_pulse", "fade_in", "fade_out", "vignette", "glitch", "slide_in"}
        assert expected == set(registry.post_effects)
