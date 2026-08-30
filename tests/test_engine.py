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

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[4.0, 8.0])
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

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[0.02, 0.04])
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

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[8.0])
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(12.0, 30.0))
    @patch("subprocess.run")
    def test_a_crossfade_over_an_unchanged_picture_is_dropped(
        self, mock_run: MagicMock, _probe: MagicMock, _cuts: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        src = tmp_path / "combined.mp4"
        src.write_bytes(b"\x00" * 10)

        result = DemoEngine._apply_step_transitions(
            src, tmp_path / "beats.mp4", [4.0, 8.0], Transitions(type="crossfade", duration=0.5)
        )

        # 4.0 has no cut near it: fading there would cost 0.5s for nothing.
        assert result.boundaries == (8.0,)

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[8.0])
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(12.0, 30.0))
    @patch("subprocess.run")
    def test_a_slide_is_kept_even_without_a_cut(
        self, mock_run: MagicMock, _probe: MagicMock, _cuts: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        src = tmp_path / "combined.mp4"
        src.write_bytes(b"\x00" * 10)

        result = DemoEngine._apply_step_transitions(
            src, tmp_path / "beats.mp4", [4.0, 8.0], Transitions(type="slide", duration=0.5)
        )

        # A slide moves the frame itself, so it reads on identical content too.
        assert result.boundaries == (4.0, 8.0)


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

    def test_a_failed_detection_never_drops_a_boundary(self) -> None:
        # None means ffmpeg could not answer — not "this clip has no cut".
        kept = DemoEngine._snap_to_cuts([1.0, 2.0], None, window=2.0, require_cut=True)
        assert kept == [1.0, 2.0]

    def test_require_cut_drops_a_boundary_with_nothing_happening(self) -> None:
        kept = DemoEngine._snap_to_cuts([1.0, 9.0], [9.1], window=2.0, require_cut=True)
        assert kept == [9.1]


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


class TestStepEffectResult:
    def test_no_shifts_is_identity(self) -> None:
        from demodsl.engine import StepEffectResult

        result = StepEffectResult(Path("out.mp4"))
        assert result.remap(3.2) == 3.2

    def test_single_positive_shift_after_boundary(self) -> None:
        from demodsl.engine import StepEffectResult

        result = StepEffectResult(Path("out.mp4"), shifts=((5.0, 2.0),))
        assert result.remap(1.0) == 1.0  # before the boundary: untouched
        assert result.remap(5.0) == 7.0  # at/after: pushed forward
        assert result.remap(10.0) == 12.0

    def test_negative_shift_never_goes_below_zero(self) -> None:
        from demodsl.engine import StepEffectResult

        result = StepEffectResult(Path("out.mp4"), shifts=((0.0, -100.0),))
        assert result.remap(1.0) == 0.0

    def test_shifts_accumulate_across_multiple_boundaries(self) -> None:
        from demodsl.engine import StepEffectResult

        result = StepEffectResult(Path("out.mp4"), shifts=((2.0, 1.0), (6.0, -0.5)))
        assert result.remap(1.0) == 1.0
        assert result.remap(3.0) == 4.0
        assert result.remap(7.0) == 7.5


class TestSpeedRampFilter:
    def test_constant_speed_halves_duration(self) -> None:
        _filter, new_len = DemoEngine._speed_ramp_filter(8.0, 2.0, 2.0, "linear")
        assert new_len == pytest.approx(4.0, abs=0.01)

    def test_constant_speed_below_one_extends_duration(self) -> None:
        _filter, new_len = DemoEngine._speed_ramp_filter(4.0, 0.5, 0.5, "linear")
        assert new_len == pytest.approx(8.0, abs=0.01)

    def test_ramp_lands_between_the_two_constant_speeds(self) -> None:
        _filter, ramped = DemoEngine._speed_ramp_filter(8.0, 1.0, 2.0, "linear")
        _filter, slow = DemoEngine._speed_ramp_filter(8.0, 1.0, 1.0, "linear")
        _filter, fast = DemoEngine._speed_ramp_filter(8.0, 2.0, 2.0, "linear")
        assert fast < ramped < slow

    def test_filter_fragment_reads_mid_writes_midout(self) -> None:
        filter_str, _new_len = DemoEngine._speed_ramp_filter(4.0, 1.0, 1.5, "ease-in-out")
        assert filter_str.startswith("[mid]split=8")
        assert filter_str.endswith("[midout]")


class TestSpliceTimeEffect:
    @patch("subprocess.run")
    def test_middle_only_when_no_before_or_after(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        out = DemoEngine._splice_time_effect(
            video, 0.0, 3.0, False, "[mid]reverse[midout]", ws, "out.mp4"
        )
        assert out == tmp_path / "out.mp4"
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "split=1" in filter_complex
        assert "reverse[midout]" in filter_complex
        assert "concat=n=1" in filter_complex

    @patch("subprocess.run")
    def test_before_and_after_are_kept_around_the_middle(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        DemoEngine._splice_time_effect(video, 2.0, 5.0, True, "[mid]reverse[midout]", ws, "out.mp4")
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "split=3" in filter_complex
        assert "concat=n=3" in filter_complex

    @patch("subprocess.run")
    def test_ffmpeg_failure_returns_none(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        mock_run.return_value = MagicMock(returncode=1, stderr="boom")

        out = DemoEngine._splice_time_effect(
            video, 0.0, 3.0, False, "[mid]reverse[midout]", ws, "out.mp4"
        )
        assert out is None


class TestApplyStepTimeEffects:
    def test_no_matching_effects_returns_video_unchanged(self, tmp_path: Path) -> None:
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)
        effects = [[("vignette", {"intensity": 0.4})]]
        out, filtered, shifts = DemoEngine._apply_step_time_effects(video, [0.0], effects, ws)
        assert out == video
        assert filtered == effects
        assert shifts == ()

    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(0.0, 0.0))
    def test_unprobeable_video_skips_gracefully(
        self, _mock_probe: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)
        effects = [[("reverse", {})]]
        out, filtered, shifts = DemoEngine._apply_step_time_effects(video, [0.0, 3.0], effects, ws)
        assert out == video
        assert filtered == [[]]
        assert shifts == ()

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=None)
    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(9.0, 30.0))
    def test_reverse_strips_effect_and_shifts_nothing(
        self, _mock_probe: MagicMock, mock_run: MagicMock, _mock_cuts: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        effects = [[("reverse", {})], []]
        out, filtered, shifts = DemoEngine._apply_step_time_effects(video, [0.0, 3.0], effects, ws)
        assert out != video
        assert filtered == [[], []]
        assert shifts == ()

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=None)
    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(9.0, 30.0))
    def test_freeze_frame_strips_effect_and_records_a_positive_shift(
        self, _mock_probe: MagicMock, mock_run: MagicMock, _mock_cuts: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        effects = [[("freeze_frame", {"freeze_duration": 2.0})], []]
        out, filtered, shifts = DemoEngine._apply_step_time_effects(video, [0.0, 3.0], effects, ws)
        assert out != video
        assert filtered == [[], []]
        assert shifts == ((3.0, 2.0),)

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=None)
    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(9.0, 24.0))
    def test_freeze_frame_loop_count_uses_real_fps_not_hardcoded_25(
        self, _mock_probe: MagicMock, mock_run: MagicMock, _mock_cuts: MagicMock, tmp_path: Path
    ) -> None:
        # A 24fps source held for 2.5s must loop 24*2.5=60 times — hardcoding
        # 25fps would silently under/overshoot the requested freeze duration.
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        effects = [[("freeze_frame", {"freeze_duration": 2.5})], []]
        DemoEngine._apply_step_time_effects(video, [0.0, 3.0], effects, ws)
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "loop=loop=60:" in filter_complex
        assert "loop=loop=62:" not in filter_complex  # int(2.5 * 25)

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=None)
    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(9.0, 30.0))
    def test_speed_ramp_records_a_negative_shift_when_it_speeds_up(
        self, _mock_probe: MagicMock, mock_run: MagicMock, _mock_cuts: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        effects = [[("speed_ramp", {"start_speed": 2.0, "end_speed": 2.0, "ease": "linear"})], []]
        out, filtered, shifts = DemoEngine._apply_step_time_effects(video, [0.0, 4.0], effects, ws)
        assert out != video
        assert filtered == [[], []]
        assert len(shifts) == 1
        boundary, delta = shifts[0]
        assert boundary == 4.0
        assert delta == pytest.approx(-2.0, abs=0.05)  # 4s at 2x -> 2s, so -2s

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=None)
    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(9.0, 30.0))
    def test_processes_multiple_steps_highest_index_first(
        self, _mock_probe: MagicMock, mock_run: MagicMock, _mock_cuts: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)
        seen_inputs: list[str] = []

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            seen_inputs.append(cmd[cmd.index("-i") + 1])
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        effects = [
            [("freeze_frame", {"freeze_duration": 1.0})],
            [("reverse", {})],
            [],
        ]
        DemoEngine._apply_step_time_effects(video, [0.0, 3.0, 6.0], effects, ws)
        # Step 1 (reverse) is spliced first, into "step_reverse_1.mp4"; step 0
        # (freeze) is spliced second, reading from that intermediate file.
        assert str(video) in seen_inputs[0]
        assert "step_reverse_1.mp4" in seen_inputs[1]

    @patch("demodsl.engine.DemoEngine._scene_cuts", return_value=[3.6])
    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_stream", return_value=(9.0, 30.0))
    def test_boundary_snaps_onto_a_nearby_real_scene_cut(
        self, _mock_probe: MagicMock, mock_run: MagicMock, _mock_cuts: MagicMock, tmp_path: Path
    ) -> None:
        # step_timestamps says the step ends at 3.0s (recorder clock), but
        # the real cut in the video is 0.6s later — reverse should split at
        # the real cut, not the drifted recorder timestamp.
        video = tmp_path / "in.mp4"
        ws = MagicMock(root=tmp_path)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        effects = [[("reverse", {})], []]
        DemoEngine._apply_step_time_effects(video, [0.0, 3.0], effects, ws)
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "trim=0.0000:3.6000" in filter_complex
        assert "trim=0.0000:3.0000" not in filter_complex


