"""Tests for demodsl.effects.popup_card — PopupCardOverlay."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from demodsl.effects.popup_card import (
    _ENTRANCE_ANIMATION,
    _EXIT_ANIMATION,
    _POSITION_CSS,
    _THEME_CSS,
    PopupCardOverlay,
)


class TestPopupCardOverlayInit:
    def test_defaults(self) -> None:
        overlay = PopupCardOverlay({})
        assert overlay.enabled is True
        assert overlay.position == "bottom-right"
        assert overlay.theme == "glass"
        assert overlay.max_width == 420
        assert overlay.animation == "slide"
        assert overlay.accent_color == "#818cf8"
        assert overlay.show_icon is True
        assert overlay.show_progress is True

    def test_custom_config(self) -> None:
        overlay = PopupCardOverlay(
            {
                "enabled": False,
                "position": "top-left",
                "theme": "dark",
                "max_width": 600,
                "animation": "fade",
                "accent_color": "#ff0000",
                "show_icon": False,
                "show_progress": False,
            }
        )
        assert overlay.enabled is False
        assert overlay.position == "top-left"
        assert overlay.theme == "dark"
        assert overlay.max_width == 600
        assert overlay.animation == "fade"
        assert overlay.accent_color == "#ff0000"
        assert overlay.show_icon is False
        assert overlay.show_progress is False


class TestPopupCardOverlayInject:
    def test_inject_calls_evaluate_js(self) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert "__demodsl_card_container" in js
        assert "__demodsl_card_show" in js
        assert "__demodsl_card_reveal_next" in js
        assert "__demodsl_card_hide" in js

    def test_inject_uses_theme(self) -> None:
        for theme in _THEME_CSS:
            overlay = PopupCardOverlay({"theme": theme})
            mock_eval = MagicMock()
            overlay.inject(mock_eval)
            mock_eval.assert_called_once()

    def test_inject_uses_position(self) -> None:
        for position in _POSITION_CSS:
            overlay = PopupCardOverlay({"position": position})
            mock_eval = MagicMock()
            overlay.inject(mock_eval)
            mock_eval.assert_called_once()

    def test_inject_animation_variants(self) -> None:
        for anim in _ENTRANCE_ANIMATION:
            overlay = PopupCardOverlay({"animation": anim})
            mock_eval = MagicMock()
            overlay.inject(mock_eval)
            js = mock_eval.call_args.args[0]
            assert _ENTRANCE_ANIMATION[anim] in js
            assert _EXIT_ANIMATION[anim] in js

    def test_inject_center_position_translate(self) -> None:
        overlay = PopupCardOverlay({"position": "bottom-center"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "translateX(-50%)" in js

    def test_inject_disabled_noop(self) -> None:
        overlay = PopupCardOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_not_called()


class TestPopupCardOverlayShow:
    @patch("demodsl.effects.popup_card.time")
    def test_show_basic(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock()
        overlay.show(mock_eval, title="Hello")
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert "window.__demodsl_card_show(" in js
        # The argument should be valid JSON
        json_str = js.split("window.__demodsl_card_show(")[1].rstrip(")")
        data = json.loads(json_str)
        assert data["title"] == "Hello"
        mock_time.sleep.assert_called_once_with(0.45)

    @patch("demodsl.effects.popup_card.time")
    def test_show_with_items(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock()
        overlay.show(mock_eval, title="Features", items=["A", "B", "C"], progressive=True)
        js = mock_eval.call_args.args[0]
        json_str = js.split("window.__demodsl_card_show(")[1].rstrip(")")
        data = json.loads(json_str)
        assert data["items"] == ["A", "B", "C"]
        assert data["progressive"] is True

    @patch("demodsl.effects.popup_card.time")
    def test_show_non_progressive(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock()
        overlay.show(mock_eval, items=["X"], progressive=False)
        js = mock_eval.call_args.args[0]
        json_str = js.split("window.__demodsl_card_show(")[1].rstrip(")")
        data = json.loads(json_str)
        assert data["progressive"] is False

    @patch("demodsl.effects.popup_card.time")
    def test_show_with_duration(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock()
        overlay.show(mock_eval, title="T", duration=5.0)
        js = mock_eval.call_args.args[0]
        json_str = js.split("window.__demodsl_card_show(")[1].rstrip(")")
        data = json.loads(json_str)
        assert data["duration"] == 5.0

    @patch("demodsl.effects.popup_card.time")
    def test_show_icon_default(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({"show_icon": True})
        mock_eval = MagicMock()
        overlay.show(mock_eval, title="T")
        js = mock_eval.call_args.args[0]
        json_str = js.split("window.__demodsl_card_show(")[1].rstrip(")")
        data = json.loads(json_str)
        assert data["icon"] == "💡"

    @patch("demodsl.effects.popup_card.time")
    def test_show_no_icon(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({"show_icon": False})
        mock_eval = MagicMock()
        overlay.show(mock_eval, title="T")
        js = mock_eval.call_args.args[0]
        json_str = js.split("window.__demodsl_card_show(")[1].rstrip(")")
        data = json.loads(json_str)
        assert data["icon"] is None

    def test_show_disabled_noop(self) -> None:
        overlay = PopupCardOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.show(mock_eval, title="T")
        mock_eval.assert_not_called()


class TestPopupCardOverlayRevealNext:
    @patch("demodsl.effects.popup_card.time")
    def test_reveal_next_returns_value(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock(return_value=2)
        result = overlay.reveal_next(mock_eval)
        mock_eval.assert_called_once_with("window.__demodsl_card_reveal_next()")
        assert result == 2
        mock_time.sleep.assert_called_once_with(0.35)

    @patch("demodsl.effects.popup_card.time")
    def test_reveal_next_returns_minus_one_when_done(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock(return_value=-1)
        result = overlay.reveal_next(mock_eval)
        assert result == -1

    @patch("demodsl.effects.popup_card.time")
    def test_reveal_next_handles_none(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock(return_value=None)
        result = overlay.reveal_next(mock_eval)
        assert result == -1

    def test_reveal_next_disabled(self) -> None:
        overlay = PopupCardOverlay({"enabled": False})
        mock_eval = MagicMock()
        result = overlay.reveal_next(mock_eval)
        assert result == -1
        mock_eval.assert_not_called()


class TestPopupCardOverlayHide:
    @patch("demodsl.effects.popup_card.time")
    def test_hide_calls_js(self, mock_time: MagicMock) -> None:
        overlay = PopupCardOverlay({})
        mock_eval = MagicMock()
        overlay.hide(mock_eval)
        mock_eval.assert_called_once_with("window.__demodsl_card_hide()")
        mock_time.sleep.assert_called_once_with(0.4)

    def test_hide_disabled_noop(self) -> None:
        overlay = PopupCardOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.hide(mock_eval)
        mock_eval.assert_not_called()
