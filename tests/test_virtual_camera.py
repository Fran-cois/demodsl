"""Tests for the virtual camera vocabulary (CameraMove, action: camera)."""

from __future__ import annotations

from typing import Any

import pytest

from demodsl.commands import CameraCommand, get_command
from demodsl.models import CameraMove, Locator, Step


class _RecordingBrowser:
    """Minimal stub that captures every evaluate_js call."""

    def __init__(self) -> None:
        self.scripts: list[str] = []

    def evaluate_js(self, script: str) -> Any:
        self.scripts.append(script)
        return None


# ── Model parsing ────────────────────────────────────────────────────────────


def test_camera_move_requires_at_least_one_field():
    with pytest.raises(ValueError, match="CameraMove requires"):
        CameraMove()


def test_camera_move_reset_alone_is_valid():
    move = CameraMove(reset=True)
    assert move.reset is True


def test_camera_move_with_zoom_only():
    move = CameraMove(zoom=1.5)
    assert move.zoom == 1.5
    assert move.duration == 0.6


def test_step_camera_action_requires_camera_block():
    with pytest.raises(ValueError, match="'camera' requires a 'camera:' block"):
        Step(action="camera")


def test_step_camera_reset_does_not_require_camera_block():
    step = Step(action="camera_reset")
    assert step.action == "camera_reset"
    assert step.camera is None


def test_step_camera_full():
    step = Step(
        action="camera",
        camera=CameraMove(
            zoom=2.0,
            target=Locator(type="css", value="#hero"),
            rotation=5,
            duration=0.8,
            ease="spring",
            hold=0.5,
        ),
    )
    assert step.camera is not None
    assert step.camera.zoom == 2.0
    assert step.camera.target is not None
    assert step.camera.target.value == "#hero"


def test_step_per_action_camera_on_click():
    """Embedding 'camera:' on a click step should parse cleanly."""
    step = Step(
        action="click",
        locator=Locator(type="css", value=".btn"),
        camera=CameraMove(zoom=1.5, target=Locator(type="css", value=".btn")),
    )
    assert step.camera is not None
    assert step.camera.zoom == 1.5


# ── Command dispatch ─────────────────────────────────────────────────────────


def test_get_command_returns_camera_command():
    cmd = get_command("camera")
    assert isinstance(cmd, CameraCommand)


def test_get_command_returns_camera_command_for_reset():
    cmd = get_command("camera_reset")
    assert isinstance(cmd, CameraCommand)


# ── JS injection ─────────────────────────────────────────────────────────────


def test_camera_command_injects_bootstrap_and_apply():
    browser = _RecordingBrowser()
    step = Step(
        action="camera",
        camera=CameraMove(zoom=1.5, target_x=0.5, target_y=0.5, duration=0),
    )
    CameraCommand().execute(browser, step)
    assert len(browser.scripts) >= 2
    assert "__demodslCamera" in browser.scripts[0]
    # The second script should call .apply(...)
    assert ".apply(" in browser.scripts[1]
    assert "1.5" in browser.scripts[1]  # zoom factor reaches the JS


def test_camera_command_reset_calls_reset():
    browser = _RecordingBrowser()
    step = Step(action="camera_reset")
    CameraCommand().execute(browser, step)
    assert any(".reset(" in s for s in browser.scripts)


def test_camera_command_with_target_uses_locator_resolver():
    browser = _RecordingBrowser()
    step = Step(
        action="camera",
        camera=CameraMove(zoom=2.0, target=Locator(type="css", value=".hero"), duration=0),
    )
    CameraCommand().execute(browser, step)
    apply_script = next(s for s in browser.scripts if ".apply(" in s)
    assert "resolveLocator" in apply_script
    assert ".hero" in apply_script


def test_camera_command_spring_ease_translates_to_cubic_bezier():
    browser = _RecordingBrowser()
    step = Step(
        action="camera",
        camera=CameraMove(zoom=1.2, target_x=0.5, ease="spring", duration=0),
    )
    CameraCommand().execute(browser, step)
    apply_script = next(s for s in browser.scripts if ".apply(" in s)
    assert "cubic-bezier" in apply_script
