"""Tests for demodsl.effects.post_effects — post-processing effects."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from demodsl.effects.post_effects import (
    BloomEffect,
    BokehBlurEffect,
    CameraShakeEffect,
    ChromaticAberrationEffect,
    ColorGradeEffect,
    CrtScanlinesEffect,
    DissolveNoiseEffect,
    DollyZoomEffect,
    DroneZoomEffect,
    ElasticZoomEffect,
    FadeInEffect,
    FadeOutEffect,
    FilmGrainEffect,
    FocusPullEffect,
    FreezeFrameEffect,
    GlitchEffect,
    IrisEffect,
    KenBurnsEffect,
    LetterboxEffect,
    LightLeakEffect,
    ParallaxEffect,
    PixelSortEffect,
    ReverseEffect,
    RotateEffect,
    SlideInEffect,
    SpeedRampEffect,
    TiltShiftEffect,
    VhsDistortionEffect,
    VignetteEffect,
    WhipPanEffect,
    WipeEffect,
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
    def test_registers_all_post_effects(self) -> None:
        registry = EffectRegistry()
        register_all_post_effects(registry)
        assert len(registry.post_effects) == 33

    def test_all_names(self) -> None:
        registry = EffectRegistry()
        register_all_post_effects(registry)
        expected = {
            "parallax",
            "zoom_pulse",
            "fade_in",
            "fade_out",
            "vignette",
            "glitch",
            "slide_in",
            "drone_zoom",
            "ken_burns",
            "zoom_to",
            "dolly_zoom",
            "elastic_zoom",
            "camera_shake",
            "whip_pan",
            "rotate",
            "letterbox",
            "film_grain",
            "color_grade",
            "focus_pull",
            "tilt_shift",
            # New effects
            "crt_scanlines",
            "chromatic_aberration",
            "vhs_distortion",
            "pixel_sort",
            "bloom",
            "bokeh_blur",
            "light_leak",
            "wipe",
            "iris",
            "dissolve_noise",
            "speed_ramp",
            "freeze_frame",
            "reverse",
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


# ── Retro / stylised effects ─────────────────────────────────────────────────


class TestCrtScanlinesEffect:
    def test_returns_transform(self) -> None:
        effect = CrtScanlinesEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = CrtScanlinesEffect()
        clip = MagicMock()
        effect.apply(clip, {"intensity": 0.6, "line_spacing": 4})
        clip.transform.assert_called_once()


class TestChromaticAberrationEffect:
    def test_returns_transform(self) -> None:
        effect = ChromaticAberrationEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_offset(self) -> None:
        effect = ChromaticAberrationEffect()
        clip = MagicMock()
        effect.apply(clip, {"offset": 5})
        clip.transform.assert_called_once()


class TestVhsDistortionEffect:
    def test_returns_transform(self) -> None:
        effect = VhsDistortionEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_intensity(self) -> None:
        effect = VhsDistortionEffect()
        clip = MagicMock()
        effect.apply(clip, {"intensity": 0.7})
        clip.transform.assert_called_once()


class TestPixelSortEffect:
    def test_returns_transform(self) -> None:
        effect = PixelSortEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_vertical_direction(self) -> None:
        effect = PixelSortEffect()
        clip = MagicMock()
        effect.apply(clip, {"direction": "vertical", "threshold": 0.6})
        clip.transform.assert_called_once()


# ── Depth & light effects ────────────────────────────────────────────────────


class TestBloomEffect:
    def test_returns_transform(self) -> None:
        effect = BloomEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = BloomEffect()
        clip = MagicMock()
        effect.apply(clip, {"threshold": 0.8, "radius": 15.0, "intensity": 0.5})
        clip.transform.assert_called_once()


class TestBokehBlurEffect:
    def test_returns_transform(self) -> None:
        effect = BokehBlurEffect()
        clip = MagicMock()
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = BokehBlurEffect()
        clip = MagicMock()
        effect.apply(clip, {"focus_area": 0.5, "radius": 12.0})
        clip.transform.assert_called_once()


class TestLightLeakEffect:
    def test_returns_transform(self) -> None:
        effect = LightLeakEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_params(self) -> None:
        effect = LightLeakEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"color": "#FF4500", "intensity": 0.5, "speed": 2.0})
        clip.transform.assert_called_once()


# ── Transition effects ───────────────────────────────────────────────────────


class TestWipeEffect:
    def test_returns_transform(self) -> None:
        effect = WipeEffect()
        clip = MagicMock()
        clip.duration = 2.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_all_directions(self) -> None:
        for direction in ("left", "right", "up", "down"):
            effect = WipeEffect()
            clip = MagicMock()
            clip.duration = 2.0
            effect.apply(clip, {"direction": direction})
            clip.transform.assert_called_once()

    def test_soft_style(self) -> None:
        effect = WipeEffect()
        clip = MagicMock()
        clip.duration = 2.0
        effect.apply(clip, {"style": "soft"})
        clip.transform.assert_called_once()


class TestIrisEffect:
    def test_returns_transform(self) -> None:
        effect = IrisEffect()
        clip = MagicMock()
        clip.duration = 2.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_direction_out(self) -> None:
        effect = IrisEffect()
        clip = MagicMock()
        clip.duration = 2.0
        effect.apply(clip, {"direction": "out"})
        clip.transform.assert_called_once()


class TestDissolveNoiseEffect:
    def test_returns_transform(self) -> None:
        effect = DissolveNoiseEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_custom_grain(self) -> None:
        effect = DissolveNoiseEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"grain_size": 8})
        clip.transform.assert_called_once()


# ── Helpers for closure tests ─────────────────────────────────────────────────


def _make_frame(w: int = 64, h: int = 48) -> np.ndarray:
    """Create a small synthetic RGB frame for testing inner closures."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def _get_transform_fn(effect, params: dict | None = None, duration: float = 2.0):
    """Apply an effect to a mock clip and return the inner closure."""
    clip = MagicMock()
    clip.duration = duration
    clip.w = 64
    clip.h = 48
    effect.apply(clip, params or {})
    return clip.transform.call_args[0][0]


