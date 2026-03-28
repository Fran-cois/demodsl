"""Performance tests for browser command actions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demodsl.commands import (
    ClickCommand,
    NavigateCommand,
    ScreenshotCommand,
    ScrollCommand,
    TypeCommand,
    WaitForCommand,
    get_command,
)
from demodsl.models import Locator, Step
from demodsl.providers.base import BrowserProvider

ITERATIONS = 500


def _mock_browser() -> MagicMock:
    browser = MagicMock(spec=BrowserProvider)
    browser.navigate = MagicMock()
    browser.click = MagicMock()
    browser.type_text = MagicMock()
    browser.scroll = MagicMock()
    browser.wait_for = MagicMock()
    browser.screenshot = MagicMock(return_value=Path("screenshot.png"))
    return browser


@pytest.mark.perf
class TestNavigatePerf:
    def test_navigate_execute(self, perf_timer) -> None:
        result, timer = perf_timer("navigate", ITERATIONS)
        cmd = NavigateCommand()
        step = Step(action="navigate", url="https://example.com")
        browser = _mock_browser()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(browser, step)
        assert result.mean_ms < 50

    def test_navigate_describe(self, perf_timer) -> None:
        result, timer = perf_timer("navigate_describe", ITERATIONS)
        cmd = NavigateCommand()
        step = Step(action="navigate", url="https://example.com")
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestClickPerf:
    def test_click_execute(self, perf_timer) -> None:
        result, timer = perf_timer("click", ITERATIONS)
        cmd = ClickCommand()
        step = Step(action="click", locator=Locator(type="css", value="#btn"))
        browser = _mock_browser()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(browser, step)
        assert result.mean_ms < 50

    def test_click_describe(self, perf_timer) -> None:
        result, timer = perf_timer("click_describe", ITERATIONS)
        cmd = ClickCommand()
        step = Step(action="click", locator=Locator(type="css", value="#btn"))
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestTypePerf:
    def test_type_execute(self, perf_timer) -> None:
        result, timer = perf_timer("type", ITERATIONS)
        cmd = TypeCommand()
        step = Step(
            action="type",
            locator=Locator(type="id", value="search"),
            value="hello world",
        )
        browser = _mock_browser()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(browser, step)
        assert result.mean_ms < 50

    def test_type_describe(self, perf_timer) -> None:
        result, timer = perf_timer("type_describe", ITERATIONS)
        cmd = TypeCommand()
        step = Step(
            action="type",
            locator=Locator(type="id", value="search"),
            value="hello world",
        )
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestScrollPerf:
    def test_scroll_execute(self, perf_timer) -> None:
        result, timer = perf_timer("scroll", ITERATIONS)
        cmd = ScrollCommand()
        step = Step(action="scroll", direction="down", pixels=500)
        browser = _mock_browser()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(browser, step)
        assert result.mean_ms < 50

    def test_scroll_describe(self, perf_timer) -> None:
        result, timer = perf_timer("scroll_describe", ITERATIONS)
        cmd = ScrollCommand()
        step = Step(action="scroll", direction="down", pixels=500)
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestWaitForPerf:
    def test_wait_for_execute(self, perf_timer) -> None:
        result, timer = perf_timer("wait_for", ITERATIONS)
        cmd = WaitForCommand()
        step = Step(
            action="wait_for",
            locator=Locator(type="xpath", value="//div[@id='result']"),
            timeout=5.0,
        )
        browser = _mock_browser()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(browser, step)
        assert result.mean_ms < 50

    def test_wait_for_describe(self, perf_timer) -> None:
        result, timer = perf_timer("wait_for_describe", ITERATIONS)
        cmd = WaitForCommand()
        step = Step(
            action="wait_for",
            locator=Locator(type="xpath", value="//div[@id='result']"),
            timeout=5.0,
        )
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestScreenshotPerf:
    def test_screenshot_execute(self, perf_timer, tmp_path: Path) -> None:
        result, timer = perf_timer("screenshot", ITERATIONS)
        cmd = ScreenshotCommand(output_dir=tmp_path)
        step = Step(action="screenshot", filename="shot.png")
        browser = _mock_browser()
        for _ in range(ITERATIONS):
            with timer:
                cmd.execute(browser, step)
        assert result.mean_ms < 50

    def test_screenshot_describe(self, perf_timer) -> None:
        result, timer = perf_timer("screenshot_describe", ITERATIONS)
        cmd = ScreenshotCommand(output_dir=Path("/tmp"))
        step = Step(action="screenshot", filename="shot.png")
        for _ in range(ITERATIONS):
            with timer:
                cmd.describe(step)
        assert result.mean_ms < 10


@pytest.mark.perf
class TestCommandDispatchPerf:
    """Benchmark the get_command() dispatch itself."""

    @pytest.mark.parametrize(
        "action",
        ["navigate", "click", "type", "scroll", "wait_for", "screenshot"],
    )
    def test_dispatch(self, perf_timer, action: str) -> None:
        result, timer = perf_timer(f"dispatch_{action}", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                get_command(action, output_dir=Path("."))
        assert result.mean_ms < 10
