"""Tests for demodsl.orchestrators.scenario — ScenarioOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demodsl.effects.cursor import CursorOverlay
from demodsl.effects.glow_select import GlowSelectOverlay
from demodsl.effects.popup_card import PopupCardOverlay
from demodsl.effects.registry import EffectRegistry
from demodsl.effects.browser_effects import register_all_browser_effects
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.models import DemoConfig, Effect, Step, Locator, CardContent
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
    @patch("demodsl.orchestrators.scenario.time")
    def test_applies_browser_effect(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        from demodsl.models import Effect

        orch._apply_browser_effects(
            mock_browser, [Effect(type="spotlight", duration=0.5)]
        )
        mock_browser.evaluate_js.assert_called()
        mock_time.sleep.assert_called_with(0.5)

    @patch("demodsl.orchestrators.scenario.time")
    def test_no_sleep_without_duration(self, mock_time: MagicMock) -> None:
        config = _make_config()
        effects = _make_effects()
        orch = ScenarioOrchestrator(config, effects)

        mock_browser = MagicMock()
        orch._apply_browser_effects(mock_browser, [Effect(type="spotlight")])
        mock_browser.evaluate_js.assert_called()
        mock_time.sleep.assert_not_called()


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
