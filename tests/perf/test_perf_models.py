"""Performance tests for model parsing, effect registry, and pipeline stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig, Effect, Locator, Step

ITERATIONS = 200


def _minimal_dict() -> dict[str, Any]:
    return {
        "metadata": {"title": "Perf Test", "version": "1.0"},
        "scenarios": [
            {
                "name": "s1",
                "url": "https://example.com",
                "steps": [{"action": "navigate", "url": "https://example.com"}],
            }
        ],
    }


def _full_step_dict() -> dict[str, Any]:
    return {
        "metadata": {"title": "Full", "version": "1"},
        "voice": {"engine": "elevenlabs", "voice_id": "josh"},
        "scenarios": [
            {
                "name": "Demo",
                "url": "https://example.com",
                "viewport": {"width": 1920, "height": 1080},
                "cursor": {"visible": True, "style": "pointer", "color": "#ff0000"},
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Opening the site",
                        "wait": 2.0,
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#btn"},
                        "effects": [{"type": "spotlight", "duration": 0.5, "intensity": 0.8}],
                    },
                    {
                        "action": "type",
                        "locator": {"type": "id", "value": "search"},
                        "value": "hello",
                    },
                    {"action": "scroll", "direction": "down", "pixels": 300},
                    {
                        "action": "wait_for",
                        "locator": {"type": "xpath", "value": "//div"},
                        "timeout": 5.0,
                    },
                    {"action": "screenshot", "filename": "final.png"},
                ],
            }
        ],
    }


# ── Model parsing ─────────────────────────────────────────────────────────────


@pytest.mark.perf
class TestModelParsingPerf:
    def test_minimal_config_parsing(self, perf_timer) -> None:
        result, timer = perf_timer("parse_minimal_config", ITERATIONS)
        data = _minimal_dict()
        for _ in range(ITERATIONS):
            with timer:
                DemoConfig(**data)
        assert result.mean_ms < 50

    def test_full_config_parsing(self, perf_timer) -> None:
        result, timer = perf_timer("parse_full_config", ITERATIONS)
        data = _full_step_dict()
        for _ in range(ITERATIONS):
            with timer:
                DemoConfig(**data)
        assert result.mean_ms < 100

    def test_step_parsing_navigate(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_navigate", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                Step(action="navigate", url="https://example.com")
        assert result.mean_ms < 10

    def test_step_parsing_click(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_click", ITERATIONS)
        loc = {"type": "css", "value": "#btn"}
        for _ in range(ITERATIONS):
            with timer:
                Step(action="click", locator=loc)
        assert result.mean_ms < 10

    def test_step_parsing_type(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_type", ITERATIONS)
        loc = {"type": "id", "value": "input"}
        for _ in range(ITERATIONS):
            with timer:
                Step(action="type", locator=loc, value="text")
        assert result.mean_ms < 10

    def test_step_parsing_scroll(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_scroll", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                Step(action="scroll", direction="down", pixels=300)
        assert result.mean_ms < 10

    def test_step_parsing_wait_for(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_wait_for", ITERATIONS)
        loc = {"type": "xpath", "value": "//div"}
        for _ in range(ITERATIONS):
            with timer:
                Step(action="wait_for", locator=loc, timeout=5.0)
        assert result.mean_ms < 10

    def test_step_parsing_screenshot(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_screenshot", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                Step(action="screenshot", filename="shot.png")
        assert result.mean_ms < 10

    def test_step_with_effects(self, perf_timer) -> None:
        result, timer = perf_timer("parse_step_with_effects", ITERATIONS)
        loc = {"type": "css", "value": "#el"}
        effects = [
            {"type": "spotlight", "intensity": 0.8},
            {"type": "confetti"},
            {"type": "glow", "color": "#ff0000"},
        ]
        for _ in range(ITERATIONS):
            with timer:
                Step(action="click", locator=loc, effects=effects)
        assert result.mean_ms < 50

    def test_effect_parsing(self, perf_timer) -> None:
        result, timer = perf_timer("parse_effect", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                Effect(type="spotlight", duration=0.5, intensity=0.9)
        assert result.mean_ms < 10

    def test_locator_parsing(self, perf_timer) -> None:
        result, timer = perf_timer("parse_locator", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                Locator(type="css", value="#main .header > a.link")
        assert result.mean_ms < 10


# ── Config loading from YAML ──────────────────────────────────────────────────


@pytest.mark.perf
class TestConfigLoadPerf:
    def test_yaml_load_and_parse(self, perf_timer, tmp_path: Path) -> None:
        data = _full_step_dict()
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml.dump(data))
        iterations = 100
        result, timer = perf_timer("yaml_load_and_parse", iterations)

        from demodsl.config_loader import load_config

        for _ in range(iterations):
            with timer:
                raw = load_config(yaml_path)
                DemoConfig(**raw)
        assert result.mean_ms < 200


# ── Effect registry ───────────────────────────────────────────────────────────


@pytest.mark.perf
class TestEffectRegistryPerf:
    def test_registry_init_and_register(self, perf_timer) -> None:
        from demodsl.effects.browser_effects import register_all_browser_effects
        from demodsl.effects.post_effects import register_all_post_effects

        result, timer = perf_timer("registry_init_register", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                reg = EffectRegistry()
                register_all_browser_effects(reg)
                register_all_post_effects(reg)
        assert result.mean_ms < 100

    def test_registry_lookup_browser(self, perf_timer) -> None:
        from demodsl.effects.browser_effects import register_all_browser_effects

        reg = EffectRegistry()
        register_all_browser_effects(reg)
        names = reg.browser_effects
        result, timer = perf_timer("registry_lookup_browser", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                for name in names:
                    reg.get_browser_effect(name)
        assert result.mean_ms < 10

    def test_registry_lookup_post(self, perf_timer) -> None:
        from demodsl.effects.post_effects import register_all_post_effects

        reg = EffectRegistry()
        register_all_post_effects(reg)
        names = reg.post_effects
        result, timer = perf_timer("registry_lookup_post", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                for name in names:
                    reg.get_post_effect(name)
        assert result.mean_ms < 10


# ── Pipeline chain ────────────────────────────────────────────────────────────


@pytest.mark.perf
class TestPipelinePerf:
    def test_build_chain(self, perf_timer) -> None:
        from demodsl.pipeline.stages import build_chain

        pipeline_dicts = [
            {"stage_type": "restore_audio", "params": {"denoise": True}},
            {"stage_type": "restore_video", "params": {"stabilize": True}},
            {"stage_type": "apply_effects", "params": {}},
            {"stage_type": "generate_narration", "params": {}},
            {"stage_type": "edit_video", "params": {}},
            {"stage_type": "mix_audio", "params": {}},
            {"stage_type": "optimize", "params": {"format": "mp4"}},
        ]
        result, timer = perf_timer("build_pipeline_chain", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                build_chain(pipeline_dicts)
        assert result.mean_ms < 50
