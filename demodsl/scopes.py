"""Video scope generation (waveform, histogram, vectorscope, RGB parade).

OpenShot shows these live while editing; this headless renderer generates
them on demand from an already-rendered frame instead, via ffmpeg's own
native scope filters — a verification/QA tool for judging exposure, spotting
clipped highlights, comparing color channels and checking skin tones after a
color-grading pass (``color_wheels``/``lut``/``color_correction`` stages).
"""

from __future__ import annotations

from pathlib import Path

from demodsl.effects._ffmpeg import run_ffmpeg

SCOPE_TYPES = ("waveform", "histogram", "vectorscope", "rgb_parade")


def _scope_filter(scope: str) -> str:
    if scope == "waveform":
        # Luma-only waveform: brightness distribution across the frame width.
        return "format=yuv420p,waveform=components=1:display=stack:envelope=peak"
    if scope == "rgb_parade":
        # Convert to planar RGB first so waveform's components map to R/G/B
        # (they otherwise map to whatever the source pixel format's planes are).
        return "format=gbrp,waveform=components=7:display=parade:envelope=peak"
    if scope == "histogram":
        return "format=gbrp,histogram=display_mode=parade"
    if scope == "vectorscope":
        # graticule=green draws the standard broadcast-safe hexagon + a
        # built-in skin-tone reference line (m=color3).
        return "vectorscope=graticule=green:m=color3"
    raise ValueError(f"Unknown scope type: {scope!r}. Must be one of {SCOPE_TYPES}.")


def render_scope(video: Path, *, timestamp: float, scope: str, output: Path) -> Path:
    """Render one video scope for the frame at *timestamp* seconds into *output* (PNG)."""
    if scope not in SCOPE_TYPES:
        raise ValueError(f"Unknown scope type: {scope!r}. Must be one of {SCOPE_TYPES}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, timestamp)),
        "-i",
        str(video),
        "-vf",
        _scope_filter(scope),
        "-frames:v",
        "1",
        str(output),
    ]
    run_ffmpeg(cmd, timeout=60, context=f"scope:{scope}")
    return output


def render_all_scopes(
    video: Path, *, timestamp: float, output_dir: Path, stem: str = "scope"
) -> dict[str, Path]:
    """Render every scope type for the same frame. Returns ``{scope_name: path}``."""
    return {
        scope: render_scope(
            video, timestamp=timestamp, scope=scope, output=output_dir / f"{stem}_{scope}.png"
        )
        for scope in SCOPE_TYPES
    }
