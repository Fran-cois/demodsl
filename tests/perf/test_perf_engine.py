"""Performance tests for engine initialisation and orchestrator operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig
from demodsl.orchestrators.narration import NarrationOrchestrator
from demodsl.orchestrators.scenario import ScenarioOrchestrator

ITERATIONS = 100


def _config_dict() -> dict[str, Any]:
    return {
        "metadata": {"title": "Perf Engine", "version": "1"},
        "voice": {"engine": "elevenlabs", "voice_id": "josh"},
        "scenarios": [
            {
                "name": "s1",
                "url": "https://example.com",
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Let's go",
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#btn"},
                        "narration": "Clicking the button",
                    },
                    {"action": "scroll", "direction": "down", "pixels": 300},
                    {"action": "screenshot", "filename": "shot.png"},
                ],
            }
        ],
    }


# ── Engine init ───────────────────────────────────────────────────────────────


@pytest.mark.perf
class TestEngineInitPerf:
    def test_engine_init(self, perf_timer, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        data = _config_dict()
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(data))

        result, timer = perf_timer("engine_init", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                DemoEngine(cfg_path, dry_run=True)
        assert result.mean_ms < 200

    def test_engine_validate(self, perf_timer, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        data = _config_dict()
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(data))
        engine = DemoEngine(cfg_path, dry_run=True)

        result, timer = perf_timer("engine_validate", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                engine.validate()
        assert result.mean_ms < 10


# ── Narration orchestrator ────────────────────────────────────────────────────


@pytest.mark.perf
class TestNarrationOrchestratorPerf:
    def test_build_narration_texts(self, perf_timer) -> None:
        cfg = DemoConfig(**_config_dict())
        orch = NarrationOrchestrator(cfg)
        result, timer = perf_timer("build_narration_texts", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                orch.build_narration_texts()
        assert result.mean_ms < 10

    def test_dry_run_narrations(self, perf_timer) -> None:
        cfg = DemoConfig(**_config_dict())
        orch = NarrationOrchestrator(cfg)
        ws = MagicMock()
        ws.root = Path("/tmp/ws")
        result, timer = perf_timer("dry_run_narrations", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                orch.generate_narrations(ws, dry_run=True)
        assert result.mean_ms < 10

    def test_measure_durations_empty(self, perf_timer) -> None:
        cfg = DemoConfig(**_config_dict())
        orch = NarrationOrchestrator(cfg)
        result, timer = perf_timer("measure_durations_empty", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                orch.measure_narration_durations({})
        assert result.mean_ms < 5


# ── Scenario orchestrator ────────────────────────────────────────────────────


@pytest.mark.perf
class TestScenarioOrchestratorPerf:
    def test_init(self, perf_timer) -> None:
        cfg = DemoConfig(**_config_dict())
        effects = EffectRegistry()
        result, timer = perf_timer("scenario_orch_init", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                ScenarioOrchestrator(cfg, effects)
        assert result.mean_ms < 10

    def test_dry_run(self, perf_timer) -> None:
        cfg = DemoConfig(**_config_dict())
        effects = EffectRegistry()
        orch = ScenarioOrchestrator(cfg, effects)
        ws = MagicMock()
        ws.root = Path("/tmp/ws")
        result, timer = perf_timer("scenario_dry_run", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                orch.run_scenarios(ws, narration_durations={}, dry_run=True)
        assert result.mean_ms < 20

    def test_collect_post_effects(self, perf_timer) -> None:
        from demodsl.effects.browser_effects import register_all_browser_effects
        from demodsl.effects.post_effects import register_all_post_effects
        from demodsl.models import Effect

        cfg = DemoConfig(**_config_dict())
        effects = EffectRegistry()
        register_all_browser_effects(effects)
        register_all_post_effects(effects)
        orch = ScenarioOrchestrator(cfg, effects)
        effect_list = [
            Effect(type="spotlight", intensity=0.8),
            Effect(type="vignette", intensity=0.5),
        ]
        result, timer = perf_timer("collect_post_effects", ITERATIONS)
        for _ in range(ITERATIONS):
            orch.step_post_effects = []
            with timer:
                orch._collect_post_effects(effect_list)
        assert result.mean_ms < 10
