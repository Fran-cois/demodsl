"""Tests for mobile commands and command registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demodsl.commands import (
    AppSwitchCommand,
    BackCommand,
    HomeCommand,
    LongPressCommand,
    MobileClickCommand,
    MobileScrollCommand,
    MobileScreenshotCommand,
    MobileTypeCommand,
    MobileWaitForCommand,
    NotificationCommand,
    PinchCommand,
    RotateDeviceCommand,
    ShakeCommand,
    SwipeCommand,
    TapCommand,
    get_mobile_command,
)
from demodsl.models import Locator, Step
from demodsl.providers.base import MobileProvider


@pytest.fixture()
def mock_mobile() -> MagicMock:
    """Mock MobileProvider."""
    return MagicMock(spec=MobileProvider)


# ── Individual commands ───────────────────────────────────────────────────────


class TestTapCommand:
    def test_tap_with_locator(self, mock_mobile: MagicMock) -> None:
        step = Step(
            action="tap",
            locator=Locator(type="accessibility_id", value="btn"),
        )
        cmd = TapCommand()
        cmd.execute(mock_mobile, step)
        mock_mobile.tap.assert_called_once_with(
            locator=step.locator, x=None, y=None, duration_ms=None
        )

    def test_tap_with_coords(self, mock_mobile: MagicMock) -> None:
        step = Step(action="tap", start_x=100.0, start_y=200.0)
        cmd = TapCommand()
        cmd.execute(mock_mobile, step)
        mock_mobile.tap.assert_called_once_with(
            locator=None, x=100.0, y=200.0, duration_ms=None
        )

    def test_describe_with_locator(self) -> None:
        step = Step(
            action="tap",
            locator=Locator(type="accessibility_id", value="btn"),
        )
        assert "btn" in TapCommand().describe(step)

    def test_describe_with_coords(self) -> None:
        step = Step(action="tap", start_x=50.0, start_y=60.0)
        desc = TapCommand().describe(step)
        assert "50.0" in desc


class TestSwipeCommand:
    def test_swipe(self, mock_mobile: MagicMock) -> None:
        step = Step(
            action="swipe",
            start_x=100.0,
            start_y=200.0,
            end_x=500.0,
            end_y=200.0,
            duration_ms=600,
        )
        SwipeCommand().execute(mock_mobile, step)
        mock_mobile.swipe.assert_called_once_with(
            start_x=100.0, start_y=200.0, end_x=500.0, end_y=200.0, duration_ms=600
        )


class TestPinchCommand:
    def test_pinch(self, mock_mobile: MagicMock) -> None:
        step = Step(
            action="pinch",
            pinch_scale=2.0,
            locator=Locator(type="accessibility_id", value="map"),
        )
        PinchCommand().execute(mock_mobile, step)
        mock_mobile.pinch.assert_called_once_with(
            locator=step.locator, scale=2.0, duration_ms=500
        )


class TestLongPressCommand:
    def test_long_press_locator(self, mock_mobile: MagicMock) -> None:
        step = Step(
            action="long_press",
            locator=Locator(type="id", value="item"),
            duration_ms=1500,
        )
        LongPressCommand().execute(mock_mobile, step)
        mock_mobile.long_press.assert_called_once_with(
            locator=step.locator, x=None, y=None, duration_ms=1500
        )


class TestSimpleCommands:
    def test_back(self, mock_mobile: MagicMock) -> None:
        step = Step(action="back")
        BackCommand().execute(mock_mobile, step)
        mock_mobile.back.assert_called_once()

    def test_home(self, mock_mobile: MagicMock) -> None:
        step = Step(action="home")
        HomeCommand().execute(mock_mobile, step)
        mock_mobile.home.assert_called_once()

    def test_notification(self, mock_mobile: MagicMock) -> None:
        step = Step(action="notification")
        NotificationCommand().execute(mock_mobile, step)
        mock_mobile.open_notifications.assert_called_once()

    def test_app_switch(self, mock_mobile: MagicMock) -> None:
        step = Step(action="app_switch")
        AppSwitchCommand().execute(mock_mobile, step)
        mock_mobile.app_switch.assert_called_once()

    def test_shake(self, mock_mobile: MagicMock) -> None:
        step = Step(action="shake")
        ShakeCommand().execute(mock_mobile, step)
        mock_mobile.shake.assert_called_once()


class TestRotateDeviceCommand:
    def test_rotate(self, mock_mobile: MagicMock) -> None:
        step = Step(action="rotate_device", orientation="landscape")
        RotateDeviceCommand().execute(mock_mobile, step)
        mock_mobile.rotate.assert_called_once_with("landscape")


class TestMobileScrollCommand:
    def test_scroll_down(self, mock_mobile: MagicMock) -> None:
        step = Step(action="scroll", direction="down", pixels=500)
        MobileScrollCommand().execute(mock_mobile, step)
        mock_mobile.scroll.assert_called_once_with("down", 500)


class TestMobileTypeCommand:
    def test_type(self, mock_mobile: MagicMock) -> None:
        step = Step(
            action="type",
            locator=Locator(type="id", value="input"),
            value="hello",
        )
        MobileTypeCommand().execute(mock_mobile, step)
        mock_mobile.type_text.assert_called_once_with(step.locator, "hello")

    def test_type_requires_locator(self, mock_mobile: MagicMock) -> None:
        with pytest.raises(ValueError, match="requires"):
            MobileTypeCommand().execute(
                mock_mobile,
                Step.model_construct(action="type", locator=None, value="x"),
            )


class TestMobileClickCommand:
    def test_click(self, mock_mobile: MagicMock) -> None:
        step = Step(
            action="click",
            locator=Locator(type="accessibility_id", value="btn"),
        )
        MobileClickCommand().execute(mock_mobile, step)
        mock_mobile.click.assert_called_once_with(step.locator)


class TestMobileScreenshotCommand:
    def test_screenshot(self, mock_mobile: MagicMock, tmp_path: Path) -> None:
        step = Step.model_construct(action="screenshot", filename="shot.png")
        cmd = MobileScreenshotCommand(output_dir=tmp_path)
        cmd.execute(mock_mobile, step)
        mock_mobile.screenshot.assert_called_once_with(tmp_path / "shot.png")


# ── Command registry ─────────────────────────────────────────────────────────


class TestGetMobileCommand:
    @pytest.mark.parametrize(
        "action,cls",
        [
            ("tap", TapCommand),
            ("swipe", SwipeCommand),
            ("pinch", PinchCommand),
            ("long_press", LongPressCommand),
            ("back", BackCommand),
            ("home", HomeCommand),
            ("notification", NotificationCommand),
            ("app_switch", AppSwitchCommand),
            ("rotate_device", RotateDeviceCommand),
            ("shake", ShakeCommand),
            ("scroll", MobileScrollCommand),
            ("type", MobileTypeCommand),
            ("click", MobileClickCommand),
            ("wait_for", MobileWaitForCommand),
        ],
    )
    def test_registry_returns_correct_type(self, action: str, cls: type) -> None:
        cmd = get_mobile_command(action)
        assert isinstance(cmd, cls)

    def test_screenshot_command(self) -> None:
        cmd = get_mobile_command("screenshot", output_dir=Path("/tmp"))
        assert isinstance(cmd, MobileScreenshotCommand)

    def test_unknown_action_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown mobile action"):
            get_mobile_command("fly")
