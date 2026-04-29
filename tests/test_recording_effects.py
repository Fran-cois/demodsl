"""Test recording with effects — simulates exact DemoDSL flow."""

import base64
import subprocess
import threading
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

FRAME_DIR = Path("/tmp/demodsl_test_frames")
FPS = 30


class SimpleRecorder:
    def __init__(self, driver, frame_dir, width, height):
        self._driver = driver
        self._frame_dir = frame_dir
        self._width = width
        self._height = height
        self._count = 0
        self._recording = False

    def start(self):
        self._frame_dir.mkdir(parents=True, exist_ok=True)
        self._recording = True
        self._count = 0
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        while self._recording:
            try:
                result = self._driver.execute_cdp_cmd(
                    "Page.captureScreenshot",
                    {
                        "format": "jpeg",
                        "quality": 80,
                        "clip": {
                            "x": 0,
                            "y": 0,
                            "width": self._width,
                            "height": self._height,
                            "scale": 1,
                        },
                        "captureBeyondViewport": False,
                    },
                )
                data = base64.b64decode(result["data"])
                (self._frame_dir / f"frame_{self._count:06d}.jpg").write_bytes(data)
                self._count += 1
            except Exception as e:
                if self._recording:
                    print(f"  Frame error: {e}")
            time.sleep(1.0 / FPS)

    def stop(self):
        self._recording = False
        self._thread.join(timeout=5)
        print(f"  Captured {self._count} frames")

    def assemble(self, out_path):
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(self._frame_dir / "frame_%06d.jpg"),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        print(f"  Video: {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


def main():
    import shutil

    if FRAME_DIR.exists():
        shutil.rmtree(FRAME_DIR)

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

        # Navigate
        d.get("http://127.0.0.1:8899/effects_showcase_page.html")
        time.sleep(1)

        # Re-install shim (page load destroyed it)
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

        # Start recording
        recorder = SimpleRecorder(d, FRAME_DIR, 1920, 1080)
        recorder.start()
        print("Recording started")

        # Wait 1 second with no effects → baseline
        time.sleep(1)

        # === Effect 1: BIG RED OVERLAY ===
        print("Injecting red overlay...")
        d.execute_script("""(() => {
            const div = document.createElement('div');
            div.id = '__test_red';
            div.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:999999;background:rgba(255,0,0,0.5);pointer-events:none;';
            div.textContent = 'RED OVERLAY TEST';
            div.style.color = 'white';
            div.style.fontSize = '100px';
            div.style.display = 'flex';
            div.style.alignItems = 'center';
            div.style.justifyContent = 'center';
            document.body.appendChild(div);
        })()""")
        red_exists = d.execute_script('return !!document.getElementById("__test_red")')
        print(f"  Red overlay exists: {red_exists}")
        time.sleep(2)

        # Remove red overlay
        d.execute_script("document.getElementById('__test_red')?.remove()")
        time.sleep(0.5)

        # === Effect 2: CONFETTI ===
        print("Injecting confetti...")
        d.execute_script("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__test_confetti';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const colors = ['#f44336','#e91e63','#9c27b0','#2196f3','#4caf50','#ff9800'];
            const pieces = Array.from({length: 200}, () => ({
                x: Math.random()*canvas.width, y: Math.random()*canvas.height * 0.3,
                w: Math.random()*20+10, h: Math.random()*15+5,
                color: colors[Math.floor(Math.random()*colors.length)],
                vy: Math.random()*5+3, vx: Math.random()*6-3, rot: Math.random()*360
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
                if (++frame < 200) requestAnimationFrame(draw);
                else canvas.remove();
            }
            draw();
        })()
        """)
        confetti_exists = d.execute_script('return !!document.getElementById("__test_confetti")')
        print(f"  Confetti canvas exists: {confetti_exists}")
        time.sleep(3)

        # Stop and assemble
        recorder.stop()
        out = Path("/tmp/test_effects_recording.mp4")
        recorder.assemble(out)

        # Extract key frames for verification
        for t in [1, 2, 4, 6]:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(t),
                    "-i",
                    str(out),
                    "-frames:v",
                    "1",
                    "-update",
                    "1",
                    f"/tmp/test_rec_frame_{t}s.png",
                ],
                capture_output=True,
                timeout=10,
            )
        print("Frames extracted: /tmp/test_rec_frame_*.png")

    finally:
        d.quit()


if __name__ == "__main__":
    main()
