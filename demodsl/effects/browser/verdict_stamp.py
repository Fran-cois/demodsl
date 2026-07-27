"""Verdict stamp — a rubber-stamp score slammed onto the page at the wrap-up.

The reviewer's final gesture: a rotated double-ring stamp ("3/5", "8/10",
"APPROVED"…) slams in with a spring scale, settles with a soft shadow and a
faint ink texture, holds through the verdict narration, then fades.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class VerdictStampEffect(BrowserEffect):
    effect_id = "verdict_stamp"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        text_raw = str(params.get("text") or "4/5")[:14]
        safe = text_raw.replace("\\", "").replace("`", "").replace("'", "\\'")
        label_raw = str(params.get("style") or "REVIEW SCORE")[:24]
        safe_label = label_raw.replace("\\", "").replace("`", "").replace("'", "\\'")
        color = sanitize_css_color(params.get("color", "#EF4444"))
        target_x = sanitize_number(
            params.get("target_x", 0.72), default=0.72, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.38), default=0.38, min_val=0.0, max_val=1.0
        )
        angle = sanitize_number(
            params.get("angle", -9.0), default=-9.0, min_val=-30.0, max_val=30.0
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=0.5, max_val=30.0
        )
        lifetime = int(duration * 1000)
        fade_ms = 300 if lifetime > 900 else 0

        js = (
            "const w = document.createElement('div');\n"
            "w.id = '__demodsl_verdict_stamp';\n"
            f"const cx = window.innerWidth * {target_x} + window.scrollX;\n"
            f"const cy = window.innerHeight * {target_y} + window.scrollY;\n"
            # absolute + page coords: rides scroll and the virtual camera.
            "w.style.cssText = `\n"
            "    position:absolute; z-index:99999; pointer-events:none;\n"
            "    left:0; top:0; opacity:0;\n"
            "`;\n"
            "w.style.left = cx + 'px';\n"
            "w.style.top = cy + 'px';\n"
            "const inner = document.createElement('div');\n"
            "inner.style.cssText = `\n"
            f"    border:4px solid {color}; border-radius:14px;\n"
            "    padding:10px 22px 12px; text-align:center;\n"
            f"    box-shadow:0 0 0 3px {color}22 inset, 0 8px 26px rgba(0,0,0,.30);\n"
            "    background:rgba(255,255,255,.07); backdrop-filter:blur(1px);\n"
            "    position:relative;\n"
            "`;\n"
            # inner hairline ring = the classic double-ring stamp
            "const ring = document.createElement('div');\n"
            "ring.style.cssText = `\n"
            f"    position:absolute; inset:4px; border:1.5px solid {color};\n"
            "    border-radius:9px; opacity:.65;\n"
            "`;\n"
            "inner.appendChild(ring);\n"
            "const small = document.createElement('div');\n"
            f"small.textContent = '{safe_label}';\n"
            "small.style.cssText = `\n"
            f"    color:{color}; font:800 11px/1.2 -apple-system,'SF Pro Text',system-ui,sans-serif;\n"
            "    letter-spacing:.22em; text-transform:uppercase; opacity:.9;\n"
            "`;\n"
            "const big = document.createElement('div');\n"
            f"big.textContent = '{safe}';\n"
            "big.style.cssText = `\n"
            f"    color:{color}; font:900 54px/1.05 -apple-system,'SF Pro Display',system-ui,sans-serif;\n"
            "    letter-spacing:.02em;\n"
            "`;\n"
            "inner.appendChild(small);\n"
            "inner.appendChild(big);\n"
            "w.appendChild(inner);\n"
            "document.body.appendChild(w);\n"
            # Slam-in: oversized + extra tilt → springs to rest. rAF-driven so
            # the pop reads even on slow screencast capture rates.
            f"const restRot = {angle};\n"
            "let t0 = null;\n"
            "function slam(ts) {\n"
            "    if (!t0) t0 = ts;\n"
            "    const p = Math.min((ts - t0) / 480, 1);\n"
            # spring-ish: overshoot at ~0.7 then settle
            "    const s = p < 1 ? 2.1 - 1.1 * (1 - Math.pow(1 - p, 2.2))"
            " - 0.18 * Math.sin(p * 9.4) * (1 - p) : 1;\n"
            "    const rot = restRot * (0.4 + 0.6 * p);\n"
            "    w.style.opacity = Math.min(1, p * 2.5);\n"
            "    w.style.transform = 'translate(-50%, -50%) rotate(' + rot"
            " + 'deg) scale(' + Math.max(1, s).toFixed(3) + ')';\n"
            "    if (p < 1) requestAnimationFrame(slam);\n"
            "}\n"
            "requestAnimationFrame(slam);\n"
            + (
                f"setTimeout(() => {{ w.style.transition = 'opacity .3s ease';"
                f" w.style.opacity = '0'; }}, {lifetime - fade_ms});\n"
                if fade_ms
                else ""
            )
            + f"setTimeout(() => w.remove(), {lifetime});\n"
        )
        evaluate_js(iife(js))
