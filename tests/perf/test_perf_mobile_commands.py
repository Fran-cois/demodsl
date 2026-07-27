"""Performance tests for mobile command actions."""

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
    MobileScreenshotCommand,
    MobileScrollCommand,
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

ITERATIONS = 500


def _mock_mobile() -> MagicMock:
    mobile = MagicMock(spec=MobileProvider)
    mobile.tap = MagicMock()
    mobile.swipe = MagicMock()
    mobile.pinch = MagicMock()
    mobile.long_press = MagicMock()
    mobile.back = MagicMock()
    mobile.home = MagicMock()
    mobile.open_notifications = MagicMock()
    mobile.app_switch = MagicMock()
    mobile.rotate = MagicMock()
    mobile.shake = MagicMock()
    mobile.scroll = MagicMock()
    mobile.type_text = MagicMock()
    mobile.click = MagicMock()
    mobile.wait_for = MagicMock()
    mobile.screenshot = MagicMock(return_value=Path("mobile_screenshot.png"))
    return mobile


@pytest.mark.perf
class TestTapPerf:
    def test_tap_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_tap", ITERATIONS)
        cmd = TapCommand()
        step = Step(action="tap", locator=Locator(type="accessibility_id", value="btn"))
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_tap_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_tap_describe", ITERATIONS)
        cmd = TapCommand()
        step = Step(action="tap", locator=Locator(type="accessibility_id", value="btn"))
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestSwipePerf:
    def test_swipe_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_swipe", ITERATIONS)
        cmd = SwipeCommand()
        step = Step(action="swipe", start_x=100, start_y=600, end_x=100, end_y=200)
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_swipe_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_swipe_describe", ITERATIONS)
        cmd = SwipeCommand()
        step = Step(action="swipe", start_x=100, start_y=600, end_x=100, end_y=200)
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestPinchPerf:
    def test_pinch_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_pinch", ITERATIONS)
        cmd = PinchCommand()
        step = Step(action="pinch", pinch_scale=0.5)
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_pinch_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_pinch_describe", ITERATIONS)
        cmd = PinchCommand()
        step = Step(action="pinch", pinch_scale=0.5)
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestLongPressPerf:
    def test_long_press_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_long_press", ITERATIONS)
        cmd = LongPressCommand()
        step = Step(action="long_press", locator=Locator(type="accessibility_id", value="cell"))
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_long_press_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_long_press_describe", ITERATIONS)
        cmd = LongPressCommand()
        step = Step(action="long_press", locator=Locator(type="accessibility_id", value="cell"))
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestHardwareButtonPerf:
    """Benchmark the parameterless hardware-button commands."""

    @pytest.mark.parametrize(
        ("cmd", "action"),
        [
            (BackCommand(), "mobile_back"),
            (HomeCommand(), "mobile_home"),
            (NotificationCommand(), "mobile_notification"),
            (AppSwitchCommand(), "mobile_app_switch"),
            (ShakeCommand(), "mobile_shake"),
        ],
    )
    def test_execute(self, perf_timer, cmd, action: str) -> None:
        result, timer = perf_timer(action, ITERATIONS)
        step = Step(action=action.removeprefix("mobile_"))
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50


@pytest.mark.perf
class TestRotateDevicePerf:
    def test_rotate_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_rotate", ITERATIONS)
        cmd = RotateDeviceCommand()
        step = Step(action="rotate_device", orientation="landscape")
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_rotate_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_rotate_describe", ITERATIONS)
        cmd = RotateDeviceCommand()
        step = Step(action="rotate_device", orientation="landscape")
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestMobileScrollPerf:
    def test_scroll_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_scroll", ITERATIONS)
        cmd = MobileScrollCommand()
        step = Step(action="scroll", direction="down", pixels=300)
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_scroll_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_scroll_describe", ITERATIONS)
        cmd = MobileScrollCommand()
        step = Step(action="scroll", direction="down", pixels=300)
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestMobileTypePerf:
    def test_type_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_type", ITERATIONS)
        cmd = MobileTypeCommand()
        step = Step(
            action="type",
            locator=Locator(type="accessibility_id", value="search"),
            value="hello world",
        )
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_type_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_type_describe", ITERATIONS)
        cmd = MobileTypeCommand()
        step = Step(
            action="type",
            locator=Locator(type="accessibility_id", value="search"),
            value="hello world",
        )
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestMobileClickPerf:
    def test_click_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_click", ITERATIONS)
        cmd = MobileClickCommand()
        step = Step(action="click", locator=Locator(type="accessibility_id", value="btn"))
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_click_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_click_describe", ITERATIONS)
        cmd = MobileClickCommand()
        step = Step(action="click", locator=Locator(type="accessibility_id", value="btn"))
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestMobileWaitForPerf:
    def test_wait_for_execute(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_wait_for", ITERATIONS)
        cmd = MobileWaitForCommand()
        step = Step(
            action="wait_for",
            locator=Locator(type="accessibility_id", value="result"),
            timeout=5.0,
        )
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_wait_for_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_wait_for_describe", ITERATIONS)
        cmd = MobileWaitForCommand()
        step = Step(
            action="wait_for",
            locator=Locator(type="accessibility_id", value="result"),
            timeout=5.0,
        )
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestMobileScreenshotPerf:
    def test_screenshot_execute(self, perf_timer, tmp_path: Path) -> None:
        result, timer = perf_timer("mobile_screenshot", ITERATIONS)
        cmd = MobileScreenshotCommand(output_dir=tmp_path)
        step = Step(action="screenshot", filename="shot.png")
        mobile = _mock_mobile()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(mobile, step)
        assert result.mean_ms < 50

    def test_screenshot_describe(self, perf_timer) -> None:
        result, timer = perf_timer("mobile_screenshot_describe", ITERATIONS)
        cmd = MobileScreenshotCommand(output_dir=Path("/tmp"))
        step = Step(action="screenshot", filename="shot.png")
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestMobileCommandDispatchPerf:
    """Benchmark the get_mobile_command() dispatch itself."""

    @pytest.mark.parametrize(
        "action",
        [
            "tap",
            "swipe",
            "pinch",
            "long_press",
            "back",
            "home",
            "notification",
            "app_switch",
            "rotate_device",
            "shake",
            "scroll",
            "type",
            "click",
            "wait_for",
            "screenshot",
        ],
    )
    def test_dispatch(self, perf_timer, action: str) -> None:
        result, timer = perf_timer(f"mobile_dispatch_{action}", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                get_mobile_command(action, output_dir=Path("."))
        assert result.mean_ms < 10
