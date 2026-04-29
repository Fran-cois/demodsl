"""Reproduce exact DemoDSL recording pipeline and check raw frames for effects."""

import shutil
import sys
import time
from base64 import b64decode
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from demodsl.effects.browser_effects import (  # noqa: E402
    ConfettiEffect,
    MatrixRainEffect,
    SpotlightEffect,
)
from demodsl.models import Viewport  # noqa: E402
from demodsl.providers.selenium_browser import SeleniumBrowserProvider  # noqa: E402

DEBUG_DIR = Path("/tmp/demodsl_pipeline_debug")
if DEBUG_DIR.exists():
    shutil.rmtree(DEBUG_DIR)
DEBUG_DIR.mkdir(parents=True)

# Create provider exactly like DemoDSL does
provider = SeleniumBrowserProvider()
vp = Viewport(width=1920, height=1080)
video_dir = DEBUG_DIR / "raw_video"
video_dir.mkdir()

# Launch WITH recording (same as scenario orchestrator)
provider.launch(
    browser_type="chrome",
    viewport=vp,
    video_dir=video_dir,
)

print("Recording started. Navigating...")

# Step 1: Navigate (same as DemoDSL)
provider.navigate("http://127.0.0.1:8899/effects_showcase_page.html")
time.sleep(2.0)

# Take a debug screenshot to verify page loaded


def take_debug_screenshot(name):
    result = provider._driver.execute_cdp_cmd(
        "Page.captureScreenshot",
        {"format": "png", "captureBeyondViewport": False},
    )
    path = DEBUG_DIR / f"{name}.png"
    path.write_bytes(b64decode(result["data"]))
    print(f"  Screenshot saved: {path.name} ({path.stat().st_size:,} bytes)")
    return path


take_debug_screenshot("01_after_navigate")

# Count frames captured so far
frame_count_before = provider._recorder._frame_count
print(f"Frames captured so far: {frame_count_before}")

# Step 2: Inject spotlight (exactly like _apply_browser_effects does)
print("\nInjecting spotlight effect...")
spotlight = SpotlightEffect()
params = {"duration": 2.5, "intensity": 0.85}
spotlight.inject(provider.evaluate_js, params)

# Small wait to let recorder capture effect
time.sleep(0.5)
take_debug_screenshot("02_spotlight_0.5s")

time.sleep(2.0)
take_debug_screenshot("03_spotlight_2.5s")

frame_count_after_spotlight = provider._recorder._frame_count
print(f"Frames captured during spotlight: {frame_count_after_spotlight - frame_count_before}")

# Step 2b: Scroll (like cmd.execute does)
provider.scroll("down", 100)
time.sleep(3.0)
take_debug_screenshot("04_after_scroll_1")

# Step 3: Inject confetti
print("\nInjecting confetti effect...")
confetti = ConfettiEffect()
confetti.inject(provider.evaluate_js, {"duration": 2.5})

time.sleep(0.5)
take_debug_screenshot("05_confetti_0.5s")

time.sleep(2.0)
take_debug_screenshot("06_confetti_2.5s")

frame_count_after_confetti = provider._recorder._frame_count
print(
    f"Frames captured during confetti: {frame_count_after_confetti - frame_count_after_spotlight}"
)

# Step 3b: scroll
provider.scroll("down", 200)
time.sleep(3.0)

# Step 4: Matrix rain
print("\nInjecting matrix rain effect...")
matrix = MatrixRainEffect()
matrix.inject(provider.evaluate_js, {"color": "#00FF41", "duration": 2.5})

time.sleep(0.5)
take_debug_screenshot("07_matrix_0.5s")

time.sleep(2.0)

# Total frames
total_frames = provider._recorder._frame_count
print(f"\nTotal frames captured: {total_frames}")

# CRITICAL: Save a copy of raw frames before close() deletes them
raw_frames_copy = DEBUG_DIR / "raw_frames_sample"
raw_frames_copy.mkdir()

frame_dir = provider._frame_dir
if frame_dir and frame_dir.exists():
    frames = sorted(frame_dir.glob("frame_*.jpg"))
    print(f"Total raw frames on disk: {len(frames)}")

    # Save every 30th frame (1 per second) and some specific ones
    for i, f in enumerate(frames):
        if i % 30 == 0 or i in [
            frame_count_before,
            frame_count_after_spotlight,
            frame_count_after_confetti,
        ]:
            dst = raw_frames_copy / f.name
            shutil.copy2(f, dst)

    # Also save frames around effect injection points
    for check_idx in [
        frame_count_before,
        frame_count_before + 5,
        frame_count_before + 15,
        frame_count_after_spotlight,
        frame_count_after_spotlight + 5,
        frame_count_after_spotlight + 15,
    ]:
        candidate = frame_dir / f"frame_{check_idx:06d}.jpg"
        if candidate.exists():
            dst = raw_frames_copy / f"EFFECT_{candidate.name}"
            shutil.copy2(f, dst)

    print(f"Saved {len(list(raw_frames_copy.iterdir()))} sample frames to {raw_frames_copy}")

# Close provider (assembles video)
video_path = provider.close()
print(f"\nAssembled video: {video_path}")

if video_path and video_path.exists():
    # Copy video to debug dir
    final_copy = DEBUG_DIR / "assembled_video.mp4"
    shutil.copy2(video_path, final_copy)
    print(f"Video copied to: {final_copy} ({final_copy.stat().st_size:,} bytes)")

# List all debug files
print(f"\nDebug files in {DEBUG_DIR}:")
for f in sorted(DEBUG_DIR.rglob("*")):
    if f.is_file():
        print(f"  {f.relative_to(DEBUG_DIR)}: {f.stat().st_size:,} bytes")
