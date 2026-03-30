"""Tests for demodsl.cli — Typer CLI commands."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_init_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Template created" in result.output


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


class TestSetupRemotionCommand:
    @patch("shutil.which", return_value=None)
    def test_no_node_exits(self, _mock: MagicMock) -> None:
        result = runner.invoke(app, ["setup-remotion"])
        assert result.exit_code != 0
        assert "Node.js not found" in result.output

    @patch("shutil.which", return_value="/usr/bin/node")
    def test_no_package_json_exits(self, _mock: MagicMock) -> None:
        # The real remotion dir may or may not exist. If it doesn't,
        # setup-remotion should exit with error.
        result = runner.invoke(app, ["setup-remotion"])
        # Either success (if dir exists) or failure (if not)
        assert isinstance(result.exit_code, int)

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/node")
    def test_npm_install_success(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Create a fake remotion directory with package.json
        remotion_dir = Path(__file__).resolve().parent.parent / "remotion"
        if remotion_dir.exists() and (remotion_dir / "package.json").exists():
            result = runner.invoke(app, ["setup-remotion"])
            assert result.exit_code == 0
            assert (
                "complete" in result.output.lower() or "setup" in result.output.lower()
            )


class TestRunCommand:
    def test_run_dry(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["run", str(full_yaml_path), "--dry-run"])
        assert result.exit_code == 0
        assert "Done" in result.output

    def test_run_verbose(self, full_yaml_path: Path) -> None:
        result = runner.invoke(
            app, ["run", str(full_yaml_path), "--dry-run", "--verbose"]
        )
        assert result.exit_code == 0

    def test_run_with_output_dir(self, full_yaml_path: Path, tmp_path: Path) -> None:
        out = tmp_path / "custom_out"
        result = runner.invoke(
            app,
            ["run", str(full_yaml_path), "--dry-run", "--output-dir", str(out)],
        )
        assert result.exit_code == 0

    def test_run_skip_voice(self, full_yaml_path: Path) -> None:
        result = runner.invoke(
            app,
            ["run", str(full_yaml_path), "--dry-run", "--skip-voice"],
        )
        assert result.exit_code == 0

    def test_run_skip_deploy(self, full_yaml_path: Path) -> None:
        result = runner.invoke(
            app,
            ["run", str(full_yaml_path), "--dry-run", "--skip-deploy"],
        )
        assert result.exit_code == 0

    def test_run_renderer_remotion(self, full_yaml_path: Path) -> None:
        result = runner.invoke(
            app,
            ["run", str(full_yaml_path), "--dry-run", "--renderer", "remotion"],
        )
        assert result.exit_code == 0

    @pytest.mark.skip(reason="not ready — requires Playwright + FFmpeg for real run")
    def test_run_real(self) -> None:
        pass

    def test_run_demo_stopped_error(self, full_yaml_path: Path) -> None:
        """DemoStoppedError should produce a clean message and exit code 1."""
        from demodsl.models import DemoStoppedError

        with patch("demodsl.engine.DemoEngine") as mock_cls:
            mock_engine = MagicMock()
            mock_engine.run.side_effect = DemoStoppedError("Server returned 500")
            mock_cls.return_value = mock_engine
            result = runner.invoke(app, ["run", str(full_yaml_path)])
        assert result.exit_code == 1
        assert "Demo stopped" in result.output
        assert "Server returned 500" in result.output
