"""Le découpage/recollage ne doit pas décaler la timeline.

Les fenêtres sont replacées sur les timestamps de la narration : une jointure
qui glisse d'une demi-seconde décale la voix sur toute la fin de la démo.
"""

import shutil
import subprocess

import pytest

from demodsl.orchestrators.post_processing import _concat_chunks, _cut_segment

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)

FPS = 30
DURATION = 6.0


def _make_clip(path):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={DURATION}:size=320x180:rate={FPS}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _probe(path, entries):
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            entries,
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _duration(path):
    return float(_probe(path, "format=duration").splitlines()[0])


def _frames(path):
    return int(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=nb_read_frames",
                "-of",
                "csv=p=0",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "source.mp4"
    _make_clip(path)
    return path


def test_a_cut_has_the_requested_duration(clip, tmp_path):
    cut = tmp_path / "cut.mp4"
    _cut_segment(clip, cut, 1.0, 3.0)
    assert _duration(cut) == pytest.approx(2.0, abs=0.1)


def test_round_trip_preserves_the_timeline(clip, tmp_path):
    """Cut into three windows, glue them back: same length, same frame count."""
    windows = [(0.0, 2.0), (2.0, 4.5), (4.5, DURATION)]
    chunks = []
    for i, (start, end) in enumerate(windows):
        cut = tmp_path / f"cut_{i}.mp4"
        _cut_segment(clip, cut, start, end)
        chunks.append(cut)

    joined = tmp_path / "joined.mp4"
    _concat_chunks(chunks, joined)

    assert _duration(joined) == pytest.approx(_duration(clip), abs=0.15)
    assert _frames(joined) == pytest.approx(_frames(clip), abs=2)


def test_concat_keeps_resolution(clip, tmp_path):
    cut = tmp_path / "cut.mp4"
    _cut_segment(clip, cut, 0.0, 2.0)
    joined = tmp_path / "joined.mp4"
    _concat_chunks([cut, cut], joined)
    assert _probe(joined, "stream=width,height") == _probe(clip, "stream=width,height")


def test_a_failing_cut_raises(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        _cut_segment(tmp_path / "missing.mp4", tmp_path / "out.mp4", 0.0, 1.0)
