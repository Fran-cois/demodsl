"""Playwright-based browser provider."""

from __future__ import annotations

import base64
import json
import logging
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from demodsl.models import Locator, Viewport
from demodsl.providers.base import BrowserProvider, BrowserProviderFactory

logger = logging.getLogger(__name__)

_BROWSER_MAP = {"chrome": "chromium", "firefox": "firefox", "webkit": "webkit"}


# ── CDP frame-by-frame recorder (raw WebSocket, thread-safe) ─────────────────


def _free_port() -> int:
    """Find a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _RawCDPRecorder:
    """High-quality recorder using a *direct* WebSocket connection to
    Chrome's ``--remote-debugging-port``.

    Completely independent of Playwright's threading model — uses
    ``websocket-client`` to connect to Chrome's DevTools endpoint and
    captures JPEG frames via ``Page.captureScreenshot`` in a background
    thread, then assembles them into an H.264 MP4 with ffmpeg.
    """

    def __init__(
        self,
        debug_port: int,
        frame_dir: Path,
        viewport: dict[str, int],
        *,
        fps: int = 30,
        quality: int = 95,
    ) -> None:
        self._port = debug_port
        self._frame_dir = frame_dir
        self._viewport = viewport
        self._fps = fps
        self._quality = quality
        self._frame_count = 0
        self._recording = False
        self._ws: Any = None
        self._lock = threading.Lock()
        self._msg_id = 0

    # ── lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Connect to Chrome's debug port and start capturing frames."""
        import websocket as ws_client  # websocket-client

        self._frame_dir.mkdir(parents=True, exist_ok=True)

        # Discover the page target's WebSocket URL
        page_ws = self._discover_page_ws(timeout=10.0)
        if not page_ws:
            raise RuntimeError(f"No debuggable page found on port {self._port}")

        self._ws = ws_client.WebSocket()
        self._ws.settimeout(5)
        self._ws.connect(page_ws)

        self._recording = True
        self._frame_count = 0
        self._start_time = time.monotonic()
        self._end_time = self._start_time
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.debug(
            "Raw CDP recording started (%dx%d @ %dfps, port %d)",
            self._viewport["width"],
            self._viewport["height"],
            self._fps,
            self._port,
        )

    def stop(self) -> int:
        self._recording = False
        self._end_time = time.monotonic()
        if hasattr(self, "_thread"):
            self._thread.join(timeout=5)
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        elapsed = self._end_time - self._start_time
        actual_fps = self._frame_count / elapsed if elapsed > 0 else self._fps
        logger.debug(
            "Raw CDP recording stopped — %d frames in %.1fs (%.1f fps)",
            self._frame_count,
            elapsed,
            actual_fps,
        )
        return self._frame_count

    # ── capture loop ──────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        interval = 1.0 / self._fps
        while self._recording:
            t0 = time.monotonic()
            try:
                self._msg_id += 1
                request = json.dumps(
                    {
                        "id": self._msg_id,
                        "method": "Page.captureScreenshot",
                        "params": {
                            "format": "jpeg",
                            "quality": self._quality,
                            "clip": {
                                "x": 0,
                                "y": 0,
                                "width": self._viewport["width"],
                                "height": self._viewport["height"],
                                "scale": 1,
                            },
                            "captureBeyondViewport": False,
                        },
                    }
                )
                self._ws.send(request)
                raw = self._ws.recv()
                resp = json.loads(raw)
                if "result" in resp and "data" in resp["result"]:
                    img = base64.b64decode(resp["result"]["data"])
                    with self._lock:
                        path = self._frame_dir / f"frame_{self._frame_count:06d}.jpg"
                        path.write_bytes(img)
                        self._frame_count += 1
            except Exception:
                if self._recording:
                    logger.debug("CDP frame capture error (transient)", exc_info=True)
            elapsed = time.monotonic() - t0
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    # ── helpers ───────────────────────────────────────────────────────

    def _discover_page_ws(self, timeout: float = 10.0) -> str | None:
        """Poll ``/json`` until a page target appears."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{self._port}/json", timeout=2
                )
                targets = json.loads(resp.read(1_048_576))  # 1 MB limit
                for t in targets:
                    if t.get("type") == "page":
                        return t.get("webSocketDebuggerUrl")
            except Exception:
                pass
            time.sleep(0.2)
        return None

    def assemble(self, output: Path) -> Path:
        """Assemble captured JPEG frames into an H.264 MP4."""
        if self._frame_count == 0:
            raise RuntimeError("CDP recorder captured 0 frames")

        # Use actual captured FPS so playback matches real-time
        elapsed = self._end_time - self._start_time
        actual_fps = round(self._frame_count / elapsed) if elapsed > 0 else self._fps
        actual_fps = max(10, min(actual_fps, 60))  # clamp to sane range

        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(actual_fps),
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
            "-s",
            f"{self._viewport['width']}x{self._viewport['height']}",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg frame assembly failed: {result.stderr[-300:]}")
        logger.info(
            "CDP video assembled: %s (%d frames, %.1f MB)",
            output.name,
            self._frame_count,
            output.stat().st_size / 1e6,
        )
        return output

    def cleanup(self) -> None:
        """Remove temporary frame directory."""
        if self._frame_dir and self._frame_dir.exists():
            shutil.rmtree(self._frame_dir, ignore_errors=True)


# ── Playwright browser provider ─────────────────────────────────────────────


class PlaywrightBrowserProvider(BrowserProvider):
    def __init__(self) -> None:
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._viewport: dict[str, int] | None = None
        self._color_scheme: str | None = None
        self._locale: str | None = None
        # CDP high-quality recording (Chromium only)
        self._is_chromium: bool = False
        self._debug_port: int = 0
        self._cdp_recorder: _RawCDPRecorder | None = None
        self._video_dir: Path | None = None
        self._frame_dir: Path | None = None

    def launch(
        self,
        browser_type: str,
        viewport: Viewport,
        video_dir: Path,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        engine_name = _BROWSER_MAP.get(browser_type, "chromium")
        self._is_chromium = engine_name == "chromium"
        launcher = getattr(self._pw, engine_name)

        launch_kwargs: dict[str, Any] = {"headless": True}
        if self._is_chromium:
            self._debug_port = _free_port()
            launch_kwargs["args"] = [
                f"--remote-debugging-port={self._debug_port}",
                "--remote-allow-origins=*",
            ]

        self._browser = launcher.launch(**launch_kwargs)
        vp = {"width": viewport.width, "height": viewport.height}
        self._viewport = vp
        self._color_scheme = color_scheme
        self._locale = locale

        ctx_kwargs: dict[str, Any] = {"viewport": vp}
        if not self._is_chromium:
            ctx_kwargs["record_video_dir"] = str(video_dir)
            ctx_kwargs["record_video_size"] = vp
        if color_scheme is not None:
            ctx_kwargs["color_scheme"] = color_scheme
        if locale is not None:
            ctx_kwargs["locale"] = locale
        self._context = self._browser.new_context(**ctx_kwargs)
        self._page = self._context.new_page()
        self._lock_horizontal_scroll()

        if self._is_chromium:
            if not self._start_cdp_recording(video_dir):
                # Fallback: recreate context with native VP8 recording
                self._context.close()
                ctx_kwargs["record_video_dir"] = str(video_dir)
                ctx_kwargs["record_video_size"] = vp
                self._context = self._browser.new_context(**ctx_kwargs)
                self._page = self._context.new_page()
                self._lock_horizontal_scroll()
                self._is_chromium = False

        mode = "CDP" if self._cdp_recorder else "native"
        logger.info(
            "Browser launched: %s %dx%d (%s recording)",
            engine_name,
            viewport.width,
            viewport.height,
            mode,
        )

    def launch_without_recording(
        self,
        browser_type: str,
        viewport: Viewport,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        engine_name = _BROWSER_MAP.get(browser_type, "chromium")
        self._is_chromium = engine_name == "chromium"
        launcher = getattr(self._pw, engine_name)

        launch_kwargs: dict[str, Any] = {"headless": True}
        if self._is_chromium:
            self._debug_port = _free_port()
            launch_kwargs["args"] = [
                f"--remote-debugging-port={self._debug_port}",
                "--remote-allow-origins=*",
            ]

        self._browser = launcher.launch(**launch_kwargs)
        vp = {"width": viewport.width, "height": viewport.height}
        self._viewport = vp
        self._color_scheme = color_scheme
        self._locale = locale
        ctx_kwargs: dict[str, Any] = {"viewport": vp}
        if color_scheme is not None:
            ctx_kwargs["color_scheme"] = color_scheme
        if locale is not None:
            ctx_kwargs["locale"] = locale
        self._context = self._browser.new_context(**ctx_kwargs)
        self._page = self._context.new_page()
        self._lock_horizontal_scroll()
        logger.info(
            "Browser launched (no recording): %s %dx%d",
            engine_name,
            viewport.width,
            viewport.height,
        )

    def restart_with_recording(self, video_dir: Path) -> None:
        current_url = self._page.url if self._page else None

        # Grab the page background colour before closing the warmup context
        # so we can paint it during navigation in the recording context.
        bg_color: str = "#ffffff"
        if self._page and current_url and current_url != "about:blank":
            try:
                bg_color = self._page.evaluate(
                    "(()=>{"
                    "const s=getComputedStyle(document.documentElement);"
                    "let c=s.backgroundColor;"
                    "if(!c||c==='rgba(0, 0, 0, 0)')c=getComputedStyle(document.body).backgroundColor;"
                    "return c||'#ffffff';"
                    "})()"
                )
            except Exception:
                pass

        # Close warmup context (no video produced)
        if self._context:
            self._context.close()

        # Open new context — without native VP8 recording for Chromium
        # (CDP screenshots are used instead).
        ctx_kwargs: dict[str, Any] = {"viewport": self._viewport}
        if not self._is_chromium:
            ctx_kwargs["record_video_dir"] = str(video_dir)
            ctx_kwargs["record_video_size"] = self._viewport
        if self._color_scheme is not None:
            ctx_kwargs["color_scheme"] = self._color_scheme
        if self._locale is not None:
            ctx_kwargs["locale"] = self._locale
        self._context = self._browser.new_context(**ctx_kwargs)

        # Paint about:blank with the target background colour at
        # document-start, so the browser never shows white.
        self._context.add_init_script(
            f"document.documentElement.style.background='{bg_color}';"
        )

        self._page = self._context.new_page()

        if self._is_chromium:
            if not self._start_cdp_recording(video_dir):
                # Fallback: recreate with native recording
                self._context.close()
                ctx_kwargs["record_video_dir"] = str(video_dir)
                ctx_kwargs["record_video_size"] = self._viewport
                self._context = self._browser.new_context(**ctx_kwargs)
                self._context.add_init_script(
                    f"document.documentElement.style.background='{bg_color}';"
                )
                self._page = self._context.new_page()

        self._lock_horizontal_scroll()
        self._warm_url = current_url
        mode = "CDP" if self._cdp_recorder else "native"
        logger.info("Recording started after warmup (%s)", mode)

    def _lock_horizontal_scroll(self) -> None:
        """Inject a <style> tag to prevent unintended horizontal scrolling.

        Uses ``overflow-x: clip`` instead of ``hidden`` to avoid the CSS
        spec rule that changes ``overflow-y: visible`` → ``auto`` when the
        other axis is not ``visible``, which would break ``window.scrollBy``
        and ``window.scrollY``.
        """
        self._page.evaluate(
            "(()=>{"
            "if(document.getElementById('__demodsl_hscroll_lock'))return;"
            "const s=document.createElement('style');"
            "s.id='__demodsl_hscroll_lock';"
            "s.textContent='html,body{overflow-x:clip!important}';"
            "document.head.appendChild(s);"
            "})()"
        )

    def _unlock_horizontal_scroll(self) -> None:
        """Remove the horizontal scroll lock (before intentional horizontal scroll)."""
        self._page.evaluate(
            "(()=>{const s=document.getElementById('__demodsl_hscroll_lock');"
            "if(s)s.remove();})()"
        )

    def navigate(self, url: str) -> None:
        # Skip redundant navigation when already on the target URL
        # (e.g. after pre-navigation + restart_with_recording).
        if self._page.url == url:
            logger.debug("Already at %s — skipping navigate", url)
            return
        self._page.goto(url, wait_until="load")
        # Wait for CSS and fonts to finish rendering so the first visible
        # frames after navigation are not blank.
        try:
            self._page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # best-effort; some pages never reach networkidle
        self._lock_horizontal_scroll()

    def click(self, locator: Locator) -> None:
        selector = self._resolve_selector(locator)
        self._page.click(selector)

    def type_text(self, locator: Locator, value: str) -> None:
        selector = self._resolve_selector(locator)
        self._page.fill(selector, value)

    def type_text_organic(
        self, locator: Locator, value: str, char_rate: float, variance: float = 0.0
    ) -> None:
        selector = self._resolve_selector(locator)
        base_delay = 1.0 / char_rate  # seconds per character
        self._page.click(selector)
        if variance <= 0:
            self._page.type(selector, value, delay=base_delay * 1000)
            return
        # Character-by-character with human-like variance
        import random

        word_len = 0
        for ch in value:
            if ch in " \t\n":
                factor = 1.0 + variance * 0.8  # pause on spaces
                word_len = 0
            elif ch in ".,;:!?'\"()-":
                factor = 1.0 + variance * 1.0  # longer pause on punctuation
                word_len = 0
            else:
                word_len += 1
                if word_len > 6 and random.random() < 0.15:
                    factor = 1.0 + variance * 1.5  # micro-hesitation mid-word
                else:
                    factor = random.uniform(1.0 - variance, 1.0 + variance)
            delay_s = base_delay * max(factor, 0.2)
            self._page.type(selector, ch, delay=0)
            time.sleep(delay_s)

    def scroll(self, direction: str, pixels: int, *, smooth: bool = False) -> None:
        delta_x, delta_y = 0, 0
        if direction == "down":
            delta_y = pixels
        elif direction == "up":
            delta_y = -pixels
        elif direction == "right":
            delta_x = pixels
        elif direction == "left":
            delta_x = -pixels
        if delta_x != 0:
            self._unlock_horizontal_scroll()
        if smooth:
            self._page.evaluate(
                f"window.scrollBy({{left:{delta_x},top:{delta_y},behavior:'smooth'}})"
            )
            # Wait for smooth scroll to reach its destination
            max_wait = min(abs(delta_x or delta_y) / 800, 2.0) + 0.3
            self._page.evaluate(
                f"""(async () => {{
                    const target = window.scrollY + {delta_y} - {delta_y};
                    const start = Date.now();
                    let prev = -1;
                    while (Date.now() - start < {int(max_wait * 1000)}) {{
                        const cur = window.scrollY;
                        if (cur === prev && prev !== -1) break;
                        prev = cur;
                        await new Promise(r => setTimeout(r, 60));
                    }}
                }})()"""
            )
        else:
            self._page.evaluate(f"window.scrollBy({delta_x}, {delta_y})")
        if delta_x != 0:
            self._lock_horizontal_scroll()

    def wait_for(self, locator: Locator, timeout: float) -> None:
        selector = self._resolve_selector(locator)
        self._page.wait_for_selector(selector, timeout=int(timeout * 1000))

    def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(path))
        return path

    def evaluate_js(self, script: str) -> Any:
        return self._page.evaluate(script)

    def press_keys(self, keys: str) -> None:
        """Use Playwright's native keyboard API for reliable shortcut handling."""
        self._page.keyboard.press(keys)

    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        selector = self._resolve_selector(locator)
        try:
            box = self._page.locator(selector).first.bounding_box(timeout=3000)
        except Exception:
            return None
        if box is None:
            return None
        return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        selector = self._resolve_selector(locator)
        try:
            box = self._page.locator(selector).first.bounding_box(timeout=3000)
        except Exception:
            return None
        return box

    def close(self) -> Path | None:
        video_path: Path | None = None

        if self._cdp_recorder:
            # CDP recording: stop capture, assemble frames → MP4
            count = self._cdp_recorder.stop()
            if count > 0 and self._video_dir:
                video_path = self._video_dir / "cdp_recording.mp4"
                self._cdp_recorder.assemble(video_path)
            else:
                logger.warning("CDP recorder captured 0 frames — no video output")
            self._cdp_recorder.cleanup()
            self._cdp_recorder = None
        elif self._page and self._page.video:
            video_path = Path(self._page.video.path())

        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        return video_path

    def _start_cdp_recording(self, video_dir: Path) -> bool:
        """Start raw CDP screenshot recording. Returns True on success."""
        if not self._debug_port:
            return False
        try:
            self._frame_dir = Path(tempfile.mkdtemp(prefix="demodsl_cdp_frames_"))
            self._cdp_recorder = _RawCDPRecorder(
                self._debug_port,
                self._frame_dir,
                self._viewport,
                fps=30,
                quality=95,
            )
            self._cdp_recorder.start()
            self._video_dir = video_dir
            return True
        except Exception as e:
            logger.warning("CDP recording unavailable, falling back to native: %s", e)
            if self._frame_dir and self._frame_dir.exists():
                shutil.rmtree(self._frame_dir, ignore_errors=True)
            self._cdp_recorder = None
            self._is_chromium = False
            return False

    @staticmethod
    def _resolve_selector(locator: Locator) -> str:
        if locator.type == "css":
            return locator.value
        if locator.type == "id":
            return f"#{locator.value}"
        if locator.type == "xpath":
            return f"xpath={locator.value}"
        if locator.type == "text":
            return f"text={locator.value}"
        raise ValueError(f"Unsupported locator type: {locator.type}")


# Register with factory
BrowserProviderFactory.register("playwright", PlaywrightBrowserProvider)
