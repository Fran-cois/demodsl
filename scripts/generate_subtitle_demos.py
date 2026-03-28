#!/usr/bin/env python3
"""Generate short demo videos for each subtitle style.

Creates a 6-second base video with a gradient background and burns
styled subtitles into it, producing one video per style in docs/public/videos/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Ensure demodsl is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from demodsl.effects.subtitle import (  # noqa: E402
    SPEED_PRESETS,
    STYLE_PRESETS,
    build_subtitle_entries,
    burn_subtitles,
    generate_ass_subtitle,
    get_merged_subtitle_config,
)

OUTPUT_DIR = ROOT / "docs" / "public" / "videos"
TMP_DIR = ROOT / "output" / "_subtitle_demos"

DEMO_TEXT = "Welcome to DemoDSL, the automated demo video generator."
DURATION = 6.0  # seconds
WIDTH, HEIGHT = 1280, 720

ALL_STYLES = list(STYLE_PRESETS.keys())


def _create_base_video(out: Path) -> Path:
    """Generate a short gradient background video with ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        (f"color=size={WIDTH}x{HEIGHT}:duration={DURATION}:rate=30:color=#1a1a2e"),
        "-f",
        "lavfi",
        "-i",
        (f"color=size={WIDTH}x{HEIGHT}:duration={DURATION}:rate=30:color=#16213e"),
        "-filter_complex",
        "[0:v][1:v]blend=all_mode=addition:all_opacity=0.5[out]",
        "-map",
        "[out]",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        "-t",
        str(DURATION),
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: simple solid color
        cmd2 = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=size={WIDTH}x{HEIGHT}:duration={DURATION}:rate=30:color=#1a1a2e",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
        subprocess.run(cmd2, capture_output=True, text=True, check=True)
    return out


def _generate_for_style(style: str, base_video: Path) -> Path:
    """Generate a demo video with the given subtitle style."""
    # Simulate narration at step 0, timestamp 0.5s
    narration_texts = {0: DEMO_TEXT}
    step_timestamps = [0.5]
    narration_durations = {0: DURATION - 1.0}

    raw_cfg = {"enabled": True, "style": style, "speed": "normal"}
    cfg = get_merged_subtitle_config(raw_cfg)

    speed_wps = SPEED_PRESETS["normal"]

    entries = build_subtitle_entries(
        narration_texts,
        step_timestamps,
        narration_durations,
        speed_wps=speed_wps,
        max_words_per_line=cfg.get("max_words_per_line", 8),
        style_name=style,
    )

    ass_path = TMP_DIR / f"subtitle_{style}.ass"
    generate_ass_subtitle(entries, cfg, ass_path)

    output = OUTPUT_DIR / f"demo_subtitle_{style}.mp4"
    return burn_subtitles(base_video, ass_path, output)


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating base video...")
    base = TMP_DIR / "base.mp4"
    _create_base_video(base)
    print(f"  ✓ Base video: {base}")

    for style in ALL_STYLES:
        print(f"Generating demo for style: {style}...")
        out = _generate_for_style(style, base)
        print(f"  ✓ {out.name}")

    print(f"\nDone — {len(ALL_STYLES)} videos in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
