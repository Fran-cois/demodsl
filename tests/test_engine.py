"""Tests for demodsl.engine — DemoEngine orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.diagnostics import DIAGNOSTIC_CODES, diagnose
from demodsl.engine import ConcatResult, DemoEngine
from demodsl.models import DemoConfig
from demodsl.models.video import Transitions


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
        # Built-in effects; plugins (e.g. demodsl-apps) add more when installed
        assert len(engine._effects.browser_effects) >= 78
        assert len(engine._effects.post_effects) >= 33

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
        result = engine._scenario._dry_run_scenarios()
        assert result == []

    def test_dry_run_narrations_returns_empty(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        result = engine._narration._dry_run_narrations()
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


class TestEngineOptions:
    def test_skip_voice(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, skip_voice=True)
        assert engine.skip_voice is True
        assert engine._narration.skip_voice is True

    def test_skip_deploy(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, skip_deploy=True)
        assert engine.skip_deploy is True

    def test_renderer_option(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, renderer="remotion")
        assert engine.renderer == "remotion"

    def test_dry_run_flag(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        assert engine.dry_run is True


class TestEngineRun:
    def test_run_creates_output_dir(self, full_yaml_path: Path, tmp_path: Path) -> None:
        out = tmp_path / "sub" / "dir"
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, output_dir=out)
        engine.run()
        assert out.exists()

    def test_run_dry_with_full_config(
        self,
        full_yaml_path: Path,
        tmp_path: Path,
    ) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, output_dir=tmp_path)
        result = engine.run()
        assert result is None  # dry-run produces no output


class TestConcatVideos:
    @patch("subprocess.run")
    def test_concat_two_videos(self, mock_run: MagicMock, tmp_path: Path) -> None:
        v1 = tmp_path / "s1.webm"
        v2 = tmp_path / "s2.webm"
        v1.write_bytes(b"\x00" * 10)
        v2.write_bytes(b"\x00" * 10)
        out = tmp_path / "combined.mp4"

        mock_run.return_value = MagicMock(returncode=0)

        result = DemoEngine._concat_videos([v1, v2], out)
        assert result.path == out
        assert result.shift == 0.0
        mock_run.assert_called_once()
        # Verify filter_complex concat is used
        cmd = mock_run.call_args[0][0]
        assert "-filter_complex" in cmd
        assert "concat=n=2" in " ".join(cmd)

    @patch("subprocess.run")
    def test_concat_failure_returns_first(self, mock_run: MagicMock, tmp_path: Path) -> None:
        v1 = tmp_path / "s1.webm"
        v1.write_bytes(b"\x00" * 10)
        out = tmp_path / "combined.mp4"

        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        result = DemoEngine._concat_videos([v1], out)
        assert result.path == v1  # Falls back to first


class TestConcatTransitions:
    """``video.transitions`` — cross-fading the per-scenario recordings."""

    @staticmethod
    def _clips(tmp_path: Path, n: int = 3) -> list[Path]:
        clips = []
        for i in range(n):
            p = tmp_path / f"s{i}.webm"
            p.write_bytes(b"\x00" * 10)
            clips.append(p)
        return clips

    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(10.0, 30.0))
    @patch("subprocess.run")
    def test_xfade_chain_offsets(
        self, mock_run: MagicMock, _probe: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        out = tmp_path / "combined.mp4"

        result = DemoEngine._concat_videos(
            self._clips(tmp_path),
            out,
            transition=Transitions(type="crossfade", duration=0.5),
        )

        assert result.path == out
        assert result.shift == 0.5
        assert result.boundaries == (10.0, 20.0)
        graph = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-filter_complex") + 1]
        # Junction 1 sits at 10 - 0.5; junction 2 on the already-shortened
        # output at (10 + 10 - 0.5) - 0.5.
        assert "xfade=transition=fade:duration=0.500:offset=9.500" in graph
        assert "xfade=transition=fade:duration=0.500:offset=19.000" in graph
        assert graph.endswith("[outv]")

    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(10.0, 30.0))
    @patch("subprocess.run")
    def test_type_maps_to_ffmpeg_name(
        self, mock_run: MagicMock, _probe: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        DemoEngine._concat_videos(
            self._clips(tmp_path, 2),
            tmp_path / "c.mp4",
            transition=Transitions(type="slide", duration=0.4),
        )
        cmd = " ".join(mock_run.call_args[0][0])
        assert "xfade=transition=slideleft" in cmd

    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(1.0, 30.0))
    @patch("subprocess.run")
    def test_clamped_to_half_the_shortest_clip(
        self, mock_run: MagicMock, _probe: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        result = DemoEngine._concat_videos(
            self._clips(tmp_path, 2),
            tmp_path / "c.mp4",
            transition=Transitions(duration=4.0),
        )
        assert result.shift == 0.5  # not 4.0 — a 1s clip cannot give more

    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(0.0, 0.0))
    @patch("subprocess.run")
    def test_unprobeable_clips_fall_back_to_plain_concat(
        self, mock_run: MagicMock, _probe: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        result = DemoEngine._concat_videos(
            self._clips(tmp_path, 2),
            tmp_path / "c.mp4",
            transition=Transitions(duration=0.5),
        )
        assert result.shift == 0.0
        assert "concat=n=2" in " ".join(mock_run.call_args[0][0])

    def test_remap_shifts_only_past_a_junction(self) -> None:
        result = ConcatResult(Path("c.mp4"), boundaries=(10.0, 20.0), shift=0.5)
        assert result.remap(4.0) == 4.0  # first clip: untouched
        assert result.remap(12.0) == 11.5  # one junction crossed
        assert result.remap(25.0) == 24.0  # two junctions crossed

    def test_remap_is_identity_without_a_transition(self) -> None:
        assert ConcatResult(Path("c.mp4")).remap(7.5) == 7.5


class TestBeatTransitions:
    """``between: navigations|steps`` — transitions inside a single clip."""

    @staticmethod
    def _config(between: str, actions: list[str]) -> DemoConfig:
        return DemoConfig(
            metadata={"title": "T", "version": "1.0"},
            video={"transitions": {"duration": 0.5, "between": between}},
            scenarios=[
                {
                    "name": "S",
                    "url": "https://example.com",
                    "steps": [
                        {"action": a, "url": "https://example.com/x"}
                        if a == "navigate"
                        else {"action": a, "locator": {"type": "css", "value": "h1"}}
                        for a in actions
                    ],
                }
            ],
        )

    def test_scenarios_mode_touches_no_step_boundary(self) -> None:
        config = self._config("scenarios", ["navigate", "hover", "navigate"])
        assert DemoEngine.transition_boundaries(config, [0.0, 2.0, 4.0]) == []

    def test_navigations_mode_only_cuts_on_page_changes(self) -> None:
        config = self._config("navigations", ["navigate", "hover", "navigate", "hover"])
        # step 2 navigates, so only its boundary (4.0) qualifies.
        assert DemoEngine.transition_boundaries(config, [0.0, 2.0, 4.0, 6.0]) == [4.0]

    def test_steps_mode_cuts_between_every_beat(self) -> None:
        config = self._config("steps", ["navigate", "hover", "navigate"])
        assert DemoEngine.transition_boundaries(config, [0.0, 2.0, 4.0]) == [2.0, 4.0]

    def test_boundaries_too_close_together_are_dropped(self) -> None:
        config = self._config("steps", ["navigate", "hover", "hover", "hover"])
        kept = DemoEngine.transition_boundaries(config, [0.0, 2.0, 2.1, 4.0], min_gap=1.0)
        assert kept == [2.0, 4.0]

    def test_a_faded_scenario_junction_is_not_faded_twice(self) -> None:
        config = self._config("steps", ["navigate", "hover", "navigate"])
        kept = DemoEngine.transition_boundaries(
            config, [0.0, 2.0, 4.0], exclude=[2.05], min_gap=1.0
        )
        assert kept == [4.0]

    def test_navigations_gives_up_when_the_step_counts_disagree(self) -> None:
        config = self._config("navigations", ["navigate", "hover"])
        assert DemoEngine.transition_boundaries(config, [0.0, 2.0, 4.0]) == []

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[])
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(12.0, 30.0))
    @patch("subprocess.run")
    def test_recut_graph_trims_and_fades(
        self, mock_run: MagicMock, _probe: MagicMock, _cuts: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        src = tmp_path / "combined.mp4"
        src.write_bytes(b"\x00" * 10)

        result = DemoEngine._apply_step_transitions(
            src, tmp_path / "beats.mp4", [4.0, 8.0], Transitions(duration=0.5)
        )

        assert result.shift == 0.5
        assert result.boundaries == (4.0, 8.0)
        cmd = mock_run.call_args[0][0]
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "split=3" in graph
        assert "trim=start=0.000:end=4.000" in graph
        assert "trim=start=4.000:end=8.000" in graph
        assert "trim=start=8.000:end=12.000" in graph
        assert graph.count("xfade=transition=fade") == 2
        assert graph.endswith("[outv]")

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[])
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(1.0, 30.0))
    @patch("subprocess.run")
    def test_beats_too_short_leave_the_clip_alone(
        self, mock_run: MagicMock, _probe: MagicMock, _cuts: MagicMock, tmp_path: Path
    ) -> None:
        src = tmp_path / "combined.mp4"
        src.write_bytes(b"\x00" * 10)

        result = DemoEngine._apply_step_transitions(
            src, tmp_path / "beats.mp4", [0.02, 0.04], Transitions(duration=0.5)
        )

        assert result.path == src
        assert result.shift == 0.0
        mock_run.assert_not_called()


class TestSnapToCuts:
    """Step timestamps drift from the video clock; the fade must land on the cut."""

    def test_a_boundary_moves_onto_a_nearby_cut(self) -> None:
        assert DemoEngine._snap_to_cuts([4.94], [4.40, 9.33], window=2.0) == [4.40]

    def test_a_boundary_with_no_cut_in_range_stays_put(self) -> None:
        assert DemoEngine._snap_to_cuts([4.94], [12.0], window=2.0) == [4.94]

    def test_two_boundaries_never_collapse_onto_one_cut(self) -> None:
        assert DemoEngine._snap_to_cuts([4.0, 4.5], [4.2], window=2.0) == [4.2]

    def test_without_detection_the_boundaries_are_untouched(self) -> None:
        assert DemoEngine._snap_to_cuts([1.0, 2.0], [], window=2.0) == [1.0, 2.0]


class TestTransitionsDiagnostic:
    """A transition with no junction to play on must be flagged, not silent."""

    @staticmethod
    def _config(n_scenarios: int) -> DemoConfig:
        return DemoConfig(
            metadata={"title": "T", "version": "1.0"},
            video={"transitions": {"type": "crossfade", "duration": 0.5}},
            scenarios=[
                {
                    "name": f"S{i}",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://example.com", "wait": 1.0}],
                }
                for i in range(n_scenarios)
            ],
        )

    def test_single_scenario_is_warned(self) -> None:
        codes = [d.code for d in diagnose(self._config(1))]
        assert "video.transitions_single_scenario" in codes

    def test_two_scenarios_are_silent(self) -> None:
        codes = [d.code for d in diagnose(self._config(2))]
        assert "video.transitions_single_scenario" not in codes

    def test_code_is_declared(self) -> None:
        assert "video.transitions_single_scenario" in DIAGNOSTIC_CODES


class TestIsSuspectVideo:
    """Tests for DemoEngine._is_suspect_video static method."""

    def test_missing_file(self, tmp_path: Path) -> None:
        assert DemoEngine._is_suspect_video(tmp_path / "no_such.mp4") is True

    def test_too_small_file(self, tmp_path: Path) -> None:
        p = tmp_path / "tiny.mp4"
        p.write_bytes(b"\x00" * 100)
        assert DemoEngine._is_suspect_video(p) is True

    def test_large_file_no_ffprobe(self, tmp_path: Path) -> None:
        p = tmp_path / "big.mp4"
        p.write_bytes(b"\x00" * 50_000)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert DemoEngine._is_suspect_video(p) is False

    @patch("subprocess.run")
    def test_valid_video(self, mock_run: MagicMock, tmp_path: Path) -> None:
        p = tmp_path / "ok.mp4"
        p.write_bytes(b"\x00" * 50_000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [{"duration": "12.5", "codec_name": "h264"}]}),
        )
        assert DemoEngine._is_suspect_video(p) is False

    @patch("subprocess.run")
    def test_short_duration_suspect(self, mock_run: MagicMock, tmp_path: Path) -> None:
        p = tmp_path / "short.mp4"
        p.write_bytes(b"\x00" * 50_000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [{"duration": "0.3", "codec_name": "h264"}]}),
        )
        assert DemoEngine._is_suspect_video(p) is True

    @patch("subprocess.run")
    def test_mjpeg_codec_suspect(self, mock_run: MagicMock, tmp_path: Path) -> None:
        p = tmp_path / "mjpeg.mp4"
        p.write_bytes(b"\x00" * 50_000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [{"duration": "10.0", "codec_name": "mjpeg"}]}),
        )
        assert DemoEngine._is_suspect_video(p) is True

    @patch("subprocess.run")
    def test_na_duration_no_crash(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """ffprobe sometimes returns 'N/A' for duration — must not crash."""
        p = tmp_path / "na.mp4"
        p.write_bytes(b"\x00" * 50_000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [{"duration": "N/A", "codec_name": "h264"}]}),
        )
        # N/A → duration defaults to 0.0 → suspect (< 1.0)
        assert DemoEngine._is_suspect_video(p) is True

    @patch("subprocess.run")
    def test_missing_duration_key(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """ffprobe may omit the duration key entirely."""
        p = tmp_path / "nodur.mp4"
        p.write_bytes(b"\x00" * 50_000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [{"codec_name": "h264"}]}),
        )
        # No duration → defaults to 0.0 → suspect
        assert DemoEngine._is_suspect_video(p) is True

    @patch("subprocess.run")
    def test_ffprobe_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        import subprocess as sp

        p = tmp_path / "hang.mp4"
        p.write_bytes(b"\x00" * 50_000)
        mock_run.side_effect = sp.TimeoutExpired(cmd="ffprobe", timeout=10)
        # Falls back to file-size check → large enough → not suspect
        assert DemoEngine._is_suspect_video(p) is False


class TestBurnWatermark:
    """Tests for the @demodsl branding watermark."""

    @patch("demodsl.engine._ffmpeg_has_drawtext", return_value=True)
    @patch("subprocess.run")
    def test_burn_watermark_success(
        self, mock_run: MagicMock, _has_drawtext: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"\x00" * 100)
        output = tmp_path / "watermarked.mp4"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = DemoEngine._burn_watermark(video, output)

        assert result == output
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd[0]
        # Verify the drawtext filter contains @demodsl
        vf_idx = cmd.index("-vf")
        assert "@demodsl" in cmd[vf_idx + 1]

    @patch("demodsl.engine._ffmpeg_has_drawtext", return_value=True)
    @patch("subprocess.run")
    def test_burn_watermark_failure_returns_original(
        self, mock_run: MagicMock, _has_drawtext: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"\x00" * 100)
        output = tmp_path / "watermarked.mp4"
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        result = DemoEngine._burn_watermark(video, output)

        assert result == video  # Fallback to original

    def test_branding_enabled_by_default(self, full_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        # output.branding should default to True
        assert engine.config.output is not None
        assert engine.config.output.branding is True

    def test_branding_opt_out(self, tmp_path: Path) -> None:
        import yaml

        cfg = {
            "metadata": {"title": "Test"},
            "output": {"filename": "out.mp4", "branding": False},
        }
        p = tmp_path / "opt_out.yaml"
        p.write_text(yaml.dump(cfg))
        engine = DemoEngine(config_path=p, dry_run=True)
        assert engine.config.output.branding is False


class TestTurboMode:
    def test_turbo_flag_defaults_false(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True)
        assert engine.turbo is False

    def test_turbo_flag_set(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True, turbo=True)
        assert engine.turbo is True

    def test_turbo_propagates_to_scenario_orch(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True, turbo=True)
        assert engine._scenario.turbo is True

    def test_turbo_false_scenario_orch(self, sample_yaml_path: Path) -> None:
        engine = DemoEngine(config_path=sample_yaml_path, dry_run=True, turbo=False)
        assert engine._scenario.turbo is False