class TestProbeDimensions:
    @patch("subprocess.run")
    def test_handles_ffprobes_trailing_separator(self, mock_run: MagicMock, tmp_path: Path) -> None:
        # Real ffprobe csv=s=x:p=0 output has a trailing separator
        # ("1280x720x"), not just "1280x720" — a naive partition() grabs the
        # trailing empty piece as the height and silently returns (0, 0).
        mock_run.return_value = MagicMock(returncode=0, stdout="1280x720x\n")
        assert DemoEngine._probe_dimensions(tmp_path / "in.mp4") == (1280, 720)

    @patch("subprocess.run")
    def test_probe_failure_returns_zeros(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert DemoEngine._probe_dimensions(tmp_path / "in.mp4") == (0, 0)


class TestCssColorRgb:
    def test_hex(self) -> None:
        assert DemoEngine._css_color_rgb("#00FF00") == (0, 255, 0)

    def test_named_color(self) -> None:
        assert DemoEngine._css_color_rgb("red") == (255, 0, 0)

    def test_rgb_function(self) -> None:
        assert DemoEngine._css_color_rgb("rgb(10, 20, 30)") == (10, 20, 30)

    def test_unparseable_falls_back(self) -> None:
        assert DemoEngine._css_color_rgb("not-a-color", fallback=(1, 2, 3)) == (1, 2, 3)


class TestBuildPipShapeMask:
    def test_circle_center_opaque_corner_transparent(self, tmp_path: Path) -> None:
        out = tmp_path / "mask.png"
        DemoEngine._build_pip_shape_mask(100, 100, "circle", out)
        from PIL import Image

        im = Image.open(out).convert("L")
        assert im.getpixel((50, 50)) > 200  # center: opaque
        assert im.getpixel((2, 2)) < 20  # corner: transparent

    def test_rectangle_is_fully_opaque(self, tmp_path: Path) -> None:
        out = tmp_path / "mask.png"
        DemoEngine._build_pip_shape_mask(100, 100, "rectangle", out)
        from PIL import Image

        im = Image.open(out).convert("L")
        assert im.getpixel((2, 2)) > 200
        assert im.getpixel((50, 50)) > 200

    def test_rounded_corner_transparent_center_opaque(self, tmp_path: Path) -> None:
        out = tmp_path / "mask.png"
        DemoEngine._build_pip_shape_mask(100, 100, "rounded", out)
        from PIL import Image

        im = Image.open(out).convert("L")
        assert im.getpixel((1, 1)) < 20  # sharp corner: outside the rounded rect
        assert im.getpixel((50, 50)) > 200


class TestBuildPipBorderRing:
    def test_ring_drawn_at_edge_not_at_center(self, tmp_path: Path) -> None:
        out = tmp_path / "ring.png"
        DemoEngine._build_pip_border_ring(100, 100, "rectangle", (255, 255, 255), 6, out)
        from PIL import Image

        im = Image.open(out).convert("RGBA")
        edge_alpha = im.getpixel((50, 3))[3]
        center_alpha = im.getpixel((50, 50))[3]
        assert edge_alpha > 200
        assert center_alpha == 0


class TestApplyPictureInPicture:
    @patch("demodsl.engine.DemoEngine._probe_dimensions", return_value=(0, 0))
    def test_missing_source_skips(self, _mock_dims: MagicMock, tmp_path: Path) -> None:
        from demodsl.models import PictureInPicture

        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        pip = PictureInPicture(source=str(tmp_path / "does_not_exist.mp4"))

        out = DemoEngine._apply_picture_in_picture(video, pip, ws)
        assert out == video

    @patch("demodsl.engine.DemoEngine._probe_dimensions", return_value=(0, 0))
    def test_unprobeable_main_video_skips(self, _mock_dims: MagicMock, tmp_path: Path) -> None:
        from demodsl.models import PictureInPicture

        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        source = tmp_path / "webcam.mp4"
        source.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        pip = PictureInPicture(source=str(source))

        out = DemoEngine._apply_picture_in_picture(video, pip, ws)
        assert out == video

    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_dimensions", return_value=(1280, 720))
    def test_chroma_key_builds_chromakey_and_despill_filters(
        self, _mock_dims: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.models import ChromaKey, PictureInPicture

        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        source = tmp_path / "webcam.mp4"
        source.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        pip = PictureInPicture(
            source=str(source),
            chroma_key=ChromaKey(color="#00FF00", similarity=0.35, blend=0.15),
        )

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        out = DemoEngine._apply_picture_in_picture(video, pip, ws)
        assert out != video
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "chromakey=color=0x00ff00:similarity=0.350:blend=0.150" in filter_complex
        assert "despill=type=green" in filter_complex
        # Only 2 real inputs (main + pip source) — no shape mask file needed.
        assert cmd.count("-i") == 2

    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_dimensions", return_value=(1280, 720))
    def test_no_chroma_key_builds_shape_mask_and_border_ring(
        self, _mock_dims: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.models import PictureInPicture

        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        source = tmp_path / "webcam.mp4"
        source.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        pip = PictureInPicture(source=str(source), shape="circle", border_width=4)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        out = DemoEngine._apply_picture_in_picture(video, pip, ws)
        assert out != video
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "alphamerge" in filter_complex
        assert "chromakey" not in filter_complex
        # main + pip source + mask + border ring = 4 real inputs.
        assert cmd.count("-i") == 4
        assert (tmp_path / "pip_mask.png").exists()
        assert (tmp_path / "pip_ring.png").exists()

    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_dimensions", return_value=(1280, 720))
    def test_position_maps_to_correct_overlay_expression(
        self, _mock_dims: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.models import PictureInPicture

        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        source = tmp_path / "webcam.mp4"
        source.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        pip = PictureInPicture(source=str(source), position="top-left", border_width=0)

        def _fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            Path(cmd[-1]).write_bytes(b"\x00" * 10)
            return MagicMock(returncode=0)

        mock_run.side_effect = _fake_run

        DemoEngine._apply_picture_in_picture(video, pip, ws)
        cmd = mock_run.call_args[0][0]
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "overlay=x=16:y=16:format=auto[outv]" in filter_complex

    @patch("subprocess.run")
    @patch("demodsl.engine.DemoEngine._probe_dimensions", return_value=(1280, 720))
    def test_ffmpeg_failure_returns_original_video(
        self, _mock_dims: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.models import PictureInPicture

        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 10)
        source = tmp_path / "webcam.mp4"
        source.write_bytes(b"\x00" * 10)
        ws = MagicMock(root=tmp_path)
        pip = PictureInPicture(source=str(source))
        mock_run.return_value = MagicMock(returncode=1, stderr="boom")

        out = DemoEngine._apply_picture_in_picture(video, pip, ws)
        assert out == video
