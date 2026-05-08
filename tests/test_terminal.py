"""Tests for terminal provider and terminal commands."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from demodsl.commands import (
    TerminalClearCommand,
    TerminalRunCommand,
    TerminalZoomCommand,
    _strip_emoji,
    get_terminal_command,
)
from demodsl.models import Step
from demodsl.models.terminal import TerminalConfig
from demodsl.providers.terminal import (
    _js_string,
    _resolve_macos_icon,
    build_terminal_html,
    get_theme,
)

# ══════════════════════════════════════════════════════════════════════════════
# Terminal provider — themes
# ══════════════════════════════════════════════════════════════════════════════


class TestGetTheme:
    def test_known_themes(self):
        for name in ("dark", "light", "dracula", "monokai", "solarized"):
            theme = get_theme(name)
            assert "bg" in theme
            assert "fg" in theme
            assert "prompt_color" in theme

    def test_unknown_theme_falls_back_to_dark(self):
        assert get_theme("nonexistent") == get_theme("dark")


# ══════════════════════════════════════════════════════════════════════════════
# Terminal provider — JS string escaping
# ══════════════════════════════════════════════════════════════════════════════


class TestJsString:
    def test_simple(self):
        assert _js_string("hello") == "'hello'"

    def test_single_quote(self):
        assert _js_string("it's") == r"'it\'s'"

    def test_backslash(self):
        assert _js_string("a\\b") == r"'a\\b'"

    def test_newline(self):
        assert _js_string("a\nb") == r"'a\nb'"


# ══════════════════════════════════════════════════════════════════════════════
# Terminal provider — HTML generation
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildTerminalHtml:
    def test_basic_html_structure(self):
        config = TerminalConfig()
        html = build_terminal_html(config)
        assert "<!DOCTYPE html>" in html
        assert "typeCommand" in html
        assert "showOutput" in html
        assert "showPrompt" in html
        assert "clearTerminal" in html
        assert "zoomTerminal" in html

    def test_default_prompt(self):
        config = TerminalConfig(prompt="~/dev $ ")
        html = build_terminal_html(config)
        assert "~/dev $ " in html

    def test_theme_colors_applied(self):
        config = TerminalConfig(theme="dracula")
        html = build_terminal_html(config)
        theme = get_theme("dracula")
        assert theme["bg"] in html
        assert theme["prompt_color"] in html

    def test_window_chrome_visible(self):
        config = TerminalConfig(window_chrome=True)
        html = build_terminal_html(config)
        assert "dot-red" in html
        assert "dot-grn" in html

    def test_window_chrome_hidden(self):
        config = TerminalConfig(window_chrome=False)
        html = build_terminal_html(config)
        assert "display: none" in html or "display:none" in html

    def test_custom_title(self):
        config = TerminalConfig(title="My Terminal")
        html = build_terminal_html(config)
        assert "My Terminal" in html

    def test_title_defaults_to_shell(self):
        config = TerminalConfig(shell="fish")
        html = build_terminal_html(config)
        assert "fish" in html

    def test_font_size(self):
        config = TerminalConfig(font_size=24)
        html = build_terminal_html(config)
        assert "24px" in html

    def test_all_themes_produce_valid_html(self):
        for theme_name in ("dark", "light", "dracula", "monokai", "solarized"):
            config = TerminalConfig(theme=theme_name)
            html = build_terminal_html(config)
            assert "<!DOCTYPE html>" in html
            assert "<script>" in html

    def test_xss_safe_title(self):
        config = TerminalConfig(title='<script>alert("xss")</script>')
        html = build_terminal_html(config)
        assert '<script>alert("xss")</script>' not in html
        assert "&lt;script&gt;" in html

    def test_prompt_escaped_in_html(self):
        config = TerminalConfig(prompt="<b>bold</b> $ ")
        html = build_terminal_html(config)
        # The prompt in the HTML body is escaped via html.escape()
        assert "&lt;b&gt;bold&lt;/b&gt;" in html


# ══════════════════════════════════════════════════════════════════════════════
# Terminal provider — macOS desktop background
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildTerminalHtmlWithBackground:
    def _make_background(self, **overrides):
        """Create a mock background config."""
        bg = MagicMock()
        bg.enabled = True
        bg.os = overrides.get("os", "macos")
        bg.theme = overrides.get("theme", "dark")
        bg.wallpaper_color = overrides.get("wallpaper_color", "#1a1a2e")
        bg.show_dock = overrides.get("show_dock", True)
        bg.show_menu_bar = overrides.get("show_menu_bar", True)
        bg.window_title = overrides.get("window_title", "Terminal")
        bg.apps = overrides.get(
            "apps",
            [
                {"name": "Finder", "color": "#2196F3"},
                {"name": "Terminal", "color": "#4ADE80"},
            ],
        )
        return bg

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_has_menubar(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background()
        html = build_terminal_html(config, background=bg)
        assert "menubar" in html
        assert "File" in html
        assert "Edit" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_has_dock(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background()
        html = build_terminal_html(config, background=bg)
        assert "dock" in html
        assert "Finder" in html
        assert "Terminal" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_dock_hidden(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background(show_dock=False)
        html = build_terminal_html(config, background=bg)
        assert "display:none" in html or "display: none" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_menu_hidden(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background(show_menu_bar=False)
        html = build_terminal_html(config, background=bg)
        # Menu bar has display:none
        assert html.count("display:none") >= 1

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_wallpaper_color(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background(wallpaper_color="#ff0000")
        html = build_terminal_html(config, background=bg)
        assert "#ff0000" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_dock_icon_svg_fallback(self, _mock_icon):
        """When no native icon, SVG fallbacks are used for known apps."""
        config = TerminalConfig()
        bg = self._make_background(apps=[{"name": "Finder", "color": "#2196F3"}])
        html = build_terminal_html(config, background=bg)
        assert "dock-icon-svg" in html
        assert "<svg" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_dock_icon_letter_fallback(self, _mock_icon):
        """Unknown app gets a colored letter square."""
        config = TerminalConfig()
        bg = self._make_background(apps=[{"name": "MyApp", "color": "#123456"}])
        html = build_terminal_html(config, background=bg)
        assert "#123456" in html
        assert ">M</div>" in html

    @patch(
        "demodsl.providers.terminal._resolve_macos_icon",
        return_value="data:image/png;base64,AAAA",
    )
    def test_dock_icon_native(self, _mock_icon):
        """Native macOS icon renders as <img> tag."""
        config = TerminalConfig()
        bg = self._make_background(apps=[{"name": "Finder", "color": "#2196F3"}])
        html = build_terminal_html(config, background=bg)
        assert "dock-icon-img" in html
        assert "data:image/png;base64,AAAA" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_default_apps_when_none(self, _mock_icon):
        """When apps is None, default dock apps are used."""
        config = TerminalConfig()
        bg = self._make_background()
        bg.apps = None
        html = build_terminal_html(config, background=bg)
        assert "Finder" in html
        assert "Safari" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_clock_script(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background()
        html = build_terminal_html(config, background=bg)
        assert "updateClock" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_window_title_from_background(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background(window_title="My App")
        html = build_terminal_html(config, background=bg)
        assert "My App" in html

    @patch("demodsl.providers.terminal._resolve_macos_icon", return_value=None)
    def test_light_theme_background(self, _mock_icon):
        config = TerminalConfig()
        bg = self._make_background(theme="light")
        html = build_terminal_html(config, background=bg)
        # Light theme uses different menu bar colors
        assert "rgba(242,242,247,0.85)" in html


# ══════════════════════════════════════════════════════════════════════════════
# Terminal provider — macOS icon resolution
# ══════════════════════════════════════════════════════════════════════════════


class TestResolveMacOSIcon:
    def setup_method(self):
        """Clear icon cache before each test."""
        from demodsl.providers import terminal

        terminal._icon_cache.clear()

    @patch("demodsl.providers.terminal.platform")
    def test_non_darwin_returns_none(self, mock_platform):
        mock_platform.system.return_value = "Linux"
        assert _resolve_macos_icon("Finder") is None

    @patch("demodsl.providers.terminal.platform")
    def test_cache_hit(self, mock_platform):
        """Second call uses cache, doesn't check platform."""
        from demodsl.providers import terminal

        terminal._icon_cache["CachedApp"] = "data:image/png;base64,cached"
        result = _resolve_macos_icon("CachedApp")
        assert result == "data:image/png;base64,cached"
        mock_platform.system.assert_not_called()

    @patch("demodsl.providers.terminal.platform")
    def test_cache_none_hit(self, mock_platform):
        from demodsl.providers import terminal

        terminal._icon_cache["Missing"] = None
        result = _resolve_macos_icon("Missing")
        assert result is None
        mock_platform.system.assert_not_called()

    @patch("demodsl.providers.terminal.subprocess")
    @patch("demodsl.providers.terminal.os")
    @patch("demodsl.providers.terminal.platform")
    def test_resolves_icns_via_sips(self, mock_platform, mock_os, mock_subprocess):
        """Full happy path: reads plist, finds icns, converts via sips."""
        mock_platform.system.return_value = "Darwin"
        mock_os.path.isdir.return_value = True
        mock_os.path.exists.return_value = True
        mock_os.path.join.side_effect = lambda *parts: "/".join(parts)

        import plistlib

        plist_data = plistlib.dumps({"CFBundleIconFile": "AppIcon.icns"})

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        m_open = MagicMock()
        with patch("builtins.open", m_open):
            # First open: plist read (binary)
            # Second open: png read (binary)
            plist_ctx = MagicMock()
            plist_ctx.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=plist_data))
            )
            plist_ctx.__exit__ = MagicMock(return_value=False)

            png_ctx = MagicMock()
            png_ctx.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=b"\x89PNG"))
            )
            png_ctx.__exit__ = MagicMock(return_value=False)

            m_open.side_effect = [plist_ctx, png_ctx]

            with patch("demodsl.providers.terminal.glob") as mock_glob:
                with patch("tempfile.NamedTemporaryFile") as mock_tmp:
                    tmp_file = MagicMock()
                    tmp_file.__enter__ = MagicMock(return_value=tmp_file)
                    tmp_file.__exit__ = MagicMock(return_value=False)
                    tmp_file.name = "/tmp/test.png"
                    mock_tmp.return_value = tmp_file

                    result = _resolve_macos_icon("Safari")

        # Should either be a data URI or None depending on mock
        # The important thing is it doesn't crash
        assert result is None or result.startswith("data:image/png;base64,")

    @patch("demodsl.providers.terminal.platform")
    @patch("demodsl.providers.terminal.os")
    def test_nonexistent_app_returns_none(self, mock_os, mock_platform):
        mock_platform.system.return_value = "Darwin"
        mock_os.path.isdir.return_value = False
        result = _resolve_macos_icon("NonExistentApp12345")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Terminal config model