# ── Closure execution tests (cover inner transform functions) ─────────────────


class TestVignetteEffectClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(VignetteEffect(), {"intensity": 0.5})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8


class TestGlitchEffectClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(GlitchEffect(), {"intensity": 0.3})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape


class TestLetterboxEffectClosure:
    def test_closure_adds_black_bars(self) -> None:
        fn = _get_transform_fn(LetterboxEffect(), {"ratio": 2.35})
        frame = _make_frame(w=64, h=48)
        result = fn(lambda t: frame, 0.0)
        assert result.shape == frame.shape
        # Top bar should be black
        assert np.all(result[0] == 0)

    def test_closure_no_bars_when_ratio_matches(self) -> None:
        fn = _get_transform_fn(LetterboxEffect(), {"ratio": 0.5})
        frame = _make_frame(w=64, h=48)
        result = fn(lambda t: frame, 0.0)
        # Ratio too small → target_h >= h → no bars
        np.testing.assert_array_equal(result, frame)


class TestFilmGrainEffectClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(FilmGrainEffect(), {"intensity": 0.3})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8


class TestColorGradeEffectClosure:
    def test_warm_preset(self) -> None:
        fn = _get_transform_fn(ColorGradeEffect(), {"preset": "warm"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8

    def test_desaturate_preset(self) -> None:
        fn = _get_transform_fn(ColorGradeEffect(), {"preset": "desaturate"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.dtype == np.uint8

    def test_noir_preset(self) -> None:
        fn = _get_transform_fn(ColorGradeEffect(), {"preset": "noir"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.shape == frame.shape

    def test_pastel_preset(self) -> None:
        fn = _get_transform_fn(ColorGradeEffect(), {"preset": "pastel"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.dtype == np.uint8

    def test_high_contrast_preset(self) -> None:
        fn = _get_transform_fn(ColorGradeEffect(), {"preset": "high_contrast"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.dtype == np.uint8


class TestCrtScanlinesEffectClosure:
    def test_closure_darkens_rows(self) -> None:
        fn = _get_transform_fn(CrtScanlinesEffect(), {"intensity": 0.4, "line_spacing": 3})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.shape == frame.shape


class TestChromaticAberrationClosure:
    def test_closure_shifts_channels(self) -> None:
        fn = _get_transform_fn(ChromaticAberrationEffect(), {"offset": 3})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.0)
        assert result.shape == frame.shape


class TestVhsDistortionClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(VhsDistortionEffect(), {"intensity": 0.4})
        frame = _make_frame(w=256, h=128)
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8


class TestPixelSortClosure:
    def test_horizontal_sort(self) -> None:
        fn = _get_transform_fn(PixelSortEffect(), {"threshold": 0.3, "direction": "horizontal"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape

    def test_vertical_sort(self) -> None:
        fn = _get_transform_fn(PixelSortEffect(), {"threshold": 0.3, "direction": "vertical"})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape


class TestWipeEffectClosure:
    def test_left_wipe(self) -> None:
        fn = _get_transform_fn(WipeEffect(), {"direction": "left", "style": "hard"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape

    def test_right_wipe(self) -> None:
        fn = _get_transform_fn(WipeEffect(), {"direction": "right"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape

    def test_up_wipe(self) -> None:
        fn = _get_transform_fn(WipeEffect(), {"direction": "up"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape

    def test_down_wipe(self) -> None:
        fn = _get_transform_fn(WipeEffect(), {"direction": "down"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape

    def test_soft_left_wipe(self) -> None:
        fn = _get_transform_fn(WipeEffect(), {"direction": "left", "style": "soft"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape


class TestIrisEffectClosure:
    def test_iris_in(self) -> None:
        fn = _get_transform_fn(IrisEffect(), {"direction": "in"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape

    def test_iris_out(self) -> None:
        fn = _get_transform_fn(IrisEffect(), {"direction": "out"})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape


class TestDissolveNoiseEffectClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(DissolveNoiseEffect(), {"grain_size": 4})
        frame = _make_frame()
        result = fn(lambda t: frame, 1.0)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8


class TestLightLeakEffectClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(
            LightLeakEffect(), {"color": "#FF8C00", "intensity": 0.35, "speed": 1.0}
        )
        frame = _make_frame()
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape
        assert result.dtype == np.uint8


class TestCameraShakeClosure:
    def test_closure_produces_valid_frame(self) -> None:
        fn = _get_transform_fn(CameraShakeEffect(), {"intensity": 0.3, "speed": 8.0})
        frame = _make_frame()
        result = fn(lambda t: frame, 0.5)
        assert result.shape == frame.shape


class TestSpeedRampEffect:
    def test_returns_transform(self) -> None:
        effect = SpeedRampEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"start_speed": 1.0, "end_speed": 0.5})
        clip.transform.assert_called_once()

    def test_no_duration(self) -> None:
        effect = SpeedRampEffect()
        clip = MagicMock()
        clip.duration = 0
        result = effect.apply(clip, {})
        assert result is clip

    def test_ease_in(self) -> None:
        effect = SpeedRampEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"ease": "ease-in"})
        clip.transform.assert_called_once()

    def test_ease_out(self) -> None:
        effect = SpeedRampEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"ease": "ease-out"})
        clip.transform.assert_called_once()

    def test_linear(self) -> None:
        effect = SpeedRampEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {"ease": "linear"})
        clip.transform.assert_called_once()


class TestFreezeFrameEffect:
    def test_returns_transform(self) -> None:
        effect = FreezeFrameEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"freeze_duration": 2.0})
        clip.transform.assert_called_once()

    def test_no_duration_returns_clip(self) -> None:
        effect = FreezeFrameEffect()
        clip = MagicMock()
        clip.duration = 0
        result = effect.apply(clip, {})
        assert result is clip

    def test_zero_freeze_returns_clip(self) -> None:
        effect = FreezeFrameEffect()
        clip = MagicMock()
        clip.duration = 5.0
        result = effect.apply(clip, {"freeze_duration": 0})
        assert result is clip


class TestReverseEffect:
    def test_returns_transform(self) -> None:
        effect = ReverseEffect()
        clip = MagicMock()
        clip.duration = 3.0
        effect.apply(clip, {})
        clip.transform.assert_called_once()

    def test_no_duration_returns_clip(self) -> None:
        effect = ReverseEffect()
        clip = MagicMock()
        clip.duration = 0
        result = effect.apply(clip, {})
        assert result is clip
