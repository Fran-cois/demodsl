#!/usr/bin/env python3
"""Open a real Chrome profile so you can sign into Google (or any IdP) once.

The session is written to a *persistent* ``--user-data-dir`` that the
``playwright-persistent`` provider then reuses, so social-login demos run
without Google blocking the automated browser.

Usage:
    python examples/auth_login_helper.py \
        --user-data-dir "$HOME/.demodsl-chrome-profile" \
        --url https://accounts.google.com

Sign in in the window that opens, then press Enter in the terminal to save
and close.  Re-run a demo with::

    DEMODSL_USER_DATA_DIR="$HOME/.demodsl-chrome-profile" \
        demodsl run examples/demo_social_login.yaml

Security: this profile stores live session cookies. Keep it outside the
repo, never commit it, and prefer a throwaway/test account.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Chrome profile directory to create/reuse (keep outside the repo).",
    )
    parser.add_argument(
        "--url",
        default="https://accounts.google.com",
        help="Page to open for sign-in (default: Google account).",
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        help="Browser channel (default: chrome; use '' for bundled Chromium).",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright not installed. Run: pip install playwright && "
            "playwright install chromium",
            file=sys.stderr,
        )
        return 1

    profile = Path(args.user_data_dir).expanduser()
    profile.mkdir(parents=True, exist_ok=True)

    launch_kwargs: dict = {"headless": False}
    if args.channel:
        launch_kwargs["channel"] = args.channel

    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(str(profile), **launch_kwargs)
        except Exception as exc:
            if args.channel:
                print(f"Channel '{args.channel}' unavailable ({exc}); using Chromium.")
                launch_kwargs.pop("channel", None)
                ctx = pw.chromium.launch_persistent_context(str(profile), **launch_kwargs)
            else:
                raise
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(args.url)
        print(f"\nProfile: {profile}")
        print("Sign in in the browser window, then press Enter here to save & close...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        ctx.close()

    print(f"Done. Reuse with: DEMODSL_USER_DATA_DIR='{profile}' demodsl run <demo>.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
