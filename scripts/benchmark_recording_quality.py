#!/usr/bin/env python3
"""Benchmark native (VP8) vs CDP (H.264) recording quality and speed.

Generates side-by-side comparison assets for the documentation.
Output goes to docs/public/videos/ and docs/public/images/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEMO_YAML = ROOT / "examples" / "demo_navigate_scroll.yaml"
OUTPUT_DIR = ROOT / "docs" / "public" / "videos"
IMG_DIR = ROOT / "docs" / "public" / "images"
COMPARISON_DIR = ROOT / "output" / "_comparison"


def _run_demo(yaml_path: Path, output_dir: Path) -> tuple[float, Path]:
    """Run a demo and return (elapsed_seconds, output_mp4_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "demodsl.cli",
            "run",
            str(yaml_path),
            "--skip-voice",
            "-o",
            str(output_dir),
            "--no-run-cache",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = time.monotonic() - t0
    if result.returncode != 0:
        print(f"FAILED: {result.stderr[-300:]}", file=sys.stderr)
        sys.exit(1)

    mp4_files = list(output_dir.glob("*.mp4"))
    if not mp4_files:
        print("No MP4 output", file=sys.stderr)
        sys.exit(1)
    return elapsed, mp4_files[0]


def _video_info(mp4: Path) -> dict:
    """Get video info via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(mp4),
        ],
        capture_output=True,
        text=True,
    )
    import json

    data = json.loads(result.stdout)
    stream = data["streams"][0]
    fmt = data["format"]
    return {
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration": float(fmt.get("duration", 0)),
        "bitrate": int(fmt.get("bit_rate", 0)),
        "size_kb": int(fmt.get("size", 0)) / 1024,
        "nb_frames": int(stream.get("nb_frames", 0)),
    }


def _extract_frame(mp4: Path, output: Path, time_s: float = 3.0) -> None:
    """Extract a frame at the given timestamp."""
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4),
            "-ss",
            str(time_s),
            "-frames:v",
            "1",
            str(output),
        ],
        capture_output=True,
        timeout=30,
    )


def main() -> None:
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    # Load base config
    with open(DEMO_YAML) as f:
        cfg = yaml.safe_load(f)

    # ── Native (webkit, VP8) ──────────────────────────────────────────
    print("Running NATIVE (webkit + VP8) recording...")
    native_dir = COMPARISON_DIR / "native"
    cfg_native = {**cfg}
    cfg_native["scenarios"] = [{**cfg["scenarios"][0], "browser": "webkit"}]
    native_yaml = COMPARISON_DIR / "native.yaml"
    with open(native_yaml, "w") as f:
        yaml.dump(cfg_native, f)
    native_time, native_mp4 = _run_demo(native_yaml, native_dir)
    native_info = _video_info(native_mp4)

    # ── CDP (chrome, H.264) ───────────────────────────────────────────
    print("Running CDP (chrome + H.264) recording...")
    cdp_dir = COMPARISON_DIR / "cdp"
    cfg_cdp = {**cfg}
    cfg_cdp["scenarios"] = [{**cfg["scenarios"][0], "browser": "chrome"}]
    cdp_yaml = COMPARISON_DIR / "cdp.yaml"
    with open(cdp_yaml, "w") as f:
        yaml.dump(cfg_cdp, f)
    cdp_time, cdp_mp4 = _run_demo(cdp_yaml, cdp_dir)
    cdp_info = _video_info(cdp_mp4)

    # ── Extract comparison frames ─────────────────────────────────────
    _extract_frame(native_mp4, IMG_DIR / "comparison_native.png")
    _extract_frame(cdp_mp4, IMG_DIR / "comparison_cdp.png")

    # Copy comparison videos to docs
    shutil.copy2(native_mp4, OUTPUT_DIR / "comparison_native.mp4")
    shutil.copy2(cdp_mp4, OUTPUT_DIR / "comparison_cdp.mp4")

    # ── Print results ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RECORDING QUALITY BENCHMARK")
    print("=" * 60)
    print(f"{'':30s} {'Native (VP8)':>14s}  {'CDP (H.264)':>14s}")
    print("-" * 60)
    print(f"{'Browser':30s} {'webkit':>14s}  {'chrome':>14s}")
    print(f"{'Recording method':30s} {'VP8 screencast':>14s}  {'CDP screenshot':>14s}")
    print(f"{'Total time':30s} {native_time:>13.1f}s  {cdp_time:>13.1f}s")
    print(
        f"{'Speedup':30s} {'—':>14s}  {native_time / cdp_time:>13.1f}x"
        if cdp_time > 0
        else ""
    )
    print(
        f"{'Video duration':30s} {native_info['duration']:>13.1f}s  {cdp_info['duration']:>13.1f}s"
    )
    print(
        f"{'File size':30s} {native_info['size_kb']:>12.0f}KB  {cdp_info['size_kb']:>12.0f}KB"
    )
    print(
        f"{'Bitrate':30s} {native_info['bitrate'] // 1000:>12d}kb  {cdp_info['bitrate'] // 1000:>12d}kb"
    )
    print(
        f"{'Frames':30s} {native_info['nb_frames']:>14d}  {cdp_info['nb_frames']:>14d}"
    )
    print(f"{'Codec':30s} {native_info['codec']:>14s}  {cdp_info['codec']:>14s}")
    print(f"{'VP8 artefacts':30s} {'Yes (deblocked)':>14s}  {'None':>14s}")
    print("=" * 60)
    print(f"\nComparison frames: {IMG_DIR}")
    print(f"Comparison videos: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
