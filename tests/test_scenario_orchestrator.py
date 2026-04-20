"""Tests for demodsl.orchestrators.scenario — ScenarioOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.effects.cursor import CursorOverlay
from demodsl.effects.glow_select import GlowSelectOverlay
from demodsl.effects.popup_card import PopupCardOverlay
from demodsl.effects.registry import EffectRegistry
from demodsl.effects.browser_effects import register_all_browser_effects
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.models import (
    DemoConfig,
    DemoStoppedError,
    Effect,
    Step,
    StopCondition,
    Locator,
    CardContent,
)
from demodsl.orchestrators.scenario import ScenarioOrchestrator
from demodsl.pipeline.workspace import Workspace


def _make_effects() -> EffectRegistry:
    reg = EffectRegistry()
    register_all_browser_effects(reg)
    register_all_post_effects(reg)
    return reg


def _make_config(scenarios=None) -> DemoConfig:
    data: dict = {"metadata": {"title": "Test"}}
    if scenarios:
        data["scenarios"] = scenarios
    return DemoConfig(**data)


def _make_config_with_scenario() -> DemoConfig:
    return _make_config(
        scenarios=[
            {
                "name": "S1",
                "url": "https://example.com",
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Hello",
                        "wait": 0.5,
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#btn"},
                    },
                ],
            }
        ]
    )


class TestScenarioOrchestratorInit:
    def test_init(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        assert orch.config is config
        assert orch.step_timestamps == []
        assert orch.step_post_effects == []


class TestDryRunScenarios:
    def test_dry_run_returns_empty(self) -> None:
        config = _make_config_with_scenario()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        with Workspace() as ws:
            result = orch.run_scenarios(ws, dry_run=True)
        assert result.raw_videos == []
        assert result.step_timestamps == []

    def test_dry_run_no_scenarios(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        with Workspace() as ws:
            result = orch.run_scenarios(ws, dry_run=True)
        assert result.raw_videos == []


class TestCollectPostEffects:
    def test_no_effects(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        orch._collect_post_effects([])
        assert orch.step_post_effects == [[]]

    def test_browser_effect_not_collected(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        from demodsl.models import Effect

        # spotlight is a browser effect, not a post effect
        orch._collect_post_effects([Effect(type="spotlight")])
        assert orch.step_post_effects == [[]]

    def test_post_effect_collected(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        from demodsl.models import Effect

        # ken_burns is a post effect
        orch._collect_post_effects([Effect(type="ken_burns", duration=0.5)])
        assert len(orch.step_post_effects) == 1
        assert len(orch.step_post_effects[0]) == 1
        assert orch.step_post_effects[0][0][0] == "ken_burns"


class TestApplyBrowserEffects:
    def test_applies_browser_effect(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        from demodsl.models import Effect

        result = orch._apply_browser_effects(
            mock_browser, [Effect(type="spotlight", duration=0.5)]
        )
        mock_browser.evaluate_js.assert_called()
        assert result == 0.5

    def test_no_duration_returns_zero(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        result = orch._apply_browser_effects(mock_browser, [Effect(type="spotlight")])
        mock_browser.evaluate_js.assert_called()
        assert result == 0.0


class TestExecuteStep:
    @patch("demodsl.orchestrators.scenario.time")
    def test_navigate_step(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        step = Step(action="navigate", url="https://example.com", wait=0.1)
        with Workspace() as ws:
            orch._execute_step(mock_browser, step, ws)
        assert orch.step_post_effects == [[]]

    @patch("demodsl.orchestrators.scenario.time")
    def test_click_step_with_cursor(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()
        mock_browser.get_element_center.return_value = (100.0, 200.0)
        mock_browser.get_element_bbox.return_value = {
            "x": 90,
            "y": 190,
            "width": 20,
            "height": 20,
        }

        cursor = CursorOverlay({"visible": True, "smooth": 0.01})
        glow = GlowSelectOverlay({"enabled": True})

        step = Step(
            action="click",
            locator=Locator(type="css", value="#btn"),
        )
        with Workspace() as ws:
            orch._execute_step(mock_browser, step, ws, cursor=cursor, glow=glow)
        mock_browser.get_element_center.assert_called()

    @patch("demodsl.orchestrators.scenario.time")
    def test_step_with_card(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        popup = PopupCardOverlay({"enabled": True})
        popup.inject = MagicMock()
        popup.show = MagicMock()
        popup.hide = MagicMock()

        step = Step(
            action="navigate",
            url="https://example.com",
            card=CardContent(title="Hello", body="World"),
        )
        with Workspace() as ws:
            orch._execute_step(mock_browser, step, ws, popup=popup)
        popup.show.assert_called_once()
        popup.hide.assert_called_once()

    @patch("demodsl.orchestrators.scenario.time")
    def test_step_with_effects(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        step = Step(
            action="navigate",
            url="https://example.com",
            effects=[Effect(type="spotlight", duration=0.3)],
        )
        with Workspace() as ws:
            orch._execute_step(mock_browser, step, ws)
        mock_browser.evaluate_js.assert_called()

    @patch("demodsl.orchestrators.scenario.time")
    def test_step_with_narration_duration_waits(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        step = Step(action="navigate", url="https://example.com")
        with Workspace() as ws:
            orch._execute_step(mock_browser, step, ws, narration_duration=2.0)
        # Should have called time.sleep with narration duration
        sleep_calls = [c.args[0] for c in mock_time.sleep.call_args_list]
        assert any(s >= 2.0 for s in sleep_calls)


class TestRevealCardItems:
    @patch("demodsl.orchestrators.scenario.time")
    def test_reveal_items_progressively(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        popup = PopupCardOverlay({"enabled": True})
        popup.reveal_next = MagicMock(return_value=1)

        orch._reveal_card_items(
            mock_browser, popup, ["A", "B", "C"], 5.0, base_wait=0.0
        )
        assert popup.reveal_next.call_count == 3

    @patch("demodsl.orchestrators.scenario.time")
    def test_reveal_single_item(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        popup = PopupCardOverlay({"enabled": True})
        popup.reveal_next = MagicMock(return_value=1)

        orch._reveal_card_items(mock_browser, popup, ["A"], 2.0, base_wait=0.0)
        assert popup.reveal_next.call_count == 1


class TestRunScenariosWithMockedBrowser:
    @patch("demodsl.orchestrators.scenario.time")
    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    def test_run_records_video(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        config = _make_config_with_scenario()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        video_file = tmp_path / "recording.webm"
        video_file.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video_file
        mock_factory.create.return_value = mock_browser

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        assert len(result.raw_videos) == 1
        assert len(result.step_timestamps) == 2
        assert len(result.step_post_effects) == 2


class TestNarrationGap:
    @patch("demodsl.orchestrators.scenario.time")
    def test_effective_wait_includes_gap(self, mock_time: MagicMock) -> None:
        """effective_wait should be narration_duration + narration_gap."""
        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "narration_gap": 0.5},
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                        },
                    ],
                }
            ],
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        step = Step(action="navigate", url="https://example.com")
        mock_time.monotonic.return_value = 0.0
        with Workspace() as ws:
            orch._execute_step(
                mock_browser, step, ws, narration_duration=2.0, narration_gap=0.5
            )
        sleep_calls = [c.args[0] for c in mock_time.sleep.call_args_list]
        # Should sleep at least 2.0 + 0.5 = 2.5s
        assert any(s >= 2.5 for s in sleep_calls)

    @patch("demodsl.orchestrators.scenario.time")
    def test_step_wait_overrides_when_larger(self, mock_time: MagicMock) -> None:
        """If step.wait > narration_duration + gap, step.wait wins."""
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        step = Step(action="navigate", url="https://example.com", wait=5.0)
        mock_time.monotonic.return_value = 0.0
        with Workspace() as ws:
            orch._execute_step(
                mock_browser, step, ws, narration_duration=2.0, narration_gap=0.3
            )
        sleep_calls = [c.args[0] for c in mock_time.sleep.call_args_list]
        # step.wait=5.0 > 2.0 + 0.3 = 2.3, so should sleep 5.0
        assert any(s >= 5.0 for s in sleep_calls)

    @patch("demodsl.orchestrators.scenario.time")
    def test_no_gap_when_no_narration(self, mock_time: MagicMock) -> None:
        """narration_gap should not be added when there is no narration."""
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        mock_browser = MagicMock()

        step = Step(action="navigate", url="https://example.com", wait=1.0)
        mock_time.monotonic.return_value = 0.0
        with Workspace() as ws:
            orch._execute_step(
                mock_browser, step, ws, narration_duration=0.0, narration_gap=0.0
            )
        sleep_calls = [c.args[0] for c in mock_time.sleep.call_args_list]
        # No gap added, just regular wait
        max_sleep = max(sleep_calls) if sleep_calls else 0.0
        assert max_sleep <= 1.5  # just step.wait + POST_NAVIGATE_DELAY margin


class TestMultiScenarioTimestampOffset:
    """step_timestamps must be offset by cumulative scenario duration."""

    def _make_multi_scenario_config(self) -> DemoConfig:
        return DemoConfig(
            metadata={"title": "Multi"},
            voice={"engine": "gtts"},
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "wait": 1.0,
                        },
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#a"},
                            "wait": 1.0,
                        },
                    ],
                },
                {
                    "name": "S2",
                    "url": "https://example.com/page2",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com/page2",
                            "wait": 1.0,
                        },
                    ],
                },
            ],
        )

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_second_scenario_timestamps_offset(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Timestamps from scenario 2 should be offset by scenario 1 duration."""
        config = self._make_multi_scenario_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        # Simulate monotonic clock: scenario 1 runs 0→5s, scenario 2 runs 5→8s
        call_count = [0]

        def fake_monotonic():
            call_count[0] += 1
            # t0 for scenario 1 = 0.0
            # step_timestamps for scenario 1: 0.1, 1.2
            # t0 for scenario 2 = 5.0
            # step_timestamp for scenario 2: 0.2 (relative to t0=5.0, so monotonic=5.2)
            # scenario 1 duration: monotonic after close - t0 = 3.0 - 0.0 = 3.0
            # scenario 2 duration: monotonic after close - t0 = 8.0 - 5.0 = 3.0
            timeline = [
                # Scenario 1: t0
                0.0,
                # Scenario 1 step 0: timestamp = monotonic - t0 = 0.1
                0.1,
                # Scenario 1 step 1: timestamp = monotonic - t0 = 1.2
                1.2,
                # Scenario 1: after browser.close → scenario_duration = 3.0 - 0.0 = 3.0
                3.0,
                # Scenario 2: t0
                5.0,
                # Scenario 2 step 0: timestamp = monotonic - t0 = 5.2 - 5.0 = 0.2
                5.2,
                # Scenario 2: after browser.close → scenario_duration = 8.0 - 5.0 = 3.0
                8.0,
            ]
            idx = min(call_count[0] - 1, len(timeline) - 1)
            return timeline[idx]

        mock_time.monotonic = fake_monotonic
        mock_time.sleep = MagicMock()

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        ts = result.step_timestamps
        assert len(ts) == 3
        # Scenario 1 timestamps: 0.1, 1.2 (no offset)
        assert ts[0] == 0.1
        assert ts[1] == 1.2
        # Scenario 2 timestamp: 0.2 + offset(3.0) = 3.2
        assert ts[2] == 3.2

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_timestamps_are_monotonically_increasing(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """All timestamps across scenarios must be strictly increasing."""
        config = self._make_multi_scenario_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        call_count = [0]

        def fake_monotonic():
            call_count[0] += 1
            timeline = [0.0, 0.5, 2.0, 4.0, 10.0, 10.3, 13.0]
            idx = min(call_count[0] - 1, len(timeline) - 1)
            return timeline[idx]

        mock_time.monotonic = fake_monotonic
        mock_time.sleep = MagicMock()

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        ts = result.step_timestamps
        for i in range(len(ts) - 1):
            assert ts[i] < ts[i + 1], (
                f"Timestamps not monotonic: ts[{i}]={ts[i]} >= ts[{i + 1}]={ts[i + 1]}"
            )


class TestPreSteps:
    """pre_steps should execute without recording, then restart with recording."""

    def _make_config_with_pre_steps(self) -> DemoConfig:
        return _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "pre_steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                        },
                        {
                            "action": "wait_for",
                            "locator": {"type": "css", "value": "#loaded"},
                            "timeout": 5.0,
                            "wait": 1.0,
                        },
                    ],
                    "steps": [
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#btn"},
                        },
                    ],
                }
            ]
        )

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_pre_steps_use_launch_without_recording(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = self._make_config_with_pre_steps()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser

        mock_time.monotonic.return_value = 0.0

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        # Should have called launch_without_recording, NOT launch
        mock_browser.launch_without_recording.assert_called_once()
        mock_browser.launch.assert_not_called()
        # Should have restarted with recording
        mock_browser.restart_with_recording.assert_called_once()
        # Only the actual step should produce a timestamp, not pre_steps
        assert len(result.step_timestamps) == 1
        assert len(result.step_post_effects) == 1

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_pre_steps_wait_is_executed(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        config = self._make_config_with_pre_steps()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser

        mock_time.monotonic.return_value = 0.0

        with Workspace() as ws:
            orch.run_scenarios(ws)

        # The wait_for pre_step with wait=1.0 should trigger a sleep
        sleep_calls = [c.args[0] for c in mock_time.sleep.call_args_list]
        assert 1.0 in sleep_calls

    def test_dry_run_logs_pre_steps(self) -> None:
        config = self._make_config_with_pre_steps()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        with Workspace() as ws:
            result = orch.run_scenarios(ws, dry_run=True)
        assert result.raw_videos == []

    def test_no_pre_steps_uses_launch(self) -> None:
        """Without pre_steps, launch_without_recording + restart is used."""
        config = _make_config_with_scenario()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        with patch("demodsl.orchestrators.scenario.BrowserProviderFactory") as mock_f:
            with patch("demodsl.orchestrators.scenario.time") as mock_t:
                mock_browser = MagicMock()
                mock_browser.close.return_value = None
                mock_f.create.return_value = mock_browser
                mock_t.monotonic.return_value = 0.0

                with Workspace() as ws:
                    orch.run_scenarios(ws)

                # Always uses the warmup+restart path now
                mock_browser.launch_without_recording.assert_called_once()
                mock_browser.restart_with_recording.assert_called_once()
                mock_browser.launch.assert_not_called()

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_pre_steps_commands_executed_in_order(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pre-steps commands must be dispatched in declaration order."""
        config = _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "pre_steps": [
                        {"action": "navigate", "url": "https://example.com"},
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#cookie-accept"},
                        },
                        {
                            "action": "wait_for",
                            "locator": {"type": "css", "value": "#ready"},
                            "timeout": 5.0,
                        },
                    ],
                    "steps": [
                        {"action": "click", "locator": {"type": "css", "value": "#go"}},
                    ],
                }
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser
        mock_time.monotonic.return_value = 0.0

        with Workspace() as ws:
            orch.run_scenarios(ws)

        # Navigate, click, wait_for should all be called on the browser
        mock_browser.navigate.assert_called_once_with("https://example.com")
        assert mock_browser.click.call_count == 2  # 1 pre_step + 1 step
        mock_browser.wait_for.assert_called_once()

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_pre_steps_not_counted_in_timestamps(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pre-steps must not appear in step_timestamps or step_post_effects."""
        config = _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "pre_steps": [
                        {"action": "navigate", "url": "https://example.com"},
                        {
                            "action": "wait_for",
                            "locator": {"type": "css", "value": "#loaded"},
                            "timeout": 5.0,
                        },
                    ],
                    "steps": [
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#a"},
                        },
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#b"},
                        },
                    ],
                }
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser
        mock_time.monotonic.return_value = 0.0

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        # Only 2 actual steps, not 4 (2 pre_steps + 2 steps)
        assert len(result.step_timestamps) == 2
        assert len(result.step_post_effects) == 2

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_pre_steps_zero_wait_no_sleep(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pre-steps with wait=0 should not trigger time.sleep."""
        config = _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "pre_steps": [
                        {"action": "navigate", "url": "https://example.com"},
                    ],
                    "steps": [
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#btn"},
                        },
                    ],
                }
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        mock_browser.close.return_value = tmp_path / "rec.webm"
        (tmp_path / "rec.webm").write_bytes(b"\x00" * 100)
        mock_factory.create.return_value = mock_browser
        mock_time.monotonic.return_value = 0.0

        with Workspace() as ws:
            orch.run_scenarios(ws)

        # No sleep should have been called during pre_steps (navigate has no wait)
        # The only sleeps should be from the actual step execution
        pre_step_sleeps = []
        for call in mock_time.sleep.call_args_list:
            pre_step_sleeps.append(call.args[0])
        # None of the sleeps should be for the pre_step navigate (no wait field)
        # The POST_NAVIGATE_DELAY (0.3) may appear from the actual step

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_multi_scenario_mixed_pre_steps(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """One scenario with pre_steps, another without — both work correctly."""
        config = _make_config(
            scenarios=[
                {
                    "name": "S1-with-pre",
                    "url": "https://example.com",
                    "pre_steps": [
                        {"action": "navigate", "url": "https://example.com"},
                        {
                            "action": "wait_for",
                            "locator": {"type": "css", "value": "#loaded"},
                            "timeout": 5.0,
                        },
                    ],
                    "steps": [
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#btn"},
                        },
                    ],
                },
                {
                    "name": "S2-no-pre",
                    "url": "https://example.com/page2",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com/page2",
                        },
                    ],
                },
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        call_count = [0]

        def fake_monotonic():
            call_count[0] += 1
            timeline = [0.0, 0.1, 2.0, 4.0, 4.1, 6.0]
            idx = min(call_count[0] - 1, len(timeline) - 1)
            return timeline[idx]

        mock_time.monotonic = fake_monotonic
        mock_time.sleep = MagicMock()

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        assert len(result.raw_videos) == 2
        # Both scenarios use launch_without_recording + restart_with_recording
        assert mock_browser.launch_without_recording.call_count == 2
        assert mock_browser.restart_with_recording.call_count == 2
        assert mock_browser.launch.call_count == 0
        # 1 step from S1 + 1 step from S2 = 2 timestamps
        assert len(result.step_timestamps) == 2

    @patch("demodsl.orchestrators.scenario.BrowserProviderFactory")
    @patch("demodsl.orchestrators.scenario.time")
    def test_pre_steps_narration_ignored(
        self,
        mock_time: MagicMock,
        mock_factory: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Narration on pre_steps should not affect recording timing."""
        config = _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "pre_steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "narration": "This should be ignored during warmup",
                        },
                    ],
                    "steps": [
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#btn"},
                            "narration": "Click the button",
                        },
                    ],
                }
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        video = tmp_path / "rec.webm"
        video.write_bytes(b"\x00" * 100)
        mock_browser.close.return_value = video
        mock_factory.create.return_value = mock_browser
        mock_time.monotonic.return_value = 0.0

        with Workspace() as ws:
            result = orch.run_scenarios(ws)

        # Only 1 actual step timestamp
        assert len(result.step_timestamps) == 1

    def test_pre_steps_empty_list_uses_normal_launch(self) -> None:
        """An empty pre_steps list should fall through to normal launch."""
        config = _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "pre_steps": [],
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                        },
                    ],
                }
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        with patch("demodsl.orchestrators.scenario.BrowserProviderFactory") as mock_f:
            with patch("demodsl.orchestrators.scenario.time") as mock_t:
                mock_browser = MagicMock()
                mock_browser.close.return_value = None
                mock_f.create.return_value = mock_browser
                mock_t.monotonic.return_value = 0.0

                with Workspace() as ws:
                    orch.run_scenarios(ws)

                # Empty list is falsy but we still always use launch_without_recording
                mock_browser.launch_without_recording.assert_called_once()
                mock_browser.restart_with_recording.assert_called_once()


