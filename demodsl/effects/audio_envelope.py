"""Amplitude envelope extraction — drives the live avatar's mouth.

Decodes an audio file to mono PCM via ffmpeg and computes a smoothed,
normalized RMS envelope sampled at the video frame rate. Pure stdlib
(struct/array) — no numpy/audioop dependency.
"""

from __future__ import annotations

import array
import logging
import math
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 8000  # plenty for an amplitude envelope


def amplitude_envelope(
    audio: Path, *, fps: int = 30, attack: float = 0.55, decay: float = 0.30
) -> list[float]:
    """Per-video-frame loudness of *audio*, normalized to 0..1.

    ``attack``/``decay`` are smoothing factors (higher = snappier): the mouth
    should open fast on onsets and close a bit slower — that asymmetry is
    what reads as natural speech at 30 fps.

    Returns ``[]`` if the file is missing or ffmpeg fails (callers treat an
    empty envelope as "idle avatar").
    """
    audio = Path(audio)
    if not audio.exists():
        return []
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(audio),
        "-ac",
        "1",
        "-ar",
        str(_SAMPLE_RATE),
        "-f",
        "s16le",
        "-",
    ]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=120, check=True).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("amplitude_envelope: ffmpeg decode failed (%s)", exc)
        return []
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if not samples:
        return []

    per_frame = _SAMPLE_RATE // fps
    rms: list[float] = []
    for i in range(0, len(samples), per_frame):
        chunk = samples[i : i + per_frame]
        if not chunk:
            break
        acc = 0
        for s in chunk:
            acc += s * s
        rms.append(math.sqrt(acc / len(chunk)))

    peak = max(rms) or 1.0
    # Soft-knee normalization: sqrt lifts quiet speech so the mouth doesn't
    # only twitch on shouted syllables.
    norm = [math.sqrt(min(1.0, v / peak)) for v in rms]

    out: list[float] = []
    level = 0.0
    for v in norm:
        k = attack if v > level else decay
        level += (v - level) * k
        out.append(round(level, 3))
    return out
