#!/usr/bin/env python3
"""Generate demo videos for camera & cinematic post-processing effects.

Captures frames from a styled HTML page via Selenium, then applies each
PostEffect (MoviePy-based) to the frames and encodes to MP4 via ffmpeg.
One video per effect in docs/public/videos/.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "docs" / "public" / "videos"
TMP_DIR = ROOT / "output" / "_camera_demos"

# Camera movement effects
CAMERA_EFFECTS = {
    "drone_zoom": {"scale": 1.4, "target_x": 0.5, "target_y": 0.3},
    "ken_burns": {"scale": 1.15, "direction": "right"},
    "zoom_to": {"scale": 1.8, "target_x": 0.5, "target_y": 0.4},
    "dolly_zoom": {"intensity": 0.3},
    "elastic_zoom": {"scale": 1.3},
    "camera_shake": {"intensity": 0.3, "speed": 8.0},
    "whip_pan": {"direction": "right"},
    "rotate": {"angle": 3.0, "speed": 1.0},
}

# Cinematic effects
CINEMATIC_EFFECTS = {
    "letterbox": {"ratio": 2.35},
    "film_grain": {"intensity": 0.3},
    "color_grade": {"preset": "cinematic"},
    "focus_pull": {"direction": "out", "intensity": 0.5},
    "tilt_shift": {"intensity": 0.6, "focus_position": 0.5},
}

ALL_EFFECTS = {**CAMERA_EFFECTS, **CINEMATIC_EFFECTS}

WIDTH, HEIGHT = 1280, 720
FPS = 20
DURATION_S = 4.0

_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; min-height: 100vh; gap: 24px;
  }
  h1 { font-size: 42px; font-weight: 700; color: #a5b4fc; }
  p { font-size: 20px; color: #94a3b8; max-width: 600px; text-align: center; }
  .card {
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px; padding: 32px 40px; max-width: 580px; text-align: center;
  }
  .btn {
    display: inline-block; margin-top: 20px; padding: 14px 36px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white;
    border: none; border-radius: 10px; font-size: 17px; font-weight: 600;
    cursor: pointer;
  }
  .grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
    margin-top: 20px; width: 100%; max-width: 700px;
  }
  .grid-item {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 18px; text-align: center; font-size: 14px;
    color: #94a3b8;
  }
  .grid-item strong { color: #a5b4fc; display: block; margin-bottom: 6px; }
</style>
</head>
<body>
  <h1>DemoDSL Camera Effects</h1>
  <div class="card">
    <p>Demonstrating post-processing camera and cinematic effects applied via MoviePy.</p>
    <a class="btn" href="#">Get Started</a>
  </div>
  <div class="grid">
    <div class="grid-item"><strong>Zoom</strong>Drone, Ken Burns, Elastic</div>
    <div class="grid-item"><strong>Motion</strong>Shake, Whip Pan, Rotate</div>
    <div class="grid-item"><strong>Cinema</strong>Letterbox, Grain, Grade</div>
  </div>
</body>
</html>
"""


