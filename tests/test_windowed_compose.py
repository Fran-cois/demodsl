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
    _concat_chunks(chunks, joined, fps=FPS)

    assert _duration(joined) == pytest.approx(_duration(clip), abs=0.15)
    assert _frames(joined) == pytest.approx(_frames(clip), abs=2)


def test_concat_keeps_resolution(clip, tmp_path):
    cut = tmp_path / "cut.mp4"
    _cut_segment(clip, cut, 0.0, 2.0)
    joined = tmp_path / "joined.mp4"
    _concat_chunks([cut, cut], joined, fps=FPS)
    assert _probe(joined, "stream=width,height") == _probe(clip, "stream=width,height")


def test_a_failing_cut_raises(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        _cut_segment(tmp_path / "missing.mp4", tmp_path / "out.mp4", 0.0, 1.0)


def _make_clip_with(path, *, fps, pix_fmt, duration):
    """Un clip aux parametres deliberement differents de la decoupe ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=320x180:rate={fps}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            pix_fmt,
            "-video_track_timescale",
            "90000",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_concat_normalise_des_troncons_heterogenes(clip, tmp_path):
    """Le troncon rendu par Remotion n'a ni le meme fps ni le meme pix_fmt.

    Un stream-copy laissait le demuxer concat produire une duree fantaisiste :
    47 s sorties a 6.6 s en production. Ce cas manquait, seuls des troncons
    decoupes par ffmpeg etaient testes.
    """
    avant = tmp_path / "avant.mp4"
    _cut_segment(clip, avant, 0.0, 2.0)

    # Ce que Remotion produit : 30 fps, plage complete, timescale 90000.
    fenetre = tmp_path / "fenetre.mp4"
    _make_clip_with(fenetre, fps=30, pix_fmt="yuvj420p", duration=1.0)

    apres = tmp_path / "apres.mp4"
    _cut_segment(clip, apres, 2.0, 4.0)

    joined = tmp_path / "joined.mp4"
    _concat_chunks([avant, fenetre, apres], joined, fps=FPS)

    assert _duration(joined) == pytest.approx(5.0, abs=0.15)


def test_concat_impose_un_seul_pix_fmt(clip, tmp_path):
    fenetre = tmp_path / "fenetre.mp4"
    _make_clip_with(fenetre, fps=30, pix_fmt="yuvj420p", duration=1.0)
    cut = tmp_path / "cut.mp4"
    _cut_segment(clip, cut, 0.0, 1.0)

    joined = tmp_path / "joined.mp4"
    _concat_chunks([cut, fenetre], joined, fps=FPS)

    assert _probe(joined, "stream=pix_fmt") == "yuv420p"
