"""Tests for new browser effects (batches 2+3) — 34 effects without prior coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demodsl.effects.browser import (
    AnimatedAnnotationEffect,
    ChartDrawEffect,
    ClickParticlesEffect,
    ClickRippleEffect,
    ConnectionTraceEffect,
    DarkModeToggleEffect,
    DashboardTimelapseEffect,
    DepthBlurEffect,
    DeviceFrameEffect,
    DirectionalBlurEffect,
    DragDropEffect,
    GlassReflectionEffect,
    GlassmorphismFloatEffect,
    HeatmapEffect,
    InfiniteCanvasEffect,
    KeyboardShortcutEffect,
    MagnifierEffect,
    MorphTransitionEffect,
    NotificationToastEffect,
    OdometerEffect,
    PaperTextureEffect,
    PerspectiveTiltEffect,
    ProgressRingEffect,
    Rotation3DEffect,
    ScrollParallaxEffect,
    SkeletonLoadingEffect,
    SplitScreenEffect,
    StickyElementEffect,
    TabSwipeEffect,
    TooltipPopEffect,
    UiShimmerEffect,
    XrayViewEffect,
    ZoomFocusEffect,
    ZoomThroughEffect,
)
from demodsl.effects.registry import EffectRegistry


# ── Parametrized inject tests ─────────────────────────────────────────────────

NEW_EFFECTS: list[tuple[str, type, str | None]] = [
    ("keyboard_shortcut", KeyboardShortcutEffect, "__demodsl_keyboard_shortcut"),
    ("zoom_focus", ZoomFocusEffect, None),  # no static root id
    ("depth_blur", DepthBlurEffect, "__demodsl_depth_blur"),
    ("animated_annotation", AnimatedAnnotationEffect, "__demodsl_annotation"),
    ("perspective_tilt", PerspectiveTiltEffect, None),  # transforms body directly
    ("glassmorphism_float", GlassmorphismFloatEffect, "__demodsl_glass_float"),
    ("morph_transition", MorphTransitionEffect, "__demodsl_morph"),
    ("scroll_parallax", ScrollParallaxEffect, "__demodsl_parallax"),
    ("dark_mode_toggle", DarkModeToggleEffect, "__demodsl_dark_toggle"),
    ("click_particles", ClickParticlesEffect, None),
    ("skeleton_loading", SkeletonLoadingEffect, "__demodsl_skeleton"),
    ("tooltip_pop", TooltipPopEffect, "__demodsl_tpop_style"),
    ("magnifier", MagnifierEffect, "__demodsl_magnifier"),
    ("drag_drop", DragDropEffect, "__demodsl_drag_drop"),
    ("progress_ring", ProgressRingEffect, "__demodsl_progress_ring"),
    ("device_frame", DeviceFrameEffect, "__demodsl_device_frame"),
    ("rotation_3d", Rotation3DEffect, "__demodsl_3d_layer"),
    ("split_screen", SplitScreenEffect, "__demodsl_split_screen"),
    ("directional_blur", DirectionalBlurEffect, "__demodsl_directional_blur"),
    ("notification_toast", NotificationToastEffect, "__demodsl_notification_toast"),
    ("dashboard_timelapse", DashboardTimelapseEffect, "__demodsl_dash_card"),
    ("click_ripple", ClickRippleEffect, "__demodsl_click_ripple"),
    ("connection_trace", ConnectionTraceEffect, "__demodsl_connection_trace"),
    ("sticky_element", StickyElementEffect, "__demodsl_sticky"),
    ("chart_draw", ChartDrawEffect, "__demodsl_chart_draw"),
    ("odometer", OdometerEffect, "__demodsl_odometer"),
    ("heatmap", HeatmapEffect, "__demodsl_heatmap"),
    ("zoom_through", ZoomThroughEffect, "__demodsl_zoom_through"),
    ("infinite_canvas", InfiniteCanvasEffect, "__demodsl_infinite"),
    ("tab_swipe", TabSwipeEffect, "__demodsl_tab_swipe"),
    ("xray_view", XrayViewEffect, "__demodsl_xray"),
    ("glass_reflection", GlassReflectionEffect, "__demodsl_glass_reflection"),
    ("paper_texture", PaperTextureEffect, "__demodsl_paper"),
    ("ui_shimmer", UiShimmerEffect, "__demodsl_shimmer"),
]


class TestNewEffectInject:
    """Every new effect must produce JS when injected."""

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_calls_evaluate_js(
        self, name: str, cls: type, expected_id: str | None
    ) -> None:
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert isinstance(js, str)
        assert len(js) > 50

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_contains_id(
        self, name: str, cls: type, expected_id: str | None
    ) -> None:
        if expected_id is None:
            pytest.skip("Effect uses dynamic ID")
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert expected_id in js

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_is_iife_wrapped(
        self, name: str, cls: type, expected_id: str | None
    ) -> None:
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "(function()" in js or "(() =>" in js

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_cleans_up(
        self, name: str, cls: type, expected_id: str | None
    ) -> None:
        """Effects should have a cleanup / setTimeout for removal."""
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "setTimeout" in js or "remove()" in js or "cleanup" in js.lower()


# ── Custom params tests ──────────────────────────────────────────────────────


class TestDeviceFrameParams:
    def test_macbook(self) -> None:
        eff = DeviceFrameEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "macbook"})
        js = mock_eval.call_args.args[0]
        assert "border-radius" in js or "radius" in js.lower()

    def test_ipad(self) -> None:
        eff = DeviceFrameEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "ipad"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_device_frame" in js

    def test_monitor(self) -> None:
        eff = DeviceFrameEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "monitor"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_device_frame" in js

    def test_invalid_device_falls_back(self) -> None:
        eff = DeviceFrameEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "invalid_device"})
        js = mock_eval.call_args.args[0]
        # Should fall back to 'macbook'
        assert "__demodsl_device_frame" in js


class TestNotificationToastParams:
    def test_macos_style(self) -> None:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"style": "macos"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_notification_toast" in js

    def test_windows_style(self) -> None:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"style": "windows"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_notification_toast" in js

    def test_invalid_style_falls_back(self) -> None:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"style": "invalid"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_notification_toast" in js

    @pytest.mark.parametrize(
        "pos", ["top-right", "top-left", "bottom-right", "bottom-left"]
    )
    def test_valid_positions(self, pos: str) -> None:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"position": pos})
        mock_eval.assert_called_once()


class TestPerspectiveTiltParams:
    def test_left_direction(self) -> None:
        eff = PerspectiveTiltEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"direction": "left", "angle": 10})
        js = mock_eval.call_args.args[0]
        assert "perspective" in js
        assert "rotateY" in js

    def test_right_direction(self) -> None:
        eff = PerspectiveTiltEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"direction": "right", "angle": 12})
        js = mock_eval.call_args.args[0]
        assert "perspective" in js
        assert "rotateY" in js


class TestChartDrawParams:
    def test_custom_color(self) -> None:
        eff = ChartDrawEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"color": "#ff0000", "intensity": 0.9})
        js = mock_eval.call_args.args[0]
        assert "#ff0000" in js

    def test_default_params(self) -> None:
        eff = ChartDrawEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_chart_draw" in js


class TestSkeletonLoadingParams:
    def test_custom_color(self) -> None:
        eff = SkeletonLoadingEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"color": "#00ff00"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_skeleton" in js

    def test_default_params(self) -> None:
        eff = SkeletonLoadingEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {})
        mock_eval.assert_called_once()


class TestMorphTransitionParams:
    def test_custom_params(self) -> None:
        eff = MorphTransitionEffect()
        mock_eval = MagicMock()
        eff.inject(
            mock_eval,
            {
                "color": "#6366f1",
                "from_x": 0.3,
                "from_y": 0.5,
                "target_x": 0.6,
                "target_y": 0.4,
                "scale": 2.5,
            },
        )
        js = mock_eval.call_args.args[0]
        assert "__demodsl_morph" in js


class TestKeyboardShortcutParams:
    def test_custom_keys(self) -> None:
        eff = KeyboardShortcutEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "Ctrl+C"})
        js = mock_eval.call_args.args[0]
        assert "__demodsl_keyboard_shortcut" in js
        assert "Ctrl" in js
        assert "C" in js

    def test_default_keys(self) -> None:
        eff = KeyboardShortcutEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {})
        mock_eval.assert_called_once()


# ── Registry integration ─────────────────────────────────────────────────────


class TestNewEffectsRegistry:
    def test_all_new_effects_registered(self) -> None:
        from demodsl.effects.browser import register_all_browser_effects

        reg = EffectRegistry()
        register_all_browser_effects(reg)
        for name, cls, _ in NEW_EFFECTS:
            handler = reg.get_browser_effect(name)
            assert handler is not None, f"Effect '{name}' not found in registry"
            assert isinstance(handler, cls)

    def test_total_browser_effects_count(self) -> None:
        from demodsl.effects.browser import register_all_browser_effects

        reg = EffectRegistry()
        register_all_browser_effects(reg)
        # 33 original + 34 new = 67 total
        assert len(reg.browser_effects) == 77