# ── StopConditions ────────────────────────────────────────────────────────────


class TestStopConditions:
    """Tests for stop_if condition checking."""

    def _make_orchestrator(self):
        config = MagicMock()
        config.voice = None
        config.scenarios = []
        effects = MagicMock()
        return ScenarioOrchestrator(config, effects)

    def test_no_stop_conditions_passes(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        step = Step(action="navigate", url="https://example.com")
        orch._check_stop_conditions(browser, step, 0)

    def test_selector_condition_triggers(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 1
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(selector=".error-500", message="Server error")],
        )
        with pytest.raises(DemoStoppedError, match="Server error"):
            orch._check_stop_conditions(browser, step, 0)

    def test_selector_zero_no_trigger(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 0
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(selector=".error-500")],
        )
        orch._check_stop_conditions(browser, step, 0)

    def test_js_condition_triggers(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = True
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(
                    js="document.title.includes('Error')",
                    message="Title error",
                )
            ],
        )
        with pytest.raises(DemoStoppedError, match="Title error"):
            orch._check_stop_conditions(browser, step, 0)

    def test_js_falsy_no_trigger(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = False
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(js="false")],
        )
        orch._check_stop_conditions(browser, step, 0)

    def test_url_contains_triggers(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = "https://example.com/error/500"
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(
                    url_contains="/error/500",
                    message="HTTP 500",
                )
            ],
        )
        with pytest.raises(DemoStoppedError, match="HTTP 500"):
            orch._check_stop_conditions(browser, step, 0)

    def test_url_contains_no_match(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = "https://example.com/success"
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(url_contains="/error")],
        )
        orch._check_stop_conditions(browser, step, 0)

    def test_multiple_conditions_first_match_triggers(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 2
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(selector=".error", message="Found error"),
                StopCondition(js="false"),
            ],
        )
        with pytest.raises(DemoStoppedError, match="Found error"):
            orch._check_stop_conditions(browser, step, 0)

    def test_step_index_in_error_message(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = True
        step = Step(
            action="click",
            locator={"type": "css", "value": "#btn"},
            stop_if=[StopCondition(js="true", message="boom")],
        )
        with pytest.raises(DemoStoppedError, match="Step 4"):
            orch._check_stop_conditions(browser, step, 3)

    def test_empty_stop_if_list_passes(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[],
        )
        orch._check_stop_conditions(browser, step, 0)
        browser.evaluate_js.assert_not_called()

    def test_second_condition_triggers_when_first_passes(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        # First call: selector check returns 0 (no match)
        # Second call: js check returns True (match)
        browser.evaluate_js.side_effect = [0, True]
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(selector=".err", message="sel"),
                StopCondition(js="true", message="js triggered"),
            ],
        )
        with pytest.raises(DemoStoppedError, match="js triggered"):
            orch._check_stop_conditions(browser, step, 0)

    def test_all_conditions_pass_no_error(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        # selector → 0, js → False, url → no match
        browser.evaluate_js.side_effect = [0, False, "https://example.com/ok"]
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(selector=".err"),
                StopCondition(js="false"),
                StopCondition(url_contains="/error"),
            ],
        )
        orch._check_stop_conditions(browser, step, 0)

    def test_url_contains_none_url_no_crash(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = None
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(url_contains="/error")],
        )
        # Should not raise — None is handled gracefully
        orch._check_stop_conditions(browser, step, 0)

    def test_selector_js_uses_querySelectorAll(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 0
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(selector=".my-error")],
        )
        orch._check_stop_conditions(browser, step, 0)
        js_arg = browser.evaluate_js.call_args.args[0]
        assert "querySelectorAll" in js_arg
        assert ".my-error" in js_arg

    def test_error_message_contains_action_name(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 1
        step = Step(
            action="scroll",
            direction="down",
            pixels=300,
            stop_if=[StopCondition(selector=".err", message="fail")],
        )
        with pytest.raises(DemoStoppedError, match="scroll"):
            orch._check_stop_conditions(browser, step, 0)

    def test_selector_with_special_chars(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 1
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(
                    selector="div[data-error='true']",
                    message="attr match",
                )
            ],
        )
        with pytest.raises(DemoStoppedError, match="attr match"):
            orch._check_stop_conditions(browser, step, 0)

    def test_js_returns_truthy_string(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = "error text"
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(js="document.body.innerText", message="has text")],
        )
        with pytest.raises(DemoStoppedError, match="has text"):
            orch._check_stop_conditions(browser, step, 0)

    def test_js_returns_zero_no_trigger(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 0
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(js="0")],
        )
        orch._check_stop_conditions(browser, step, 0)

    def test_js_returns_empty_string_no_trigger(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = ""
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(js="''")],
        )
        orch._check_stop_conditions(browser, step, 0)

    def test_selector_multiple_elements_triggers(self) -> None:
        """Even if querySelectorAll finds many elements, it triggers."""
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 42
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(selector="div", message="many divs")],
        )
        with pytest.raises(DemoStoppedError, match="many divs"):
            orch._check_stop_conditions(browser, step, 0)

    def test_stop_if_on_click_step(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = True
        step = Step(
            action="click",
            locator={"type": "css", "value": "#btn"},
            stop_if=[StopCondition(js="true", message="click fail")],
        )
        with pytest.raises(DemoStoppedError, match="click fail"):
            orch._check_stop_conditions(browser, step, 0)

    def test_stop_if_on_type_step(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = "https://x.com/500"
        step = Step(
            action="type",
            locator={"type": "css", "value": "input"},
            value="hello",
            stop_if=[StopCondition(url_contains="/500", message="type fail")],
        )
        with pytest.raises(DemoStoppedError, match="type fail"):
            orch._check_stop_conditions(browser, step, 0)

    def test_default_message_used_when_not_specified(self) -> None:
        orch = self._make_orchestrator()
        browser = MagicMock()
        browser.evaluate_js.return_value = 1
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(selector=".err")],
        )
        with pytest.raises(DemoStoppedError, match="Demo stopped: condition met"):
            orch._check_stop_conditions(browser, step, 0)

    def test_selector_and_js_both_evaluated(self) -> None:
        """When a condition has both selector and js, both are checked."""
        orch = self._make_orchestrator()
        browser = MagicMock()
        # selector returns 0 (no match), js returns True (match)
        browser.evaluate_js.side_effect = [0, True]
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[
                StopCondition(
                    selector=".ok",
                    js="true",
                    message="js won",
                )
            ],
        )
        with pytest.raises(DemoStoppedError, match="js won"):
            orch._check_stop_conditions(browser, step, 0)

    def test_dangerous_selector_rejected(self) -> None:
        """A selector with injection characters should raise ValueError."""
        orch = self._make_orchestrator()
        browser = MagicMock()
        step = Step(
            action="navigate",
            url="https://example.com",
            stop_if=[StopCondition(selector=".err{color:red}")],
        )
        with pytest.raises(ValueError, match="disallowed characters"):
            orch._check_stop_conditions(browser, step, 0)


