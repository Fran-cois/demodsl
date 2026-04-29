"""Minimal integration test: inject confetti, capture CDP screenshot, check pixels."""

import base64
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def main():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")

    d = webdriver.Chrome(options=opts)
    d.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1920,
            "height": 1080,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )

    try:
        # Navigate
        d.get("http://127.0.0.1:8899/effects_showcase_page.html")
        time.sleep(1)

        # Install rAF shim
        d.execute_script("""(() => {
            if (window.__demodsl_raf_shim) return;
            window.__demodsl_raf_shim = true;
            const cbs = new Map();
            let nextId = 1;
            window.requestAnimationFrame = function(cb) {
                const id = nextId++;
                cbs.set(id, cb);
                return id;
            };
            window.cancelAnimationFrame = function(id) {
                cbs.delete(id);
            };
            setInterval(() => {
                const now = performance.now();
                const pending = Array.from(cbs.entries());
                cbs.clear();
                for (const [, cb] of pending) {
                    try { cb(now); } catch(e) {}
                }
            }, 16);
        })()""")

        # Screenshot BEFORE effects
        shot1 = d.execute_cdp_cmd(
            "Page.captureScreenshot",
            {
                "format": "png",
                "clip": {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1},
                "captureBeyondViewport": False,
            },
        )
        Path("/tmp/before_effects.png").write_bytes(base64.b64decode(shot1["data"]))
        print("Screenshot before: /tmp/before_effects.png")

        # Inject confetti (same code as ConfettiEffect)
        d.execute_script("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_confetti';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const colors = ['#f44336','#e91e63','#9c27b0','#2196f3','#4caf50','#ff9800'];
            const pieces = Array.from({length: 80}, () => ({
                x: Math.random()*canvas.width, y: -20,
                w: Math.random()*8+4, h: Math.random()*6+2,
                color: colors[Math.floor(Math.random()*colors.length)],
                vy: Math.random()*3+2, vx: Math.random()*4-2, rot: Math.random()*360
            }));
            let frame = 0;
            function draw() {
                ctx.clearRect(0,0,canvas.width,canvas.height);
                pieces.forEach(p => {
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.fillStyle=p.color; ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);
                    ctx.restore();
                    p.y+=p.vy; p.x+=p.vx; p.rot+=3;
                });
                if (++frame < 120) requestAnimationFrame(draw);
                else canvas.remove();
            }
            draw();
        })()
        """)

        # Check canvas exists
        has_canvas = d.execute_script("return !!document.getElementById('__demodsl_confetti')")
        print(f"Canvas exists after inject: {has_canvas}")

        # Wait for animation frames to process
        time.sleep(0.5)

        # Check how many frames the rAF shim processed
        frame_count = d.execute_script("""
            return document.getElementById('__demodsl_confetti') ? 'still present' : 'removed (animation done)';
        """)
        print(f"Canvas after 0.5s: {frame_count}")

        # Screenshot AFTER effects
        shot2 = d.execute_cdp_cmd(
            "Page.captureScreenshot",
            {
                "format": "png",
                "clip": {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1},
                "captureBeyondViewport": False,
            },
        )
        Path("/tmp/after_effects.png").write_bytes(base64.b64decode(shot2["data"]))
        print("Screenshot after: /tmp/after_effects.png")

        # Compare sizes — effects should make the image bigger
        s1 = Path("/tmp/before_effects.png").stat().st_size
        s2 = Path("/tmp/after_effects.png").stat().st_size
        print(f"Before size: {s1} bytes, After size: {s2} bytes, Diff: {s2 - s1}")

        # Also test: inject a VERY obvious red overlay (non-canvas, pure DOM)
        d.execute_script("""
        (() => {
            const div = document.createElement('div');
            div.id = '__demodsl_test_overlay';
            div.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:999999;background:rgba(255,0,0,0.5);pointer-events:none;';
            document.body.appendChild(div);
        })()
        """)
        has_overlay = d.execute_script("return !!document.getElementById('__demodsl_test_overlay')")
        print(f"Red overlay exists: {has_overlay}")
        time.sleep(0.2)

        shot3 = d.execute_cdp_cmd(
            "Page.captureScreenshot",
            {
                "format": "png",
                "clip": {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1},
                "captureBeyondViewport": False,
            },
        )
        Path("/tmp/red_overlay.png").write_bytes(base64.b64decode(shot3["data"]))
        s3 = Path("/tmp/red_overlay.png").stat().st_size
        print(f"Red overlay screenshot: {s3} bytes (vs before {s1})")
        print("Screenshot: /tmp/red_overlay.png")

    finally:
        d.quit()


if __name__ == "__main__":
    main()
