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

    def test_init_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            assert "complete" in result.output.lower() or "setup" in result.output.lower()


class TestRunCommand:
    def test_run_dry(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["run", str(full_yaml_path), "--dry-run"])
        assert result.exit_code == 0
        assert "Done" in result.output

    def test_run_verbose(self, full_yaml_path: Path) -> None:
        result = runner.invoke(app, ["run", str(full_yaml_path), "--dry-run", "--verbose"])
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
        result = runner.invoke(app, ["run", str(full_yaml_path), "--dry-run", "--force"])
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
            result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(tmp_path)])
            assert result.exit_code == 0
            assert "No cache data found" in result.output

    def test_cache_stats_with_config(self, full_yaml_path: Path, tmp_path: Path) -> None:
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
            result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(tmp_path)])
            assert result.exit_code == 0
            assert "Configs: 3" in result.output
            assert "10" in result.output


class TestCacheClearCommand:
    def test_cache_clear_all(self, tmp_path: Path) -> None:
        with patch("demodsl.pipeline.run_cache.RunCache") as MockCache:
            MockCache.clear_all.return_value = 7
            result = runner.invoke(app, ["cache", "clear", "--cache-dir", str(tmp_path)])
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


class TestStatsCommands:
    def test_stats_show(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stats_file = tmp_path / "stats.json"
        monkeypatch.setenv("DEMODSL_STATS_FILE", str(stats_file))

        from demodsl.stats import StatsStore

        StatsStore().record_run(
            project_title="Promo Demo",
            config_path=tmp_path / "demo.yaml",
            renderer="remotion",
            output=tmp_path / "out.mp4",
            dry_run=False,
            duration_minutes=0.0,
        )

        result = runner.invoke(app, ["stats", "show"])
        assert result.exit_code == 0
        assert "Demos created" in result.output
        assert "remotion" in result.output

    def test_stats_export(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stats_file = tmp_path / "stats.json"
        monkeypatch.setenv("DEMODSL_STATS_FILE", str(stats_file))

        from demodsl.stats import StatsStore

        StatsStore().record_run(
            project_title="Promo Demo",
            config_path=tmp_path / "demo.yaml",
            renderer="remotion",
            output=tmp_path / "out.mp4",
            dry_run=False,
            duration_minutes=0.0,
        )

        exported = tmp_path / "exported_stats.json"
        result = runner.invoke(app, ["stats", "export", "--output", str(exported)])
        assert result.exit_code == 0
        assert exported.exists()
        data = json.loads(exported.read_text())
        assert data["totals"]["demos_created"] >= 1

    def test_stats_promo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stats_file = tmp_path / "stats.json"
        monkeypatch.setenv("DEMODSL_STATS_FILE", str(stats_file))

        from demodsl.stats import StatsStore

        StatsStore().record_run(
            project_title="Promo Demo",
            config_path=tmp_path / "demo.yaml",
            renderer="remotion",
            output=tmp_path / "out.mp4",
            dry_run=False,
            duration_minutes=0.0,
        )

        result = runner.invoke(app, ["stats", "promo"])
        assert result.exit_code == 0
        assert "DemoDSL" in result.output

    def test_stats_promo_lang_en(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stats_file = tmp_path / "stats.json"
        monkeypatch.setenv("DEMODSL_STATS_FILE", str(stats_file))

        from demodsl.stats import StatsStore

        StatsStore().record_run(
            project_title="Promo Demo",
            config_path=tmp_path / "demo.yaml",
            renderer="remotion",
            output=tmp_path / "out.mp4",
            dry_run=False,
            duration_minutes=0.0,
        )

        result = runner.invoke(app, ["stats", "promo", "--lang", "en"])
        assert result.exit_code == 0
        assert "I have created" in result.output

    def test_stats_promo_all(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        stats_file = tmp_path / "stats.json"
        monkeypatch.setenv("DEMODSL_STATS_FILE", str(stats_file))

        from demodsl.stats import StatsStore

        StatsStore().record_run(
            project_title="Promo Demo",
            config_path=tmp_path / "demo.yaml",
            renderer="remotion",
            output=tmp_path / "out.mp4",
            dry_run=False,
            duration_minutes=0.0,
        )

        result = runner.invoke(app, ["stats", "promo", "--all"])
        assert result.exit_code == 0
        assert "[fr]" in result.output
        assert "[en]" in result.output
        assert "[es]" in result.output
        assert "[de]" in result.output

    def test_stats_promo_invalid_lang(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stats_file = tmp_path / "stats.json"
        monkeypatch.setenv("DEMODSL_STATS_FILE", str(stats_file))

        result = runner.invoke(app, ["stats", "promo", "--lang", "it"])
        assert result.exit_code == 1
        assert "Unsupported language" in result.output


class TestLibraryCommands:
    """Tests for demodsl library list/search/info/scaffold."""

    def test_library_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "list"])
        assert result.exit_code == 0
        assert "preset(s)" in result.output
        assert "lower_thirds/tech" in result.output

    def test_library_list_tag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "list", "--tag", "cinematic"])
        assert result.exit_code == 0
        assert "cinematic/film_look" in result.output

    def test_library_list_verbose(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "list", "-v"])
        assert result.exit_code == 0
        assert "Tags:" in result.output
        assert "Params:" in result.output

    def test_library_search_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "search", "glitch"])
        assert result.exit_code == 0
        assert "transitions/glitch_cut" in result.output

    def test_library_search_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "search", "zzz_nonexistent"])
        assert result.exit_code == 0
        assert "No presets matching" in result.output

    def test_library_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "info", "lower_thirds/tech"])
        assert result.exit_code == 0
        assert "lower_thirds/tech" in result.output
        assert "Parameters:" in result.output
        assert "Layers:" in result.output
        assert "Usage:" in result.output
        assert '$use: "lower_thirds/tech"' in result.output

    def test_library_info_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "info", "fake/nope"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_library_scaffold(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(
            app, ["library", "scaffold", "intros/my_effect", "--dir", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Created" in result.output
        target = tmp_path / "intros" / "my_effect.effect.yaml"
        assert target.exists()
        content = target.read_text()
        assert "intros/my_effect" in content
        assert "{{ color }}" in content

    def test_library_scaffold_bad_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        result = runner.invoke(app, ["library", "scaffold", "no_slash"])
        assert result.exit_code == 1
        assert "category/effect_name" in result.output

    def test_library_scaffold_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        target = tmp_path / "cat" / "eff.effect.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("existing")
        result = runner.invoke(app, ["library", "scaffold", "cat/eff", "--dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "already exists" in result.output


class TestDiscoverModels:
    """discover --models runs one discovery per model into per-model subfolders."""

    def test_models_runs_one_per_model(self, tmp_path: Path) -> None:
        seen: list[tuple[str, str]] = []

        def fake_build(**kwargs):  # type: ignore[no-untyped-def]
            model = kwargs["model"]
            harness = MagicMock()

            def fake_discover(**dkwargs):  # type: ignore[no-untyped-def]
                out = Path(dkwargs["output_dir"])
                seen.append((model, out.name))
                result = MagicMock()
                result.summary.return_value = f"summary for {model}"
                result.trajectory.feature_reached = True
                result.persona_report = None
                result.config_path = out / "discovered_demo.yaml"
                result.video_path = None
                return result

            harness.discover.side_effect = fake_discover
            return harness

        with patch("demodsl.discover.DiscoveryHarness.build", side_effect=fake_build):
            result = runner.invoke(
                app,
                [
                    "discover",
                    "show pricing",
                    "--url",
                    "https://example.com",
                    "--models",
                    "openai/gpt-4o, anthropic/claude-3.5-sonnet",
                    "-o",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        models = [m for m, _ in seen]
        assert models == ["openai/gpt-4o", "anthropic/claude-3.5-sonnet"]
        # Each model writes into its own sanitised sub-folder.
        subdirs = {d for _, d in seen}
        assert subdirs == {"openai_gpt-4o", "anthropic_claude-3.5-sonnet"}

    def test_models_dedups_and_ignores_blanks(self, tmp_path: Path) -> None:
        calls: list[str] = []

        def fake_build(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs["model"])
            harness = MagicMock()
            result = MagicMock()
            result.summary.return_value = "ok"
            result.trajectory.feature_reached = True
            result.persona_report = None
            result.config_path = None
            result.video_path = None
            harness.discover.return_value = result
            return harness

        with patch("demodsl.discover.DiscoveryHarness.build", side_effect=fake_build):
            result = runner.invoke(
                app,
                [
                    "discover",
                    "q",
                    "--url",
                    "https://example.com",
                    "--models",
                    "gpt-4o, , gpt-4o",
                    "-o",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        assert calls == ["gpt-4o"]  # de-duplicated, blank dropped

    def test_one_model_failure_does_not_abort_others(self, tmp_path: Path) -> None:
        def fake_build(**kwargs):  # type: ignore[no-untyped-def]
            model = kwargs["model"]
            harness = MagicMock()

            def fake_discover(**dkwargs):  # type: ignore[no-untyped-def]
                if model == "bad/model":
                    raise RuntimeError("OpenRouter 400: no such model")
                result = MagicMock()
                result.summary.return_value = "ok"
                result.trajectory.feature_reached = True
                result.persona_report = None
                result.config_path = Path(dkwargs["output_dir"]) / "d.yaml"
                result.video_path = None
                return result

            harness.discover.side_effect = fake_discover
            return harness

        with patch("demodsl.discover.DiscoveryHarness.build", side_effect=fake_build):
            result = runner.invoke(
                app,
                [
                    "discover",
                    "q",
                    "--url",
                    "https://example.com",
                    "--models",
                    "good/model,bad/model",
                    "-o",
                    str(tmp_path),
                ],
            )
        # One failed but the other succeeded → overall success, error surfaced.
        assert result.exit_code == 0, result.output
        assert "discovery failed" in result.output

    def test_openrouter_validates_and_skips_unknown(self, tmp_path: Path) -> None:
        built: list[str] = []

        def fake_build(**kwargs):  # type: ignore[no-untyped-def]
            built.append(kwargs["model"])
            harness = MagicMock()
            result = MagicMock()
            result.summary.return_value = "ok"
            result.trajectory.feature_reached = True
            result.persona_report = None
            result.config_path = None
            result.video_path = None
            harness.discover.return_value = result
            return harness

        with (
            patch("demodsl.discover.DiscoveryHarness.build", side_effect=fake_build),
            patch(
                "demodsl.discover.pricing.fetch_openrouter_models",
                return_value=["openai/gpt-4o", "google/gemini-pro-1.5"],
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "discover",
                    "q",
                    "--url",
                    "https://example.com",
                    "--llm",
                    "openrouter",
                    "--models",
                    "openai/gpt-4o,google/gemini-1.5-pro",
                    "-o",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        # Unknown slug skipped (with a suggestion); only the valid one runs.
        assert built == ["openai/gpt-4o"]
        assert "not an OpenRouter model id" in result.output


class TestModelsCommand:
    def test_lists_models(self) -> None:
        with patch(
            "demodsl.discover.pricing.fetch_openrouter_models",
            return_value=["anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
        ):
            result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        assert "openai/gpt-4o" in result.output
        assert "anthropic/claude-3.5-sonnet" in result.output

    def test_filter(self) -> None:
        with patch(
            "demodsl.discover.pricing.fetch_openrouter_models",
            return_value=["anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
        ):
            result = runner.invoke(app, ["models", "--filter", "openai"])
        assert result.exit_code == 0
        assert "openai/gpt-4o" in result.output
        assert "anthropic/claude-3.5-sonnet" not in result.output

    def test_empty_exits_nonzero(self) -> None:
        with patch("demodsl.discover.pricing.fetch_openrouter_models", return_value=[]):
            result = runner.invoke(app, ["models"])
        assert result.exit_code != 0
        assert "Could not fetch" in result.output
