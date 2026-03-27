"""Tests for demodsl.effects.post_effects — post-processing effects."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.effects.post_effects import (
    CameraShakeEffect,
    ColorGradeEffect,
    DollyZoomEffect,
    DroneZoomEffect,
    ElasticZoomEffect,
    FadeInEffect,
    FadeOutEffect,
    FilmGrainEffect,
    FocusPullEffect,
    GlitchEffect,
    KenBurnsEffect,
    LetterboxEffect,
    ParallaxEffect,
    RotateEffect,
    SlideInEffect,
    TiltShiftEffect,
    VignetteEffect,
    WhipPanEffect,
    ZoomPulseEffect,
    ZoomToEffect,
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
    def test_registers_all_20(self) -> None:
        registry = EffectRegistry()
        register_all_post_effects(registry)
        assert len(registry.post_effects) == 20

    def test_all_names(self) -> None:
        registry = EffectRegistry()
        register_all_post_effects(registry)
        expected = {
            "parallax", "zoom_pulse", "fade_in", "fade_out", "vignette", "glitch", "slide_in",
            "drone_zoom", "ken_burns", "zoom_to", "dolly_zoom", "elastic_zoom",
            "camera_shake", "whip_pan", "rotate",
            "letterbox", "film_grain", "color_grade", "focus_pull", "tilt_shift",
        }
        assert expected == set(registry.post_effects)


# ── Camera movement effects ───────────────────────────────────────────────────


class TestDroneZoomEffect:
    def test_returns_transform(self) -> None:
        effect = DroneZoomEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = DroneZoomEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"scale": 2.0, "target_x": 0.3, "target_y": 0.7})
        clip.transform.assert_called_once()


class TestKenBurnsEffect:
    def test_returns_transform(self) -> None:
        effect = KenBurnsEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_all_directions(self) -> None:
        for direction in ("right", "left", "up", "down"):
            effect = KenBurnsEffect()
            clip = MagicMock()
            clip.duration = 3.0
            effect.apply(clip, {"direction": direction})
            clip.transform.assert_called_once()


class TestZoomToEffect:
    def test_returns_transform(self) -> None:
        effect = ZoomToEffect()
        clip = MagicMock()
        clip.duration = 4.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_target(self) -> None:
        effect = ZoomToEffect()
        clip = MagicMock()
        clip.duration = 4.0
        effect.apply(clip, {"scale": 2.5, "target_x": 0.8, "target_y": 0.2})
        clip.transform.assert_called_once()


class TestDollyZoomEffect:
    def test_returns_transform(self) -> None:
        effect = DollyZoomEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_intensity(self) -> None:
        effect = DollyZoomEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"intensity": 0.6})
        clip.transform.assert_called_once()


class TestElasticZoomEffect:
    def test_returns_transform(self) -> None:
        effect = ElasticZoomEffect()
        clip = MagicMock()
        clip.duration = 2.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_scale(self) -> None:
        effect = ElasticZoomEffect()
        clip = MagicMock()
        clip.duration = 2.0
        effect.apply(clip, {"scale": 1.5})
        clip.transform.assert_called_once()


class TestCameraShakeEffect:
    def test_returns_transform(self) -> None:
        effect = CameraShakeEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = CameraShakeEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"intensity": 0.8, "speed": 12.0})
        clip.transform.assert_called_once()


class TestWhipPanEffect:
    def test_returns_transform(self) -> None:
        effect = WhipPanEffect()
        clip = MagicMock()
        clip.duration = 1.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_all_directions(self) -> None:
        for direction in ("right", "left", "up", "down"):
            effect = WhipPanEffect()
            clip = MagicMock()
            clip.duration = 1.0
            effect.apply(clip, {"direction": direction})
            clip.transform.assert_called_once()


class TestRotateEffect:
    def test_returns_transform(self) -> None:
        effect = RotateEffect()
        clip = MagicMock()
        clip.duration = 4.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = RotateEffect()
        clip = MagicMock()
        clip.duration = 4.0
        effect.apply(clip, {"angle": 5.0, "speed": 2.0})
        clip.transform.assert_called_once()


# ── Cinematic effects ─────────────────────────────────────────────────────────


class TestLetterboxEffect:
    def test_returns_transform(self) -> None:
        effect = LetterboxEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_ratio(self) -> None:
        effect = LetterboxEffect()
        clip = MagicMock()
        effect.apply(clip, {"ratio": 2.39})
        clip.transform.assert_called_once()


class TestFilmGrainEffect:
    def test_returns_transform(self) -> None:
        effect = FilmGrainEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_intensity(self) -> None:
        effect = FilmGrainEffect()
        clip = MagicMock()
        effect.apply(clip, {"intensity": 0.7})
        clip.transform.assert_called_once()


class TestColorGradeEffect:
    def test_returns_transform(self) -> None:
        effect = ColorGradeEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_all_presets(self) -> None:
        for preset in ("warm", "cool", "desaturate", "vintage", "cinematic"):
            effect = ColorGradeEffect()
            clip = MagicMock()
            effect.apply(clip, {"preset": preset})
            clip.transform.assert_called_once()

    def test_unknown_preset_falls_back(self) -> None:
        effect = ColorGradeEffect()
        clip = MagicMock()
        effect.apply(clip, {"preset": "unknown"})
        clip.transform.assert_called_once()


class TestFocusPullEffect:
    def test_returns_transform(self) -> None:
        effect = FocusPullEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_direction_in(self) -> None:
        effect = FocusPullEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"direction": "in", "intensity": 0.8})
        clip.transform.assert_called_once()


class TestTiltShiftEffect:
    def test_returns_transform(self) -> None:
        effect = TiltShiftEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = TiltShiftEffect()
        clip = MagicMock()
        effect.apply(clip, {"intensity": 0.8, "focus_position": 0.4})
        clip.transform.assert_called_once()
