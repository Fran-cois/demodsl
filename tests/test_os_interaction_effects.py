"""Tests for OS desktop interaction effects (Phase 1)."""

from __future__ import annotations

from unittest.mock import MagicMock

from demodsl.effects.browser.context_menu import ContextMenuEffect
from demodsl.effects.browser.menu_dropdown import MenuDropdownEffect
from demodsl.effects.browser.window_animation import WindowAnimationEffect


class TestMenuDropdown:
    def test_inject_default_file_menu(self) -> None:
        eff = MenuDropdownEffect()
        mock = MagicMock()
        eff.inject(mock, {"menu": "File"})
        js = mock.call_args.args[0]
        assert "__demodsl_menu_dropdown" in js
        assert 'data-menu="File"' in js or "data-menu='File'" in js
        # Default items are present
        assert "Open" in js
        assert "Save" in js

    def test_custom_items(self) -> None:
        eff = MenuDropdownEffect()
        mock = MagicMock()
        eff.inject(mock, {"menu": "Custom", "items": ["Foo", "---", "Bar"]})
        js = mock.call_args.args[0]
        assert "Foo" in js and "Bar" in js

    def test_highlight(self) -> None:
        eff = MenuDropdownEffect()
        mock = MagicMock()
        eff.inject(mock, {"menu": "File", "highlight": 0, "color": "#FF0000"})
        js = mock.call_args.args[0]
        assert "#FF0000" in js

    def test_duration(self) -> None:
        eff = MenuDropdownEffect()
        mock = MagicMock()
        eff.inject(mock, {"menu": "File", "duration": 2.0})
        js = mock.call_args.args[0]
        assert "2000" in js  # 2.0s = 2000ms


class TestWindowAnimation:
    def test_open_main(self) -> None:
        eff = WindowAnimationEffect()
        mock = MagicMock()
        eff.inject(mock, {"animation": "open"})
        js = mock.call_args.args[0]
        assert "__demodsl_win_open" in js
        assert "document.body" in js

    def test_close_secondary_window(self) -> None:
        eff = WindowAnimationEffect()
        mock = MagicMock()
        eff.inject(mock, {"animation": "close", "target": 0})
        js = mock.call_args.args[0]
        assert "__demodsl_win_close" in js
        assert "__demodsl_secondary_window" in js
        assert "[0]" in js

    def test_minimize_uses_genie(self) -> None:
        eff = WindowAnimationEffect()
        mock = MagicMock()
        eff.inject(mock, {"animation": "minimize"})
        js = mock.call_args.args[0]
        # Genie uses scale + translate + skew
        assert "skewX" in js
        assert "scale(" in js

    def test_maximize(self) -> None:
        eff = WindowAnimationEffect()
        mock = MagicMock()
        eff.inject(mock, {"animation": "maximize"})
        js = mock.call_args.args[0]
        assert "__demodsl_win_maximize" in js

    def test_invalid_animation_defaults_to_open(self) -> None:
        eff = WindowAnimationEffect()
        mock = MagicMock()
        eff.inject(mock, {"animation": "bogus"})
        js = mock.call_args.args[0]
        assert "__demodsl_win_open" in js

    def test_duration_applied(self) -> None:
        eff = WindowAnimationEffect()
        mock = MagicMock()
        eff.inject(mock, {"animation": "close", "duration": 1.5})
        js = mock.call_args.args[0]
        assert "1500ms" in js


class TestContextMenu:
    def test_default_items(self) -> None:
        eff = ContextMenuEffect()
        mock = MagicMock()
        eff.inject(mock, {"target_x": 0.5, "target_y": 0.3})
        js = mock.call_args.args[0]
        assert "__demodsl_context_menu" in js
        assert "New Folder" in js
        assert "Get Info" in js

    def test_custom_items(self) -> None:
        eff = ContextMenuEffect()
        mock = MagicMock()
        eff.inject(mock, {"items": ["Copy", "Paste", "---", "Inspect"]})
        js = mock.call_args.args[0]
        assert "Copy" in js and "Paste" in js and "Inspect" in js

    def test_position_applied(self) -> None:
        eff = ContextMenuEffect()
        mock = MagicMock()
        eff.inject(mock, {"target_x": 0.25, "target_y": 0.75})
        js = mock.call_args.args[0]
        # Position rendered as vw/vh with 1 decimal
        assert "25.0vw" in js
        assert "75.0vh" in js

    def test_highlight_color(self) -> None:
        eff = ContextMenuEffect()
        mock = MagicMock()
        eff.inject(
            mock,
            {"items": ["A", "B", "C"], "highlight": 1, "color": "#FF00FF"},
        )
        js = mock.call_args.args[0]
        assert "#FF00FF" in js

    def test_safe_against_xss(self) -> None:
        eff = ContextMenuEffect()
        mock = MagicMock()
        eff.inject(mock, {"items": ["<script>alert(1)</script>"]})
        js = mock.call_args.args[0]
        assert "<script>" not in js
        assert "&lt;script&gt;" in js

    def test_separator_rendering(self) -> None:
        eff = ContextMenuEffect()
        mock = MagicMock()
        eff.inject(mock, {"items": ["A", "---", "B"]})
        js = mock.call_args.args[0]
        # The separator div uses a 1px height line
        assert "height:1px" in js


class TestRegistration:
    def test_effects_registered(self) -> None:
        from demodsl.effects.browser import _BROWSER_EFFECTS

        assert "menu_dropdown" in _BROWSER_EFFECTS
        assert "window_animation" in _BROWSER_EFFECTS
        assert "context_menu" in _BROWSER_EFFECTS
