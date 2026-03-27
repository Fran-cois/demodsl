"""Tests for demodsl.commands — Command pattern dispatch and validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demodsl.commands import (
    BrowserCommand,
    ClickCommand,
    NavigateCommand,
    ScreenshotCommand,
    ScrollCommand,
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
        with pytest.raises(ValueError, match="Unknown browser action 'hover'"):
            get_command("hover")


# ── NavigateCommand ───────────────────────────────────────────────────────────


class TestNavigateCommand:
    def test_execute_calls_navigate(self, mock_browser: MagicMock) -> None:
        step = Step(action="navigate", url="https://example.com")
        NavigateCommand().execute(mock_browser, step)
        mock_browser.navigate.assert_called_once_with("https://example.com")

    def test_execute_raises_without_url(self, mock_browser: MagicMock) -> None:
        step = Step(action="navigate")
        with pytest.raises(ValueError, match="requires 'url'"):
            NavigateCommand().execute(mock_browser, step)

    def test_describe(self) -> None:
        step = Step(action="navigate", url="https://test.com")
        assert NavigateCommand().describe(step) == "Navigate to https://test.com"


# ── ClickCommand ──────────────────────────────────────────────────────────────


class TestClickCommand:
    def test_execute_calls_click(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#btn")
        step = Step(action="click", locator=loc)
        ClickCommand().execute(mock_browser, step)
        mock_browser.click.assert_called_once_with(loc)

    def test_execute_raises_without_locator(self, mock_browser: MagicMock) -> None:
        step = Step(action="click")
        with pytest.raises(ValueError, match="requires 'locator'"):
            ClickCommand().execute(mock_browser, step)

    def test_describe_with_locator(self) -> None:
        step = Step(action="click", locator={"type": "id", "value": "submit"})
        assert "Click on [id] submit" == ClickCommand().describe(step)

    def test_describe_without_locator(self) -> None:
        step = Step(action="click")
        assert "Click (no locator)" == ClickCommand().describe(step)


# ── TypeCommand ───────────────────────────────────────────────────────────────


class TestTypeCommand:
    def test_execute_calls_type_text(self, mock_browser: MagicMock) -> None:
        loc = Locator(type="css", value="#input")
        step = Step(action="type", locator=loc, value="hello")
        TypeCommand().execute(mock_browser, step)
        mock_browser.type_text.assert_called_once_with(loc, "hello")

    def test_execute_raises_without_locator(self, mock_browser: MagicMock) -> None:
        step = Step(action="type", value="hello")
        with pytest.raises(ValueError, match="requires 'locator' and 'value'"):
            TypeCommand().execute(mock_browser, step)

    def test_execute_raises_without_value(self, mock_browser: MagicMock) -> None:
        step = Step(action="type", locator={"type": "css", "value": "#x"})
        with pytest.raises(ValueError, match="requires 'locator' and 'value'"):
            TypeCommand().execute(mock_browser, step)

    def test_describe(self) -> None:
        step = Step(action="type", locator={"type": "css", "value": "#x"}, value="abc")
        desc = TypeCommand().describe(step)
        assert "Type 'abc'" in desc
        assert "[css] #x" in desc


# ── ScrollCommand ─────────────────────────────────────────────────────────────


class TestScrollCommand:
    def test_execute_defaults(self, mock_browser: MagicMock) -> None:
        step = Step(action="scroll")
        ScrollCommand().execute(mock_browser, step)
        mock_browser.scroll.assert_called_once_with("down", 300)

    def test_execute_custom(self, mock_browser: MagicMock) -> None:
        step = Step(action="scroll", direction="up", pixels=500)
        ScrollCommand().execute(mock_browser, step)
        mock_browser.scroll.assert_called_once_with("up", 500)

    def test_describe_defaults(self) -> None:
        step = Step(action="scroll")
        assert ScrollCommand().describe(step) == "Scroll down 300px"

    def test_describe_custom(self) -> None:
        step = Step(action="scroll", direction="left", pixels=100)
        assert ScrollCommand().describe(step) == "Scroll left 100px"


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

    def test_execute_raises_without_locator(self, mock_browser: MagicMock) -> None:
        step = Step(action="wait_for")
        with pytest.raises(ValueError, match="requires 'locator'"):
            WaitForCommand().execute(mock_browser, step)

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
