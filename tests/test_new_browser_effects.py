"""Tests for new browser effects (batches 2+3) — 34 effects without prior coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demodsl.effects.browser import (
    AnimatedAnnotationEffect,
    AuroraEffect,
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
    GlassmorphismFloatEffect,
    GlassReflectionEffect,
    HeatmapEffect,
    InfiniteCanvasEffect,
    KeyboardShortcutEffect,
    LightningEffect,
    MagnifierEffect,
    MorphTransitionEffect,
    NotificationToastEffect,
    OdometerEffect,
    PaperTextureEffect,
    PerspectiveTiltEffect,
    ProgressRingEffect,
    RainEffect,
    RetroBrowserEffect,
    Rotation3DEffect,
    ScrollParallaxEffect,
    SkeletonLoadingEffect,
    SplitScreenEffect,
    StarfieldEffect,
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
    ("retro_browser", RetroBrowserEffect, "__retro_browser"),  # default skin = ie6
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
    # Ambient / weather effects
    ("rain", RainEffect, "__demodsl_rain"),
    ("starfield", StarfieldEffect, "__demodsl_starfield"),
    ("lightning", LightningEffect, "__demodsl_lightning"),
    ("aurora", AuroraEffect, "__demodsl_aurora"),
]


class TestNewEffectInject:
    """Every new effect must produce JS when injected."""

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_calls_evaluate_js(self, name: str, cls: type, expected_id: str | None) -> None:
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert isinstance(js, str)
        assert len(js) > 50

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_contains_id(self, name: str, cls: type, expected_id: str | None) -> None:
        if expected_id is None:
            pytest.skip("Effect uses dynamic ID")
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert expected_id in js

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_is_iife_wrapped(self, name: str, cls: type, expected_id: str | None) -> None:
        effect = cls()
        mock_eval = MagicMock()
        effect.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "(function()" in js or "(() =>" in js

    @pytest.mark.parametrize("name,cls,expected_id", NEW_EFFECTS)
    def test_inject_cleans_up(self, name: str, cls: type, expected_id: str | None) -> None:
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


class TestRetroBrowserParams:
    def test_ie6_default(self) -> None:
        eff = RetroBrowserEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {})
        js = mock_eval.call_args.args[0]
        assert "__retro_browser" in js
        assert "Internet Explorer" in js

    def test_firefox(self) -> None:
        eff = RetroBrowserEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "firefox"})
        js = mock_eval.call_args.args[0]
        assert "Firefox" in js

    def test_netscape(self) -> None:
        eff = RetroBrowserEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "netscape"})
        js = mock_eval.call_args.args[0]
        assert "Netscape" in js

    def test_safari(self) -> None:
        eff = RetroBrowserEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "safari", "url": "https://example.com/pricing"})
        js = mock_eval.call_args.args[0]
        assert "__safari_browser" in js
        assert "__safari_dots" in js
        assert "example.com/pricing" in js
        # Safari skin has no classic menu bar / status bar.
        assert "__retro_menubar" not in js
        assert "__retro_statusbar" not in js

    def test_invalid_skin_falls_back(self) -> None:
        eff = RetroBrowserEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"text": "chrome_ancient"})
        js = mock_eval.call_args.args[0]
        assert "__retro_browser" in js

    def test_cleanup_removes_safari_element(self) -> None:
        eff = RetroBrowserEffect()
        mock_eval = MagicMock()
        eff.cleanup(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "__safari_browser" in js


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

    @pytest.mark.parametrize("pos", ["top-right", "top-left", "bottom-right", "bottom-left"])
    def test_valid_positions(self, pos: str) -> None:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, {"position": pos})
        mock_eval.assert_called_once()


class TestNotificationToastCustomContent:
    HEALTHCARE = [
        {"app": "Granit", "title": "Tiers-payant envoyé", "body": "14 dossiers à la CPAM"},
        {"app": "Granit", "title": "Facturation validée", "body": "2 296 €", "color": "#5C9E6B"},
    ]

    @staticmethod
    def _inject(params: dict) -> str:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, params)
        return mock_eval.call_args.args[0]

    def test_custom_notifications_replace_defaults(self) -> None:
        js = self._inject({"notifications": self.HEALTHCARE})
        assert "Tiers-payant envoyé" in js
        assert "Facturation validée" in js
        assert "Xcode" not in js and "Slack" not in js

    def test_per_item_color_is_used(self) -> None:
        js = self._inject({"color": "#D4583A", "notifications": self.HEALTHCARE})
        assert "#5C9E6B" in js  # second item overrides the effect-level colour
        assert "#D4583A" in js  # first item inherits it

    def test_falls_back_to_defaults_when_empty_or_invalid(self) -> None:
        for value in ([], None, "not-a-list", [123, "x"]):
            js = self._inject({"notifications": value})
            assert "Xcode" in js

    def test_windows_style_also_accepts_custom(self) -> None:
        js = self._inject({"style": "windows", "notifications": self.HEALTHCARE})
        assert "Tiers-payant envoyé" in js
        assert "Visual Studio Code" not in js

    def test_caller_markup_is_escaped(self) -> None:
        js = self._inject(
            {"notifications": [{"app": "X", "title": "<img src=x onerror=boom>", "body": "b"}]}
        )
        assert "<img" not in js
        assert "&lt;img" in js

    def test_quote_and_backslash_cannot_break_out_of_the_js_literal(self) -> None:
        js = self._inject(
            {"notifications": [{"app": "E", "title": "back\\", "body": "'); alert(1); ('"}]}
        )
        for line in js.splitlines():
            if line.strip().startswith("{app:"):
                assert line.count("'") % 2 == 0

    def test_item_count_is_capped(self) -> None:
        many = [{"app": "A", "title": f"n{i}", "body": "b"} for i in range(20)]
        js = self._inject({"notifications": many})
        assert js.count("{app:") <= 6


class TestNotificationToastTheming:
    @staticmethod
    def _inject(params: dict) -> str:
        eff = NotificationToastEffect()
        mock_eval = MagicMock()
        eff.inject(mock_eval, params)
        return mock_eval.call_args.args[0]

    @pytest.mark.parametrize("style", ["macos", "windows"])
    def test_theme_surface_and_ink_drive_the_chrome(self, style: str) -> None:
        js = self._inject({"style": style, "surface": "#FFFFFF", "ink": "#0F0C08"})
        assert "background: #FFFFFF;" in js
        assert "color: #0F0C08;" in js

    @pytest.mark.parametrize("style", ["macos", "windows"])
    def test_no_hardcoded_light_on_dark_text_remains(self, style: str) -> None:
        js = self._inject({"style": style, "surface": "#FFFFFF", "ink": "#0F0C08"})
        for leftover in ("rgba(255,255,255,0.55)", "rgba(255,255,255,0.6)", "#f5f5f5"):
            assert leftover not in js

    def test_ink_is_derived_when_only_a_surface_is_given(self) -> None:
        js = self._inject({"surface": "#FFFFFF"})
        assert "color: #101418;" in js  # readable_ink() picked the dark ink

    def test_defaults_keep_the_native_dark_look(self) -> None:
        js = self._inject({})
        assert "background: #282A2D;" in js
        assert "color: #F0F0F0;" in js


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


class TestDepthBlurRackFocus:
    """``focus_position_to`` turns the static tilt-shift into a focus pull."""

    def _js(self, params: dict) -> str:
        mock_eval = MagicMock()
        DepthBlurEffect().inject(mock_eval, params)
        return str(mock_eval.call_args[0][0])

    def test_without_a_destination_the_band_is_written_once(self) -> None:
        js = self._js({"focus_position": 0.3})
        assert "requestAnimationFrame(pull)" not in js

    def test_a_destination_installs_the_pull_loop(self) -> None:
        js = self._js({"focus_position": 0.2, "focus_position_to": 0.8})
        assert "requestAnimationFrame(pull)" in js
        assert "const FROM = 0.2, TO = 0.8" in js

    def test_a_destination_equal_to_the_start_is_a_no_op(self) -> None:
        js = self._js({"focus_position": 0.4, "focus_position_to": 0.4})
        assert "requestAnimationFrame(pull)" not in js

    def test_an_out_of_range_destination_is_clamped(self) -> None:
        js = self._js({"focus_position": 0.5, "focus_position_to": 9.0})
        assert "TO = 0.9" in js

    def test_the_pull_stops_once_the_overlay_is_gone(self) -> None:
        js = self._js({"focus_position": 0.2, "focus_position_to": 0.8})
        assert "overlay.isConnected" in js


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
        from demodsl.effects.browser import _BROWSER_EFFECTS, register_all_browser_effects

        reg = EffectRegistry()
        register_all_browser_effects(reg)
        # Catches a dropped registration without hard-coding a total that goes
        # stale every time an effect is added.
        assert sorted(reg.browser_effects) == sorted(_BROWSER_EFFECTS)
        assert len(reg.browser_effects) >= len(NEW_EFFECTS)
