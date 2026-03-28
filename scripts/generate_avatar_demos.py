#!/usr/bin/env python3
"""Generate short demo videos for each avatar animation style.

Creates a 4-second synthetic audio, generates an avatar clip per style
using AnimatedAvatarProvider, then composites each onto a dark background
to produce one video per style in docs/public/videos/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "docs" / "public" / "videos"
TMP_DIR = ROOT / "output" / "_avatar_demos"

STYLES = ["bounce", "waveform", "pulse", "equalizer", "xp_bliss", "clippy", "visualizer", "pacman", "space_invader", "mario_block", "nyan_cat", "matrix", "pickle_rick", "chrome_dino", "marvin", "mac128k", "floppy_disk", "bsod", "bugdroid", "qr_code", "gpu_sweat"]
DURATION_MS = 4000
WIDTH, HEIGHT = 1280, 720
AVATAR_SIZE = 200  # larger so it's clearly visible in the demo


def _create_audio(out: Path) -> Path:
    """Generate a synthetic audio clip with varying amplitude using pydub."""
    import numpy as np
    from pydub import AudioSegment
    from pydub.generators import Sine

    # Build a waveform with rising/falling amplitude to exercise animation
    sr = 44100
    dur_s = DURATION_MS / 1000.0
    t = np.linspace(0, dur_s, int(sr * dur_s), endpoint=False)
    # Amplitude envelope: sine modulation to create pulsing
    envelope = np.abs(np.sin(2 * np.pi * 1.5 * t))  # 1.5 Hz pulse
    # Carrier: 440 Hz
    carrier = np.sin(2 * np.pi * 440 * t) * envelope
    # Normalize to 16-bit
    samples = (carrier * 32767 * 0.8).astype(np.int16)

    audio = AudioSegment(
        samples.tobytes(),
        frame_rate=sr,
        sample_width=2,
        channels=1,
    )
    audio.export(str(out), format="mp3")
    return out


def _create_base_video(out: Path) -> Path:
    """Generate a dark solid background video."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=size={WIDTH}x{HEIGHT}:duration={DURATION_MS / 1000:.1f}:rate=30:color=#16213e",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out


def _generate_for_style(style: str, audio_path: Path, base_video: Path) -> Path:
    """Generate avatar clip and composite it centered onto the base video."""
    from demodsl.providers.avatar import AnimatedAvatarProvider

    clip_dir = TMP_DIR / f"clips_{style}"
    clip_dir.mkdir(parents=True, exist_ok=True)

    provider = AnimatedAvatarProvider(output_dir=clip_dir)
    clip_path = provider.generate(
        audio_path,
        image=None,
        size=AVATAR_SIZE,
        style=style,
        shape="circle",
    )
    provider.close()

    # Composite centered onto base video
    output = OUTPUT_DIR / f"demo_avatar_{style}.mp4"
    canvas = int(AVATAR_SIZE * 1.4)
    x = (WIDTH - canvas) // 2
    y = (HEIGHT - canvas) // 2

    cmd = [
        "ffmpeg", "-y",
        "-i", str(base_video),
        "-i", str(clip_path),
        "-filter_complex",
        f"[1:v]scale={canvas}:{canvas}:flags=lanczos,format=yuva420p[av];"
        f"[0:v][av]overlay={x}:{y}:format=auto[out]",
        "-map", "[out]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ ffmpeg composite failed for {style}: {result.stderr[-200:]}")
        return base_video

    return output


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic audio...")
    audio = TMP_DIR / "pulse_audio.mp3"
    _create_audio(audio)
    print(f"  ✓ {audio.name}")

    print("Generating base video...")
    base = TMP_DIR / "base_avatar.mp4"
    _create_base_video(base)
    print(f"  ✓ {base.name}")

    for style in STYLES:
        print(f"Generating demo for avatar style: {style}...")
        out = _generate_for_style(style, audio, base)
        print(f"  ✓ {out.name}")

    print(f"\nDone — {len(STYLES)} avatar videos in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
