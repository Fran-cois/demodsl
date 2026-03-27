#!/usr/bin/env python3
"""Generate demo videos for each browser JS effect.

Uses Playwright to load a styled HTML page, inject each effect's JS code,
and record a short screencast — one video per effect in docs/public/videos/.
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

# All 11 browser effects
EFFECTS = [
    "spotlight", "highlight", "confetti", "typewriter", "glow",
    "shockwave", "sparkle", "cursor_trail", "ripple", "neon_glow",
    "success_checkmark",
]

WIDTH, HEIGHT = 1280, 720


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


def _generate_for_effect(effect_name: str) -> Path:
    """Record a Playwright screencast with the given effect injected."""
    from playwright.sync_api import sync_playwright

    from demodsl.effects.browser_effects import (
        ConfettiEffect,
        CursorTrailEffect,
        GlowEffect,
        HighlightEffect,
        NeonGlowEffect,
        RippleEffect,
        ShockwaveEffect,
        SparkleEffect,
        SpotlightEffect,
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
    }

    effect_obj, params = effect_map[effect_name]

    # Write demo HTML to temp dir
    html_path = TMP_DIR / "demo_page.html"
    html_path.write_text(_DEMO_HTML, encoding="utf-8")

    raw_video = TMP_DIR / f"raw_{effect_name}.webm"
    output = OUTPUT_DIR / f"demo_effect_{effect_name}.mp4"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=str(TMP_DIR),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(f"file://{html_path}")
        page.wait_for_load_state("networkidle")

        # Small pause before effect
        time.sleep(0.5)

        # Inject the effect
        effect_obj.inject(page.evaluate, params)

        # For interactive effects, simulate mouse/interaction
        if effect_name == "cursor_trail":
            for i in range(20):
                x = 200 + i * 40
                y = 300 + int(80 * ((-1) ** i))
                page.mouse.move(x, y)
                time.sleep(0.08)
        elif effect_name == "ripple":
            page.click("#cta")
            time.sleep(0.3)
            page.click("h1")
            time.sleep(0.3)
        elif effect_name == "highlight":
            page.hover(".btn")
            time.sleep(0.5)
            page.hover(".card")
            time.sleep(0.5)
            page.hover("h1")
            time.sleep(0.5)
        elif effect_name == "typewriter":
            page.click("#demo-input")
            page.keyboard.type("Hello DemoDSL!", delay=80)

        # Let effect play
        time.sleep(2.5)

        # Get the video path before closing
        video_path = page.video.path()
        context.close()
        browser.close()

    # Convert webm to mp4
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-t", "4",
        "-an",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ ffmpeg conversion failed: {result.stderr[-200:]}")
        return raw_video

    return output


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
