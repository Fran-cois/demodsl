"""Tests for the blank lead-in trimmed off a raw scenario recording."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from demodsl.orchestrators.scenario import ScenarioOrchestrator

_has_ffmpeg = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

pytestmark = pytest.mark.skipif(not _has_ffmpeg, reason="ffmpeg not available")


def _clip(path: Path, blank_seconds: float, content_seconds: float) -> Path:
    """Une vidéo : *blank_seconds* de blanc uni, puis une mire contrastée."""
    blank = path.with_stem("blank")
    content = path.with_stem("content")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=white:s=320x240:r=10:d={blank_seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "5",
            str(blank),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=s=320x240:r=10:d={content_seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "5",
            str(content),
        ],
        check=True,
    )
    listing = path.with_suffix(".txt")
    listing.write_text(f"file '{blank}'\nfile '{content}'\n")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(path),
        ],
        check=True,
    )
    return path


def _screencast(path: Path, blank_seconds: float, content_seconds: float) -> Path:
    """Une capture façon Playwright : VP8, une seule image-clé, en tête du fichier."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=white:s=320x240:r=10:d={blank_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=s=320x240:r=10:d={content_seconds}",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libvpx",
            "-b:v",
            "500k",
            "-deadline",
            "realtime",
            "-g",
            "9999",
            "-keyint_min",
            "9999",
            str(path),
        ],
        check=True,
    )
    return path


def _duration(video: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def test_blank_lead_in_is_measured(tmp_path):
    video = _clip(tmp_path / "v.mp4", blank_seconds=3.0, content_seconds=2.0)

    assert ScenarioOrchestrator.blank_lead_in(video) == pytest.approx(3.0, abs=0.3)


def test_a_clip_that_starts_painted_has_no_lead_in(tmp_path):
    video = _clip(tmp_path / "v.mp4", blank_seconds=0.1, content_seconds=2.0)

    assert ScenarioOrchestrator.blank_lead_in(video) < 0.3


def test_measurement_is_capped(tmp_path):
    video = _clip(tmp_path / "v.mp4", blank_seconds=4.0, content_seconds=1.0)

    assert ScenarioOrchestrator.blank_lead_in(video, max_seconds=2.0) <= 2.0


def test_missing_file_reports_no_lead_in(tmp_path):
    assert ScenarioOrchestrator.blank_lead_in(tmp_path / "nope.mp4") == 0.0


def test_a_long_blank_head_is_cut_off(tmp_path, caplog):
    import logging

    video = _clip(tmp_path / "v.mp4", blank_seconds=3.0, content_seconds=3.0)

    with caplog.at_level(logging.WARNING, logger="demodsl.orchestrators.scenario"):
        cleaned = ScenarioOrchestrator._clean_leading_frames(video)

    assert cleaned is not None
    assert _duration(cleaned) == pytest.approx(3.0, abs=0.5)
    assert ScenarioOrchestrator.blank_lead_in(cleaned) < 0.3
    assert "Blank page filmed" in caplog.text


def test_a_painted_clip_only_loses_the_usual_few_frames(tmp_path, caplog):
    import logging

    video = _clip(tmp_path / "v.mp4", blank_seconds=0.1, content_seconds=4.0)
    before = _duration(video)

    with caplog.at_level(logging.WARNING, logger="demodsl.orchestrators.scenario"):
        cleaned = ScenarioOrchestrator._clean_leading_frames(video)

    assert cleaned is not None
    assert before - _duration(cleaned) < 1.0
    assert "Blank page filmed" not in caplog.text


def test_a_screencast_without_a_keyframe_at_the_cut_is_still_trimmed(tmp_path):
    """Le cas de production : la capture Playwright n'a qu'une image-clé.

    Un ``-c copy`` recule alors la coupe jusqu'à cette image-clé, en tête du
    fichier — il ne retire rien, sans erreur, et la démo s'ouvrait sur trois
    secondes de blanc.
    """
    video = _screencast(tmp_path / "v.webm", blank_seconds=3.0, content_seconds=3.0)
    assert ScenarioOrchestrator.blank_lead_in(video) == pytest.approx(3.0, abs=0.3)

    cleaned = ScenarioOrchestrator._clean_leading_frames(video)

    assert cleaned is not None
    assert ScenarioOrchestrator.blank_lead_in(cleaned) < 0.3
    assert _duration(cleaned) == pytest.approx(3.0, abs=0.5)


def test_the_cut_never_reaches_past_the_pre_roll(tmp_path, caplog):
    """Une page dont le premier rendu est un aplat reste « blanche » a la mesure.

    Couper jusque-la mange du temps d'etape : la narration, placee a partir de
    la premiere etape, se retrouve en retard sur l'image et deborde de la fin.
    """
    import logging

    video = _clip(tmp_path / "v.mp4", blank_seconds=5.0, content_seconds=3.0)
    assert ScenarioOrchestrator.blank_lead_in(video) == pytest.approx(5.0, abs=0.3)

    with caplog.at_level(logging.WARNING, logger="demodsl.orchestrators.scenario"):
        cleaned = ScenarioOrchestrator._clean_leading_frames(video, maximum=2.0)

    assert cleaned is not None
    assert _duration(cleaned) == pytest.approx(6.0, abs=0.5)  # 8.0 - 2.0, pas 3.0
    assert "trimming stops there" in caplog.text


def test_a_short_pre_roll_still_gets_its_usual_minimum(tmp_path):
    video = _clip(tmp_path / "v.mp4", blank_seconds=0.1, content_seconds=4.0)
    before = _duration(video)

    cleaned = ScenarioOrchestrator._clean_leading_frames(video, maximum=0.0)

    assert cleaned is not None
    assert before - _duration(cleaned) < 1.0
