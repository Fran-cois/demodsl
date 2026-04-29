"""Unit tests for new browser actions (hover, drag, press_key)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from demodsl.commands import get_command
from demodsl.models import Locator, Step

# ── Validation ────────────────────────────────────────────────────────────────


class TestStepValidation:
    def test_hover_requires_locator(self) -> None:
        with pytest.raises(ValidationError):
            Step(action="hover")

    def test_hover_ok(self) -> None:
        s = Step(action="hover", locator=Locator(type="css", value=".btn"))
        assert s.action == "hover"

    def test_drag_requires_source_locator(self) -> None:
        with pytest.raises(ValidationError):
            Step(action="drag")

    def test_drag_with_target_locator(self) -> None:
        Step(
            action="drag",
            locator=Locator(type="css", value=".src"),
            target_locator=Locator(type="css", value=".dst"),
        )

    def test_drag_with_end_coords(self) -> None:
        Step(
            action="drag",
            locator=Locator(type="css", value=".src"),
            end_x=100,
            end_y=200,
        )

    def test_press_key_requires_key(self) -> None:
        with pytest.raises(ValidationError):
            Step(action="press_key")

    def test_press_key_ok(self) -> None:
        s = Step(action="press_key", key="Enter")
        assert s.key == "Enter"


# ── Command dispatch ──────────────────────────────────────────────────────────


class TestCommandDispatch:
    def test_hover_command(self) -> None:
        step = Step(action="hover", locator=Locator(type="css", value=".btn"))
        cmd = get_command("hover")
        browser = MagicMock()
        cmd.execute(browser, step)
        browser.hover.assert_called_once()

    def test_press_key_command(self) -> None:
        step = Step(action="press_key", key="Enter")
        cmd = get_command("press_key")
        browser = MagicMock()
        cmd.execute(browser, step)
        browser.press_keys.assert_called_once()

    def test_drag_command_with_target(self) -> None:
        step = Step(
            action="drag",
            locator=Locator(type="css", value=".s"),
            target_locator=Locator(type="css", value=".t"),
        )
        cmd = get_command("drag")
        browser = MagicMock()
        cmd.execute(browser, step)
        browser.drag_and_drop.assert_called_once()

    def test_drag_command_with_coords(self) -> None:
        step = Step(
            action="drag",
            locator=Locator(type="css", value=".s"),
            end_x=10,
            end_y=20,
        )
        cmd = get_command("drag")
        browser = MagicMock()
        cmd.execute(browser, step)
        browser.drag_and_drop.assert_called_once()