def _create_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WIDTH},{HEIGHT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(WIDTH, HEIGHT)
    return driver


def _capture_base_frames(
    driver, frames_dir: Path, num_frames: int, interval: float
) -> int:
    """Capture screenshots as PNG frames with adaptive timing."""
    captured = 0
    for i in range(num_frames):
        t0 = time.monotonic()
        frame_path = frames_dir / f"frame_{i:05d}.png"
        driver.save_screenshot(str(frame_path))
        captured += 1
        elapsed = time.monotonic() - t0
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
    return captured


def _load_frames(frames_dir: Path) -> list[np.ndarray]:
    """Load all PNG frames as RGB numpy arrays."""
    frames = []
    for path in sorted(frames_dir.glob("frame_*.png")):
        img = Image.open(path).convert("RGB")
        frames.append(np.array(img))
    return frames


def _apply_effect_to_frames(
    effect_name: str,
    params: dict,
    frames: list[np.ndarray],
    fps: int,
) -> list[np.ndarray]:
    """Apply a PostEffect to a list of frames, simulating a MoviePy clip."""
    from demodsl.effects.post_effects import (
        CameraShakeEffect,
        ColorGradeEffect,
        DollyZoomEffect,
        DroneZoomEffect,
        ElasticZoomEffect,
        FilmGrainEffect,
        FocusPullEffect,
        KenBurnsEffect,
        LetterboxEffect,
        RotateEffect,
        TiltShiftEffect,
        WhipPanEffect,
        ZoomToEffect,
    )

    effect_map = {
        "drone_zoom": DroneZoomEffect,
        "ken_burns": KenBurnsEffect,
        "zoom_to": ZoomToEffect,
        "dolly_zoom": DollyZoomEffect,
        "elastic_zoom": ElasticZoomEffect,
        "camera_shake": CameraShakeEffect,
        "whip_pan": WhipPanEffect,
        "rotate": RotateEffect,
        "letterbox": LetterboxEffect,
        "film_grain": FilmGrainEffect,
        "color_grade": ColorGradeEffect,
        "focus_pull": FocusPullEffect,
        "tilt_shift": TiltShiftEffect,
    }

    effect_cls = effect_map[effect_name]
    effect = effect_cls()

    duration = len(frames) / fps
    len(frames)

    # Create a fake clip-like object to use the effect's apply method
    # The effects use clip.transform(fn) where fn(get_frame, t) -> frame
    # We'll extract the transform function and apply it directly
    class FakeClip:
        def __init__(self, frame_list, dur):
            self._frames = frame_list
            self.duration = dur
            self.w = frame_list[0].shape[1]
            self.h = frame_list[0].shape[0]

        def transform(self, func):
            """Return a new FakeClip with the transform applied."""
            new_frames = []
            for i, frame in enumerate(self._frames):
                t = i / fps

                def get_frame(t_inner, _f=frame):
                    return _f

                new_frame = func(get_frame, t)
                new_frames.append(new_frame)
            return FakeClip(new_frames, self.duration)

        def resized(self, scale):
            """Resize all frames."""
            new_frames = []
            for frame in self._frames:
                img = Image.fromarray(frame)
                w, h = img.size
                nw, nh = int(w * scale), int(h * scale)
                img = img.resize((nw, nh), Image.LANCZOS)
                new_frames.append(np.array(img))
            return FakeClip(new_frames, self.duration)

        def cropped(self, x_center, y_center, width, height):
            """Crop all frames."""
            new_frames = []
            for frame in self._frames:
                img = Image.fromarray(frame)
                left = int(x_center - width / 2)
                top = int(y_center - height / 2)
                img = img.crop((left, top, left + int(width), top + int(height)))
                new_frames.append(np.array(img))
            return FakeClip(new_frames, self.duration)

    fake = FakeClip(frames, duration)
    result = effect.apply(fake, params)
    return result._frames


def _frames_to_video(
    frames: list[np.ndarray], output: Path, tmp_dir: Path | None = None
) -> Path:
    """Encode numpy frames to MP4 via ffmpeg, normalizing all to WIDTH x HEIGHT."""
    # Write normalized frames to temp PNGs
    work_dir = tmp_dir or TMP_DIR / "_encode_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    for f in work_dir.glob("*.png"):
        f.unlink()

    for i, frame in enumerate(frames):
        img = Image.fromarray(frame[:, :, :3].astype(np.uint8))
        if img.size != (WIDTH, HEIGHT):
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        img.save(work_dir / f"frame_{i:05d}.png")

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(work_dir / "frame_%05d.png"),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ ffmpeg encode failed: {result.stderr[-300:]}")
    return output


def _generate_for_effect(effect_name: str, params: dict, base_frames_dir: Path) -> Path:
    """Apply a post-effect to base frames and encode to video."""
    frames = _load_frames(base_frames_dir)
    if not frames:
        raise RuntimeError(f"No base frames found in {base_frames_dir}")

    print(f"  Applying {effect_name} to {len(frames)} frames...")
    transformed = _apply_effect_to_frames(effect_name, params, frames, FPS)

    output = OUTPUT_DIR / f"demo_effect_{effect_name}.mp4"
    return _frames_to_video(transformed, output)


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Capture base frames once (reused for all effects)
    base_frames_dir = TMP_DIR / "base_frames"
    base_frames_dir.mkdir(parents=True, exist_ok=True)

    existing = list(base_frames_dir.glob("frame_*.png"))
    num_frames = int(FPS * DURATION_S)

    if len(existing) < num_frames:
        print("Capturing base frames with Selenium...")
        # Clean old frames
        for f in base_frames_dir.glob("*.png"):
            f.unlink()

        html_path = TMP_DIR / "demo_page.html"
        html_path.write_text(_DEMO_HTML, encoding="utf-8")

        driver = _create_driver()
        try:
            driver.get(f"file://{html_path}")
            time.sleep(1.0)
            _capture_base_frames(driver, base_frames_dir, num_frames, 1.0 / FPS)
        finally:
            driver.quit()
        print(f"  ✓ Captured {num_frames} base frames")
    else:
        print(f"Using {len(existing)} existing base frames")

    # Step 2: Generate a video for each effect
    success = 0
    failed = 0
    for effect_name, params in ALL_EFFECTS.items():
        print(f"Generating demo for: {effect_name}...")
        try:
            out = _generate_for_effect(effect_name, params, base_frames_dir)
            print(f"  ✓ {out.name}")
            success += 1
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"  ✗ Failed: {e}")
            failed += 1

    print(f"\nDone — {success} camera/cinematic videos generated, {failed} failed")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
