"""Tests for demodsl.effects.registry — EffectRegistry CRUD + bulk registration."""

from __future__ import annotations

from typing import Any

import pytest

from demodsl.effects.registry import BrowserEffect, EffectRegistry, PostEffect


# ── Helpers ───────────────────────────────────────────────────────────────────


class _FakeBrowserEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        pass


class _FakePostEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        return clip


# ── EffectRegistry ────────────────────────────────────────────────────────────


class TestEffectRegistry:
    def test_empty_at_init(self) -> None:
        reg = EffectRegistry()
        assert reg.browser_effects == []
        assert reg.post_effects == []

    def test_register_browser(self) -> None:
        reg = EffectRegistry()
        effect = _FakeBrowserEffect()
        reg.register_browser("test_effect", effect)
        assert reg.is_browser_effect("test_effect")
        assert not reg.is_post_effect("test_effect")

    def test_register_post(self) -> None:
        reg = EffectRegistry()
        effect = _FakePostEffect()
        reg.register_post("test_post", effect)
        assert reg.is_post_effect("test_post")
        assert not reg.is_browser_effect("test_post")

    def test_get_browser_effect(self) -> None:
        reg = EffectRegistry()
        effect = _FakeBrowserEffect()
        reg.register_browser("spot", effect)
        assert reg.get_browser_effect("spot") is effect

    def test_get_browser_effect_unknown(self) -> None:
        reg = EffectRegistry()
        with pytest.raises(KeyError, match="Unknown browser effect 'missing'"):
            reg.get_browser_effect("missing")

    def test_get_post_effect(self) -> None:
        reg = EffectRegistry()
        effect = _FakePostEffect()
        reg.register_post("fade", effect)
        assert reg.get_post_effect("fade") is effect

    def test_get_post_effect_unknown(self) -> None:
        reg = EffectRegistry()
        with pytest.raises(KeyError, match="Unknown post effect 'nope'"):
            reg.get_post_effect("nope")

    def test_browser_effects_property(self) -> None:
        reg = EffectRegistry()
        reg.register_browser("a", _FakeBrowserEffect())
        reg.register_browser("b", _FakeBrowserEffect())
        assert sorted(reg.browser_effects) == ["a", "b"]

    def test_post_effects_property(self) -> None:
        reg = EffectRegistry()
        reg.register_post("x", _FakePostEffect())
        assert reg.post_effects == ["x"]

    def test_is_browser_effect_false(self) -> None:
        reg = EffectRegistry()
        assert not reg.is_browser_effect("nonexistent")

    def test_is_post_effect_false(self) -> None:
        reg = EffectRegistry()
        assert not reg.is_post_effect("nonexistent")

    def test_overwrite_registration(self) -> None:
        reg = EffectRegistry()
        e1 = _FakeBrowserEffect()
        e2 = _FakeBrowserEffect()
        reg.register_browser("x", e1)
        reg.register_browser("x", e2)
        assert reg.get_browser_effect("x") is e2


# ── Bulk registration ────────────────────────────────────────────────────────


class TestBulkRegistration:
    def test_register_all_browser_effects(self) -> None:
        from demodsl.effects.browser_effects import register_all_browser_effects

        reg = EffectRegistry()
        register_all_browser_effects(reg)

        expected = {
            "spotlight", "highlight", "confetti", "typewriter", "glow",
            "shockwave", "sparkle", "cursor_trail", "cursor_trail_rainbow",
            "cursor_trail_comet", "cursor_trail_glow", "cursor_trail_line",
            "cursor_trail_particles", "cursor_trail_fire", "ripple",
            "neon_glow", "success_checkmark",
            "emoji_rain", "fireworks", "bubbles", "snow",
            "star_burst", "party_popper",
        }
        assert set(reg.browser_effects) == expected
        assert len(reg.browser_effects) == 23

    def test_register_all_post_effects(self) -> None:
        from demodsl.effects.post_effects import register_all_post_effects

        reg = EffectRegistry()
        register_all_post_effects(reg)

        expected = {
            "parallax", "zoom_pulse", "fade_in", "fade_out",
            "vignette", "glitch", "slide_in",
            "drone_zoom", "ken_burns", "zoom_to", "dolly_zoom", "elastic_zoom",
            "camera_shake", "whip_pan", "rotate",
            "letterbox", "film_grain", "color_grade", "focus_pull", "tilt_shift",
        }
        assert set(reg.post_effects) == expected
        assert len(reg.post_effects) == 20
