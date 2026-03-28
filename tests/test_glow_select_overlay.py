"""Tests for demodsl.effects.glow_select — GlowSelectOverlay."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from demodsl.effects.glow_select import GlowSelectOverlay


class TestGlowSelectOverlayInit:
    def test_defaults(self) -> None:
        overlay = GlowSelectOverlay({})
        assert overlay.enabled is True
        assert overlay.colors == ["#a855f7", "#6366f1", "#ec4899", "#a855f7"]
        assert overlay.duration == 0.8
        assert overlay.padding == 8
        assert overlay.border_radius == 12
        assert overlay.intensity == 0.9

    def test_custom_config(self) -> None:
        overlay = GlowSelectOverlay(
            {
                "enabled": False,
                "colors": ["#ff0000", "#00ff00"],
                "duration": 1.5,
                "padding": 16,
                "border_radius": 8,
                "intensity": 0.5,
            }
        )
        assert overlay.enabled is False
        assert overlay.colors == ["#ff0000", "#00ff00"]
        assert overlay.duration == 1.5
        assert overlay.padding == 16
        assert overlay.border_radius == 8
        assert overlay.intensity == 0.5


class TestGlowSelectOverlayInject:
    def test_inject_calls_evaluate_js(self) -> None:
        overlay = GlowSelectOverlay({})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert "__demodsl_glow_overlay" in js
        assert "__demodsl_glow_show" in js
        assert "__demodsl_glow_hide" in js
        assert "hue-rotate" in js

    def test_inject_includes_colors(self) -> None:
        overlay = GlowSelectOverlay({"colors": ["#ff0000", "#00ff00"]})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "#ff0000" in js
        assert "#00ff00" in js

    def test_inject_single_color_fallback(self) -> None:
        overlay = GlowSelectOverlay({"colors": ["#abcdef"]})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "#abcdef" in js

    def test_inject_disabled_noop(self) -> None:
        overlay = GlowSelectOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_not_called()


class TestGlowSelectOverlayShow:
    @patch("demodsl.effects.glow_select.time")
    def test_show_calls_js(self, mock_time: MagicMock) -> None:
        overlay = GlowSelectOverlay({})
        mock_eval = MagicMock()
        bbox = {"x": 10, "y": 20, "width": 100, "height": 50}
        overlay.show(mock_eval, bbox)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert "window.__demodsl_glow_show(10, 20, 100, 50)" in js
        mock_time.sleep.assert_called_once_with(0.3)

    def test_show_disabled_noop(self) -> None:
        overlay = GlowSelectOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.show(mock_eval, {"x": 0, "y": 0, "width": 10, "height": 10})
        mock_eval.assert_not_called()


class TestGlowSelectOverlayHide:
    @patch("demodsl.effects.glow_select.time")
    def test_hide_calls_js(self, mock_time: MagicMock) -> None:
        overlay = GlowSelectOverlay({})
        mock_eval = MagicMock()
        overlay.hide(mock_eval)
        mock_eval.assert_called_once_with("window.__demodsl_glow_hide()")
        mock_time.sleep.assert_called_once_with(0.35)

    def test_hide_disabled_noop(self) -> None:
        overlay = GlowSelectOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.hide(mock_eval)
        mock_eval.assert_not_called()
