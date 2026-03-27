"""Tests for demodsl.cli — Typer CLI commands."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from demodsl.cli import _setup_logging, app

runner = CliRunner()


class TestValidateCommand:
    def test_valid_yaml(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["validate", str(full_yaml_path)])
        assert result.exit_code == 0
        assert "Valid ✓" in result.output

    def test_valid_json(self, full_json_path: Path) -> None:
        result = runner.invoke(app, ["validate", str(full_json_path)])
        assert result.exit_code == 0
        assert "Valid ✓" in result.output

    def test_invalid_config(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("scenarios: []\n")
        result = runner.invoke(app, ["validate", str(bad)])
        assert result.exit_code != 0

    def test_output_includes_counts(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["validate", str(full_yaml_path)])
        assert "Scenarios:" in result.output
        assert "Steps:" in result.output
        assert "Pipeline:" in result.output


class TestInitCommand:
    def test_init_yaml(self, tmp_path: Path) -> None:
        out = tmp_path / "new_demo.yaml"
        result = runner.invoke(app, ["init", "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        data = yaml.safe_load(out.read_text())
        assert data["metadata"]["title"] == "My Product Demo"

    def test_init_json(self, tmp_path: Path) -> None:
        out = tmp_path / "new_demo.json"
        result = runner.invoke(app, ["init", "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["metadata"]["title"] == "My Product Demo"

    def test_init_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Template created" in result.output


class TestRunCommand:
    def test_run_dry(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["run", str(full_yaml_path), "--dry-run"])
        assert result.exit_code == 0
        assert "Done" in result.output

    def test_run_verbose(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["run", str(full_yaml_path), "--dry-run", "--verbose"])
        assert result.exit_code == 0

    @pytest.mark.skip(reason="not ready — requires Playwright + FFmpeg for real run")
    def test_run_real(self) -> None:
        pass


class TestSetupLogging:
    def test_verbose_sets_debug(self) -> None:
        root = logging.getLogger()
        old_level = root.level
        old_handlers = root.handlers[:]
        root.handlers.clear()
        try:
            _setup_logging(verbose=True)
            assert root.level == logging.DEBUG
        finally:
            root.setLevel(old_level)
            root.handlers = old_handlers

    def test_non_verbose_sets_info(self) -> None:
        root = logging.getLogger()
        old_level = root.level
        old_handlers = root.handlers[:]
        root.handlers.clear()
        try:
            _setup_logging(verbose=False)
            assert root.level == logging.INFO
        finally:
            root.setLevel(old_level)
            root.handlers = old_handlers
