"""Tests for demodsl.camera_check — camera choreography coherence."""

from __future__ import annotations

import warnings

import pytest

from demodsl.camera_check import ERROR, WARN, check_camera_flow
from demodsl.models import Scenario
from demodsl.recipe import walkthrough


def _scenario(steps: list[dict]) -> Scenario:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # exercised explicitly below
        return Scenario(name="t", url="https://x.io", steps=steps)


HOVER_ZOOM = {
    "action": "hover",
    "locator": {"type": "css", "value": "h1"},
    "camera": {"zoom": 1.5, "target": {"type": "css", "value": "h1"}},
    "wait": 3.0,
}
RESET = {"action": "camera_reset", "camera": {"reset": True}}


class TestCameraFlow:
    def test_clean_flow_passes(self) -> None:
        sc = _scenario(
            [
                {"action": "navigate", "url": "https://x.io"},
                HOVER_ZOOM,
                RESET,
                {"action": "scroll", "direction": "down", "pixels": 300},
            ]
        )
        assert check_camera_flow(sc) == []

    def test_scroll_while_zoomed_is_error(self) -> None:
        sc = _scenario(
            [
                HOVER_ZOOM,
                {"action": "scroll", "direction": "down", "pixels": 300},
                RESET,
            ]
        )
        issues = check_camera_flow(sc)
        assert any(i.severity == ERROR and "scroll" in i.message for i in issues)

    def test_dangling_zoom_at_end_is_error(self) -> None:
        issues = check_camera_flow(_scenario([HOVER_ZOOM]))
        assert any(i.severity == ERROR and "ends with the camera" in i.message for i in issues)

    def test_camera_on_navigate_is_error(self) -> None:
        sc = _scenario(
            [
                {"action": "navigate", "url": "https://x.io", "camera": {"zoom": 1.4}},
                RESET,
            ]
        )
        issues = check_camera_flow(sc)
        assert any(i.severity == ERROR and "navigate" in i.message for i in issues)

    def test_extreme_zoom_warns(self) -> None:
        sc = _scenario(
            [
                {**HOVER_ZOOM, "camera": {"zoom": 3.5, "target": {"type": "css", "value": "h1"}}},
                RESET,
            ]
        )
        issues = check_camera_flow(sc)
        assert any(i.severity == WARN and "exceeds" in i.message for i in issues)

    def test_retarget_without_reset_warns(self) -> None:
        second = {
            "action": "hover",
            "locator": {"type": "text", "value": "Pricing"},
            "camera": {"zoom": 1.6, "target": {"type": "text", "value": "Pricing"}},
        }
        sc = _scenario([HOVER_ZOOM, second, RESET])
        issues = check_camera_flow(sc)
        assert any(i.severity == WARN and "re-targets" in i.message for i in issues)

    def test_hold_longer_than_wait_warns(self) -> None:
        sc = _scenario(
            [
                {
                    **HOVER_ZOOM,
                    "camera": {"zoom": 1.5, "hold": 9.0, "target": {"type": "css", "value": "h1"}},
                    "wait": 2.0,
                },
                RESET,
            ]
        )
        issues = check_camera_flow(sc)
        assert any("hold" in i.message for i in issues)

    def test_target_mismatch_warns(self) -> None:
        sc = _scenario(
            [
                {
                    "action": "hover",
                    "locator": {"type": "css", "value": "h1"},
                    "camera": {"zoom": 1.5, "target": {"type": "text", "value": "Other"}},
                },
                RESET,
            ]
        )
        issues = check_camera_flow(sc)
        assert any("intentional" in i.message for i in issues)

    def test_model_validation_emits_warnings(self) -> None:
        with pytest.warns(UserWarning, match="camera"):
            Scenario(name="t", url="https://x.io", steps=[HOVER_ZOOM])


def test_recipe_output_is_camera_coherent() -> None:
    """The house recipe must never trip its own coherence checker."""
    cfg = walkthrough(
        company="Acme",
        url="https://acme.com",
        beats=[
            {
                "locator": {"type": "css", "value": "h1"},
                "narration": "The hero promises effortless invoicing today.",
            },
            {"locator": None, "narration": "Proof lives below the fold here."},
            {
                "locator": {"type": "text", "value": "Start free"},
                "role": "cta",
                "narration": "One clear call to action seals the pitch now.",
            },
        ],
        verdict="Solid — 4 out of 5.",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sc = Scenario(**cfg["scenarios"][0])
    assert [i for i in check_camera_flow(sc) if i.severity == ERROR] == []
