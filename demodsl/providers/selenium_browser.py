"""Selenium + CDP browser provider — supports true 4K recording via Chrome DevTools Protocol."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import threading
import time
from base64 import b64decode
from pathlib import Path
from typing import Any

from demodsl.models import Locator, Viewport
from demodsl.providers.base import BrowserProvider, BrowserProviderFactory

logger = logging.getLogger(__name__)


class _CDPFrameRecorder:
    """Captures frames via CDP Page.screencastFrame and assembles a video with ffmpeg.

    This allows true 4K (3840×2160) recording without requiring Xvfb or a
    physical display — Chrome renders headlessly and streams raw frames.
    """

    def __init__(
        self,
        driver: Any,
        frame_dir: Path,
        viewport: dict[str, int],
        *,
        fps: int = 30,
        quality: int = 95,
    ) -> None:
        self._driver = driver
        self._frame_dir = frame_dir
        self._viewport = viewport
        self._fps = fps
        self._quality = quality
        self._frame_count = 0
        self._recording = False
        self._lock = threading.Lock()

    def start(self) -> None:
        self._frame_dir.mkdir(parents=True, exist_ok=True)
        self._recording = True
        self._frame_count = 0

        # Enable CDP screencast
        self._driver.execute_cdp_cmd(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": self._quality,
                "maxWidth": self._viewport["width"],
                "maxHeight": self._viewport["height"],
                "everyNthFrame": 1,
            },
        )

        # Start background thread to poll for frames
        self._thread = threading.Thread(target=self._poll_frames, daemon=True)
        self._thread.start()
        logger.debug(
            "CDP screencast started at %dx%d",
            self._viewport["width"],
            self._viewport["height"],
        )

    def _poll_frames(self) -> None:
        """Poll CDP for screencast frames in background.

        Uses adaptive timing: measures how long each screenshot takes and
        sleeps only the remaining time to maintain the target FPS.
        """
        target_interval = 1.0 / self._fps
        while self._recording:
            t0 = time.monotonic()
            try:
                result = self._driver.execute_cdp_cmd(
                    "Page.captureScreenshot",
                    {
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
                )
                data = b64decode(result["data"])
                with self._lock:
                    frame_path = self._frame_dir / f"frame_{self._frame_count:06d}.jpg"
                    frame_path.write_bytes(data)
                    self._frame_count += 1
            except Exception:
                if self._recording:
                    logger.debug("Frame capture error, continuing", exc_info=True)

            elapsed = time.monotonic() - t0
            remaining = target_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def stop(self) -> int:
        self._recording = False
        if hasattr(self, "_thread"):
            self._thread.join(timeout=5)
        try:
            self._driver.execute_cdp_cmd("Page.stopScreencast", {})
        except Exception:
            pass
        logger.debug("CDP screencast stopped, %d frames captured", self._frame_count)
        return self._frame_count

    def assemble_video(self, output_path: Path) -> Path:
        """Assemble captured frames into a video using ffmpeg."""
        if self._frame_count == 0:
            logger.warning("No frames captured, cannot assemble video")
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(self._fps),
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
            "-movflags",
            "+faststart",
            "-s",
            f"{self._viewport['width']}x{self._viewport['height']}",
            str(output_path),
        ]
        logger.info(
            "Assembling %d frames → %s (%dx%d)",
            self._frame_count,
            output_path.name,
            self._viewport["width"],
            self._viewport["height"],
        )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error("ffmpeg failed: %s", result.stderr[-500:])
            raise RuntimeError(f"ffmpeg assembly failed: {result.stderr[-300:]}")

        logger.info(
            "Video assembled: %s (%.1f MB)",
            output_path.name,
            output_path.stat().st_size / 1e6,
        )
        return output_path


class SeleniumBrowserProvider(BrowserProvider):
    """Chrome via Selenium WebDriver with CDP-based 4K video recording.

    Supports viewports up to 3840×2160 (and beyond) — unlike Playwright
    whose built-in recording is limited by the viewport.

    Effects (JS injection) work identically via ``driver.execute_script()``.
    """

    def __init__(self) -> None:
        self._driver: Any = None
        self._viewport: dict[str, int] | None = None
        self._recorder: _CDPFrameRecorder | None = None
        self._frame_dir: Path | None = None
        self._video_dir: Path | None = None
        self._video_path: Path | None = None
        self._recording: bool = False

    def launch(
        self,
        browser_type: str,
        viewport: Viewport,
        video_dir: Path,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        self._start_driver(viewport, color_scheme=color_scheme, locale=locale)
        self._start_recording(viewport, video_dir)
        logger.info(
            "Selenium browser launched: chrome %dx%d (4K-capable)",
            viewport.width,
            viewport.height,
        )

    def launch_without_recording(
        self,
        browser_type: str,
        viewport: Viewport,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        self._start_driver(viewport, color_scheme=color_scheme, locale=locale)
        logger.info(
            "Selenium browser launched (no recording): %dx%d",
            viewport.width,
            viewport.height,
        )

    def _start_driver(
        self,
        viewport: Viewport,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={viewport.width},{viewport.height}")
        # Force exact viewport via device metrics
        options.add_argument("--force-device-scale-factor=1")
        options.add_argument("--hide-scrollbars")

        if locale:
            options.add_argument(f"--lang={locale}")

        if color_scheme == "dark":
            options.add_argument("--force-dark-mode")

        # High-res rendering
        options.add_argument("--high-dpi-support=1")

        self._driver = webdriver.Chrome(options=options)

        self._install_raf_shim()

        # Set exact viewport via CDP
        vp = {"width": viewport.width, "height": viewport.height}
        self._viewport = vp
        self._driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": viewport.width,
                "height": viewport.height,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )

    def _start_recording(self, viewport: Viewport, video_dir: Path) -> None:
        self._video_dir = video_dir
        self._frame_dir = Path(tempfile.mkdtemp(prefix="demodsl_frames_"))

        vp = {"width": viewport.width, "height": viewport.height}
        self._recorder = _CDPFrameRecorder(self._driver, self._frame_dir, vp)
        self._recorder.start()
        self._recording = True

    def restart_with_recording(self, video_dir: Path) -> None:
        current_url = self._driver.current_url if self._driver else None

        # Start recording on existing driver
        vp_obj = Viewport(
            width=self._viewport["width"],
            height=self._viewport["height"],
        )
        self._start_recording(vp_obj, video_dir)

        # Restore URL if needed
        if current_url and current_url != "data:,":
            self._driver.get(current_url)
        self._lock_horizontal_scroll()
        logger.info("Selenium recording started after warmup")

    def _install_raf_shim(self) -> None:
        """Replace requestAnimationFrame with setInterval-driven processing.

        Headless Chrome does not reliably fire rAF callbacks between CDP
        ``Page.captureScreenshot`` calls.  This shim ensures canvas/DOM
        animations execute at ~60 fps even without a real display.
        """
        self._driver.execute_script(
            """(() => {
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
            })()"""
        )

    def _lock_horizontal_scroll(self) -> None:
        self._driver.execute_script(
            "(()=>{"
            "if(document.getElementById('__demodsl_hscroll_lock'))return;"
            "const s=document.createElement('style');"
            "s.id='__demodsl_hscroll_lock';"
            "s.textContent='html,body{overflow-x:clip!important}';"
            "document.head.appendChild(s);"
            "})()"
        )

    def _unlock_horizontal_scroll(self) -> None:
        self._driver.execute_script(
            "(()=>{const s=document.getElementById('__demodsl_hscroll_lock');"
            "if(s)s.remove();})()"
        )

    def navigate(self, url: str) -> None:
        self._driver.get(url)
        # Wait for DOM ready
        self._driver.execute_script(
            "return new Promise(r => {"
            "  if (document.readyState === 'complete') r();"
            "  else window.addEventListener('load', r);"
            "})"
        )
        self._install_raf_shim()

    def reload(self) -> None:
        """Reload the current page — kills all JS execution and DOM cleanly."""
        self._driver.refresh()
        self._driver.execute_script(
            "return new Promise(r => {"
            "  if (document.readyState === 'complete') r();"
            "  else window.addEventListener('load', r);"
            "})"
        )
        self._install_raf_shim()
        self._lock_horizontal_scroll()

    def click(self, locator: Locator) -> None:
        element = self._find_element(locator)
        element.click()

    def type_text(self, locator: Locator, value: str) -> None:
        element = self._find_element(locator)
        element.clear()
        element.send_keys(value)

    def type_text_organic(
        self, locator: Locator, value: str, char_rate: float, variance: float = 0.0
    ) -> None:
        import random

        element = self._find_element(locator)
        element.click()
        element.clear()

        base_delay = 1.0 / char_rate
        word_len = 0
        for ch in value:
            if ch in " \t\n":
                factor = 1.0 + variance * 0.8
                word_len = 0
            elif ch in ".,;:!?'\"()-":
                factor = 1.0 + variance * 1.0
                word_len = 0
            else:
                word_len += 1
                if word_len > 6 and random.random() < 0.15:
                    factor = 1.0 + variance * 1.5
                else:
                    factor = (
                        random.uniform(1.0 - variance, 1.0 + variance)
                        if variance > 0
                        else 1.0
                    )
            delay_s = base_delay * max(factor, 0.2)
            element.send_keys(ch)
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
            self._driver.execute_script(
                f"window.scrollBy({{left:{delta_x},top:{delta_y},behavior:'smooth'}})"
            )
            max_wait = min(abs(delta_x or delta_y) / 800, 2.0) + 0.3
            time.sleep(max_wait)
        else:
            self._driver.execute_script(f"window.scrollBy({delta_x}, {delta_y})")
        if delta_x != 0:
            self._lock_horizontal_scroll()

    def wait_for(self, locator: Locator, timeout: float) -> None:
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        by, value = self._resolve_by(locator)
        WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Use CDP for full-viewport screenshot (supports 4K)
        result = self._driver.execute_cdp_cmd(
            "Page.captureScreenshot",
            {
                "format": "png",
                "clip": {
                    "x": 0,
                    "y": 0,
                    "width": self._viewport["width"],
                    "height": self._viewport["height"],
                    "scale": 1,
                },
                "captureBeyondViewport": False,
            },
        )
        path.write_bytes(b64decode(result["data"]))
        return path

    def evaluate_js(self, script: str) -> Any:
        snippet = script.strip()[:80].replace("\n", " ")
        logger.debug("evaluate_js: %s…", snippet)
        return self._driver.execute_script(script)

    def press_keys(self, keys: str) -> None:
        """Use Selenium ActionChains for keyboard shortcuts."""
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys

        _KEY_MAP = {
            "Control": Keys.CONTROL,
            "Meta": Keys.META,
            "Command": Keys.COMMAND,
            "Shift": Keys.SHIFT,
            "Alt": Keys.ALT,
            "Enter": Keys.ENTER,
            "Escape": Keys.ESCAPE,
            "Tab": Keys.TAB,
            "Backspace": Keys.BACKSPACE,
            "Delete": Keys.DELETE,
            "ArrowUp": Keys.ARROW_UP,
            "ArrowDown": Keys.ARROW_DOWN,
            "ArrowLeft": Keys.ARROW_LEFT,
            "ArrowRight": Keys.ARROW_RIGHT,
        }

        parts = keys.split("+")
        chain = ActionChains(self._driver)
        modifiers = []
        for part in parts[:-1]:
            mod = _KEY_MAP.get(part, part)
            chain.key_down(mod)
            modifiers.append(mod)

        final_key = _KEY_MAP.get(parts[-1], parts[-1].lower())
        chain.send_keys(final_key)

        for mod in reversed(modifiers):
            chain.key_up(mod)

        chain.perform()

    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        try:
            element = self._find_element(locator)
            loc = element.location
            size = element.size
            return (loc["x"] + size["width"] / 2, loc["y"] + size["height"] / 2)
        except Exception:
            return None

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        try:
            element = self._find_element(locator)
            loc = element.location
            size = element.size
            return {
                "x": float(loc["x"]),
                "y": float(loc["y"]),
                "width": float(size["width"]),
                "height": float(size["height"]),
            }
        except Exception:
            return None

    def close(self) -> Path | None:
        # Stop recording and assemble video
        if self._recorder and self._recording:
            self._recorder.stop()
            self._recording = False

            video_name = f"recording_{int(time.time())}.mp4"
            self._video_path = self._video_dir / video_name
            try:
                self._recorder.assemble_video(self._video_path)
            except RuntimeError:
                logger.error("Failed to assemble video", exc_info=True)
                self._video_path = None
            finally:
                # Cleanup frame directory
                if self._frame_dir and self._frame_dir.exists():
                    shutil.rmtree(self._frame_dir, ignore_errors=True)

        if self._driver:
            self._driver.quit()

        return self._video_path

    def _find_element(self, locator: Locator) -> Any:
        by, value = self._resolve_by(locator)
        return self._driver.find_element(by, value)

    @staticmethod
    def _resolve_by(locator: Locator) -> tuple[str, str]:
        from selenium.webdriver.common.by import By

        if locator.type == "css":
            return By.CSS_SELECTOR, locator.value
        if locator.type == "id":
            return By.ID, locator.value
        if locator.type == "xpath":
            return By.XPATH, locator.value
        if locator.type == "text":
            return By.XPATH, f"//*[contains(text(), '{locator.value}')]"
        raise ValueError(f"Unsupported locator type: {locator.type}")


# Register with factory
BrowserProviderFactory.register("selenium", SeleniumBrowserProvider)
