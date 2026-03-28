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
            "spotlight",
            "highlight",
            "confetti",
            "typewriter",
            "glow",
            "shockwave",
            "sparkle",
            "cursor_trail",
            "cursor_trail_rainbow",
            "cursor_trail_comet",
            "cursor_trail_glow",
            "cursor_trail_line",
            "cursor_trail_particles",
            "cursor_trail_fire",
            "ripple",
            "neon_glow",
            "success_checkmark",
            "emoji_rain",
            "fireworks",
            "bubbles",
            "snow",
            "star_burst",
            "party_popper",
            # New effects
            "text_highlight",
            "text_scramble",
            "magnetic_hover",
            "tooltip_annotation",
            "morphing_background",
            "matrix_rain",
            "frosted_glass",
            "progress_bar",
            "countdown_timer",
            "callout_arrow",
        }
        assert set(reg.browser_effects) == expected
        assert len(reg.browser_effects) == 33

    def test_register_all_post_effects(self) -> None:
        from demodsl.effects.post_effects import register_all_post_effects

        reg = EffectRegistry()
        register_all_post_effects(reg)

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
        }
        assert set(reg.post_effects) == expected
        assert len(reg.post_effects) == 30


# ── EFFECT_VALID_PARAMS sync guard ────────────────────────────────────────────


class TestEffectValidParamsSync:
    """Parse browser_effects.py and post_effects.py via AST, extract all
    params.get("key") calls per class, and verify they match EFFECT_VALID_PARAMS."""

    def test_effect_valid_params_matches_code(self) -> None:
        import ast
        import inspect

        import demodsl.effects.browser_effects as browser_mod
        import demodsl.effects.post_effects as post_mod
        from demodsl.models import EFFECT_VALID_PARAMS

        all_code_params: dict[str, set[str]] = {}

        for mod in (browser_mod, post_mod):
            source = inspect.getsource(mod)
            tree = ast.parse(source)

            # Build a map from class name to the effect name it's registered under
            # We use the class's inject()/apply() method's params.get() keys
            for cls_node in ast.walk(tree):
                if not isinstance(cls_node, ast.ClassDef):
                    continue
                # Find the method (inject for browser, apply for post)
                for method in cls_node.body:
                    if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if method.name not in ("inject", "apply"):
                        continue

                    # Extract params.get("key") calls
                    keys: set[str] = set()
                    for node in ast.walk(method):
                        if (
                            isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "get"
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "params"
                            and node.args
                            and isinstance(node.args[0], ast.Constant)
                            and isinstance(node.args[0].value, str)
                        ):
                            keys.add(node.args[0].value)

                    if keys:
                        # Try to find the effect name by looking for the
                        # register_* function calls — we'll use the class name
                        all_code_params[cls_node.name] = keys

        # Now match against EFFECT_VALID_PARAMS registrations
        from demodsl.effects.browser_effects import register_all_browser_effects
        from demodsl.effects.post_effects import register_all_post_effects

        reg = EffectRegistry()
        register_all_browser_effects(reg)
        register_all_post_effects(reg)

        # Build class-name → effect-name map
        class_to_name: dict[str, str] = {}
        for name, handler in reg._browser.items():
            class_to_name[type(handler).__name__] = name
        for name, handler in reg._post.items():
            class_to_name[type(handler).__name__] = name

        mismatches: list[str] = []
        for class_name, code_keys in all_code_params.items():
            effect_name = class_to_name.get(class_name)
            if effect_name is None:
                continue
            declared = EFFECT_VALID_PARAMS.get(effect_name)
            if declared is None:
                mismatches.append(
                    f"{effect_name}: missing from EFFECT_VALID_PARAMS (code uses: {sorted(code_keys)})"
                )
                continue
            if not code_keys.issubset(declared):
                extra = code_keys - declared
                mismatches.append(
                    f"{effect_name}: code uses {sorted(extra)} not declared in EFFECT_VALID_PARAMS"
                )

        assert not mismatches, (
            "EFFECT_VALID_PARAMS out of sync with code:\n"
            + "\n".join(f"  - {m}" for m in mismatches)
        )

    def test_effect_type_matches_valid_params_keys(self) -> None:
        """Every value in EffectType must have a corresponding EFFECT_VALID_PARAMS entry
        and vice-versa."""
        from typing import get_args

        from demodsl.models import EFFECT_VALID_PARAMS, EffectType

        effect_types = set(get_args(EffectType))
        param_keys = set(EFFECT_VALID_PARAMS.keys())

        missing_from_params = effect_types - param_keys
        extra_in_params = param_keys - effect_types

        errors: list[str] = []
        if missing_from_params:
            errors.append(
                f"EffectType values missing from EFFECT_VALID_PARAMS: {sorted(missing_from_params)}"
            )
        if extra_in_params:
            errors.append(
                f"EFFECT_VALID_PARAMS keys not in EffectType: {sorted(extra_in_params)}"
            )
        assert not errors, "\n".join(errors)
