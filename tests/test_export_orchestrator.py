"""Tests for demodsl.orchestrators.export — ExportOrchestrator."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import DemoConfig
from demodsl.orchestrators.export import ExportOrchestrator, _human_size

_has_ffmpeg = shutil.which("ffmpeg") is not None


def _make_config(**kwargs) -> DemoConfig:
    data: dict = {"metadata": {"title": "Test"}}
    data.update(kwargs)
    return DemoConfig(**data)


class TestHumanSize:
    def test_bytes(self) -> None:
        assert _human_size(500) == "500B"

    def test_kilobytes(self) -> None:
        assert _human_size(2048) == "2KB"

    def test_megabytes(self) -> None:
        assert _human_size(5 * 1024 * 1024) == "5MB"

    def test_gigabytes(self) -> None:
        assert _human_size(3 * 1024 * 1024 * 1024) == "3GB"

    def test_terabytes(self) -> None:
        result = _human_size(2 * 1024 * 1024 * 1024 * 1024)
        assert "TB" in result


class TestExportOrchestratorInit:
    def test_creates_with_config(self) -> None:
        config = _make_config()
        orch = ExportOrchestrator(config)
        assert orch.config is config


class TestNeedsConversion:
    @patch("subprocess.run")
    def test_webm_needs_conversion(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "webm\n"
        mock_run.return_value = mock_result
        assert ExportOrchestrator._needs_conversion(Path("in.webm"), Path("out.mp4"))

    @patch("subprocess.run")
    def test_matroska_needs_conversion(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "matroska,webm\n"
        mock_run.return_value = mock_result
        assert ExportOrchestrator._needs_conversion(Path("in.mkv"), Path("out.mp4"))

    @patch("subprocess.run")
    def test_mp4_does_not_need_conversion(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "mov,mp4\n"
        mock_run.return_value = mock_result
        assert not ExportOrchestrator._needs_conversion(Path("in.mp4"), Path("out.mp4"))

    def test_non_mp4_dest_no_conversion(self) -> None:
        assert not ExportOrchestrator._needs_conversion(Path("in.mp4"), Path("out.webm"))

    @patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe"))
    def test_ffprobe_missing_returns_false(self, _mock: MagicMock) -> None:
        assert not ExportOrchestrator._needs_conversion(Path("in.webm"), Path("out.mp4"))

    @patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=10),
    )
    def test_ffprobe_timeout_returns_false(self, _mock: MagicMock) -> None:
        assert not ExportOrchestrator._needs_conversion(Path("in.webm"), Path("out.mp4"))


class TestVerifyVideo:
    def test_missing_file(self, tmp_path: Path) -> None:
        # Should not raise, just log error
        ExportOrchestrator.verify_video(tmp_path / "missing.mp4")

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.mp4"
        f.write_bytes(b"")
        ExportOrchestrator.verify_video(f)

    @patch("subprocess.run")
    def test_successful_verify(self, mock_run: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "good.mp4"
        f.write_bytes(b"\x00" * 1000)
        mock_result = MagicMock()
        mock_result.stdout = (
            "format_name=mov,mp4\ncodec_name=h264\n"
            "width=1920\nheight=1080\nduration=10.5\n"
        )
        mock_run.return_value = mock_result
        # Should not raise
        ExportOrchestrator.verify_video(f)

    @patch("subprocess.run")
    def test_format_mismatch(self, mock_run: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "bad.mp4"
        f.write_bytes(b"\x00" * 100)
        mock_result = MagicMock()
        mock_result.stdout = "format_name=webm\ncodec_name=vp8\n"
        mock_run.return_value = mock_result
        # Should not raise, but logs error
        ExportOrchestrator.verify_video(f)

    @patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe"))
    def test_ffprobe_missing(self, _mock: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "file.mp4"
        f.write_bytes(b"\x00" * 100)
        # Should not raise
        ExportOrchestrator.verify_video(f)


class TestExportVideo:
    @patch.object(ExportOrchestrator, "verify_video")
    @patch.object(ExportOrchestrator, "_needs_conversion", return_value=False)
    def test_simple_copy(
        self, _needs: MagicMock, _verify: MagicMock, tmp_path: Path
    ) -> None:
        src = tmp_path / "input.mp4"
        src.write_bytes(b"\x00" * 100)
        dest = tmp_path / "output.mp4"

        config = _make_config()
        orch = ExportOrchestrator(config)
        orch.export_video(src, dest)
        assert dest.exists()
        _verify.assert_called_once_with(dest)

    @patch.object(ExportOrchestrator, "verify_video")
    @patch("subprocess.run")
    @patch.object(ExportOrchestrator, "_needs_conversion", return_value=True)
    def test_conversion_with_ffmpeg(
        self,
        _needs: MagicMock,
        mock_run: MagicMock,
        _verify: MagicMock,
        tmp_path: Path,
    ) -> None:
        src = tmp_path / "input.webm"
        src.write_bytes(b"\x00" * 100)
        dest = tmp_path / "output.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        config = _make_config()
        orch = ExportOrchestrator(config)
        orch.export_video(src, dest)
        mock_run.assert_called_once()

    @patch.object(ExportOrchestrator, "verify_video")
    @patch("subprocess.run")
    @patch.object(ExportOrchestrator, "_needs_conversion", return_value=True)
    def test_ffmpeg_failure_fallback_copy(
        self,
        _needs: MagicMock,
        mock_run: MagicMock,
        _verify: MagicMock,
        tmp_path: Path,
    ) -> None:
        src = tmp_path / "input.webm"
        src.write_bytes(b"\x00" * 100)
        dest = tmp_path / "output.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_run.return_value = mock_result

        config = _make_config()
        orch = ExportOrchestrator(config)
        orch.export_video(src, dest)
        assert dest.exists()

    @patch.object(ExportOrchestrator, "verify_video")
    @patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=600),
    )
    @patch.object(ExportOrchestrator, "_needs_conversion", return_value=True)
    def test_ffmpeg_timeout_fallback_copy(
        self,
        _needs: MagicMock,
        _run: MagicMock,
        _verify: MagicMock,
        tmp_path: Path,
    ) -> None:
        src = tmp_path / "input.webm"
        src.write_bytes(b"\x00" * 100)
        dest = tmp_path / "output.mp4"

        config = _make_config()
        orch = ExportOrchestrator(config)
        orch.export_video(src, dest)
        assert dest.exists()

    @patch.object(ExportOrchestrator, "verify_video")
    @patch("subprocess.run")
    @patch.object(ExportOrchestrator, "_needs_conversion", return_value=False)
    def test_export_with_audio(
        self,
        _needs: MagicMock,
        mock_run: MagicMock,
        _verify: MagicMock,
        tmp_path: Path,
    ) -> None:
        src = tmp_path / "input.mp4"
        src.write_bytes(b"\x00" * 100)
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\x00" * 50)
        dest = tmp_path / "output.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        config = _make_config()
        orch = ExportOrchestrator(config)
        orch.export_video(src, dest, audio=audio)
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert "-i" in cmd
        assert str(audio) in cmd


class TestDeployToCloud:
    def test_no_deploy_config(self) -> None:
        config = _make_config()
        orch = ExportOrchestrator(config)
        result = orch.deploy_to_cloud(Path("video.mp4"))
        assert result is None

    def test_no_output_config(self) -> None:
        config = _make_config()
        orch = ExportOrchestrator(config)
        result = orch.deploy_to_cloud(Path("video.mp4"))
        assert result is None
