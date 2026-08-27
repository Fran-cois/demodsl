"""Perspective tilt — 3D isometric view of the page with depth shadow."""

from __future__ import annotations

from typing import Any

from demodsl.effects.browser._tilt_backdrop import build_tilt_backdrop
from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


class PerspectiveTiltEffect(BrowserEffect):
    effect_id = "perspective_tilt"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        angle = sanitize_number(params.get("angle", 12), default=12, min_val=2, max_val=45)
        direction = params.get("direction", "left")
        if direction not in ("left", "right", "top", "bottom"):
            direction = "left"
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=0.5, max_val=10.0
        )
        # Optional backdrop shown around the tilted window card. Applied to
        # <html> (a sibling of <body>, never transformed) so it stays put
        # while the page tilts. A plain CSS color or an animated preset
        # ("stars"/"starfield", "aurora") — left untouched when omitted.
        background = params.get("background")
        bg_set_js, bg_reset_js = build_tilt_backdrop(background)

        if direction in ("left", "right"):
            ry = angle if direction == "left" else -angle
            rx = 3.0
            shadow_x = 20 if ry >= 0 else -20
        else:
            rx = angle if direction == "top" else -angle
            ry = 0.0
            shadow_x = 0

        tilt_in_ms = 600
        hold_ms = max(100, int(duration * 1000) - tilt_in_ms * 2)

        js = (
            "history.scrollRestoration = 'manual';\n"
            "const el = document.body;\n" + bg_set_js +
            # document.body spans the whole page, so the default 50% 50% origin
            # sits far outside the viewport and any tilt throws it off screen.
            "el.style.transformOrigin = '50% ' + (window.scrollY + window.innerHeight / 2) + 'px';\n"
            # Clip to the currently-visible slice so the tilt reads as a
            # finite bounded window card, not an edgeless shear of the whole
            # (often much taller) document. A visible border + rounded
            # corners (matched to the clip shape) sell the window boundary,
            # which would otherwise blend invisibly into a dark page bg.
            "const __st = window.scrollY;\n"
            "const __cb = Math.max(0, document.documentElement.scrollHeight - __st - window.innerHeight);\n"
            "el.style.clipPath = `inset(${__st}px 0px ${__cb}px 0px round 14px)`;\n"
            "el.style.border = '1px solid rgba(255,255,255,0.18)';\n"
            "el.style.borderRadius = '14px';\n"
            f"el.style.transition = 'transform {tilt_in_ms}ms cubic-bezier(0.25,0.46,0.45,0.94),"
            f" box-shadow {tilt_in_ms}ms ease';\n"
            "requestAnimationFrame(() => {\n"
            f"    el.style.transform = 'perspective(1200px) rotateY({ry}deg)"
            f" rotateX({rx}deg) scale(0.92)';\n"
            f"    el.style.boxShadow = '{shadow_x}px 15px 50px rgba(0,0,0,0.35)';\n"
            "});\n"
            f"setTimeout(() => {{\n"
            f"    el.style.transition = 'transform {tilt_in_ms}ms cubic-bezier(0.25,0.46,0.45,0.94),"
            f" box-shadow {tilt_in_ms}ms ease';\n"
            "    el.style.transform = '';\n"
            "    el.style.boxShadow = '';\n"
            f"    setTimeout(() => {{\n"
            "        el.style.transition = '';\n"
            "        el.style.transformOrigin = '';\n"
            "        el.style.clipPath = '';\n"
            "        el.style.border = '';\n"
            "        el.style.borderRadius = '';\n"
            f"        {bg_reset_js}"
            f"    }}, {tilt_in_ms});\n"
            f"}}, {tilt_in_ms + hold_ms});\n"
        )
        evaluate_js(iife(js))
