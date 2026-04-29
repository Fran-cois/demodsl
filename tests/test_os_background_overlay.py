"""Tests for demodsl.effects.os_background — OsBackgroundOverlay."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from demodsl.effects.os_background import OsBackgroundOverlay
from demodsl.models.overlays import BackgroundConfig

# ── BackgroundConfig model tests ──────────────────────────────────────────────


class TestBackgroundConfigModel:
    def test_defaults(self) -> None:
        cfg = BackgroundConfig()
        assert cfg.enabled is True
        assert cfg.os == "macos"
        assert cfg.theme == "dark"
        assert cfg.wallpaper_color == "#1a1a2e"
        assert cfg.window_title == "Demo App"
        assert cfg.show_dock is True
        assert cfg.show_menu_bar is True

    def test_custom_values(self) -> None:
        cfg = BackgroundConfig(
            enabled=False,
            os="windows",
            theme="light",
            wallpaper_color="#ff0000",
            window_title="My App",
            show_dock=False,
            show_menu_bar=False,
        )
        assert cfg.enabled is False
        assert cfg.os == "windows"
        assert cfg.theme == "light"
        assert cfg.wallpaper_color == "#ff0000"
        assert cfg.window_title == "My App"
        assert cfg.show_dock is False
        assert cfg.show_menu_bar is False

    def test_invalid_os(self) -> None:
        with pytest.raises(ValidationError):
            BackgroundConfig(os="linux")

    def test_invalid_theme(self) -> None:
        with pytest.raises(ValidationError):
            BackgroundConfig(theme="neon")

    def test_invalid_wallpaper_color(self) -> None:
        with pytest.raises(ValidationError):
            BackgroundConfig(wallpaper_color="not-a-color")

    def test_valid_hex_colors(self) -> None:
        for color in ("#000", "#fff", "#1a1a2e", "#AABBCC"):
            cfg = BackgroundConfig(wallpaper_color=color)
            assert cfg.wallpaper_color == color

    def test_model_dump(self) -> None:
        cfg = BackgroundConfig(os="windows", theme="light")
        d = cfg.model_dump()
        assert d["os"] == "windows"
        assert d["theme"] == "light"
        assert isinstance(d, dict)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BackgroundConfig(os="macos", unknown_field="bad")


# ── Scenario model integration ────────────────────────────────────────────────


class TestScenarioBackgroundField:
    def test_scenario_accepts_background(self) -> None:
        from demodsl.models import Scenario

        s = Scenario(
            name="test",
            url="https://example.com",
            steps=[{"action": "navigate", "url": "https://example.com"}],
            background={"os": "macos", "theme": "dark"},
        )
        assert s.background is not None
        assert s.background.os == "macos"

    def test_scenario_background_none_by_default(self) -> None:
        from demodsl.models import Scenario

        s = Scenario(
            name="test",
            url="https://example.com",
            steps=[{"action": "navigate", "url": "https://example.com"}],
        )
        assert s.background is None

    def test_scenario_background_windows(self) -> None:
        from demodsl.models import Scenario

        s = Scenario(
            name="test",
            url="https://example.com",
            steps=[{"action": "navigate", "url": "https://example.com"}],
            background={"os": "windows", "theme": "light", "window_title": "Edge"},
        )
        assert s.background.os == "windows"
        assert s.background.window_title == "Edge"


# ── OsBackgroundOverlay init ─────────────────────────────────────────────────


class TestOsBackgroundOverlayInit:
    def test_defaults(self) -> None:
        overlay = OsBackgroundOverlay({})
        assert overlay.enabled is True
        assert overlay.os == "macos"
        assert overlay.theme == "dark"
        assert overlay.wallpaper_color == "#1a1a2e"
        assert overlay.window_title == "Demo App"
        assert overlay.show_dock is True
        assert overlay.show_menu_bar is True

    def test_custom_config(self) -> None:
        overlay = OsBackgroundOverlay(
            {
                "enabled": False,
                "os": "windows",
                "theme": "light",
                "wallpaper_color": "#0c1445",
                "window_title": "VS Code",
                "show_dock": False,
                "show_menu_bar": False,
            }
        )
        assert overlay.enabled is False
        assert overlay.os == "windows"
        assert overlay.theme == "light"
        assert overlay.wallpaper_color == "#0c1445"
        assert overlay.window_title == "VS Code"
        assert overlay.show_dock is False
        assert overlay.show_menu_bar is False


# ── OsBackgroundOverlay inject — macOS ────────────────────────────────────────


class TestOsBackgroundOverlayMacOS:
    def test_inject_calls_evaluate_js(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert isinstance(js, str)
        assert len(js) > 100

    def test_inject_contains_guard(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "__demodsl_os_bg" in js

    def test_inject_contains_menu_bar(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_menu_bar": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "menuBar" in js
        assert "File" in js
        assert "Edit" in js
        assert "Window" in js

    def test_inject_no_menu_bar(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_menu_bar": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "menuBar" not in js

    def test_inject_contains_traffic_lights(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "#ff5f57" in js  # red
        assert "#febc2e" in js  # yellow
        assert "#28c840" in js  # green

    def test_inject_contains_dock(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_dock": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "dock" in js
        assert "Finder" in js

    def test_inject_no_dock(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_dock": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "dock" not in js.lower() or "show_dock" in js.lower()

    def test_inject_contains_title(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "window_title": "Test App"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "Test App" in js

    def test_inject_dark_theme(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "theme": "dark"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "rgba(30,30,30,0.85)" in js

    def test_inject_light_theme(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "theme": "light"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "rgba(240,240,240,0.85)" in js

    def test_inject_wallpaper_color(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "wallpaper_color": "#ff00ff"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "#ff00ff" in js

    def test_inject_sets_body_padding(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "padding-top" in js
        assert "padding-bottom" in js

    def test_inject_title_xss_escaped(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "window_title": "<script>alert(1)</script>"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "<script>" not in js
        assert "&lt;" in js


# ── OsBackgroundOverlay inject — Windows ──────────────────────────────────────


class TestOsBackgroundOverlayWindows:
    def test_inject_calls_evaluate_js(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_called_once()
        js = mock_eval.call_args.args[0]
        assert isinstance(js, str)
        assert len(js) > 100

    def test_inject_contains_title_bar(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "titleBar" in js

    def test_inject_contains_window_controls(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        # Minimize (horizontal line), Maximize (rect), Close (X paths)
        assert "M0 0l10 10" in js  # close button X

    def test_inject_contains_taskbar(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "show_dock": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "taskbar" in js
        assert "Start" in js

    def test_inject_no_taskbar(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "show_dock": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "taskbar" not in js

    def test_inject_dark_theme(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "theme": "dark"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "rgba(32,32,32,0.92)" in js

    def test_inject_light_theme(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "theme": "light"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "rgba(243,243,243,0.92)" in js

    def test_inject_segoe_ui_font(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "Segoe UI" in js

    def test_inject_contains_clock(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "show_dock": True})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "14:32" in js

    def test_inject_title_xss_escaped(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "window_title": "<img onerror=alert(1)>"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "<img" not in js
        assert "&lt;" in js


# ── OsBackgroundOverlay disabled ──────────────────────────────────────────────


class TestOsBackgroundOverlayDisabled:
    def test_inject_noop_when_disabled(self) -> None:
        overlay = OsBackgroundOverlay({"enabled": False})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        mock_eval.assert_not_called()


# ── Guard clause (idempotency) ────────────────────────────────────────────────


class TestOsBackgroundOverlayIdempotency:
    def test_guard_clause_present_macos(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "if(document.getElementById('__demodsl_os_bg')) return" in js

    def test_guard_clause_present_windows(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows"})
        mock_eval = MagicMock()
        overlay.inject(mock_eval)
        js = mock_eval.call_args.args[0]
        assert "if(document.getElementById('__demodsl_os_bg')) return" in js
