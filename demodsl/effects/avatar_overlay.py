"""Avatar overlay — composites avatar video clip onto the main video."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Position offsets from edges (pixels)
_MARGIN = 20


def composite_avatar(
    video_path: Path,
    avatar_clips: dict[int, Path],
    step_timestamps: list[float],
    narration_durations: dict[int, float],
    output_path: Path,
    *,
    position: str = "bottom-right",
    size: int = 120,
    background: str = "rgba(0,0,0,0.5)",
    show_subtitle: bool = False,
    subtitle_font_size: int = 18,
    subtitle_font_color: str = "#FFFFFF",
    subtitle_bg_color: str = "rgba(0,0,0,0.7)",
    narration_texts: dict[int, str] | None = None,
) -> Path:
    """Overlay avatar clips onto the main video at narration timestamps.

    Uses ffmpeg filter_complex to overlay each avatar clip at the right time.

    Args:
        video_path: Source video file.
        avatar_clips: Mapping of step_index → avatar clip path.
        step_timestamps: Timestamp (seconds) for each step.
        narration_durations: Duration (seconds) of narration for each step.
        output_path: Where to write the composited video.
        position: Corner placement.
        size: Avatar size in pixels.
        background: Background color (unused for VP9 alpha, kept for config).

    Returns:
        Path to the composited video.
    """
    if not avatar_clips:
        logger.info("No avatar clips to composite")
        return video_path

    # Get video dimensions via ffprobe
    width, height = _get_video_dimensions(video_path)

    # Calculate overlay position
    x, y = _calc_position(position, width, height, size)

    # Build ffmpeg command with multiple overlays
    cmd = ["ffmpeg", "-y", "-i", str(video_path)]

    # Add each avatar clip as an input, with -itsoffset to delay start
    sorted_steps = sorted(avatar_clips.keys())
    start_times: list[float] = []
    for step_idx in sorted_steps:
        start_t = step_timestamps[step_idx] if step_idx < len(step_timestamps) else 0.0
        start_times.append(start_t)
        cmd += ["-itsoffset", f"{start_t:.3f}", "-i", str(avatar_clips[step_idx])]

    # Build filter_complex chain
    filters = []
    prev_label = "[0:v]"

    canvas_size = int(size * 1.4)

    for i, step_idx in enumerate(sorted_steps):
        input_idx = i + 1  # 0 is the main video
        start_t = start_times[i]
        duration = narration_durations.get(step_idx, 3.0)
        end_t = start_t + duration

        # Scale avatar clip to target size
        scale_label = f"[scaled{i}]"
        filters.append(
            f"[{input_idx}:v]scale={canvas_size}:{canvas_size}:flags=lanczos,"
            f"format=yuva420p{scale_label}"
        )

        # Overlay with enable between timestamps
        out_label = f"[ov{i}]" if i < len(sorted_steps) - 1 else "[out]"
        # If this is the last overlay AND we need drawtext, use intermediate label
        needs_drawtext = show_subtitle and narration_texts
        if needs_drawtext and i == len(sorted_steps) - 1:
            out_label = f"[ov{i}]"
        filters.append(
            f"{prev_label}{scale_label}overlay={x}:{y}"
            f":enable='between(t,{start_t:.2f},{end_t:.2f})'"
            f":format=auto:eof_action=pass{out_label}"
        )
        prev_label = out_label

    # Add drawtext filters for narration text below avatar box
    if show_subtitle and narration_texts:
        text_x, text_y, text_w = _calc_text_position(
            position, width, height, size, subtitle_font_size,
        )
        # Collect steps that have narration text
        dt_steps = [(i, si) for i, si in enumerate(sorted_steps)
                     if narration_texts.get(si)]
        for j, (i, step_idx) in enumerate(dt_steps):
            text = narration_texts[step_idx]
            start_t = start_times[i]
            duration = narration_durations.get(step_idx, 3.0)
            end_t = start_t + duration

            escaped = _escape_drawtext(text)
            out_label = f"[dt{j}]" if j < len(dt_steps) - 1 else "[out]"
            filters.append(
                f"{prev_label}drawtext=text='{escaped}'"
                f":fontsize={subtitle_font_size}"
                f":fontcolor={subtitle_font_color}"
                f":x={text_x}:y={text_y}"
                f":box=1:boxcolor={_parse_box_color(subtitle_bg_color)}"
                f":boxborderw=6"
                f":enable='between(t,{start_t:.2f},{end_t:.2f})'"
                f"{out_label}"
            )
            prev_label = out_label

    # Ensure the filter chain ends with [out]
    if prev_label != "[out]":
        old_suffix = prev_label
        filters[-1] = filters[-1][: -len(old_suffix)] + "[out]"

    filter_complex = ";".join(filters)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    logger.info("Compositing %d avatar overlays onto video", len(avatar_clips))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Avatar composite failed: %s", result.stderr[-400:])
        logger.info("Returning original video without avatar")
        return video_path

    logger.info("Avatar composited video: %s", output_path.name)
    return output_path


def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Get video width and height via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        parts = result.stdout.strip().split("x")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return 1920, 1080  # fallback


def _calc_position(
    position: str, video_w: int, video_h: int, avatar_size: int,
) -> tuple[int, int]:
    """Calculate x, y for the avatar overlay based on position string."""
    canvas = int(avatar_size * 1.4)

    positions = {
        "bottom-right": (video_w - canvas - _MARGIN, video_h - canvas - _MARGIN),
        "bottom-left": (_MARGIN, video_h - canvas - _MARGIN),
        "top-right": (video_w - canvas - _MARGIN, _MARGIN),
        "top-left": (_MARGIN, _MARGIN),
    }
    return positions.get(position, positions["bottom-right"])


def _calc_text_position(
    position: str, video_w: int, video_h: int, avatar_size: int,
    font_size: int,
) -> tuple[str, str, int]:
    """Calculate x, y, width for the drawtext below the avatar box.

    Returns x (str expression), y (str expression), text_width (int).
    """
    canvas = int(avatar_size * 1.4)
    text_w = canvas + 40  # slightly wider than avatar box

    if position in ("bottom-right",):
        tx = video_w - text_w - _MARGIN + 10
        ty = video_h - _MARGIN - 4  # just above bottom margin
    elif position in ("bottom-left",):
        tx = _MARGIN - 10
        ty = video_h - _MARGIN - 4
    elif position in ("top-right",):
        tx = video_w - text_w - _MARGIN + 10
        ty = _MARGIN + canvas + 8
    elif position in ("top-left",):
        tx = _MARGIN - 10
        ty = _MARGIN + canvas + 8
    else:
        tx = video_w - text_w - _MARGIN + 10
        ty = video_h - _MARGIN - 4

    return str(tx), str(ty), text_w


def _escape_drawtext(text: str) -> str:
    """Escape text for ffmpeg drawtext filter."""
    # ffmpeg drawtext needs these chars escaped
    text = text.replace("\\", "\\\\\\\\")
    text = text.replace("'", "\u2019")  # replace apostrophe with unicode right quote
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    text = text.replace("\n", " ")
    return text


def _parse_box_color(color: str) -> str:
    """Convert CSS-style rgba() to ffmpeg-compatible color string."""
    if color.startswith("rgba("):
        # rgba(0,0,0,0.7) → black@0.7
        parts = color[5:-1].split(",")
        if len(parts) == 4:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            a = float(parts[3])
            return f"#{r:02x}{g:02x}{b:02x}@{a}"
    return color
