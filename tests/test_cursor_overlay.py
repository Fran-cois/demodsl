"""Tests for demodsl.effects.cursor — CursorOverlay."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from demodsl.effects.cursor import CursorOverlay


class TestCursorOverlayInit:
    def test_defaults(self) -> None:
        overlay = CursorOverlay({})
        assert overlay.visible is True
        assert overlay.style == "dot"
        assert overlay.color == "#ef4444"
        assert overlay.size == 20
        assert overlay.click_effect == "ripple"
        assert overlay.smooth == 0.4
        assert overlay.bezier is True

    def test_custom_config(self) -> None:
        overlay = CursorOverlay(
            {
                "visible": False,
                "style": "pointer",
                "color": "#00ff00",
                "size": 32,
                "click_effect": "pulse",
                "smooth": 0.6,
            }
        )
        assert overlay.visible is False
        assert overlay.style == "pointer"
        assert overlay.color == "#00ff00"
        assert overlay.size == 32
        assert overlay.click_effect == "pulse"
        assert overlay.smooth == 0.6


class TestCursorOverlayInject:
    def test_inject_dot_style(self) -> None:
        overlay = CursorOverlay({"style": "dot"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert "__demodsl_cursor" in js
        assert "border-radius:50%" in js

    def test_inject_pointer_style(self) -> None:
        overlay = CursorOverlay({"style": "pointer"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert "background:url(" in js

    def test_inject_ripple_click_effect(self) -> None:
        overlay = CursorOverlay({"click_effect": "ripple"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "__demodsl_click_ripple" in js

    def test_inject_pulse_click_effect(self) -> None:
        overlay = CursorOverlay({"click_effect": "pulse"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "scale(1.8)" in js

    def test_inject_none_click_effect(self) -> None:
        overlay = CursorOverlay({"click_effect": "none"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "scale(1.8)" not in js

    def test_inject_not_visible_noop(self) -> None:
        overlay = CursorOverlay({"visible": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_not_called()


class TestCursorOverlayMoveTo:
    @patch("demodsl.effects.cursor.time")
    def test_move_to_calls_js(self, mock_time: MagicMock) -> None:
        overlay = CursorOverlay({"smooth": 0.3})
        mock_eval = MagicMock()
        overlay.move_to(mock_eval, 100.0, 200.0)
        mock_eval.assert_called_once_with("window.__demodsl_cursor_move(100.0, 200.0)")
        mock_time.sleep.assert_called_once_with(0.35)

    def test_move_to_not_visible_noop(self) -> None:
        overlay = CursorOverlay({"visible": False})
        mock_eval = MagicMock()
        overlay.move_to(mock_eval, 50, 50)
        mock_eval.assert_not_called()


class TestCursorOverlayTriggerClick:
    @patch("demodsl.effects.cursor.time")
    def test_trigger_click_calls_js(self, mock_time: MagicMock) -> None:
        overlay = CursorOverlay({"click_effect": "ripple"})
        mock_eval = MagicMock()
        overlay.trigger_click(mock_eval)
        mock_eval.assert_called_once_with("window.__demodsl_cursor_click()")
        mock_time.sleep.assert_called_once_with(0.35)

    def test_trigger_click_not_visible_noop(self) -> None:
        overlay = CursorOverlay({"visible": False})
        mock_eval = MagicMock()
        overlay.trigger_click(mock_eval)
        mock_eval.assert_not_called()

    def test_trigger_click_effect_none_noop(self) -> None:
        overlay = CursorOverlay({"click_effect": "none"})
        mock_eval = MagicMock()
        overlay.trigger_click(mock_eval)
        mock_eval.assert_not_called()


class TestCursorOverlayBezier:
    def test_bezier_false_keeps_css_transition(self) -> None:
        overlay = CursorOverlay({"bezier": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args[0][0]
        assert "transition:" in js
        assert "__cbez" not in js

    def test_bezier_true_uses_raf_animation(self) -> None:
        overlay = CursorOverlay({"bezier": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args[0][0]
        assert "__cbez" in js
        assert "requestAnimationFrame" in js

    def test_bezier_default_true_injects_animation(self) -> None:
        overlay = CursorOverlay({})
        assert overlay.bezier is True
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args[0][0]
        assert "requestAnimationFrame" in js
