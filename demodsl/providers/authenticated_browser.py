"""Browser providers that reuse an *already-authenticated* Chrome session.

These providers exist to demo flows that require a real, signed-in browser
— typically **social login** (Google / GitHub / Microsoft OAuth).  A fresh
Playwright/Chromium context (the stock :class:`PlaywrightBrowserProvider`)
is rejected by Google with *"This browser or app may not be secure"* /
``disallowed_useragent`` because it has ``navigator.webdriver === true``, no
browsing history and uses the bundled Chromium build instead of real Chrome.

Two strategies are provided, both selectable via ``provider:`` in the YAML:

``playwright-cdp``
    Attaches to a Chrome **you launched yourself** with
    ``--remote-debugging-port`` and signed into Google by hand.  The most
    robust option against Google's automation detection — it is a genuine
    human Chrome session.  Configure with ``DEMODSL_CDP_URL``
    (default ``http://127.0.0.1:9222``).

    Launch that Chrome with ``--remote-allow-origins=*`` as well, otherwise
    Chrome rejects the CDP video recorder's WebSocket (403) and the demo
    runs without a recording.

``playwright-persistent``
    Launches real Chrome (``channel=chrome``) against a **reusable profile
    directory** where you signed into Google once.  Cookies/session persist
    across runs.  Configure with ``DEMODSL_USER_DATA_DIR`` (required) and,
    optionally, ``DEMODSL_CHROME_CHANNEL`` / ``DEMODSL_BROWSER_HEADLESS``.

Both reuse the parent's CDP screenshot recorder, interaction and effect
machinery — only browser *acquisition* and teardown differ.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from demodsl.models import Viewport
from demodsl.providers.base import BrowserProviderFactory
from demodsl.providers.browser import (
    PlaywrightBrowserProvider,
    _chromium_stability_args,
    _free_port,
)

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a truthy/falsey environment variable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class _AuthenticatedBrowserBase(PlaywrightBrowserProvider):
    """Shared lifecycle for providers backed by an existing browser session.

    Unlike the stock provider, these never *recreate* the browser context
    when recording starts — doing so would drop the authenticated session
    (persistent profile) or close the user's real browser (CDP attach).
    Instead the same page is kept throughout and CDP screenshot recording
    is started in-place.
    """

    # Whether ``close()`` is allowed to terminate the underlying browser.
    # Persistent profile → yes (we own it).  CDP attach → no (user owns it).
    _owns_browser: bool = True

    def __init__(self) -> None:
        super().__init__()
        # These providers are always Chromium-based.
        self._is_chromium = True
        # Per-scenario auth config (overrides DEMODSL_* env vars).  Set by
        # the orchestrator via :meth:`set_auth_config` before launch.
        self._auth: dict[str, Any] = {}
        # Native Playwright video recording (smooth, full frame rate) instead
        # of the periodic CDP screenshot recorder.  Resolved at launch.
        self._native_video: bool = False
        self._native_video_dir: Path | None = None
        # monotonic timestamps used to trim the warm-up preamble out of the
        # native recording (which starts at launch, before the demo proper).
        self._video_start_mono: float = 0.0
        self._record_from_mono: float = 0.0

    def _wants_native_video(self) -> bool:
        """Resolve the recording backend: scenario ``auth.record`` -> env -> cdp."""
        val = self._auth.get("record")
        if val is None:
            val = os.environ.get("DEMODSL_RECORD")
        return (val or "cdp").strip().lower() == "playwright"

    def set_auth_config(self, config: dict[str, Any] | None) -> None:
        """Apply per-scenario auth config (from ``scenario.auth``).

        Values present here take precedence over the global ``DEMODSL_*``
        environment variables, enabling several scenarios to each drive
        their own authenticated browser session.
        """
        self._auth = {k: v for k, v in (config or {}).items() if v is not None}

    def _auth_str(self, key: str, env: str, default: str | None) -> str | None:
        """Resolve a string setting: scenario auth → env var → default."""
        val = self._auth.get(key)
        if val is not None:
            return str(val)
        return os.environ.get(env, default)

    def _auth_flag(self, key: str, env: str, default: bool) -> bool:
        """Resolve a boolean setting: scenario auth → env var → default."""
        val = self._auth.get(key)
        if val is not None:
            return bool(val)
        return _env_flag(env, default=default)

    # ── recording: start in-place, never recreate the context ──────────

    def restart_with_recording(self, video_dir: Path) -> None:
        current_url = self._page.url if self._page else None
        if self._native_video:
            # Native Playwright video is already recording since launch. Mark
            # the logical start so the warm-up preamble can be trimmed off in
            # close().  Skip the CDP recorder and the re-navigate: the context
            # is NOT recreated, so the pre-navigated DOM is still live.
            self._record_from_mono = time.monotonic()
            self._video_dir = video_dir
            self._warm_url = None
            self._lock_horizontal_scroll()
            logger.info("Recording in-place (%s, native Playwright video)", type(self).__name__)
            return
        if not self._start_cdp_recording(video_dir):
            logger.warning(
                "CDP recording unavailable for %s — proceeding without video. "
                "If using playwright-cdp, ensure Chrome was launched with "
                "--remote-allow-origins=* so the recorder's WebSocket is accepted.",
                type(self).__name__,
            )
        self._lock_horizontal_scroll()
        self._warm_url = current_url
        logger.info("Recording started in-place (%s, CDP)", type(self).__name__)

    def launch(
        self,
        browser_type: str,
        viewport: Viewport,
        video_dir: Path,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        self.launch_without_recording(
            browser_type,
            viewport,
            color_scheme=color_scheme,
            locale=locale,
        )
        self.restart_with_recording(video_dir)

    # ── teardown: assemble video but respect browser ownership ─────────

    def close(self) -> Path | None:
        import shutil

        video_path: Path | None = None

        # Native Playwright video: grab the handle BEFORE closing the context
        # (Playwright finalises the .webm only when the context closes).
        native_video_obj = None
        if self._native_video and self._page is not None:
            try:
                native_video_obj = self._page.video
            except Exception:
                native_video_obj = None

        if self._cdp_recorder:
            count = self._cdp_recorder.stop()
            if count > 0 and self._video_dir:
                video_path = self._video_dir / "cdp_recording.mp4"
                self._cdp_recorder.assemble(video_path)
            else:
                logger.warning("CDP recorder captured 0 frames — no video output")
            self._cdp_recorder.cleanup()
            self._cdp_recorder = None

        if self._owns_browser:
            if self._context:
                try:
                    self._context.close()
                except Exception:
                    pass
        else:
            # CDP attach: leave the user's browser running, just detach.
            logger.info("Detaching from attached browser (left running)")

        # The context is now closed, so the native recording file is complete.
        if native_video_obj is not None:
            try:
                raw = Path(native_video_obj.path())
                video_path = self._finalize_native_video(raw)
            except Exception as exc:
                logger.warning("Native video capture failed: %s", exc)

        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass

        if self._frame_dir and Path(self._frame_dir).exists():
            shutil.rmtree(self._frame_dir, ignore_errors=True)

        return video_path

    # ── shared helpers ─────────────────────────────────────────────────

    def _finalize_native_video(self, raw: Path) -> Path:
        """Trim the warm-up preamble off the native Playwright recording.

        Native recording starts at launch (covering the pre-navigation), so we
        drop everything before the logical recording start to keep the video in
        sync with the t0-relative narration timeline.
        """
        if not raw.exists():
            logger.warning("Native video file not found: %s", raw)
            return raw
        offset = max(0.0, self._record_from_mono - self._video_start_mono)
        size_mb = raw.stat().st_size / (1024 * 1024)
        logger.info(
            "Native Playwright video: %s (%.1f MB, trimming %.2fs preamble)",
            raw.name,
            size_mb,
            offset,
        )
        if offset < 0.1:
            return raw
        import subprocess

        out = raw.with_name("native_recording_trimmed.webm")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{offset:.3f}",
            "-i",
            str(raw),
            "-c",
            "copy",
            "-an",
            str(out),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as exc:
            logger.debug("Native video trim failed (%s) — using untrimmed", exc)
            return raw
        if result.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
        logger.debug(
            "Native video trim skipped: %s",
            (result.stderr or "")[-200:],
        )
        return raw

    def _apply_viewport(self, vp: dict[str, int]) -> None:
        """Best-effort viewport sync on an existing page."""
        if not self._page:
            return
        try:
            self._page.set_viewport_size(vp)
        except Exception as exc:  # real Chrome windows may reject this
            logger.debug("set_viewport_size failed (non-fatal): %s", exc)


class CDPConnectBrowserProvider(_AuthenticatedBrowserBase):
    """Attach to a Chrome already running with ``--remote-debugging-port``.

    The user launches their own Chrome and signs into Google manually; this
    provider attaches over CDP and drives the existing, authenticated tab.

    Environment:
        DEMODSL_CDP_URL  DevTools endpoint (default ``http://127.0.0.1:9222``).
    """

    _owns_browser = False

    def launch_without_recording(
        self,
        browser_type: str,
        viewport: Viewport,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        from playwright.sync_api import sync_playwright

        cdp_url = self._auth_str("cdp_url", "DEMODSL_CDP_URL", "http://127.0.0.1:9222")
        parsed = urlparse(cdp_url)
        self._debug_port = parsed.port or 9222

        vp = {"width": viewport.width, "height": viewport.height}
        self._viewport = vp
        self._color_scheme = color_scheme
        self._locale = locale

        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            self._pw.stop()
            raise RuntimeError(
                f"Could not attach to Chrome at {cdp_url}. Start Chrome with "
                f"`--remote-debugging-port={self._debug_port} --remote-allow-origins=*` "
                f"and sign in first. Original error: {exc}"
            ) from exc

        # Reuse the existing (authenticated) context and tab.
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else self._browser.new_context()
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        self._page.bring_to_front()

        self._apply_viewport(vp)
        self._lock_horizontal_scroll()
        logger.info(
            "Attached to Chrome via CDP at %s (%dx%d)",
            cdp_url,
            viewport.width,
            viewport.height,
        )


class PersistentProfileBrowserProvider(_AuthenticatedBrowserBase):
    """Launch real Chrome against a reusable, pre-authenticated profile.

    Sign into Google once in this profile (e.g. via ``demodsl setup-login``);
    the session persists across runs.  Configure per-scenario via the YAML
    ``auth:`` block, or globally via environment variables.

    Environment (overridden by ``scenario.auth``):
        DEMODSL_USER_DATA_DIR   Path to the Chrome profile dir (required).
        DEMODSL_CHROME_CHANNEL  Browser channel (default ``chrome``;
                                use ``""`` to force bundled Chromium).
        DEMODSL_BROWSER_HEADLESS  ``1`` to run headless=new (default headed,
                                which is more reliable for Google sign-in).
    """

    _owns_browser = True

    def __init__(self) -> None:
        super().__init__()
        # Temp clone created when ``isolate`` is set — removed on close.
        self._cloned_profile: Path | None = None

    def launch_without_recording(
        self,
        browser_type: str,
        viewport: Viewport,
        *,
        color_scheme: str | None = None,
        locale: str | None = None,
    ) -> None:
        from playwright.sync_api import sync_playwright

        user_data_dir = self._auth_str("user_data_dir", "DEMODSL_USER_DATA_DIR", None)
        if not user_data_dir:
            raise RuntimeError(
                "provider 'playwright-persistent' requires a profile dir: set "
                "`auth.user_data_dir` in the scenario or DEMODSL_USER_DATA_DIR."
            )
        profile = Path(user_data_dir).expanduser()
        profile.mkdir(parents=True, exist_ok=True)

        # Parallel safety: when the SAME profile backs multiple scenarios
        # running concurrently, Chrome's single-instance lock clashes.
        # ``isolate`` clones the logged-in profile to a throwaway dir so each
        # run gets its own copy (read-only session is preserved).
        if self._auth_flag("isolate", "DEMODSL_PROFILE_ISOLATE", default=False):
            cloned = self._clone_profile(profile)
            if cloned != profile:
                self._cloned_profile = cloned
            profile = cloned

        channel = (self._auth_str("channel", "DEMODSL_CHROME_CHANNEL", "chrome") or "").strip()
        headless = self._auth_flag("headless", "DEMODSL_BROWSER_HEADLESS", default=False)

        vp = {"width": viewport.width, "height": viewport.height}
        self._viewport = vp
        self._color_scheme = color_scheme
        self._locale = locale

        self._debug_port = _free_port()
        args = [
            f"--remote-debugging-port={self._debug_port}",
            f"--remote-allow-origins=http://127.0.0.1:{self._debug_port}",
            f"--window-size={viewport.width},{viewport.height}",
            # Hide navigator.webdriver so Google's "this browser may not be
            # secure" block (and the automation infobar) doesn't trip.
            "--disable-blink-features=AutomationControlled",
            *_chromium_stability_args(),
        ]
        if headless:
            args.append("--headless=new")
        if locale:
            args.append(f"--lang={locale}")

        ctx_kwargs: dict[str, Any] = {
            "viewport": vp,
            "args": args,
            "headless": False,  # headedness controlled via --headless=new flag
            "ignore_default_args": ["--enable-automation"],
        }
        if channel:
            ctx_kwargs["channel"] = channel
        if color_scheme is not None:
            ctx_kwargs["color_scheme"] = color_scheme
        if locale is not None:
            ctx_kwargs["locale"] = locale

        # Native Playwright video records smoothly from launch (vs the choppy
        # CDP screenshot recorder). The persistent context can't be recreated
        # mid-session without dropping auth, so recording must be armed here.
        self._native_video = self._wants_native_video()
        if self._native_video:
            self._native_video_dir = Path(tempfile.mkdtemp(prefix="demodsl_pwvideo_"))
            ctx_kwargs["record_video_dir"] = str(self._native_video_dir)
            ctx_kwargs["record_video_size"] = vp

        self._pw = sync_playwright().start()
        try:
            self._context = self._pw.chromium.launch_persistent_context(str(profile), **ctx_kwargs)
        except Exception as exc:
            # Fall back to bundled Chromium if the requested channel is absent.
            if channel:
                logger.warning(
                    "Chrome channel '%s' unavailable (%s), retrying with bundled Chromium",
                    channel,
                    exc,
                )
                ctx_kwargs.pop("channel", None)
                self._context = self._pw.chromium.launch_persistent_context(
                    str(profile), **ctx_kwargs
                )
            else:
                self._pw.stop()
                raise

        self._browser = self._context.browser
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        # Native recording is live from this point — record the wall clock so
        # the warm-up preamble can be trimmed precisely in close().
        self._video_start_mono = time.monotonic()
        self._lock_horizontal_scroll()
        logger.info(
            "Persistent Chrome profile launched: %s (%dx%d, channel=%s, headless=%s)",
            profile,
            viewport.width,
            viewport.height,
            channel or "chromium",
            headless,
        )

    def close(self) -> Path | None:
        # Persistent context owns no separate Browser object; closing the
        # context terminates the browser.  Avoid double-close in the parent.
        self._browser = None
        result = super().close()
        if self._cloned_profile and self._cloned_profile.exists():
            import shutil

            shutil.rmtree(self._cloned_profile, ignore_errors=True)
            self._cloned_profile = None
        return result

    @staticmethod
    def _clone_profile(profile: Path) -> Path:
        """Copy a logged-in profile to a throwaway dir for parallel-safe launch.

        Heavy cache subdirectories are skipped to keep the copy light; the
        cookie/session state that keeps you signed in is preserved.
        """
        import shutil
        import tempfile

        dest = Path(tempfile.mkdtemp(prefix="demodsl_profile_clone_"))
        _skip = {
            "Cache",
            "Code Cache",
            "GPUCache",
            "ShaderCache",
            "GrShaderCache",
            "Service Worker",
            "DawnCache",
            "component_crx_cache",
        }
        try:
            shutil.copytree(
                profile,
                dest,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*_skip, "Singleton*"),
            )
        except Exception as exc:
            logger.warning("Profile clone failed (%s); using original dir", exc)
            shutil.rmtree(dest, ignore_errors=True)
            return profile
        return dest


# Register with the factory
BrowserProviderFactory.register("playwright-cdp", CDPConnectBrowserProvider)
BrowserProviderFactory.register("playwright-persistent", PersistentProfileBrowserProvider)
