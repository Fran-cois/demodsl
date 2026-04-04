"""Test the EXACT DemoDSL flow: SeleniumBrowserProvider + BrowserEffect classes."""

import sys
import time
import base64
from pathlib import Path

sys.path.insert(0, ".")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from demodsl.providers.selenium_browser import SeleniumBrowserProvider
from demodsl.effects.browser_effects import SpotlightEffect, ConfettiEffect


def main():
    out = Path("/tmp/demodsl_exact_test")
    out.mkdir(parents=True, exist_ok=True)

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
        {"width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False},
    )

    # Wire up a minimal SeleniumBrowserProvider
    p = SeleniumBrowserProvider.__new__(SeleniumBrowserProvider)
    p._driver = d
    p._viewport = {"width": 1920, "height": 1080}
    p._recording = False

    try:
        # Navigate & install shim (same as DemoDSL's navigate())
        d.get("http://127.0.0.1:8899/effects_showcase_page.html")
        d.execute_script(
            "return new Promise(r => {"
            "  if (document.readyState === 'complete') r();"
            "  else window.addEventListener('load', r);"
            "})"
        )
        p._install_raf_shim()
        time.sleep(1)

        # Screenshot BEFORE
        def cdp_shot(name):
            r = d.execute_cdp_cmd(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "clip": {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1},
                    "captureBeyondViewport": False,
                },
            )
            path = out / f"{name}.png"
            path.write_bytes(base64.b64decode(r["data"]))
            return path.stat().st_size

        s0 = cdp_shot("01_before")
        print(f"Before: {s0} bytes")

        # SPOTLIGHT via DemoDSL's exact flow
        spotlight = SpotlightEffect()
        spotlight.inject(p.evaluate_js, {"intensity": 0.85, "duration": 2.5})
        time.sleep(0.3)  # Let it render

        has_spot = d.execute_script(
            "return !!document.getElementById('__demodsl_spotlight')"
        )
        print(f"Spotlight element exists: {has_spot}")

        s1 = cdp_shot("02_spotlight")
        print(f"After spotlight: {s1} bytes (diff {s1 - s0:+d})")

        # CONFETTI via DemoDSL's exact flow
        confetti = ConfettiEffect()
        confetti.inject(p.evaluate_js, {"duration": 2.5})
        time.sleep(1)  # Let rAF shim process frames

        has_conf = d.execute_script(
            "return !!document.getElementById('__demodsl_confetti')"
        )
        print(f"Confetti canvas exists: {has_conf}")

        s2 = cdp_shot("03_confetti")
        print(f"After confetti: {s2} bytes (diff {s2 - s0:+d})")

        print(f"\nScreenshots saved to {out}/")

    finally:
        d.quit()


if __name__ == "__main__":
    main()
