"""Tests for demodsl.commands — Command pattern dispatch and validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from demodsl.commands import (
    ClickCommand,
    NavigateCommand,
    ScreenshotCommand,
    ScrollCommand,
    ShortcutCommand,
    TypeCommand,
    WaitForCommand,
    get_command,
)
from demodsl.models import Locator, Step

# ── get_command() ─────────────────────────────────────────────────────────────


class TestGetCommand:
    @pytest.mark.parametrize(
        "action, expected_cls",
        [
            ("navigate", NavigateCommand),
            ("click", ClickCommand),
            ("type", TypeCommand),
            ("scroll", ScrollCommand),
            ("wait_for", WaitForCommand),
        ],
    )
    def test_returns_correct_class(self, action: str, expected_cls: type) -> None:
        cmd = get_command(action)
        assert isinstance(cmd, expected_cls)

    def test_screenshot_returns_screenshot_command(self) -> None:
        cmd = get_command("screenshot", output_dir=Path("/tmp"))
        assert isinstance(cmd, ScreenshotCommand)

    def test_screenshot_default_output_dir(self) -> None:
        cmd = get_command("screenshot")
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd._output_dir == Path(".")

    def test_unknown_action_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown browser action 'does_not_exist'"):
            get_command("does_not_exist")


# ── NavigateCommand ───────────────────────────────────────────────────────────


class TestNavigateCommand:
    def test_execute_calls_navigate(self, mock_browser: MagicMock) -> None:
        step = Step(action="navigate", url="https://example.com")
        NavigateCommand().execute(mock_browser, step)
        mock_browser.navigate.assert_called_once_with("https://example.com")

    def test_model_rejects_navigate_without_url(self, mock_browser: MagicMock) -> None:
        with pytest.raises(ValidationError, match="navigate.*requires.*url"):
            Step(action="navigate")

    def test_describe(self) -> None:
        step = Step(action="navigate", url="https://test.com")
        assert NavigateCommand().describe(step) == "Navigate to https://test.com"

    def test_http_url_allowed(self, mock_browser: MagicMock) -> None:
        step = Step(action="navigate", url="http://example.com")
        NavigateCommand().execute(mock_browser, step)
        mock_browser.navigate.assert_called_once()

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "file:///etc/passwd",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:MsgBox",
        ],
    )
    def test_rejects_dangerous_schemes(self, mock_browser: MagicMock, url: str) -> None:
        # URL scheme validation now happens at model parse time (field_validator)
        with pytest.raises(ValidationError, match="not allowed"):
            Step(action="navigate", url=url)

    def test_allows_schemeless_url(self, mock_browser: MagicMock) -> None:
        step = Step(action="navigate", url="/page")
        NavigateCommand().execute(mock_browser, step)
        mock_browser.navigate.assert_called_once_with("/page")


# ── ClickCommand ──────────────────────────────────────────────────────────────


class TestClickCommand:
    def test_execute_calls_click(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#btn")
        step = Step(action="click", locator=loc)
        ClickCommand().execute(mock_browser, step)
        mock_browser.click.assert_called_once_with(loc)

    def test_model_rejects_click_without_locator(self, mock_browser: MagicMock) -> None:
        with pytest.raises(ValidationError, match="click.*requires.*locator"):
            Step(action="click")

    def test_describe_with_locator(self) -> None:
        step = Step(action="click", locator={"type": "id", "value": "submit"})
        assert "Click on [id] submit" == ClickCommand().describe(step)


# ── TypeCommand ───────────────────────────────────────────────────────────────


class TestTypeCommand:
    def test_execute_calls_type_text(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#input")
        step = Step(action="type", locator=loc, value="hello")
        TypeCommand().execute(mock_browser, step)
        mock_browser.type_text.assert_called_once_with(loc, "hello")

    def test_model_rejects_type_without_locator(self, mock_browser: MagicMock) -> None:
        with pytest.raises(ValidationError, match="type.*requires"):
            Step(action="type", value="hello")

    def test_model_rejects_type_without_value(self, mock_browser: MagicMock) -> None:
        with pytest.raises(ValidationError, match="type.*requires"):
            Step(action="type", locator={"type": "css", "value": "#x"})

    def test_describe(self) -> None:
        step = Step(action="type", locator={"type": "css", "value": "#x"}, value="abc")
        desc = TypeCommand().describe(step)
        assert "Type 'abc'" in desc
        assert "[css] #x" in desc

    def test_organic_typing_dispatches_to_type_text_organic(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#input")
        step = Step(action="type", locator=loc, value="hello", char_rate=10)
        TypeCommand().execute(mock_browser, step)
        mock_browser.type_text_organic.assert_called_once_with(loc, "hello", 10, variance=0.0)
        mock_browser.type_text.assert_not_called()

    def test_organic_typing_with_variance(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#input")
        step = Step(action="type", locator=loc, value="hello", char_rate=10, typing_variance=0.5)
        TypeCommand().execute(mock_browser, step)
        mock_browser.type_text_organic.assert_called_once_with(loc, "hello", 10, variance=0.5)

    def test_no_char_rate_uses_fill(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#input")
        step = Step(action="type", locator=loc, value="hello")
        TypeCommand().execute(mock_browser, step)
        mock_browser.type_text.assert_called_once_with(loc, "hello")
        mock_browser.type_text_organic.assert_not_called()

    def test_describe_with_char_rate(self) -> None:
        step = Step(
            action="type",
            locator={"type": "css", "value": "#x"},
            value="abc",
            char_rate=8,
        )
        desc = TypeCommand().describe(step)
        assert "@8" in desc and "ch/s" in desc


# ── ScrollCommand ─────────────────────────────────────────────────────────────


class TestScrollCommand:
    def test_execute_defaults(self, mock_browser: MagicMock) -> None:
        step = Step(action="scroll")
        ScrollCommand().execute(mock_browser, step)
        mock_browser.scroll.assert_called_once_with("down", 300, smooth=False)

    def test_execute_custom(self, mock_browser: MagicMock) -> None:
        step = Step(action="scroll", direction="up", pixels=500)
        ScrollCommand().execute(mock_browser, step)
        mock_browser.scroll.assert_called_once_with("up", 500, smooth=False)

    def test_execute_smooth(self, mock_browser: MagicMock) -> None:
        step = Step(action="scroll", smooth_scroll=True)
        ScrollCommand().execute(mock_browser, step)
        mock_browser.scroll.assert_called_once_with("down", 300, smooth=True)

    def test_describe_defaults(self) -> None:
        step = Step(action="scroll")
        assert ScrollCommand().describe(step) == "Scroll down 300px"

    def test_describe_custom(self) -> None:
        step = Step(action="scroll", direction="left", pixels=100)
        assert ScrollCommand().describe(step) == "Scroll left 100px"

    def test_describe_smooth(self) -> None:
        step = Step(action="scroll", smooth_scroll=True)
        assert ScrollCommand().describe(step) == "Scroll down 300px (smooth)"


# ── WaitForCommand ────────────────────────────────────────────────────────────


class TestWaitForCommand:
    def test_execute_calls_wait_for(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="text", value="Submit")
        step = Step(action="wait_for", locator=loc, timeout=10.0)
        WaitForCommand().execute(mock_browser, step)
        mock_browser.wait_for.assert_called_once_with(loc, 10.0)

    def test_execute_default_timeout(self, mock_browser: MagicMock) -> None:
        loc = Locator(value="x")
        step = Step(action="wait_for", locator=loc)
        WaitForCommand().execute(mock_browser, step)
        mock_browser.wait_for.assert_called_once_with(loc, 5.0)

    def test_model_rejects_wait_for_without_locator(self, mock_browser: MagicMock) -> None:
        with pytest.raises(ValidationError, match="wait_for.*requires.*locator"):
            Step(action="wait_for")

    def test_describe(self) -> None:
        step = Step(action="wait_for", locator={"type": "xpath", "value": "//div"})
        desc = WaitForCommand().describe(step)
        assert "[xpath] //div" in desc
        assert "timeout=5.0s" in desc


# ── ScreenshotCommand ─────────────────────────────────────────────────────────


class TestScreenshotCommand:
    def test_execute_default_filename(self, mock_browser: MagicMock) -> None:
        cmd = ScreenshotCommand(output_dir=Path("/out"))
        step = Step(action="screenshot")
        cmd.execute(mock_browser, step)
        mock_browser.screenshot.assert_called_once_with(Path("/out/screenshot.png"))

    def test_execute_custom_filename(self, mock_browser: MagicMock) -> None:
        cmd = ScreenshotCommand(output_dir=Path("/out"))
        step = Step(action="screenshot", filename="final.png")
        cmd.execute(mock_browser, step)
        mock_browser.screenshot.assert_called_once_with(Path("/out/final.png"))

    def test_describe_default(self) -> None:
        step = Step(action="screenshot")
        assert ScreenshotCommand(Path(".")).describe(step) == "Screenshot → screenshot.png"

    def test_describe_custom(self) -> None:
        step = Step(action="screenshot", filename="page.png")
        assert ScreenshotCommand(Path(".")).describe(step) == "Screenshot → page.png"


# ── ShortcutCommand ──────────────────────────────────────────────────────────


class TestShortcutCommand:
    def test_get_command_returns_shortcut(self) -> None:
        cmd = get_command("shortcut")
        assert isinstance(cmd, ShortcutCommand)

    def test_format_label_meta_f(self) -> None:
        assert ShortcutCommand._format_label("Meta+f") == "⌘ F"

    def test_format_label_ctrl_shift_p(self) -> None:
        assert ShortcutCommand._format_label("Control+Shift+p") == "Ctrl ⇧ P"

    def test_format_label_single_key(self) -> None:
        assert ShortcutCommand._format_label("Escape") == "Esc"

    def test_format_label_alt_enter(self) -> None:
        assert ShortcutCommand._format_label("Alt+Enter") == "⌥ ↵"

    def test_execute_calls_press_keys(self) -> None:
        browser = MagicMock()
        step = Step(action="shortcut", keys="Meta+f")
        ShortcutCommand().execute(browser, step)

        browser.evaluate_js.assert_called_once()
        browser.press_keys.assert_called_once_with("Meta+f")

    def test_execute_requires_keys(self) -> None:
        browser = MagicMock()
        # Step validation prevents keys=None for shortcut action,
        # but test the command guard directly
        step = MagicMock()
        step.keys = None
        with pytest.raises(ValueError, match="requires 'keys'"):
            ShortcutCommand().execute(browser, step)

    def test_overlay_js_contains_label(self) -> None:
        js = ShortcutCommand._overlay_js("⌘ F", 1.5)
        assert "⌘ F" in js
        assert "__demodsl_shortcut" in js
        assert "1500" in js  # duration: 1.5s = 1500ms

    def test_describe(self) -> None:
        step = Step(action="shortcut", keys="Control+c")
        assert ShortcutCommand().describe(step) == "Shortcut Control+c"


class TestStepShortcutValidation:
    def test_shortcut_requires_keys(self) -> None:
        with pytest.raises(ValidationError):
            Step(action="shortcut")

    def test_shortcut_with_keys_valid(self) -> None:
        step = Step(action="shortcut", keys="Meta+f")
        assert step.keys == "Meta+f"
        assert step.action == "shortcut"

    def test_shortcut_warns_on_irrelevant_fields(self) -> None:
        with pytest.warns(UserWarning, match="not relevant"):
            Step(action="shortcut", keys="Meta+f", url="https://example.com")
