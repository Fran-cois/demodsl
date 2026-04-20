"""Tests for new video editing tools — pipeline stages, effects, models, and export."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.pipeline.stages import (
    ChapterStage,
    ColorCorrectionStage,
    FrameRateStage,
    PiPStage,
    PipelineContext,
    RestoreAudioStage,
    SpeedStage,
    ThumbnailStage,
    _STAGE_MAP,
    build_chain,
)


# ── Stage map includes new stages ─────────────────────────────────────────────


class TestNewStageMap:
    @pytest.mark.parametrize(
        "name",
        [
            "color_correction",
            "frame_rate",
            "speed",
            "pip",
            "thumbnail",
            "chapters",
        ],
    )
    def test_new_stage_registered(self, name: str) -> None:
        assert name in _STAGE_MAP

    def test_total_stage_count(self) -> None:
        assert len(_STAGE_MAP) == 15

    def test_new_stages_are_optional(self) -> None:
        for name in (
            "color_correction",
            "frame_rate",
            "speed",
            "fit_duration",
            "pip",
            "thumbnail",
            "chapters",
        ):
            cls = _STAGE_MAP[name]
            instance = cls({})
            assert instance.critical is False, f"{name} should be optional"


# ── RestoreAudioStage — new audio features ────────────────────────────────────


class TestRestoreAudioEQ:
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_eq_preset_podcast(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "eq_preset": "podcast"}
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        assert "highpass=f=80" in cmd[af_idx + 1]
        assert "equalizer" in cmd[af_idx + 1]

    @pytest.mark.parametrize("preset", ["warm", "bright", "telephone", "radio", "deep"])
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_eq_presets_all(
        self, mock_run: MagicMock, tmp_path: Path, preset: str
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "eq_preset": preset}
        )
        stage.process(ctx)
        mock_run.assert_called_once()

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_custom_eq_bands(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {
                "denoise": False,
                "normalize": False,
                "eq_preset": "custom",
                "eq_bands": [
                    {"frequency": 1000, "gain": 3.0, "q": 1.5},
                    {"frequency": 5000, "gain": -2.0, "q": 1.0},
                ],
            }
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        af = cmd[af_idx + 1]
        assert "equalizer=f=1000" in af
        assert "equalizer=f=5000" in af


class TestRestoreAudioCompression:
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_compression_custom(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {
                "denoise": False,
                "normalize": False,
                "compression": {
                    "threshold": -18,
                    "ratio": 4,
                    "attack": 10,
                    "release": 100,
                },
            }
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        af = cmd[af_idx + 1]
        assert "acompressor" in af
        assert "threshold=-18dB" in af
        assert "ratio=4" in af

    @pytest.mark.parametrize("preset", ["voice", "podcast", "broadcast", "gentle"])
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_compression_presets(
        self, mock_run: MagicMock, tmp_path: Path, preset: str
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "compression": {"preset": preset}}
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        assert "acompressor" in cmd[af_idx + 1]


class TestRestoreAudioDeEss:
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_de_ess_enabled(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {
                "denoise": False,
                "normalize": False,
                "de_ess": True,
                "de_ess_intensity": 0.8,
            }
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        assert "equalizer=f=6000" in cmd[af_idx + 1]


class TestRestoreAudioReverb:
    @pytest.mark.parametrize(
        "preset", ["small_room", "large_room", "hall", "cathedral", "plate"]
    )
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_reverb_presets(
        self, mock_run: MagicMock, tmp_path: Path, preset: str
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "reverb_preset": preset}
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        assert "aecho" in cmd[af_idx + 1]

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_reverb_none_skips(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "reverb_preset": "none"}
        )
        stage.process(ctx)
        mock_run.assert_not_called()


class TestRestoreAudioSilenceRemoval:
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_silence_removal(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {
                "denoise": False,
                "normalize": False,
                "remove_silence": True,
                "silence_threshold": -35,
                "min_silence_duration": 0.3,
            }
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        af = cmd[af_idx + 1]
        assert "silenceremove" in af
        assert "-35dB" in af


class TestRestoreAudioVoiceEnhancement:
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_enhance_clarity(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "enhance_clarity": True}
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        af = cmd[af_idx + 1]
        assert "highpass=f=80" in af
        assert "equalizer=f=3000" in af

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_enhance_warmth(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": False, "normalize": False, "enhance_warmth": True}
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        af = cmd[af_idx + 1]
        assert "equalizer=f=200" in af


class TestRestoreAudioNoiseStrength:
    @pytest.mark.parametrize(
        "strength,expected_nr",
        [("light", 10), ("moderate", 20), ("heavy", 40), ("auto", 25)],
    )
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_noise_reduction_strengths(
        self, mock_run: MagicMock, tmp_path: Path, strength: str, expected_nr: int
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = RestoreAudioStage(
            {"denoise": True, "normalize": False, "noise_reduction_strength": strength}
        )
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        af_idx = cmd.index("-af")
        assert f"afftdn=nr={expected_nr}" in cmd[af_idx + 1]


# ── ColorCorrectionStage ──────────────────────────────────────────────────────


class TestColorCorrectionStage:
    def test_skips_no_video(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = ColorCorrectionStage({})
        result = stage.process(ctx)
        assert result.processed_video is None

    def test_skips_default_params(self, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = ColorCorrectionStage({})
        result = stage.process(ctx)
        assert result.processed_video is None

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_brightness_contrast(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = ColorCorrectionStage({"brightness": 0.1, "contrast": 0.2})
        result = stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        assert "eq=" in cmd[vf_idx + 1]
        assert "brightness=0.1" in cmd[vf_idx + 1]
        assert result.processed_video == tmp_path / "color_corrected.mp4"

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_white_balance_preset(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = ColorCorrectionStage({"white_balance": "tungsten"})
        _result = stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        vf_idx = cmd.index("-vf")
        assert "colortemperature=temperature=3200" in cmd[vf_idx + 1]

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_temperature_overrides_wb(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = ColorCorrectionStage({"temperature": 4500, "white_balance": "tungsten"})
        _result = stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        vf_idx = cmd.index("-vf")
        assert "temperature=4500" in cmd[vf_idx + 1]


# ── FrameRateStage ────────────────────────────────────────────────────────────


class TestFrameRateStage:
    def test_skips_no_video(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = FrameRateStage({})
        result = stage.process(ctx)
        assert result.processed_video is None

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_simple_fps(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = FrameRateStage({"fps": 60})
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "fps=60" in cmd

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_interpolated_fps(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = FrameRateStage({"fps": 60, "interpolate": True})
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "minterpolate" in " ".join(cmd)


# ── SpeedStage ────────────────────────────────────────────────────────────────


class TestSpeedStage:
    def test_skips_no_video(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = SpeedStage({})
        result = stage.process(ctx)
        assert result.processed_video is None

    def test_skips_speed_1(self, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = SpeedStage({"speed": 1.0})
        result = stage.process(ctx)
        assert result.processed_video is None

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_speed_2x(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = SpeedStage({"speed": 2.0})
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-vf" in cmd
        assert "-af" in cmd
        vf_idx = cmd.index("-vf")
        af_idx = cmd.index("-af")
        assert "setpts=" in cmd[vf_idx + 1]
        assert "atempo" in cmd[af_idx + 1]

    def test_build_atempo_normal(self) -> None:
        result = SpeedStage._build_atempo(2.0)
        assert "atempo=2.0" in result

    def test_build_atempo_slow(self) -> None:
        result = SpeedStage._build_atempo(0.25)
        assert result.count("atempo=0.5") == 2

    def test_build_atempo_3x(self) -> None:
        result = SpeedStage._build_atempo(3.0)
        assert "atempo=2.0" in result
        assert "atempo=1.5" in result

    def test_build_atempo_4x(self) -> None:
        result = SpeedStage._build_atempo(4.0)
        assert result.count("atempo=2.0") == 2

    def test_build_atempo_extreme_slow(self) -> None:
        result = SpeedStage._build_atempo(0.1)
        # 0.1 requires multiple 0.5 chains: 0.5*0.5*0.4=0.1
        assert result.count("atempo=0.5") >= 2

    def test_build_atempo_10x(self) -> None:
        result = SpeedStage._build_atempo(10.0)
        # 10 = 2 * 2 * 2.5 → atempo=2.0,atempo=2.0,atempo=2.5
        assert result.count("atempo=2.0") >= 2


# ── PiPStage ─────────────────────────────────────────────────────────────────


class TestPiPStage:
    def test_skips_no_source(self, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = PiPStage({})
        result = stage.process(ctx)
        assert result.processed_video is None

    @patch("demodsl.models._validate_safe_path", side_effect=lambda v: v)
    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_pip_overlay(
        self, mock_run: MagicMock, _mock_safe: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        pip_src = tmp_path / "webcam.mp4"
        pip_src.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = PiPStage({"source": str(pip_src), "position": "top-left", "size": 0.2})
        result = stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-filter_complex" in cmd
        assert result.processed_video == tmp_path / "pip_composited.mp4"

    def test_pip_path_traversal(self, tmp_path: Path) -> None:
        """PiP source with path traversal should be rejected gracefully."""
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = PiPStage(
            {"source": "../../../etc/passwd", "position": "top-left", "size": 0.2}
        )
        result = stage.process(ctx)
        # Should skip without crashing
        assert result.processed_video is None or result.processed_video == video


# ── ThumbnailStage ────────────────────────────────────────────────────────────


class TestThumbnailStage:
    def test_skips_no_video(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = ThumbnailStage({})
        result = stage.process(ctx)
        assert "thumbnails" not in result.metadata

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_auto_thumbnail(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = ThumbnailStage({})
        with patch.object(ThumbnailStage, "_probe_duration", return_value=10.0):
            result = stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-ss" in cmd
        assert "-vframes" in cmd
        assert "thumbnails" in result.metadata

    @patch("demodsl.pipeline.stages.subprocess.run")
    def test_timestamp_thumbnail(self, mock_run: MagicMock, tmp_path: Path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        ctx = PipelineContext(workspace_root=tmp_path, raw_video=video)
        stage = ThumbnailStage({"thumbnails": [{"timestamp": 5.0, "format": "jpeg"}]})
        stage.process(ctx)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "5.0" in cmd


# ── ChapterStage ──────────────────────────────────────────────────────────────


class TestChapterStage:
    def test_skips_no_chapters(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = ChapterStage({})
        result = stage.process(ctx)
        assert "chapters" not in result.metadata

    def test_manual_chapters(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = ChapterStage(
            {
                "chapters": [
                    {"title": "Introduction", "timestamp": 0.0},
                    {"title": "Demo", "timestamp": 30.0},
                    {"title": "Conclusion", "timestamp": 120.0},
                ]
            }
        )
        result = stage.process(ctx)
        assert "chapters" in result.metadata
        assert len(result.metadata["chapters"]) == 3
        assert "chapters_file" in result.metadata
        # Check ffmetadata file exists
        meta_file = Path(result.metadata["chapters_file"])
        assert meta_file.exists()
        content = meta_file.read_text()
        assert ";FFMETADATA1" in content
        assert "Introduction" in content
        # Verify END[0] == START[1] and END[1] == START[2]
        assert "END=30000" in content
        assert "END=120000" in content

    def test_youtube_timestamps_generated(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = ChapterStage(
            {
                "chapters": [
                    {"title": "Start", "timestamp": 0.0},
                    {"title": "Middle", "timestamp": 65.0},
                ]
            }
        )
        result = stage.process(ctx)
        yt_file = Path(result.metadata["chapters_youtube"])
        assert yt_file.exists()
        content = yt_file.read_text()
        assert "0:00 Start" in content
        assert "1:05 Middle" in content

    def test_auto_chapters_from_scenarios(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        ctx.config = {
            "scenarios": [
                {"name": "Scene 1", "steps": [{}, {}, {}]},
                {"name": "Scene 2", "steps": [{}]},
            ]
        }
        ctx.metadata = {"step_timestamps": [0.0, 5.0, 10.0, 15.0]}
        stage = ChapterStage({"auto": True})
        result = stage.process(ctx)
        assert len(result.metadata["chapters"]) == 2
        assert result.metadata["chapters"][0]["title"] == "Scene 1"
        assert result.metadata["chapters"][1]["title"] == "Scene 2"


# ── Model validation tests ───────────────────────────────────────────────────


class TestNewModels:
    def test_voice_processing_new_fields(self) -> None:
        from demodsl.models import VoiceProcessing

        vp = VoiceProcessing(
            de_ess=True,
            de_ess_intensity=0.7,
            noise_reduction=True,
            noise_reduction_strength="heavy",
            min_silence_duration=0.8,
        )
        assert vp.de_ess is True
        assert vp.de_ess_intensity == 0.7
        assert vp.noise_reduction_strength == "heavy"
        assert vp.min_silence_duration == 0.8

    def test_compression_preset(self) -> None:
        from demodsl.models import Compression

        c = Compression(preset="podcast")
        assert c.preset == "podcast"

    def test_eq_band(self) -> None:
        from demodsl.models import EQBand

        band = EQBand(frequency=3000, gain=5.0, q=1.5)
        assert band.frequency == 3000
        assert band.gain == 5.0

    def test_audio_effects_typed_presets(self) -> None:
        from demodsl.models import AudioEffects

        ae = AudioEffects(eq_preset="podcast", reverb_preset="hall")
        assert ae.eq_preset == "podcast"
        assert ae.reverb_preset == "hall"

    def test_color_correction(self) -> None:
        from demodsl.models import ColorCorrection

        cc = ColorCorrection(
            brightness=0.1,
            contrast=0.2,
            saturation=1.5,
            gamma=1.2,
            white_balance="daylight",
            temperature=5600,
        )
        assert cc.brightness == 0.1
        assert cc.white_balance == "daylight"

    def test_speed_ramp(self) -> None:
        from demodsl.models import SpeedRamp

        sr = SpeedRamp(start_speed=1.0, end_speed=0.5, ease="ease-in-out")
        assert sr.start_speed == 1.0
        assert sr.end_speed == 0.5

    def test_pip_config(self) -> None:
        from demodsl.models import PictureInPicture

        pip = PictureInPicture(source="webcam.mp4", position="top-left", size=0.3)
        assert pip.source == "webcam.mp4"
        assert pip.size == 0.3

    def test_chapter_marker(self) -> None:
        from demodsl.models import ChapterMarker

        ch = ChapterMarker(title="Introduction", timestamp=0.0)
        assert ch.title == "Introduction"

    def test_step_new_fields(self) -> None:
        from demodsl.models import SpeedRamp, Step

        step = Step(
            action="click",
            locator={"type": "css", "value": "#btn"},
            speed=0.5,
            speed_ramp=SpeedRamp(start_speed=1.0, end_speed=0.5),
            freeze_duration=3.0,
            audio_offset=-0.5,
        )
        assert step.speed == 0.5
        assert step.freeze_duration == 3.0
        assert step.audio_offset == -0.5

    def test_thumbnail_new_fields(self) -> None:
        from demodsl.models import Thumbnail

        t = Thumbnail(auto=True, overlay_text="My Demo", format="webp")
        assert t.auto is True
        assert t.format == "webp"

    def test_social_export_typed_platform(self) -> None:
        from demodsl.models import SocialExport

        s = SocialExport(platform="instagram_reels", crop_mode="smart")
        assert s.platform == "instagram_reels"
        assert s.crop_mode == "smart"

    def test_video_config_new_fields(self) -> None:
        from demodsl.models import ColorCorrection, VideoConfig

        vc = VideoConfig(
            color_correction=ColorCorrection(brightness=0.1),
            frame_rate=30,
            speed=1.5,
        )
        assert vc.color_correction.brightness == 0.1
        assert vc.frame_rate == 30
        assert vc.speed == 1.5


# ── New post-effects tests ────────────────────────────────────────────────────


class TestNewPostEffects:
    def test_color_grade_noir(self) -> None:
        from demodsl.effects.post_effects import ColorGradeEffect

        effect = ColorGradeEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"preset": "noir"})
        clip.transform.assert_called_once()

    def test_color_grade_pastel(self) -> None:
        from demodsl.effects.post_effects import ColorGradeEffect

        effect = ColorGradeEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"preset": "pastel"})
        clip.transform.assert_called_once()

    def test_color_grade_high_contrast(self) -> None:
        from demodsl.effects.post_effects import ColorGradeEffect

        effect = ColorGradeEffect()
        clip = MagicMock()
        clip.duration = 5.0
        effect.apply(clip, {"preset": "high_contrast"})
        clip.transform.assert_called_once()

    def test_speed_ramp_effect(self) -> None:
        from demodsl.effects.post_effects import SpeedRampEffect

        effect = SpeedRampEffect()
        clip = MagicMock()
        clip.duration = 5.0
        _result = effect.apply(
            clip, {"start_speed": 1.0, "end_speed": 0.5, "ease": "linear"}
        )
        clip.transform.assert_called_once()

    def test_freeze_frame_effect(self) -> None:
        from demodsl.effects.post_effects import FreezeFrameEffect

        effect = FreezeFrameEffect()
        clip = MagicMock()
        clip.duration = 5.0
        _result = effect.apply(clip, {"freeze_duration": 2.0})
        clip.transform.assert_called_once()

    def test_reverse_effect(self) -> None:
        from demodsl.effects.post_effects import ReverseEffect

        effect = ReverseEffect()
        clip = MagicMock()
        clip.duration = 5.0
        _result = effect.apply(clip, {})
        clip.transform.assert_called_once()


# ── Effects registry tests ────────────────────────────────────────────────────


class TestNewEffectsRegistered:
    def test_new_effects_in_registry(self) -> None:
        from demodsl.effects.post_effects import register_all_post_effects
        from demodsl.effects.registry import EffectRegistry

        registry = EffectRegistry()
        register_all_post_effects(registry)
        for name in ("speed_ramp", "freeze_frame", "reverse"):
            assert registry.is_post_effect(name), f"{name} not registered"


# ── Effect type validation ────────────────────────────────────────────────────


class TestNewEffectTypes:
    @pytest.mark.parametrize("effect_type", ["speed_ramp", "freeze_frame", "reverse"])
    def test_new_types_valid(self, effect_type: str) -> None:
        from demodsl.models import Effect

        effect = Effect(type=effect_type)
        assert effect.type == effect_type


# ── Social export tests ───────────────────────────────────────────────────────


class TestSocialExport:
    def test_social_profiles_defined(self) -> None:
        from demodsl.orchestrators.export import ExportOrchestrator

        profiles = ExportOrchestrator._SOCIAL_PROFILES
        assert "youtube" in profiles
        assert "instagram_reels" in profiles
        assert "tiktok" in profiles
        assert "twitter" in profiles
        assert "linkedin" in profiles

    def test_instagram_is_portrait(self) -> None:
        from demodsl.orchestrators.export import ExportOrchestrator

        profile = ExportOrchestrator._SOCIAL_PROFILES["instagram_reels"]
        assert profile["resolution"] == "1080x1920"
        assert profile["aspect_ratio"] == "9:16"

    def test_export_social_no_config(self, tmp_path: Path) -> None:
        from demodsl.models import DemoConfig, Metadata
        from demodsl.orchestrators.export import ExportOrchestrator

        config = DemoConfig(metadata=Metadata(title="Test"))
        orch = ExportOrchestrator(config)
        results = orch.export_social(tmp_path / "video.mp4", tmp_path)
        assert results == []


# ── Integration: full chain with new stages ──────────────────────────────────


class TestFullChainWithNewStages:
    def test_chain_with_new_stages(self) -> None:
        stages = [
            {"stage_type": "restore_audio", "params": {}},
            {"stage_type": "color_correction", "params": {}},
            {"stage_type": "edit_video", "params": {}},
            {"stage_type": "speed", "params": {"speed": 1.5}},
            {"stage_type": "frame_rate", "params": {"fps": 30}},
            {"stage_type": "chapters", "params": {"auto": True}},
            {"stage_type": "thumbnail", "params": {}},
            {"stage_type": "optimize", "params": {}},
        ]
        head = build_chain(stages)
        assert head is not None
        assert head.name == "restore_audio"
        # Count chain length
        count = 1
        node = head
        while node._next:
            node = node._next
            count += 1
        assert count == 8


# ── Negative / Edge-case Tests ───────────────────────────────────────────────


class TestNegativeEdgeCases:
    def test_speed_too_low_clamps(self) -> None:
        """Speed values below 0.5 should still produce valid atempo chain."""
        result = SpeedStage._build_atempo(0.01)
        parts = result.split(",")
        for p in parts:
            val = float(p.split("=")[1])
            assert 0.5 <= val <= 2.0

    def test_speed_too_high_chains(self) -> None:
        """Speed values above 2.0 should chain multiple atempo filters."""
        result = SpeedStage._build_atempo(100.0)
        parts = result.split(",")
        assert len(parts) > 1
        for p in parts:
            val = float(p.split("=")[1])
            assert 0.5 <= val <= 2.0

    def test_chapters_auto_without_scenarios(self, tmp_path: Path) -> None:
        """Auto chapters with no scenarios should produce empty chapter list."""
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = ChapterStage({"auto": True})
        result = stage.process(ctx)
        chapters = result.metadata.get("chapters", [])
        assert chapters == []

    def test_social_export_rejects_manual_crop(self) -> None:
        """crop_mode='manual' should be rejected by Pydantic validation."""
        from pydantic import ValidationError
        from demodsl.models import SocialExport

        with pytest.raises(ValidationError):
            SocialExport(platform="instagram_reels", crop_mode="manual")


# ── Step-level speed field wiring tests ───────────────────────────────────────


class TestStepSpeedWiring:
    """Test that step.speed, step.speed_ramp, step.freeze_duration are
    properly injected as post-effects by _collect_post_effects."""

    def _make_orchestrator(self):
        from demodsl.effects.registry import EffectRegistry
        from demodsl.effects.post_effects import register_all_post_effects
        from demodsl.orchestrators.scenario import ScenarioOrchestrator

        config = MagicMock()
        config.scenarios = []
        registry = EffectRegistry()
        register_all_post_effects(registry)
        orch = ScenarioOrchestrator.__new__(ScenarioOrchestrator)
        orch.config = config
        orch._effects = registry
        orch.step_post_effects = []
        return orch

    def test_step_speed_injects_speed_ramp(self) -> None:
        from demodsl.models import Step

        orch = self._make_orchestrator()
        step = Step(action="screenshot", speed=2.0)
        orch._collect_post_effects([], step)
        assert len(orch.step_post_effects) == 1
        collected = orch.step_post_effects[0]
        assert len(collected) == 1
        assert collected[0][0] == "speed_ramp"
        assert collected[0][1]["start_speed"] == 2.0
        assert collected[0][1]["end_speed"] == 2.0

    def test_step_speed_1x_no_injection(self) -> None:
        from demodsl.models import Step

        orch = self._make_orchestrator()
        step = Step(action="screenshot", speed=1.0)
        orch._collect_post_effects([], step)
        collected = orch.step_post_effects[0]
        assert len(collected) == 0

    def test_step_speed_ramp_injects(self) -> None:
        from demodsl.models import SpeedRamp, Step

        orch = self._make_orchestrator()
        step = Step(
            action="screenshot",
            speed_ramp=SpeedRamp(start_speed=0.5, end_speed=3.0, ease="ease-in"),
        )
        orch._collect_post_effects([], step)
        collected = orch.step_post_effects[0]
        assert len(collected) == 1
        assert collected[0][0] == "speed_ramp"
        assert collected[0][1]["start_speed"] == 0.5
        assert collected[0][1]["end_speed"] == 3.0
        assert collected[0][1]["ease"] == "ease-in"

    def test_step_freeze_duration_injects(self) -> None:
        from demodsl.models import Step

        orch = self._make_orchestrator()
        step = Step(action="screenshot", freeze_duration=2.5)
        orch._collect_post_effects([], step)
        collected = orch.step_post_effects[0]
        assert len(collected) == 1
        assert collected[0][0] == "freeze_frame"
        assert collected[0][1]["freeze_duration"] == 2.5

    def test_step_freeze_zero_no_injection(self) -> None:
        from demodsl.models import Step

        orch = self._make_orchestrator()
        step = Step(action="screenshot", freeze_duration=0.0)
        orch._collect_post_effects([], step)
        collected = orch.step_post_effects[0]
        assert len(collected) == 0

    def test_step_combo_speed_and_freeze(self) -> None:
        from demodsl.models import Step

        orch = self._make_orchestrator()
        step = Step(action="screenshot", speed=2.0, freeze_duration=1.5)
        orch._collect_post_effects([], step)
        collected = orch.step_post_effects[0]
        assert len(collected) == 2
        names = [c[0] for c in collected]
        assert "speed_ramp" in names
        assert "freeze_frame" in names

    def test_step_no_speed_fields_empty(self) -> None:
        from demodsl.models import Step

        orch = self._make_orchestrator()
        step = Step(action="screenshot")
        orch._collect_post_effects([], step)
        collected = orch.step_post_effects[0]
        assert len(collected) == 0

    def test_backward_compat_no_step_arg(self) -> None:
        """Calling without step arg still works (backward compat)."""
        orch = self._make_orchestrator()
        orch._collect_post_effects([])
        collected = orch.step_post_effects[0]
        assert len(collected) == 0