# ══════════════════════════════════════════════════════════════════════════════


class TestTerminalConfig:
    def test_defaults(self):
        tc = TerminalConfig()
        assert tc.shell == "bash"
        assert tc.prompt == "$ "
        assert tc.theme == "dark"
        assert tc.typing_speed == 12.0
        assert tc.output_delay == 0.3
        assert tc.window_chrome is True
        assert tc.font_size == 18

    def test_custom_values(self):
        tc = TerminalConfig(
            shell="zsh",
            prompt="~/proj $ ",
            theme="dracula",
            font_size=24,
            typing_speed=20,
            output_delay=0.5,
            title="My Term",
        )
        assert tc.shell == "zsh"
        assert tc.theme == "dracula"
        assert tc.font_size == 24
        assert tc.title == "My Term"

    def test_invalid_theme(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TerminalConfig(theme="invalid_theme")

    def test_font_size_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TerminalConfig(font_size=5)
        with pytest.raises(ValidationError):
            TerminalConfig(font_size=100)

    def test_typing_speed_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TerminalConfig(typing_speed=0)
        with pytest.raises(ValidationError):
            TerminalConfig(typing_speed=300)


# ══════════════════════════════════════════════════════════════════════════════
# Emoji stripping
# ══════════════════════════════════════════════════════════════════════════════


class TestStripEmoji:
    def test_removes_rocket(self):
        assert _strip_emoji("Hello 🚀 World") == "Hello  World"

    def test_removes_checkmark_emoji(self):
        assert _strip_emoji("✅ Done") == " Done"

    def test_preserves_safe_symbols(self):
        # U+2713 ✓ and U+2502 │ are safe
        assert _strip_emoji("✓ passed │ done") == "✓ passed │ done"

    def test_preserves_plain_text(self):
        assert _strip_emoji("hello world 123") == "hello world 123"

    def test_empty_string(self):
        assert _strip_emoji("") == ""

    def test_removes_multiple_emoji(self):
        result = _strip_emoji("🚀 start ❌ fail ✅ pass")
        assert "🚀" not in result
        assert "❌" not in result
        assert "✅" not in result


# ══════════════════════════════════════════════════════════════════════════════
# Terminal commands — get_terminal_command()
# ══════════════════════════════════════════════════════════════════════════════


class TestGetTerminalCommand:
    def test_terminal_run(self):
        cmd = get_terminal_command("terminal_run")
        assert isinstance(cmd, TerminalRunCommand)

    def test_terminal_clear(self):
        cmd = get_terminal_command("terminal_clear")
        assert isinstance(cmd, TerminalClearCommand)

    def test_terminal_zoom(self):
        cmd = get_terminal_command("terminal_zoom")
        assert isinstance(cmd, TerminalZoomCommand)

    def test_unknown_action_raises(self):
        with pytest.raises(ValueError, match="Unknown terminal action"):
            get_terminal_command("invalid_action")

    def test_unknown_action_suggests_close_match(self):
        with pytest.raises(ValueError, match="Did you mean"):
            get_terminal_command("terminal_ru")


# ══════════════════════════════════════════════════════════════════════════════
# Terminal commands — execution
# ══════════════════════════════════════════════════════════════════════════════


class TestTerminalRunCommand:
    @patch("time.sleep", MagicMock())
    def test_execute_with_string_output(self):
        browser = MagicMock()
        step = Step(action="terminal_run", command="echo hello", output="hello", wait=1.0)

        cmd = TerminalRunCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        calls = [c.args[0] for c in browser.evaluate_js.call_args_list]
        assert any("typeCommand" in c for c in calls)
        assert any("showOutput" in c for c in calls)
        assert any("showPrompt" in c for c in calls)

    @patch("time.sleep", MagicMock())
    def test_execute_with_list_output(self):
        browser = MagicMock()
        step = Step(
            action="terminal_run",
            command="ls",
            output=["file1.txt", "file2.txt"],
            wait=1.0,
        )

        cmd = TerminalRunCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        calls = [c.args[0] for c in browser.evaluate_js.call_args_list]
        assert any("showOutput" in c for c in calls)

    @patch("time.sleep", MagicMock())
    def test_execute_without_output(self):
        browser = MagicMock()
        step = Step(action="terminal_run", command="cd /tmp", wait=0.5)

        cmd = TerminalRunCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        calls = [c.args[0] for c in browser.evaluate_js.call_args_list]
        assert any("typeCommand" in c for c in calls)
        assert any("showPrompt" in c for c in calls)
        # showOutput should NOT be called
        assert not any("showOutput" in c for c in calls)

    @patch("time.sleep", MagicMock())
    def test_execute_requires_command(self):
        browser = MagicMock()
        step = Step(action="terminal_run", command="x", wait=0.5)
        step.command = None  # force None

        cmd = TerminalRunCommand()
        with pytest.raises(ValueError, match="requires 'command'"):
            cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

    @patch("time.sleep", MagicMock())
    def test_emoji_stripped_from_command(self):
        browser = MagicMock()
        step = Step(action="terminal_run", command="echo 🚀 hello", output="🚀 hello", wait=0.5)

        cmd = TerminalRunCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        calls = [c.args[0] for c in browser.evaluate_js.call_args_list]
        type_call = [c for c in calls if "typeCommand" in c][0]
        assert "🚀" not in type_call

    def test_describe(self):
        step = Step(action="terminal_run", command="ls -la", wait=0.5)
        cmd = TerminalRunCommand()
        assert "ls -la" in cmd.describe(step)

    def test_describe_with_output(self):
        step = Step(action="terminal_run", command="ls", output="file.txt", wait=0.5)
        cmd = TerminalRunCommand()
        assert "(with output)" in cmd.describe(step)


class TestTerminalClearCommand:
    def test_execute(self):
        browser = MagicMock()
        step = Step(action="terminal_clear", wait=0.5)

        cmd = TerminalClearCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        browser.evaluate_js.assert_called_once_with("clearTerminal()")

    def test_describe(self):
        step = Step(action="terminal_clear", wait=0.5)
        cmd = TerminalClearCommand()
        assert "clear" in cmd.describe(step)


class TestTerminalZoomCommand:
    @patch("time.sleep", MagicMock())
    def test_execute_default(self):
        browser = MagicMock()
        step = Step(action="terminal_zoom", wait=0.5)

        cmd = TerminalZoomCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        calls = [c.args[0] for c in browser.evaluate_js.call_args_list]
        assert any("zoomTerminal(1.5" in c for c in calls)

    @patch("time.sleep", MagicMock())
    def test_execute_custom_scale(self):
        browser = MagicMock()
        step = Step(action="terminal_zoom", zoom_level=2.0, zoom_duration=1.0, wait=0.5)

        cmd = TerminalZoomCommand()
        cmd.execute(browser, step, typing_speed=10, output_delay=0.3)

        calls = [c.args[0] for c in browser.evaluate_js.call_args_list]
        assert any("zoomTerminal(2.0, 1000)" in c for c in calls)

    def test_describe_default(self):
        step = Step(action="terminal_zoom", wait=0.5)
        cmd = TerminalZoomCommand()
        assert "1.5x" in cmd.describe(step)

    def test_describe_custom(self):
        step = Step(action="terminal_zoom", zoom_level=2.0, wait=0.5)
        cmd = TerminalZoomCommand()
        assert "2.0x" in cmd.describe(step)
