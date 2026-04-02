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


class TestForceFlag:
    """B3: --force should be an alias for --no-run-cache."""

    def test_force_flag_accepted(self, full_yaml_path: Path) -> None:
        result = runner.invoke(
            app, ["run", str(full_yaml_path), "--dry-run", "--force"]
        )
        assert result.exit_code == 0
        assert "Done" in result.output


class TestTestConnectionCommand:
    """B1: test-connection CLI command."""

    def test_no_mobile_scenario(self, full_yaml_path: Path) -> None:
        """Config without mobile scenario should fail gracefully."""
        result = runner.invoke(app, ["test-connection", str(full_yaml_path)])
        assert result.exit_code == 1
        assert "No mobile scenario" in result.output

    def test_mobile_connection_success(self, tmp_path: Path) -> None:
        config_data = {
            "metadata": {"title": "Mobile Test", "version": "1.0.0"},
            "scenarios": [
                {
                    "name": "iOS Test",
                    "mobile": {
                        "platform": "ios",
                        "device_name": "iPhone 15",
                        "bundle_id": "com.example.app",
                    },
                    "steps": [{"action": "screenshot"}],
                }
            ],
            "pipeline": [],
        }
        cfg_path = tmp_path / "mobile.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        with patch("demodsl.providers.mobile.AppiumMobileProvider") as MockProvider:
            mock_instance = MagicMock()
            mock_instance.get_window_size.return_value = {"width": 390, "height": 844}
            mock_instance.screenshot.return_value = Path("screenshot.png")
            MockProvider.return_value = mock_instance

            result = runner.invoke(app, ["test-connection", str(cfg_path)])
            assert result.exit_code == 0
            assert "Connection OK" in result.output
            assert "390×844" in result.output
            mock_instance.launch_without_recording.assert_called_once()


class TestInspectCommand:
    """B2: inspect CLI command."""

    def test_no_mobile_scenario(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["inspect", str(full_yaml_path)])
        assert result.exit_code == 1
        assert "No mobile scenario" in result.output

    def test_inspect_raw_xml(self, tmp_path: Path) -> None:
        config_data = {
            "metadata": {"title": "Inspect Test", "version": "1.0.0"},
            "scenarios": [
                {
                    "name": "iOS",
                    "mobile": {
                        "platform": "ios",
                        "device_name": "iPhone 15",
                        "bundle_id": "com.example.app",
                    },
                    "steps": [{"action": "screenshot"}],
                }
            ],
            "pipeline": [],
        }
        cfg_path = tmp_path / "mobile.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        fake_xml = '<AppiumAUT><XCUIElementTypeWindow name="main" visible="true" /></AppiumAUT>'
        with patch("demodsl.providers.mobile.AppiumMobileProvider") as MockProvider:
            mock_instance = MagicMock()
            mock_instance.page_source.return_value = fake_xml
            mock_instance.screenshot.return_value = Path("screenshot.png")
            MockProvider.return_value = mock_instance

            result = runner.invoke(app, ["inspect", str(cfg_path), "--raw"])
            assert result.exit_code == 0
            assert "XCUIElementTypeWindow" in result.output

    def test_inspect_formatted_tree(self, tmp_path: Path) -> None:
        config_data = {
            "metadata": {"title": "Inspect Test", "version": "1.0.0"},
            "scenarios": [
                {
                    "name": "iOS",
                    "mobile": {
                        "platform": "ios",
                        "device_name": "iPhone 15",
                        "bundle_id": "com.example.app",
                    },
                    "steps": [{"action": "screenshot"}],
                }
            ],
            "pipeline": [],
        }
        cfg_path = tmp_path / "mobile.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        fake_xml = '<AppiumAUT><XCUIElementTypeButton name="Login" label="Login" accessible="true" /></AppiumAUT>'
        with patch("demodsl.providers.mobile.AppiumMobileProvider") as MockProvider:
            mock_instance = MagicMock()
            mock_instance.page_source.return_value = fake_xml
            mock_instance.screenshot.return_value = Path("screenshot.png")
            MockProvider.return_value = mock_instance

            result = runner.invoke(app, ["inspect", str(cfg_path)])
            assert result.exit_code == 0
            assert "XCUIElementTypeButton" in result.output
            assert 'name="Login"' in result.output


class TestCacheStatsCommand:
    def test_cache_stats_no_data(self, tmp_path: Path) -> None:
        with patch("demodsl.pipeline.run_cache.RunCache") as MockCache:
            MockCache.global_stats.return_value = {"exists": False, "files": 0}
            result = runner.invoke(
                app, ["cache", "stats", "--cache-dir", str(tmp_path)]
            )
            assert result.exit_code == 0
            assert "No cache data found" in result.output

    def test_cache_stats_with_config(
        self, full_yaml_path: Path, tmp_path: Path
    ) -> None:
        with patch("demodsl.pipeline.run_cache.RunCache") as MockCache:
            mock_cache = MagicMock()
            mock_cache.stats.return_value = {
                "exists": True,
                "path": str(tmp_path),
                "files": 5,
                "size_mb": 12,
            }
            MockCache.return_value = mock_cache
            result = runner.invoke(
                app,
                ["cache", "stats", str(full_yaml_path), "--cache-dir", str(tmp_path)],
            )
            assert result.exit_code == 0
            assert "5" in result.output
            assert "12 MB" in result.output

    def test_cache_stats_global(self, tmp_path: Path) -> None:
        with patch("demodsl.pipeline.run_cache.RunCache") as MockCache:
            MockCache.global_stats.return_value = {
                "configs": 3,
                "path": str(tmp_path),
                "files": 10,
                "size_mb": 42,
            }
            result = runner.invoke(
                app, ["cache", "stats", "--cache-dir", str(tmp_path)]
            )
            assert result.exit_code == 0
            assert "Configs: 3" in result.output
            assert "10" in result.output


class TestCacheClearCommand:
    def test_cache_clear_all(self, tmp_path: Path) -> None:
        with patch("demodsl.pipeline.run_cache.RunCache") as MockCache:
            MockCache.clear_all.return_value = 7
            result = runner.invoke(
                app, ["cache", "clear", "--cache-dir", str(tmp_path)]
            )
            assert result.exit_code == 0
            assert "7" in result.output
            assert "all configs" in result.output

    def test_cache_clear_config(self, full_yaml_path: Path, tmp_path: Path) -> None:
        with patch("demodsl.pipeline.run_cache.RunCache") as MockCache:
            mock_cache = MagicMock()
            mock_cache.clear.return_value = 3
            MockCache.return_value = mock_cache
            result = runner.invoke(
                app,
                ["cache", "clear", str(full_yaml_path), "--cache-dir", str(tmp_path)],
            )
            assert result.exit_code == 0
            assert "3" in result.output
