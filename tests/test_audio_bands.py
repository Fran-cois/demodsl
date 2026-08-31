"""Tests for demodsl.effects.audio_bands (frequency-band envelope extraction)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from demodsl.effects import audio_bands


def _pcm_from_tone(freq_hz: float, duration_s: float) -> bytes:
    sample_rate = audio_bands._SAMPLE_RATE
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    tone = (0.8 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
    return tone.tobytes()


class TestAudioBandEnvelope:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert audio_bands.audio_band_envelope(tmp_path / "nope.mp3") == []

    def test_survives_a_broken_decode(self) -> None:
        with (
            patch.object(audio_bands.Path, "exists", return_value=True),
            patch.object(
                audio_bands.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
            ),
        ):
            assert audio_bands.audio_band_envelope(Path("n.mp3")) == []

    def test_empty_pcm_returns_empty(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"")
        with (
            patch.object(audio_bands.Path, "exists", return_value=True),
            patch.object(audio_bands.subprocess, "run", return_value=completed),
        ):
            assert audio_bands.audio_band_envelope(Path("silence.mp3")) == []

    def test_one_row_per_frame_all_bands_bounded(self) -> None:
        pcm = _pcm_from_tone(440.0, duration_s=1.0)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=pcm)
        with (
            patch.object(audio_bands.Path, "exists", return_value=True),
            patch.object(audio_bands.subprocess, "run", return_value=completed),
        ):
            envelope = audio_bands.audio_band_envelope(Path("music.mp3"), fps=30, n_bands=16)

        assert len(envelope) == pytest.approx(30, abs=2)
        assert all(len(row) == 16 for row in envelope)
        assert all(0.0 <= v <= 1.0 for row in envelope for v in row)

    def test_low_tone_lights_up_low_bands_more(self) -> None:
        pcm = _pcm_from_tone(80.0, duration_s=1.0)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=pcm)
        with (
            patch.object(audio_bands.Path, "exists", return_value=True),
            patch.object(audio_bands.subprocess, "run", return_value=completed),
        ):
            envelope = audio_bands.audio_band_envelope(Path("bass.mp3"), fps=30, n_bands=16)

        matrix = np.array(envelope)
        avg_per_band = matrix.mean(axis=0)
        assert avg_per_band[:4].mean() > avg_per_band[-4:].mean()

    def test_high_tone_lights_up_high_bands_more(self) -> None:
        pcm = _pcm_from_tone(8000.0, duration_s=1.0)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=pcm)
        with (
            patch.object(audio_bands.Path, "exists", return_value=True),
            patch.object(audio_bands.subprocess, "run", return_value=completed),
        ):
            envelope = audio_bands.audio_band_envelope(Path("treble.mp3"), fps=30, n_bands=16)

        matrix = np.array(envelope)
        avg_per_band = matrix.mean(axis=0)
        assert avg_per_band[-4:].mean() > avg_per_band[:4].mean()
