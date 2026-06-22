#!/usr/bin/env python3
"""Real end-to-end test for the two authenticated-browser providers.

Drives an ACTUAL Chrome (no mocks) against a local HTTP origin, so we can
verify the things that matter for social login:

  Option B (playwright-persistent)
    - launches real Chrome against a reusable profile dir
    - records a video via the CDP recorder
    - SESSION PERSISTS across runs (localStorage written in run 1 is read
      back in run 2 — exactly what keeps you "signed in" to Google)

  Option A (playwright-cdp)
    - attaches to a Chrome we launched ourselves with --remote-debugging-port
    - records a video
    - does NOT close our browser on .close() (detach only)

No network or Google account required — uses a tiny local server.
"""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import demodsl.providers.authenticated_browser  # noqa: F401  (registers providers)
from demodsl.models import Locator, Viewport
from demodsl.providers.base import BrowserProviderFactory

GREEN, RED, RESET = "\033[92m", "\033[91m", "\033[0m"
PASS, FAIL = f"{GREEN}PASS{RESET}", f"{RED}FAIL{RESET}"

INDEX_HTML = """<!doctype html><html><head><meta charset=utf-8>
<title>auth test</title></head><body style='height:3000px'>
<h1 id=title>Auth provider e2e</h1>
<button id=btn>Continue with Google</button>
<input id=field />
<script>window.__loaded = true;</script>
</body></html>"""

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}{(' — ' + detail) if detail else ''}")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(directory: Path) -> tuple[http.server.HTTPServer, str]:
    port = _free_port()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(directory), **k)

        def log_message(self, *a):  # silence
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/index.html"


def short_interaction(provider) -> None:
    """Generate ~1.5s of activity so the recorder captures frames."""
    provider.evaluate_js("window.scrollTo(0, 0)")
    for _ in range(3):
        provider.scroll("down", 400)
        time.sleep(0.4)
    provider.click(Locator(type="id", value="btn"))
    time.sleep(0.3)


# ── Option B: persistent profile ──────────────────────────────────────────


def test_persistent(url: str, work: Path) -> None:
    print("\nOption B — playwright-persistent (reusable profile)")
    profile = work / "profile"
    os.environ["DEMODSL_USER_DATA_DIR"] = str(profile)
    os.environ["DEMODSL_BROWSER_HEADLESS"] = "1"  # CI-friendly; CDP still records
    os.environ.pop("DEMODSL_CHROME_CHANNEL", None)  # use bundled Chromium (always present)

    # ── Run 1: write a session marker, record a clip ──
    p1 = BrowserProviderFactory.create("playwright-persistent")
    p1.launch_without_recording("chrome", Viewport(width=1000, height=700))
    p1.navigate(url)
    check("run1: page loaded", p1.evaluate_js("window.__loaded") is True)
    p1.evaluate_js("localStorage.setItem('demodsl_session', 'signed-in-token')")
    vid_dir1 = work / "vid1"
    p1.restart_with_recording(vid_dir1)
    p1.navigate(url)
    short_interaction(p1)
    video1 = p1.close()
    ok_vid = bool(video1 and Path(video1).exists() and Path(video1).stat().st_size > 0)
    check("run1: video recorded", ok_vid, str(video1) if video1 else "no video")
    check("profile dir populated (entropy)", profile.exists() and any(profile.iterdir()))

    # ── Run 2: SAME profile — session must persist ──
    p2 = BrowserProviderFactory.create("playwright-persistent")
    p2.launch_without_recording("chrome", Viewport(width=1000, height=700))
    p2.navigate(url)
    token = p2.evaluate_js("localStorage.getItem('demodsl_session')")
    check(
        "run2: session persisted across runs",
        token == "signed-in-token",
        f"localStorage='{token}'",
    )
    p2.close()


# ── Option A: CDP attach ───────────────────────────────────────────────────


def _wait_cdp(port: int, timeout: float = 15.0) -> bool:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def test_cdp(url: str, work: Path) -> None:
    print("\nOption A — playwright-cdp (attach to my own Chrome)")
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).exists():
        check("system Chrome present", False, "skipping CDP test")
        return

    port = _free_port()
    user_dir = work / "cdp_profile"
    proc = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_dir}",
            "--remote-allow-origins=*",  # required so the CDP recorder can attach
            "--no-first-run",
            "--no-default-browser-check",
            "--headless=new",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        check("my Chrome started with debug port", _wait_cdp(port), f"port {port}")

        os.environ["DEMODSL_CDP_URL"] = f"http://127.0.0.1:{port}"
        provider = BrowserProviderFactory.create("playwright-cdp")
        provider.launch_without_recording("chrome", Viewport(width=1000, height=700))
        provider.navigate(url)
        check("attached & page loaded", provider.evaluate_js("window.__loaded") is True)
        provider.restart_with_recording(work / "vid_cdp")
        provider.navigate(url)
        short_interaction(provider)
        video = provider.close()
        ok_vid = bool(video and Path(video).exists() and Path(video).stat().st_size > 0)
        check("video recorded", ok_vid, str(video) if video else "no video")

        # The crucial guarantee: we only detach, never kill the user's browser.
        time.sleep(0.5)
        check("my Chrome still running after close()", proc.poll() is None)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main() -> int:
    with TemporaryDirectory(prefix="demodsl_auth_e2e_") as tmp:
        work = Path(tmp)
        srv_dir = work / "site"
        srv_dir.mkdir()
        (srv_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
        httpd, url = serve(srv_dir)
        print(f"Local origin: {url}")
        try:
            test_persistent(url, work)
            test_cdp(url, work)
        finally:
            httpd.shutdown()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'=' * 50}\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
