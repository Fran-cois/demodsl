"""Tests for demodsl.scopes (waveform/histogram/vectorscope/RGB parade generation)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.scopes import SCOPE_TYPES, _scope_filter, render_all_scopes, render_scope


class TestScopeFilter:
    @pytest.mark.parametrize("scope", SCOPE_TYPES)
    def test_every_scope_type_has_a_filter(self, scope: str) -> None:
        assert _scope_filter(scope)

    def test_unknown_scope_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown scope type"):
            _scope_filter("bogus")

    def test_waveform_is_luma_only(self) -> None:
        assert "components=1" in _scope_filter("waveform")

    def test_rgb_parade_converts_to_planar_rgb_first(self) -> None:
        vf = _scope_filter("rgb_parade")
        assert "format=gbrp" in vf
        assert "display=parade" in vf
        assert "components=7" in vf

    def test_vectorscope_has_a_graticule(self) -> None:
        assert "graticule=green" in _scope_filter("vectorscope")


class TestRenderScope:
    def test_unknown_scope_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown scope type"):
            render_scope(
                tmp_path / "in.mp4", timestamp=0.0, scope="bogus", output=tmp_path / "o.png"
            )

    @patch("demodsl.scopes.run_ffmpeg")
    def test_builds_the_right_ffmpeg_command(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "in.mp4"
        output = tmp_path / "out" / "scope_waveform.png"
        result = render_scope(video, timestamp=2.5, scope="waveform", output=output)
        assert result == output
        assert output.parent.exists()  # parent dir created
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-ss" in cmd and cmd[cmd.index("-ss") + 1] == "2.5"
        assert "-i" in cmd and cmd[cmd.index("-i") + 1] == str(video)
        assert "-frames:v" in cmd and cmd[cmd.index("-frames:v") + 1] == "1"
        assert cmd[-1] == str(output)

    @patch("demodsl.scopes.run_ffmpeg")
    def test_negative_timestamp_clamped_to_zero(self, mock_run: MagicMock, tmp_path: Path) -> None:
        render_scope(
            tmp_path / "in.mp4", timestamp=-3.0, scope="histogram", output=tmp_path / "o.png"
        )
        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("-ss") + 1] == "0.0"

    @patch("demodsl.scopes.run_ffmpeg", side_effect=RuntimeError("ffmpeg failed"))
    def test_propagates_ffmpeg_failure(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            render_scope(
                tmp_path / "in.mp4", timestamp=0.0, scope="waveform", output=tmp_path / "o.png"
            )


class TestRenderAllScopes:
    @patch("demodsl.scopes.run_ffmpeg")
    def test_renders_every_scope_type(self, mock_run: MagicMock, tmp_path: Path) -> None:
        paths = render_all_scopes(tmp_path / "in.mp4", timestamp=1.0, output_dir=tmp_path, stem="s")
        assert set(paths.keys()) == set(SCOPE_TYPES)
        assert mock_run.call_count == len(SCOPE_TYPES)
        for scope, path in paths.items():
            assert path == tmp_path / f"s_{scope}.png"


class TestScopesCli:
    def test_missing_video_exits_nonzero(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        result = CliRunner().invoke(app, ["scopes", str(tmp_path / "nope.mp4")])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_unknown_scope_exits_nonzero(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        video = tmp_path / "in.mp4"
        video.write_bytes(b"fake")
        result = CliRunner().invoke(app, ["scopes", str(video), "--scope", "bogus"])
        assert result.exit_code == 1
        assert "Unknown scope" in result.output

    @patch("demodsl.scopes.render_all_scopes")
    def test_default_renders_all_scopes(self, mock_all: MagicMock, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        video = tmp_path / "in.mp4"
        video.write_bytes(b"fake")
        mock_all.return_value = {"waveform": tmp_path / "in_waveform.png"}
        result = CliRunner().invoke(app, ["scopes", str(video), "--output-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "waveform" in result.output
        mock_all.assert_called_once()

    @patch("demodsl.scopes.render_scope")
    def test_single_scope_selection(self, mock_one: MagicMock, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        video = tmp_path / "in.mp4"
        video.write_bytes(b"fake")
        mock_one.return_value = tmp_path / "in_vectorscope.png"
        result = CliRunner().invoke(
            app, ["scopes", str(video), "--scope", "vectorscope", "--output-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        mock_one.assert_called_once()
        assert mock_one.call_args.kwargs["scope"] == "vectorscope"

    @patch("demodsl.scopes.render_all_scopes", side_effect=RuntimeError("boom"))
    def test_ffmpeg_failure_exits_nonzero(self, _mock_all: MagicMock, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        video = tmp_path / "in.mp4"
        video.write_bytes(b"fake")
        result = CliRunner().invoke(app, ["scopes", str(video), "--output-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "failed" in result.output
