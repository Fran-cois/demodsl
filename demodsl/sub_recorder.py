"""Sub-demo recorder — captures a short video clip of a URL for embedding
inside a ``SecondaryWindow`` when the URL blocks iframe embedding.

Used by ``iframe_precheck.auto_record_blocked_urls``.  Records a fresh
headless Chromium session (isolated from the main demo), performs a gentle
scroll-down/scroll-up animation, and writes an MP4 file.

Design constraints addressed:
- Muted, no narration, no subtitles (the video will be embedded silent
  and looped; the main demo owns all audio/subtitles).
- Independent browser instance — no interference with the main demo's
  recorder or monitor plugin.
- Persistent cache keyed by (url, width, height, duration, version) so
  repeat runs skip the recording.
- Strict timeouts — never blocks the demo forever.
- Fails gracefully: on any error, returns ``None`` and the caller falls
  back to stripping the URL.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_ROOT = Path.home() / ".cache" / "demodsl" / "subrec"
_SUBREC_VERSION = "v1"
_GOTO_TIMEOUT_MS = 15_000
_DEFAULT_DURATION = 8.0
_SCROLL_PIXELS = 220


def _cache_key(url: str, width: int, height: int, duration: float) -> str:
    raw = f"{_SUBREC_VERSION}|{url}|{width}x{height}|{duration}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def record_sub_demo(
    url: str,
    *,
    width: int,
    height: int,
    duration: float = _DEFAULT_DURATION,
    cache_dir: Path | None = None,
    force: bool = False,
) -> Path | None:
    """Record ``url`` into a short MP4.  Returns the MP4 path or ``None``.

    Uses Playwright's built-in video recording (webm) + ffmpeg conversion.
    Results are cached in ``cache_dir`` (default ``~/.cache/demodsl/subrec``).
    """
    if shutil.which("ffmpeg") is None:
        logger.warning("[sub-recorder] ffmpeg not found — skipping %s", url)
        return None

    cache_root = cache_dir or _CACHE_ROOT
    cache_root.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url, width, height, duration)
    out_path = cache_root / f"{key}.mp4"
    if out_path.exists() and not force:
        logger.info("[sub-recorder] cache hit: %s → %s", url, out_path.name)
        return out_path

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        logger.warning("[sub-recorder] playwright not installed — skipping %s", url)
        return None

    logger.info("[sub-recorder] recording %s (%dx%d, %.1fs)…", url, width, height, duration)

    # Run the Playwright sync API in a dedicated thread so it never
    # collides with the main engine's asyncio event loop.
    def _do_record() -> Path | None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="demodsl_subrec_"))
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    record_video_dir=str(tmp_dir),
                    record_video_size={"width": width, "height": height},
                )
                page = context.new_page()
                page.set_default_timeout(_GOTO_TIMEOUT_MS)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=_GOTO_TIMEOUT_MS)
                except Exception as exc:
                    logger.warning(
                        "[sub-recorder] goto failed for %s (%s) — recording partial page",
                        url,
                        exc,
                    )
                # Initial pause so the page settles
                page.wait_for_timeout(1500)
                # Gentle scroll-down / scroll-up cycle across the duration budget
                total_ms = max(2000, int(duration * 1000) - 1500)
                steps = max(2, min(8, int(duration // 1)))
                dwell = max(150, total_ms // (steps * 2))
                for _ in range(steps):
                    try:
                        page.evaluate(f"window.scrollBy(0, {_SCROLL_PIXELS})")
                    except Exception:
                        pass
                    page.wait_for_timeout(dwell)
                for _ in range(steps):
                    try:
                        page.evaluate(f"window.scrollBy(0, -{_SCROLL_PIXELS})")
                    except Exception:
                        pass
                    page.wait_for_timeout(dwell)
                video_handle = page.video
                context.close()  # flushes webm to disk
                browser.close()

                if video_handle is None:
                    logger.warning("[sub-recorder] no video captured for %s", url)
                    return None
                webm_path = Path(video_handle.path())
                if not webm_path.exists() or webm_path.stat().st_size == 0:
                    logger.warning("[sub-recorder] empty video for %s", url)
                    return None

                # Convert webm → mp4 (H.264, no audio, web-friendly moov atom)
                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-loglevel",
                            "error",
                            "-i",
                            str(webm_path),
                            "-c:v",
                            "libx264",
                            "-pix_fmt",
                            "yuv420p",
                            "-movflags",
                            "+faststart",
                            "-an",
                            str(out_path),
                        ],
                        check=True,
                        timeout=60,
                    )
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ) as exc:
                    logger.warning("[sub-recorder] ffmpeg failed for %s: %s", url, exc)
                    return None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[sub-recorder] unexpected error for %s: %s", url, exc)
            return None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return out_path

    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(_do_record).result()

    if result is None:
        return None

    logger.info(
        "[sub-recorder] done: %s → %s (%.1f KB)",
        url,
        out_path.name,
        out_path.stat().st_size / 1024,
    )
    return out_path
