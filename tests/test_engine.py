"""Tests for demodsl.engine — DemoEngine orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from demodsl.engine import DemoEngine


class TestDemoEngineInit:
    def test_from_yaml(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True)
        assert engine.config.metadata.title == "Test Demo"

    def test_from_json(self, sample_json_path: Path) -> None:
        engine = DemoEngine(config_path=sample_json_path, dry_run=True)
        assert engine.config.metadata.title == "Test Demo"

    def test_from_full_yaml(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        assert engine.config.metadata.title == "Full Demo"
        assert len(engine.config.scenarios) == 1
        assert len(engine.config.pipeline) == 8

    def test_from_full_json(self, full_json_path: Path) -> None:
        engine = DemoEngine(config_path=full_json_path, dry_run=True)
        assert engine.config.metadata.title == "Full Demo"

    def test_effects_registry_populated(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True)
        assert len(engine._effects.browser_effects) == 23
        assert len(engine._effects.post_effects) == 20

    def test_invalid_config_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("scenarios: []\n")
        with pytest.raises(Exception):
            DemoEngine(config_path=bad)


class TestValidate:
    def test_validate_returns_config(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True)
        cfg = engine.validate()
        assert cfg.metadata.title == "Test Demo"

    def test_validate_full(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        cfg = engine.validate()
        assert len(cfg.scenarios) == 1
        assert len(cfg.scenarios[0].steps) == 6


class TestDryRun:
    def test_dry_run_scenarios_returns_empty(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        result = engine._dry_run_scenarios()
        assert result == []

    def test_dry_run_narrations_returns_empty(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        result = engine._dry_run_narrations()
        assert result == {}

    def test_run_dry_returns_none(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        result = engine.run()
        assert result is None

    @pytest.mark.skip(reason="not ready — requires Playwright + FFmpeg")
    def test_run_real(self) -> None:
        pass


class TestOutputDir:
    def test_default_from_config(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        assert engine._output_dir == Path("output/")

    def test_override_output_dir(self, full_yaml_path: Path, tmp_path: Path) -> None:
        custom = tmp_path / "my_output"
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, output_dir=custom)
        assert engine._output_dir == custom

    def test_default_fallback(self, sample_yaml_path: Path) -> None:
        # Minimal config without output section → falls back to "output"
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True)
        assert str(engine._output_dir) == "output"
