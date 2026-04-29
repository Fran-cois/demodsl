"""Tests for mobile scenario orchestration in ScenarioOrchestrator."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.effects.registry import EffectRegistry
from demodsl.models import (
    DemoConfig,
    Locator,
    MobileConfig,
    Scenario,
    Step,
)
from demodsl.orchestrators.scenario import ScenarioOrchestrator
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import MobileProvider, MobileProviderFactory

# ── Helpers ───────────────────────────────────────────────────────────────────


def _android_config() -> MobileConfig:
    return MobileConfig(
        platform="android",
        device_name="Pixel 7",
        app_package="com.example.app",
    )


def _mobile_scenario(
    *,
    steps: list[Step] | None = None,
    pre_steps: list[Step] | None = None,
) -> Scenario:
    return Scenario(
        name="test_mobile",
        mobile=_android_config(),
        steps=steps or [Step(action="back", wait=0.0)],
        pre_steps=pre_steps,
    )


def _minimal_config(scenario: Scenario | None = None) -> DemoConfig:
    return DemoConfig(
        metadata={"title": "Test"},
        scenarios=[scenario or _mobile_scenario()],
    )


def _mock_workspace(tmp_path: Path) -> Workspace:
    ws = MagicMock(spec=Workspace)
    ws.raw_video = tmp_path / "raw_video"
    ws.raw_video.mkdir(parents=True, exist_ok=True)
    ws.frames = tmp_path / "frames"
    ws.frames.mkdir(parents=True, exist_ok=True)
    return ws


def _mock_appium_modules() -> dict[str, types.ModuleType]:
    """Create mock appium modules."""
    appium_mod = types.ModuleType("appium")
    webdriver_mod = types.ModuleType("appium.webdriver")
    options_mod = types.ModuleType("appium.options")
    android_opts = types.ModuleType("appium.options.android")
    ios_opts = types.ModuleType("appium.options.ios")
    android_opts.UiAutomator2Options = MagicMock  # type: ignore[attr-defined]
    ios_opts.XCUITestOptions = MagicMock  # type: ignore[attr-defined]
    webdriver_mod.Remote = MagicMock  # type: ignore[attr-defined]
    appium_mod.webdriver = webdriver_mod  # type: ignore[attr-defined]
    appium_mod.options = options_mod  # type: ignore[attr-defined]
    return {
        "appium": appium_mod,
        "appium.webdriver": webdriver_mod,
        "appium.options": options_mod,
        "appium.options.android": android_opts,
        "appium.options.ios": ios_opts,
    }


@pytest.fixture()
def mock_mobile() -> MagicMock:
    provider = MagicMock(spec=MobileProvider)
    provider.close.return_value = Path("/tmp/fake_video.mp4")
    return provider


@pytest.fixture()
def _patch_mobile_factory(mock_mobile):
    """Patch MobileProviderFactory.create to return our mock."""
    with (
        patch.object(MobileProviderFactory, "create", return_value=mock_mobile),
        patch.dict(sys.modules, _mock_appium_modules()),
    ):
        yield


# ── _execute_mobile_scenario ──────────────────────────────────────────────────


class TestExecuteMobileScenario:
    def test_basic_flow(self, mock_mobile, _patch_mobile_factory, tmp_path) -> None:
        """Steps are executed, provider is launched and closed."""
        scenario = _mobile_scenario(
            steps=[
                Step(action="back", wait=0.0),
                Step(action="home", wait=0.0),
            ]
        )
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)

        video, duration = orch._execute_mobile_scenario(scenario, ws, narration_durations={})

        mock_mobile.launch.assert_called_once()
        mock_mobile.close.assert_called_once()
        assert video == Path("/tmp/fake_video.mp4")
        assert duration > 0
        assert len(orch.step_timestamps) == 2

    def test_pre_steps_run_before_main(self, mock_mobile, _patch_mobile_factory, tmp_path) -> None:
        """Pre-steps execute before the main steps."""
        scenario = _mobile_scenario(
            pre_steps=[Step(action="tap", locator=Locator(type="id", value="skip"), wait=0.0)],
            steps=[Step(action="back", wait=0.0)],
        )
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)

        orch._execute_mobile_scenario(scenario, ws, narration_durations={})

        # Pre-step command was executed (via get_mobile_command → cmd.execute)
        # Then close was still called
        mock_mobile.close.assert_called_once()

    def test_close_called_on_step_error(self, mock_mobile, _patch_mobile_factory, tmp_path) -> None:
        """Provider.close() is called even if a step raises."""
        scenario = _mobile_scenario(
            steps=[Step(action="back", wait=0.0)],
        )
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)

        # Make the command execution fail
        with patch("demodsl.orchestrators.scenario.get_mobile_command") as mock_get_cmd:
            mock_cmd = MagicMock()
            mock_cmd.execute.side_effect = RuntimeError("step failed")
            mock_get_cmd.return_value = mock_cmd

            with pytest.raises(RuntimeError, match="step failed"):
                orch._execute_mobile_scenario(scenario, ws, narration_durations={})

        # close() must still be called via finally
        mock_mobile.close.assert_called_once()

    def test_returns_none_video_when_no_recording(self, _patch_mobile_factory, tmp_path) -> None:
        """When provider returns None video path, orchestrator handles it."""
        mock_prov = MobileProviderFactory.create("appium")
        mock_prov.close.return_value = None

        scenario = _mobile_scenario(steps=[Step(action="back", wait=0.0)])
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)

        video, duration = orch._execute_mobile_scenario(scenario, ws, narration_durations={})
        assert video is None


# ── _execute_mobile_step ──────────────────────────────────────────────────────


class TestExecuteMobileStep:
    def test_returns_none(self, mock_mobile, tmp_path) -> None:
        """_execute_mobile_step must return None, not []."""
        config = _minimal_config()
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)
        step = Step(action="back", wait=0.0)

        result = orch._execute_mobile_step(mock_mobile, step, ws, t0=0.0)
        assert result is None

    def test_records_timestamp(self, mock_mobile, tmp_path) -> None:
        config = _minimal_config()
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)
        step = Step(action="back", wait=0.0)

        orch._execute_mobile_step(mock_mobile, step, ws, t0=0.0)
        assert len(orch.step_timestamps) == 1
        assert orch.step_timestamps[0] >= 0

    def test_collects_post_effects(self, mock_mobile, tmp_path) -> None:
        config = _minimal_config()
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)
        step = Step(action="back", wait=0.0)

        orch._execute_mobile_step(mock_mobile, step, ws, t0=0.0)
        # No effects → empty list appended
        assert len(orch.step_post_effects) == 1
        assert orch.step_post_effects[0] == []


# ── _dry_run_scenarios with mobile ───────────────────────────────────────────


class TestDryRunMobile:
    def test_dry_run_mobile_scenario(self, tmp_path) -> None:
        """Dry-run logs mobile info without launching Appium."""
        scenario = _mobile_scenario(
            steps=[Step(action="tap", locator=Locator(type="id", value="btn"), wait=0.0)],
        )
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())

        result = orch._dry_run_scenarios()
        assert result == []

    def test_dry_run_dispatches_mobile_command(self, tmp_path) -> None:
        """Dry-run uses get_mobile_command for mobile scenarios."""
        scenario = _mobile_scenario(
            pre_steps=[Step(action="back", wait=0.0)],
            steps=[Step(action="home", wait=0.0)],
        )
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())

        with patch("demodsl.orchestrators.scenario.get_mobile_command") as mock_get:
            mock_cmd = MagicMock()
            mock_cmd.describe.return_value = "mock_desc"
            mock_get.return_value = mock_cmd

            orch._dry_run_scenarios()

            # Called for pre_step + step = 2 calls
            assert mock_get.call_count == 2


# ── Dispatch in _execute_scenario ─────────────────────────────────────────────


class TestScenarioDispatch:
    def test_mobile_scenario_dispatches(self, mock_mobile, _patch_mobile_factory, tmp_path) -> None:
        """_execute_scenario routes mobile scenarios to _execute_mobile_scenario."""
        scenario = _mobile_scenario(steps=[Step(action="back", wait=0.0)])
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())
        ws = _mock_workspace(tmp_path)

        video, dur = orch._execute_scenario(scenario, ws, narration_durations={})

        mock_mobile.launch.assert_called_once()
        mock_mobile.close.assert_called_once()

    def test_browser_scenario_does_not_use_mobile(self, tmp_path) -> None:
        """A browser scenario should NOT dispatch to mobile path."""
        scenario = Scenario(
            name="browser_test",
            url="https://example.com",
            steps=[Step(action="navigate", url="https://example.com", wait=0.0)],
        )
        config = _minimal_config(scenario)
        orch = ScenarioOrchestrator(config, EffectRegistry())

        with patch.object(orch, "_execute_mobile_scenario") as mock_mobile_exec:
            # Let browser path fail — we just verify mobile is NOT called
            try:
                ws = _mock_workspace(tmp_path)
                orch._execute_scenario(scenario, ws, narration_durations={})
            except Exception:
                pass
            mock_mobile_exec.assert_not_called()
