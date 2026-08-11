"""Central H.264 encoding settings.

A single render chains several full-length re-encodes (global speed, freeze
pauses, concat, watermark, subtitle burn, final export). Each one used a
hardcoded ``-preset medium -crf 18``, which on a 2-vCPU worker made encoding
the dominant cost of the pipeline. Screen recordings are near-static, so a
faster preset and a slightly higher CRF cost almost nothing visually.

Every knob is env-tunable so a quality-sensitive deployment can restore the
old behaviour without a code change:

    DEMODSL_X264_PRESET=medium DEMODSL_X264_CRF=18 DEMODSL_DEBLOCK=full
"""

from __future__ import annotations

import os

DEFAULT_PRESET = "veryfast"
DEFAULT_CRF = "21"

# Deblocking applied when transcoding the low-bitrate VP8 screencast.
# ``spp`` works in the DCT domain and its cost grows steeply with `quality`:
# quality=4 (the previous hardcoded value) is several times slower than the
# encode it feeds.
_DEBLOCK_PROFILES = {
    "off": [],
    "fast": ["spp=quality=1:qp=2"],
    "full": ["spp=quality=4:qp=2", "hqdn3d=3:2:3:2"],
}
DEFAULT_DEBLOCK = "fast"


def x264_preset() -> str:
    return os.environ.get("DEMODSL_X264_PRESET") or DEFAULT_PRESET


def x264_crf() -> str:
    return os.environ.get("DEMODSL_X264_CRF") or DEFAULT_CRF


def x264_args(
    *,
    pix_fmt: str | None = "yuv420p",
    faststart: bool = False,
) -> list[str]:
    """ffmpeg arguments for the video stream of an intermediate or final file."""
    args = [
        "-c:v",
        "libx264",
        "-preset",
        x264_preset(),
        "-crf",
        x264_crf(),
    ]
    if pix_fmt:
        args += ["-pix_fmt", pix_fmt]
    if faststart:
        args += ["-movflags", "+faststart"]
    return args


def deblock_filters(source_suffix: str) -> list[str]:
    """ffmpeg ``-vf`` entries to clean up a VP8 screencast, or ``[]``."""
    if source_suffix.lower() not in (".webm", ".mkv"):
        return []
    profile = (os.environ.get("DEMODSL_DEBLOCK") or DEFAULT_DEBLOCK).lower()
    return list(_DEBLOCK_PROFILES.get(profile, _DEBLOCK_PROFILES[DEFAULT_DEBLOCK]))


def is_h264(path) -> bool:
    """True when *path* already holds an H.264 video stream (so it can be copied)."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "h264"
