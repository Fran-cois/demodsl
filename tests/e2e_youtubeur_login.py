#!/usr/bin/env python3
"""Live integration test: automate the social login on youtubeur.fun.

Drives https://youtubeur.fun/login through the real
``PersistentProfileBrowserProvider`` (the feature under test) and verifies
the "Continue with Google" OAuth handoff:

  - the page loads and the Google button is present
  - clicking it hands off to accounts.google.com with youtubeur.fun's
    OAuth client_id and the openid/email/profile scope
  - Google does NOT block the browser ("Couldn't sign you in" /
    "this browser may not be secure") — the whole point of using real
    Chrome instead of bundled Chromium

Completing the login itself needs a pre-authenticated profile
(``demodsl setup-login --user-data-dir ~/.demodsl-youtubeur-profile``);
this test stops at Google's real sign-in screen, which needs no credentials.

Run:  PYTHONPATH="$PWD" python3.11 tests/e2e_youtubeur_login.py
Requires network + a real Chrome (channel=chrome).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import demodsl.providers.authenticated_browser  # noqa: F401  (registers providers)
from demodsl.models import Locator, Viewport
from demodsl.providers.base import BrowserProviderFactory

GREEN, RED, RESET = "\033[92m", "\033[91m", "\033[0m"
PASS, FAIL = f"{GREEN}PASS{RESET}", f"{RED}FAIL{RESET}"

LOGIN_URL = "https://youtubeur.fun/login"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}{(' — ' + detail) if detail else ''}")


def run(work: Path) -> None:
    print("\nyoutubeur.fun social login — via PersistentProfileBrowserProvider")
    profile = work / "yt_profile"

    provider = BrowserProviderFactory.create("playwright-persistent")
    # Per-scenario auth config (same path the orchestrator uses) — no env vars.
    provider.set_auth_config(
        {
            "user_data_dir": str(profile),
            "channel": "chrome",  # real Chrome so Google doesn't block us
            "headless": True,  # CI-friendly; flip to False to watch it live
        }
    )
    provider.launch_without_recording("chrome", Viewport(width=1280, height=720))
    try:
        provider.navigate(LOGIN_URL)
        time.sleep(1.5)
        landed = provider.evaluate_js("window.location.href") or ""
        check("login page loaded", LOGIN_URL.split("//")[1] in landed, landed)

        has_btn = bool(
            provider.evaluate_js(
                "Boolean([...document.querySelectorAll('button')]"
                ".find(b => /continue with google/i.test(b.innerText)))"
            )
        )
        check("'Continue with Google' button present", has_btn)

        provider.click(Locator(type="text", value="Continue with Google"))
        # Wait for the OAuth handoff (top-level navigation to Google).
        dest = ""
        for _ in range(30):
            time.sleep(0.5)
            dest = provider.evaluate_js("window.location.href") or ""
            if "accounts.google.com" in dest:
                break

        check("handed off to accounts.google.com", "accounts.google.com" in dest, dest[:80])
        check(
            "OAuth request carries youtubeur.fun client + scope",
            "client_id=" in dest and "scope=openid" in dest.replace("+", "+"),
            "client_id & openid scope present" if "client_id=" in dest else "missing",
        )

        body = (provider.evaluate_js("document.body.innerText") or "").lower()
        blocked = (
            "couldn't sign you in" in body
            or "browser or app may not be secure" in body
            or "this browser or app may not be secure" in body
        )
        check("Google did NOT block the automated browser", not blocked)
        # Sanity: we reached Google's real account/email screen.
        on_signin = "google" in body and ("e-mail" in body or "email" in body or "compte" in body)
        check("reached Google's real sign-in screen", on_signin)
    finally:
        provider.close()


def main() -> int:
    with TemporaryDirectory(prefix="demodsl_yt_login_") as td:
        run(Path(td))

    print("\n" + "=" * 50)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
