import subprocess
from pathlib import Path

import pytest

from demodsl.encoding import (
    DEFAULT_CRF,
    DEFAULT_PRESET,
    deblock_filters,
    is_h264,
    x264_args,
)


class TestX264Args:
    def test_defaults(self):
        args = x264_args()
        assert args[:2] == ["-c:v", "libx264"]
        assert args[args.index("-preset") + 1] == DEFAULT_PRESET
        assert args[args.index("-crf") + 1] == DEFAULT_CRF
        assert "-pix_fmt" in args
        assert "-movflags" not in args

    def test_faststart_and_no_pix_fmt(self):
        args = x264_args(pix_fmt=None, faststart=True)
        assert "-pix_fmt" not in args
        assert args[-2:] == ["-movflags", "+faststart"]

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DEMODSL_X264_PRESET", "medium")
        monkeypatch.setenv("DEMODSL_X264_CRF", "18")
        args = x264_args()
        assert args[args.index("-preset") + 1] == "medium"
        assert args[args.index("-crf") + 1] == "18"


class TestDeblockFilters:
    def test_only_applies_to_webm_sources(self):
        assert deblock_filters(".mp4") == []
        assert deblock_filters(".webm")

    def test_profiles(self, monkeypatch):
        monkeypatch.setenv("DEMODSL_DEBLOCK", "off")
        assert deblock_filters(".webm") == []
        monkeypatch.setenv("DEMODSL_DEBLOCK", "full")
        assert deblock_filters(".webm") == ["spp=quality=4:qp=2", "hqdn3d=3:2:3:2"]

    def test_unknown_profile_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("DEMODSL_DEBLOCK", "wat")
        assert deblock_filters(".webm") == deblock_filters(".webm")
        assert deblock_filters(".webm") == ["spp=quality=1:qp=2"]


class TestIsH264:
    def test_missing_file_is_not_h264(self, tmp_path):
        assert is_h264(tmp_path / "nope.mp4") is False

    @pytest.mark.skipif(
        subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0,
        reason="ffmpeg not installed",
    )
    def test_detects_h264(self, tmp_path: Path):
        out = tmp_path / "clip.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=1:size=128x72:rate=5",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
        assert is_h264(out) is True
