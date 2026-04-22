#!/usr/bin/env python3
"""Screenshot state-recovery test — verifies every browser effect returns the page
to its initial state after a reload-based cleanup.

Usage::

    python scripts/test_effect_screenshot.py          # run all 33 effects
    python scripts/test_effect_screenshot.py glow neon_glow  # run specific effects

Exit code 0 = all pass, 1 = one or more failures.
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

# ── Project imports ──────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from demodsl.effects.browser import _BROWSER_EFFECTS  # noqa: E402
from demodsl.effects.registry import EffectRegistry  # noqa: E402

# ── Config ───────────────────────────────────────────────────────────────────

URL = "https://fran-cois.github.io/demodsl/"
VIEWPORT = {"width": 1280, "height": 720}
OUT_DIR = ROOT / "output" / "screenshot_test"
# Maximum acceptable pixel-diff percentage (tolerance for sub-pixel rendering)
MAX_DIFF_PCT = 0.5


# ── Helpers ──────────────────────────────────────────────────────────────────


def _pixel_diff(img_a: bytes, img_b: bytes) -> tuple[int, float]:
    """Compare two PNGs.  Returns (differing_pixels, diff_percentage).

    A pixel is considered different if any channel differs by more than 2.
    Uses numpy for speed when available, falls back to pure-PIL.
    """
    from PIL import Image

    a = Image.open(io.BytesIO(img_a)).convert("RGB")
    b = Image.open(io.BytesIO(img_b)).convert("RGB")
    if a.size != b.size:
        return -1, 100.0

    try:
        import numpy as np

        arr_a = np.array(a, dtype=np.int16)
        arr_b = np.array(b, dtype=np.int16)
        diff_mask = np.any(np.abs(arr_a - arr_b) > 2, axis=2)
        diff_count = int(np.sum(diff_mask))
    except ImportError:
        pa, pb = a.load(), b.load()  # type: ignore[union-attr]
        diff_count = 0
        for y in range(a.height):
            for x in range(a.width):
                ra, ga, ba = pa[x, y]
                rb, gb, bb = pb[x, y]
                if abs(ra - rb) > 2 or abs(ga - gb) > 2 or abs(ba - bb) > 2:
                    diff_count += 1

    total = a.width * a.height
    return diff_count, (diff_count / total) * 100


_NAV_JS = """(() => {
    const nav = document.querySelector('nav')
              || document.querySelector('header')
              || document.querySelector('[class*=nav]');
    if (!nav) return null;
    const r = nav.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height};
})()"""


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    from playwright.sync_api import sync_playwright

    # Build registry
    registry = EffectRegistry()
    for name, cls in _BROWSER_EFFECTS.items():
        registry.register_browser(name, cls())

    # Determine which effects to test
    requested = sys.argv[1:] if len(sys.argv) > 1 else list(_BROWSER_EFFECTS.keys())
    unknown = [n for n in requested if n not in _BROWSER_EFFECTS]
    if unknown:
        print(f"Unknown effects: {', '.join(unknown)}")
        sys.exit(2)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT)
        page.goto(URL, wait_until="networkidle")
        time.sleep(1)

        # Capture global reference
        ref_bytes = page.screenshot(type="png")
        (OUT_DIR / "00_reference.png").write_bytes(ref_bytes)
        print(f"[REF] Reference saved  ({VIEWPORT['width']}x{VIEWPORT['height']})")

        results: dict[str, dict] = {}

        for effect_name in requested:
            print(f"\n{'─' * 60}")
            print(f" {effect_name}")
            print(f"{'─' * 60}")

            handler = registry.get_browser_effect(effect_name)

            # 1) Reload to start from a clean state
            page.reload(wait_until="networkidle")
            time.sleep(0.5)

            # 2) Screenshot BEFORE
            before = page.screenshot(type="png")
            (OUT_DIR / f"{effect_name}_1_before.png").write_bytes(before)
            nav_before = page.evaluate(_NAV_JS)

            # 3) Inject effect via the real handler
            def _eval(js: str) -> object:
                return page.evaluate(js)

            handler.inject(_eval, {})
            time.sleep(0.5)

            # 4) Screenshot DURING + navbar check
            during = page.screenshot(type="png")
            (OUT_DIR / f"{effect_name}_2_during.png").write_bytes(during)
            nav_during = page.evaluate(_NAV_JS)

            nav_shifted_during = False
            if nav_before and nav_during:
                dy = abs(nav_during["y"] - nav_before["y"])
                if dy > 0.5:
                    print(f"  ⚠  Navbar shifted {dy}px during effect")
                    nav_shifted_during = True

            # 5) Cleanup via reload (same as production pipeline)
            page.reload(wait_until="networkidle")
            time.sleep(0.5)

            # 6) Screenshot AFTER
            after = page.screenshot(type="png")
            (OUT_DIR / f"{effect_name}_3_after.png").write_bytes(after)
            nav_after = page.evaluate(_NAV_JS)

            # 7) Compare before vs after
            diff_count, diff_pct = _pixel_diff(before, after)

            # Nav stuck = nav still displaced AFTER cleanup (real failure)
            # Nav shifted during effect is informational only (expected for
            # page-level transforms like zoom_focus, perspective_tilt)
            nav_stuck = False
            if nav_before and nav_after:
                dy = abs(nav_after["y"] - nav_before["y"])
                if dy > 0.5:
                    nav_stuck = True

            passed = diff_pct <= MAX_DIFF_PCT and not nav_stuck

            results[effect_name] = {
                "diff_pct": diff_pct,
                "diff_px": diff_count,
                "nav_shifted": nav_shifted_during,
                "nav_stuck": nav_stuck,
                "passed": passed,
            }

            status = "✅" if passed else "❌"
            print(f"  {status} Pixel diff: {diff_count}px ({diff_pct:.2f}%)")
            if nav_stuck:
                print("  ❌ Navbar stuck after cleanup!")
            if nav_before != nav_after:
                print(f"     nav before: {nav_before}")
                print(f"     nav after:  {nav_after}")

        browser.close()

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print(" SUMMARY")
    print(f"{'═' * 60}")
    passed_list, failed_list = [], []
    for name, r in results.items():
        tag = "PASS" if r["passed"] else "FAIL"
        extra = ""
        if r.get("nav_stuck"):
            extra = " [nav stuck!]"
        elif r.get("nav_shifted"):
            extra = " [nav shifted during]"
        print(f"  [{tag}] {name}: {r['diff_pct']:.2f}%{extra}")
        (passed_list if r["passed"] else failed_list).append(name)

    print(
        f"\n  {len(passed_list)} passed, {len(failed_list)} failed"
        f" (threshold: {MAX_DIFF_PCT}%)"
    )

    if failed_list:
        print(f"\n  ❌ Failed effects: {', '.join(failed_list)}")
        sys.exit(1)
    else:
        print(f"\n  ✅ All {len(passed_list)} effects return to initial state")


if __name__ == "__main__":
    main()