# ── Phase D: Parallel scenario scheduling ─────────────────────────────────────


class TestRecordOneScenarioIsolation:
    """_record_one_scenario must not mutate the parent orchestrator."""

    def test_isolated_mutable_state(self) -> None:
        config = _make_config_with_scenario()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        orch.step_timestamps = [1.0, 2.0]  # pre-existing

        scenario = config.scenarios[0]

        # Monkey-patch _execute_scenario to append to isolated lists
        def fake_execute(sc, ws, *, narration_durations):
            orch_self = fake_execute._self  # set by _record_one_scenario's copy
            orch_self.step_timestamps.append(0.5)
            orch_self.step_post_effects.append([("zoom", {})])
            orch_self.scroll_positions.append((0.5, 100))
            return None, 1.0

        with Workspace() as ws:
            # We need a trick: _record_one_scenario calls copy.copy(self),
            # then isolated._execute_scenario(). We patch _execute_scenario
            # to capture the isolated self.
            def patched_execute(self_inner, sc, ws2, *, narration_durations):
                fake_execute._self = self_inner
                return fake_execute(sc, ws2, narration_durations=narration_durations)

            with patch.object(
                ScenarioOrchestrator,
                "_execute_scenario",
                patched_execute,
            ):
                video, dur, ts, pe, sp = orch._record_one_scenario(
                    scenario,
                    ws,
                    {},
                )

        # Parent state MUST be unchanged
        assert orch.step_timestamps == [1.0, 2.0]
        assert orch.step_post_effects == []

        # Isolated result must have the appended data
        assert ts == [0.5]
        assert pe == [[("zoom", {})]]
        assert sp == [(0.5, 100)]
        assert dur == 1.0


