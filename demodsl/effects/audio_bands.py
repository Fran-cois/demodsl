"""Frequency-band amplitude envelope extraction for the Audio Visualization overlay.

Decodes audio to mono PCM via ffmpeg, then computes one short-time FFT per
video frame (hop = sample_rate / fps, mirroring
:func:`demodsl.effects.audio_envelope.amplitude_envelope`) and buckets the
magnitude spectrum into ``n_bands`` logarithmically-spaced bands — bass gets
more visual resolution than treble, which is what a music-reactive graphic
should look like. Same STFT/geomspace bucketing approach as
demodsl-blender's ``fx_scene.py`` audio spectrum.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 22050  # plenty of spectral resolution for a visualizer, decodes fast
_FFT_SIZE = 2048
_MIN_FREQ_HZ = 30.0


def audio_band_envelope(
    audio: Path,
    *,
    fps: int = 30,
    n_bands: int = 24,
    attack: float = 0.6,
    decay: float = 0.35,
) -> list[list[float]]:
    """Per-video-frame frequency-band amplitudes of *audio*, each 0..1.

    Returns one row per frame, each row ``n_bands`` floats (low to high
    frequency). Returns ``[]`` if the file is missing or ffmpeg fails —
    callers treat an empty envelope as a silent/idle visualizer.
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
        "f32le",
        "-",
    ]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=120, check=True).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("audio_band_envelope: ffmpeg decode failed (%s)", exc)
        return []
    samples = np.frombuffer(raw, dtype=np.float32)
    if samples.size == 0:
        return []

    hop = max(1, _SAMPLE_RATE // fps)
    window = np.hanning(_FFT_SIZE).astype(np.float32)
    freqs = np.fft.rfftfreq(_FFT_SIZE, d=1.0 / _SAMPLE_RATE)
    edges = np.geomspace(_MIN_FREQ_HZ, _SAMPLE_RATE / 2.0, n_bands + 1)
    bin_edges = np.searchsorted(freqs, edges)

    n_frames = max(1, samples.size // hop)
    frames: list[np.ndarray] = []
    for i in range(n_frames):
        start = i * hop
        chunk = samples[start : start + _FFT_SIZE]
        if chunk.size == 0:
            break
        if chunk.size < _FFT_SIZE:
            chunk = np.pad(chunk, (0, _FFT_SIZE - chunk.size))
        spectrum = np.abs(np.fft.rfft(chunk * window))
        bands = np.zeros(n_bands, dtype=np.float32)
        for b in range(n_bands):
            lo, hi = int(bin_edges[b]), max(int(bin_edges[b]) + 1, int(bin_edges[b + 1]))
            bands[b] = spectrum[lo:hi].mean() if hi > lo else 0.0
        frames.append(bands)

    if not frames:
        return []
    matrix = np.stack(frames)
    peak = float(matrix.max()) or 1.0
    # Soft-knee normalization (same rationale as amplitude_envelope): lifts
    # quiet passages so bars aren't only alive on the loudest hits.
    norm = np.sqrt(np.clip(matrix / peak, 0.0, 1.0))

    # Per-band attack/decay smoothing — rises fast, falls slower, which reads
    # as a real VU meter rather than a flickery raw FFT.
    out = np.zeros_like(norm)
    level = np.zeros(n_bands, dtype=np.float32)
    for i in range(norm.shape[0]):
        v = norm[i]
        k = np.where(v > level, attack, decay)
        level = level + (v - level) * k
        out[i] = level

    return [[round(float(x), 3) for x in row] for row in out]
