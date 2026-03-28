#!/usr/bin/env python3
"""Generate demo videos for new browser effects only."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "docs" / "public" / "videos"
TMP_DIR = ROOT / "output" / "_effect_demos"

# Only trail effects that need regeneration
EFFECTS = [
    "cursor_trail",
    "cursor_trail_rainbow", "cursor_trail_comet", "cursor_trail_glow",
    "cursor_trail_line", "cursor_trail_particles", "cursor_trail_fire",
]

WIDTH, HEIGHT = 1280, 720
FPS = 20
DURATION_S = 6.0

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
</style>
</head>
<body>
  <h1>DemoDSL Effects</h1>
  <div class="card">
    <p>Visual effects demo page</p>
    <a class="btn" id="cta" href="#">Get Started</a>
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


def _frames_to_video(frames_dir: Path, output: Path) -> Path:
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=#0f0c29",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr[-200:]}")
    return output


def _get_effect(name: str):
    from demodsl.effects.browser_effects import (
        BubblesEffect, CursorTrailEffect, CursorTrailCometEffect,
        CursorTrailFireEffect, CursorTrailGlowEffect, CursorTrailLineEffect,
        CursorTrailParticlesEffect, CursorTrailRainbowEffect,
        EmojiRainEffect, FireworksEffect, NeonGlowEffect,
        PartyPopperEffect, SnowEffect, SparkleEffect,
        StarBurstEffect, SuccessCheckmarkEffect,
    )
    mapping = {
        "cursor_trail": (CursorTrailEffect(), {}),
        "success_checkmark": (SuccessCheckmarkEffect(), {}),
        "cursor_trail_rainbow": (CursorTrailRainbowEffect(), {}),
        "cursor_trail_comet": (CursorTrailCometEffect(), {}),
        "cursor_trail_glow": (CursorTrailGlowEffect(), {"color": "#00BFFF"}),
        "cursor_trail_line": (CursorTrailLineEffect(), {}),
        "cursor_trail_particles": (CursorTrailParticlesEffect(), {}),
        "cursor_trail_fire": (CursorTrailFireEffect(), {}),
        "emoji_rain": (EmojiRainEffect(), {}),
        "fireworks": (FireworksEffect(), {}),
        "bubbles": (BubblesEffect(), {}),
        "snow": (SnowEffect(), {}),
        "star_burst": (StarBurstEffect(), {}),
        "party_popper": (PartyPopperEffect(), {}),
    }
    return mapping[name]


def _generate(name: str) -> Path:
    effect_obj, params = _get_effect(name)

    html_path = TMP_DIR / "demo_page.html"
    html_path.write_text(_DEMO_HTML, encoding="utf-8")

    frames_dir = TMP_DIR / f"frames_{name}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob("*.png"):
        f.unlink()

    output = OUTPUT_DIR / f"demo_effect_{name}.mp4"

    driver = _create_driver()
    try:
        driver.get(f"file://{html_path}")
        time.sleep(0.5)

        # "Before" frames
        before = int(FPS * 0.5)
        for i in range(before):
            driver.save_screenshot(str(frames_dir / f"frame_{i:05d}.png"))
            time.sleep(1.0 / FPS)

        # Inject effect
        def evaluate_js(script: str):
            return driver.execute_script(script)
        effect_obj.inject(evaluate_js, params)

        # Simulate mouse movement for cursor trail effects
        # Interleave mouse moves with screenshots so trails are captured while visible
        if name.startswith("cursor_trail"):
            after = int(FPS * DURATION_S) - before
            move_steps = 30
            frames_per_move = max(2, after // move_steps)
            frame_idx = before
            for step in range(move_steps):
                # Smooth sinusoidal path across the screen
                t = step / move_steps
                x = int(100 + t * (WIDTH - 200))
                y = int(HEIGHT / 2 + 160 * __import__('math').sin(t * __import__('math').pi * 2.5))
                driver.execute_script(
                    f"document.dispatchEvent(new MouseEvent('mousemove', "
                    f"{{clientX: {x}, clientY: {y}, bubbles: true}}));"
                )
                time.sleep(0.08)
                # Capture frames between moves
                for _ in range(frames_per_move):
                    if frame_idx >= before + after:
                        break
                    driver.save_screenshot(str(frames_dir / f"frame_{frame_idx:05d}.png"))
                    frame_idx += 1
                    time.sleep(1.0 / FPS)
            # Capture remaining frames (trail fading)
            while frame_idx < before + after:
                driver.save_screenshot(str(frames_dir / f"frame_{frame_idx:05d}.png"))
                frame_idx += 1
                time.sleep(1.0 / FPS)
        else:
            # "After" frames for non-cursor effects
            after = int(FPS * DURATION_S) - before
            for i in range(after):
                idx = before + i
                driver.save_screenshot(str(frames_dir / f"frame_{idx:05d}.png"))
                time.sleep(1.0 / FPS)
    finally:
        driver.quit()

    return _frames_to_video(frames_dir, output)


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name in EFFECTS:
        print(f"Generating: {name}...")
        try:
            out = _generate(name)
            sz = out.stat().st_size
            print(f"  ✓ {out.name} ({sz // 1024}KB)")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    print(f"\nDone — {len(EFFECTS)} videos")


if __name__ == "__main__":
    main()
