#!/usr/bin/env python3
"""Generate demo videos for each browser JS effect.

Uses Selenium (headless Chrome) to load a styled HTML page, inject each
effect's JS code, and capture screenshots as frames — then encodes to
MP4 via ffmpeg. One video per effect in docs/public/videos/.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "docs" / "public" / "videos"
TMP_DIR = ROOT / "output" / "_effect_demos"

# All 23 browser effects
EFFECTS = [
    "spotlight", "highlight", "confetti", "typewriter", "glow",
    "shockwave", "sparkle", "cursor_trail", "ripple", "neon_glow",
    "success_checkmark",
    # cursor trail variants
    "cursor_trail_rainbow", "cursor_trail_comet", "cursor_trail_glow",
    "cursor_trail_line", "cursor_trail_particles", "cursor_trail_fire",
    # fun / celebration effects
    "emoji_rain", "fireworks", "bubbles", "snow", "star_burst",
    "party_popper",
]

WIDTH, HEIGHT = 1280, 720
FPS = 20
DURATION_S = 4.0


# A minimal demo HTML page with styled content to show effects on
_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
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
    cursor: pointer; text-decoration: none;
  }
  .btn:hover { filter: brightness(1.15); }
  input {
    margin-top: 16px; padding: 12px 20px; width: 320px;
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px; color: white; font-size: 16px; outline: none;
  }
  input:focus { border-color: #6366f1; }
</style>
</head>
<body>
  <h1>DemoDSL Effects</h1>
  <div class="card">
    <p>This page demonstrates browser-injected visual effects running in real time.</p>
    <a class="btn" id="cta" href="#">Get Started</a>
    <br/>
    <input type="text" placeholder="Type something here..." id="demo-input" />
  </div>
</body>
</html>
"""


def _create_driver():
    """Create a headless Chrome Selenium WebDriver."""
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


def _capture_frames(driver, frames_dir: Path, num_frames: int, interval: float) -> int:
    """Capture screenshots as PNG frames."""
    captured = 0
    for i in range(num_frames):
        frame_path = frames_dir / f"frame_{i:05d}.png"
        driver.save_screenshot(str(frame_path))
        captured += 1
        time.sleep(interval)
    return captured


def _frames_to_video(frames_dir: Path, output: Path) -> Path:
    """Encode PNG frames to MP4 via ffmpeg, scaling to exact dimensions."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=#0f0c29",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ ffmpeg encode failed: {result.stderr[-300:]}")
    return output


def _generate_for_effect(effect_name: str) -> Path:
    """Capture frames with Selenium after injecting the JS effect."""
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By

    from demodsl.effects.browser_effects import (
        BubblesEffect,
        ConfettiEffect,
        CursorTrailEffect,
        CursorTrailCometEffect,
        CursorTrailFireEffect,
        CursorTrailGlowEffect,
        CursorTrailLineEffect,
        CursorTrailParticlesEffect,
        CursorTrailRainbowEffect,
        EmojiRainEffect,
        FireworksEffect,
        GlowEffect,
        HighlightEffect,
        NeonGlowEffect,
        PartyPopperEffect,
        RippleEffect,
        ShockwaveEffect,
        SnowEffect,
        SparkleEffect,
        SpotlightEffect,
        StarBurstEffect,
        SuccessCheckmarkEffect,
        TypewriterEffect,
    )

    effect_map = {
        "spotlight": (SpotlightEffect(), {"intensity": 0.8}),
        "highlight": (HighlightEffect(), {"color": "#FFD700", "intensity": 0.9}),
        "confetti": (ConfettiEffect(), {}),
        "typewriter": (TypewriterEffect(), {}),
        "glow": (GlowEffect(), {"color": "#6366f1"}),
        "shockwave": (ShockwaveEffect(), {}),
        "sparkle": (SparkleEffect(), {}),
        "cursor_trail": (CursorTrailEffect(), {}),
        "ripple": (RippleEffect(), {}),
        "neon_glow": (NeonGlowEffect(), {"color": "#FF00FF"}),
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

    effect_obj, params = effect_map[effect_name]

    # Write demo HTML
    html_path = TMP_DIR / "demo_page.html"
    html_path.write_text(_DEMO_HTML, encoding="utf-8")

    # Prepare frames dir
    frames_dir = TMP_DIR / f"frames_{effect_name}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    # Clean previous frames
    for f in frames_dir.glob("*.png"):
        f.unlink()

    output = OUTPUT_DIR / f"demo_effect_{effect_name}.mp4"

    driver = _create_driver()
    try:
        driver.get(f"file://{html_path}")
        time.sleep(0.5)

        # Capture a few "before" frames
        _capture_frames(driver, frames_dir, num_frames=int(FPS * 0.5), interval=1.0 / FPS)
        before_count = int(FPS * 0.5)

        # Inject the effect via Selenium's execute_script
        def evaluate_js(script: str):
            return driver.execute_script(script)

        effect_obj.inject(evaluate_js, params)

        # For interactive effects, simulate mouse/interaction
        actions = ActionChains(driver)
        is_cursor_effect = effect_name.startswith("cursor_trail")
        if is_cursor_effect:
            # Move to absolute positions by using JS to dispatch mouse events
            for i in range(20):
                x = 200 + i * 40
                y = 300 + int(80 * ((-1) ** i))
                driver.execute_script(
                    f"document.dispatchEvent(new MouseEvent('mousemove', "
                    f"{{clientX: {x}, clientY: {y}, bubbles: true}}));"
                )
                time.sleep(0.08)
        elif effect_name == "ripple":
            cta = driver.find_element(By.ID, "cta")
            cta.click()
            time.sleep(0.3)
            h1 = driver.find_element(By.TAG_NAME, "h1")
            h1.click()
        elif effect_name == "highlight":
            btn = driver.find_element(By.CSS_SELECTOR, ".btn")
            actions.move_to_element(btn).perform()
            time.sleep(0.4)
            card = driver.find_element(By.CSS_SELECTOR, ".card")
            actions.move_to_element(card).perform()
            time.sleep(0.4)
            h1 = driver.find_element(By.TAG_NAME, "h1")
            actions.move_to_element(h1).perform()
        elif effect_name == "typewriter":
            inp = driver.find_element(By.ID, "demo-input")
            inp.click()
            for ch in "Hello DemoDSL!":
                inp.send_keys(ch)
                time.sleep(0.08)

        # Capture "after" frames for the remaining duration
        after_frames = int(FPS * DURATION_S) - before_count
        # Renumber frames continuing from before_count
        for i in range(after_frames):
            idx = before_count + i
            frame_path = frames_dir / f"frame_{idx:05d}.png"
            driver.save_screenshot(str(frame_path))
            time.sleep(1.0 / FPS)

    finally:
        driver.quit()

    return _frames_to_video(frames_dir, output)


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for effect in EFFECTS:
        print(f"Generating demo for effect: {effect}...")
        try:
            out = _generate_for_effect(effect)
            print(f"  ✓ {out.name}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    print(f"\nDone — {len(EFFECTS)} effect videos in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