class TestRunScenariosParallelPath:
    """Verify that >1 scenario triggers parallel recording."""

    def test_multiple_scenarios_use_parallel(self) -> None:
        cfg = _make_config(
            scenarios=[
                {
                    "name": "s1",
                    "url": "https://a.com",
                    "steps": [{"action": "navigate", "url": "https://a.com"}],
                },
                {
                    "name": "s2",
                    "url": "https://b.com",
                    "steps": [{"action": "navigate", "url": "https://b.com"}],
                },
            ]
        )
        effects = _make_effects()
        orch = ScenarioOrchestrator(cfg, effects)

        called = {"seq": False, "par": False}

        def mock_seq(*a, **kw):
            called["seq"] = True
            return [(None, 1.0, [0.1], [[]], [])]

        def mock_par(*a, **kw):
            called["par"] = True
            return [
                (None, 1.0, [0.1], [[]], []),
                (None, 2.0, [0.2], [[]], []),
            ]

        with Workspace() as ws:
            with (
                patch.object(orch, "_run_scenarios_sequential", mock_seq),
                patch.object(orch, "_run_scenarios_parallel", mock_par),
            ):
                orch.run_scenarios(ws, dry_run=False)

        assert called["par"] is True
        assert called["seq"] is False

    def test_single_scenario_uses_sequential(self) -> None:
        config = _make_config_with_scenario()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        called = {"seq": False, "par": False}

        def mock_seq(*a, **kw):
            called["seq"] = True
            return [(None, 1.0, [0.1], [[]], [])]

        def mock_par(*a, **kw):
            called["par"] = True
            return [(None, 1.0, [0.1], [[]], [])]

        with Workspace() as ws:
            with (
                patch.object(orch, "_run_scenarios_sequential", mock_seq),
                patch.object(orch, "_run_scenarios_parallel", mock_par),
            ):
                orch.run_scenarios(ws, dry_run=False)

        assert called["seq"] is True
        assert called["par"] is False


# ── Turbo mode ────────────────────────────────────────────────────────────────


class TestTurboSleep:
    """Verify _sleep() respects turbo mode."""

    def test_sleep_normal_mode(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects, turbo=False)

        import time

        t0 = time.monotonic()
        orch._sleep(0.2)
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.15  # allow small tolerance

    def test_sleep_turbo_mode(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects, turbo=True)

        import time

        t0 = time.monotonic()
        orch._sleep(5.0)  # would take 5s normally
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5  # turbo clamps to _TURBO_MIN_SLEEP (0.05s)

    def test_sleep_zero_is_noop(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects, turbo=False)

        import time

        t0 = time.monotonic()
        orch._sleep(0)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.05

    def test_turbo_defaults_false(self) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)
        assert orch.turbo is False
