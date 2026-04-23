"""Tests for Windows XP theme, XP cursor, dock bounce, plugin effect types,
and the non-reload cleanup_browser_effects logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from demodsl.effects.cursor import CursorOverlay
from demodsl.effects.os_background import OsBackgroundOverlay
from demodsl.models import Effect
from demodsl.models.overlays import BackgroundConfig, CursorConfig, OsApp


# ── BackgroundConfig: XP theme ────────────────────────────────────────────────


class TestBackgroundConfigXpTheme:
    def test_xp_theme_accepted(self) -> None:
        cfg = BackgroundConfig(os="windows", theme="xp")
        assert cfg.theme == "xp"

    def test_xp_theme_with_custom_wallpaper(self) -> None:
        cfg = BackgroundConfig(os="windows", theme="xp", wallpaper_color="#3a6ea5")
        assert cfg.wallpaper_color == "#3a6ea5"


# ── CursorConfig: XP style ───────────────────────────────────────────────────


class TestCursorConfigXpStyle:
    def test_xp_style_accepted(self) -> None:
        cfg = CursorConfig(style="xp")
        assert cfg.style == "xp"

    def test_invalid_cursor_style_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CursorConfig(style="win98")


# ── CursorOverlay: XP cursor injection ───────────────────────────────────────


class TestCursorOverlayXp:
    def test_xp_cursor_svg_injected(self) -> None:
        overlay = CursorOverlay({"style": "xp", "visible": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        # XP cursor uses a distinct SVG with a miter join and drop shadow
        assert "miter" in js
        assert "feDropShadow" in js or "filter" in js

    def test_pointer_cursor_not_affected(self) -> None:
        overlay = CursorOverlay({"style": "pointer", "visible": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "miter" not in js  # no XP SVG

    def test_dot_cursor_not_affected(self) -> None:
        overlay = CursorOverlay({"style": "dot", "visible": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "miter" not in js


# ── OsBackgroundOverlay: Windows XP JS ───────────────────────────────────────


class TestOsBackgroundXp:
    def test_xp_generates_luna_title_bar(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "theme": "xp"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        # Luna blue gradient colors
        assert "#0831D9" in js or "#0A246A" in js
        assert "Tahoma" in js

    def test_xp_not_used_for_dark_theme(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "theme": "dark"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "Tahoma" not in js

    def test_xp_secondary_windows(self) -> None:
        overlay = OsBackgroundOverlay(
            {
                "os": "windows",
                "theme": "xp",
                "secondary_windows": [
                    {"title": "My Doc", "x": 50, "y": 50, "width": 400, "height": 300},
                ],
            }
        )
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "My Doc" in js
        assert "__demodsl_secondary_window" in js


# ── OsApp: bounce field ──────────────────────────────────────────────────────


class TestOsAppBounce:
    def test_bounce_default_false(self) -> None:
        app = OsApp(name="Finder", color="#2196F3")
        assert app.bounce is False

    def test_bounce_true(self) -> None:
        app = OsApp(name="Terminal", color="#333", bounce=True)
        assert app.bounce is True

    def test_bounce_in_dock_js(self) -> None:
        overlay = OsBackgroundOverlay(
            {
                "os": "macos",
                "show_dock": True,
                "apps": [
                    {"name": "Terminal", "color": "#333", "bounce": True},
                ],
            }
        )
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "data-bounce='1'" in js
        assert "__demodsl_dock_bounce" in js


# ── Dock magnification / interaction ──────────────────────────────────────────


class TestDockInteraction:
    def test_dock_icons_have_data_attributes(self) -> None:
        overlay = OsBackgroundOverlay(
            {
                "os": "macos",
                "show_dock": True,
                "apps": [
                    {
                        "name": "Safari",
                        "color": "#3B82F6",
                        "url": "https://example.com",
                    },
                ],
            }
        )
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "data-name='Safari'" in js
        assert "data-url='https://example.com'" in js

    def test_dock_magnification_js(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_dock": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "scale(1.5)" in js  # primary icon magnification
        assert "scale(1.25)" in js  # neighbor


# ── Menu bar interactivity (macOS) ────────────────────────────────────────────


class TestMenuBarInteractivity:
    def test_menu_items_have_data_menu(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_menu_bar": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "data-menu='File'" in js
        assert "data-menu='Edit'" in js
        assert "__demodsl_menu_click" in js

    def test_status_icons_dispatch_events(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_menu_bar": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "__demodsl_status_click" in js
        assert "data-status='wifi'" in js


# ── Plugin effect type registration ──────────────────────────────────────────


class TestPluginEffectTypeRegistration:
    def test_register_and_use(self) -> None:
        from demodsl.models.effects import register_plugin_effect_type

        register_plugin_effect_type("test_my_custom_fx", {"color", "speed"})
        # Model should accept it
        eff = Effect(type="test_my_custom_fx", color="#fff")
        assert eff.type == "test_my_custom_fx"

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Unknown effect type"):
            Effect(type="completely_unknown_effect_xyz_123")


# ── Effect model: new OS interaction types ────────────────────────────────────


class TestEffectModelNewTypes:
    def test_menu_dropdown(self) -> None:
        eff = Effect(type="menu_dropdown", menu="File", highlight=2)
        assert eff.menu == "File"
        assert eff.highlight == 2

    def test_window_animation(self) -> None:
        eff = Effect(type="window_animation", animation="minimize")
        assert eff.animation == "minimize"

    def test_context_menu(self) -> None:
        eff = Effect(
            type="context_menu", items=["Copy", "Paste"], target_x=0.5, target_y=0.3
        )
        assert eff.items == ["Copy", "Paste"]

    def test_spotlight_search(self) -> None:
        eff = Effect(type="spotlight_search", query="hello", typing_speed=0.05)
        assert eff.query == "hello"
        assert eff.typing_speed == 0.05

    def test_control_center(self) -> None:
        eff = Effect(type="control_center", wifi=True, brightness=0.5, volume=0.8)
        assert eff.wifi is True
        assert eff.brightness == 0.5

    def test_notification_center(self) -> None:
        eff = Effect(
            type="notification_center",
            notifications=[{"app": "Messages", "title": "hi", "body": "hello"}],
            show_widgets=True,
        )
        assert eff.show_widgets is True

    def test_mission_control(self) -> None:
        eff = Effect(
            type="mission_control",
            windows=[{"title": "Browser", "color": "#000"}],
            highlight=0,
        )
        assert eff.windows is not None

    def test_launchpad(self) -> None:
        eff = Effect(type="launchpad", highlight=3)
        assert eff.highlight == 3

    def test_system_settings(self) -> None:
        eff = Effect(type="system_settings", category="Wi-Fi")
        assert eff.category == "Wi-Fi"


# ── Cleanup browser effects (non-reload) ─────────────────────────────────────


class TestCleanupBrowserEffects:
    """Test the non-reload DOM cleanup in ScenarioOrchestrator."""

    def test_cleanup_js_removes_demodsl_elements(self) -> None:
        """The cleanup JS should remove __demodsl_ elements and clear intervals."""
        from demodsl.orchestrators.scenario import ScenarioOrchestrator

        orch = ScenarioOrchestrator.__new__(ScenarioOrchestrator)
        orch._has_injected_effects = True
        orch._active_browser_effects = []

        browser = MagicMock()
        orch._cleanup_browser_effects(browser)

        js = browser.evaluate_js.call_args.args[0]
        assert "querySelectorAll('[id^=\"__demodsl_\"]')" in js
        assert "clearInterval" in js
        assert "clearTimeout" in js
