"""Morph transition — animated morphing between two page landmarks.

Landmarks System
================
Landmarks are stored as normalised viewport coordinates (0-1).  The effect
captures a visual clone of the source region, then scales / translates /
cross-fades it into the destination region.

**YAML usage** (coords-based)::

    effects:
      - type: morph_transition
        from_x: 0.15       # source center X (0-1)
        from_y: 0.3        # source center Y (0-1)
        target_x: 0.75     # dest center X
        target_y: 0.6      # dest center Y
        scale: 1.2          # final scale factor
        color: "#6366f1"    # glow colour during morph
        duration: 2.0

**YAML usage** (CSS-selector based via ``text``)::

    effects:
      - type: morph_transition
        text: ".hero-card -> .detail-panel"  # CSS selector pair
        color: "#6366f1"

Landmark persistence plan (future)
-----------------------------------
1. **landmarks.yaml** at project root — maps friendly names to selectors +
   optional scroll offsets::

       landmarks:
         hero:   { selector: ".hero-card", scroll_y: 0 }
         detail: { selector: "#detail-panel", scroll_y: 800 }
         cta:    { selector: "button.cta" }

2. During ``pre_steps``, a ``capture_landmarks`` action would screenshot each
   landmark bounding-box and store the data in a runtime dict.

3. The morph_transition effect would resolve landmarks by name at inject time,
   reading the stored rects + thumbnails.

4. For cross-URL morphs, each URL's landmarks would be captured independently,
   and the morph would cross-fade between pre-rendered thumbnails.

This keeps the architecture compatible with the existing ``evaluate_js``
injection pattern — all data flows through params.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import auto_remove_multi, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_js_string,
    sanitize_number,
)


class MorphTransitionEffect(BrowserEffect):
    effect_id = "morph_transition"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        # Source coords (defaults: top-left quadrant)
        from_x = sanitize_number(
            params.get("from_x", 0.25), default=0.25, min_val=0.0, max_val=1.0
        )
        from_y = sanitize_number(
            params.get("from_y", 0.3), default=0.3, min_val=0.0, max_val=1.0
        )
        # Destination coords
        to_x = sanitize_number(
            params.get("target_x", 0.75), default=0.75, min_val=0.0, max_val=1.0
        )
        to_y = sanitize_number(
            params.get("target_y", 0.6), default=0.6, min_val=0.0, max_val=1.0
        )
        scale = sanitize_number(
            params.get("scale", 1.2), default=1.2, min_val=0.5, max_val=3.0
        )
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 2.0), default=2.0, min_val=0.5, max_val=10.0
        )

        # CSS selectors via text: "sel1 -> sel2"
        text_raw = params.get("text") or ""
        use_selectors = False
        sel_from = ""
        sel_to = ""
        if text_raw and "->" in str(text_raw):
            parts = str(text_raw).split("->", 1)
            sel_from = sanitize_js_string(parts[0].strip())
            sel_to = sanitize_js_string(parts[1].strip())
            use_selectors = True

        morph_ms = int(duration * 1000)
        half = morph_ms // 2

        # Detect OS background window area — if the fake OS frame is
        # present, constrain the morph animation to the visible window
        # region (between title-bar and dock/taskbar).
        os_detect_js = (
            "const osBg = document.getElementById('__demodsl_os_bg');\n"
            "let winTop = 0, winLeft = 0, winW = window.innerWidth, winH = window.innerHeight;\n"
            "if (osBg) {\n"
            "    const bodyCS = getComputedStyle(document.body);\n"
            "    const padTop = parseFloat(bodyCS.paddingTop) || 0;\n"
            "    const padBot = parseFloat(bodyCS.paddingBottom) || 0;\n"
            "    winTop = padTop;\n"
            "    winH = window.innerHeight - padTop - padBot;\n"
            "}\n"
        )

        # JS that resolves source/dest rects (either from selectors or coords)
        # When OS background is active, coords are relative to the OS window area.
        if use_selectors:
            resolve_js = (
                f"const srcEl = document.querySelector('{sel_from}');\n"
                f"const dstEl = document.querySelector('{sel_to}');\n"
                "const srcR = srcEl ? srcEl.getBoundingClientRect() "
                ": {x:winLeft + winW*0.25-75, y:winTop + winH*0.3-50, width:150, height:100};\n"
                "const dstR = dstEl ? dstEl.getBoundingClientRect() "
                ": {x:winLeft + winW*0.75-75, y:winTop + winH*0.6-50, width:150, height:100};\n"
            )
        else:
            resolve_js = (
                f"const srcR = {{x:winLeft + winW*{from_x}-75, y:winTop + winH*{from_y}-50, width:150, height:100}};\n"
                f"const dstR = {{x:winLeft + winW*{to_x}-75, y:winTop + winH*{to_y}-50, width:150, height:100}};\n"
            )

        js = (
            os_detect_js + resolve_js + "const ghost = document.createElement('div');\n"
            "ghost.id = '__demodsl_morph_transition';\n"
            "ghost.style.cssText = `\n"
            "    position:fixed; z-index:99999; pointer-events:none;\n"
            "    border-radius: 12px;\n"
            f"    border: 2px solid {color};\n"
            f"    box-shadow: 0 0 30px {color}44, inset 0 0 20px {color}22;\n"
            f"    background: {color}11;\n"
            "    transition: none;\n"
            "`;\n"
            # Start at source rect
            "ghost.style.left = srcR.x + 'px';\n"
            "ghost.style.top = srcR.y + 'px';\n"
            "ghost.style.width = srcR.width + 'px';\n"
            "ghost.style.height = srcR.height + 'px';\n"
            "ghost.style.opacity = '0';\n"
            "document.body.appendChild(ghost);\n"
            # Glow ring at source
            "const ring = document.createElement('div');\n"
            "ring.id = '__demodsl_morph_ring';\n"
            "ring.style.cssText = `\n"
            "    position:fixed; z-index:99998; pointer-events:none;\n"
            "    border-radius: 50%; opacity:0;\n"
            f"    border: 2px solid {color};\n"
            f"    box-shadow: 0 0 20px {color}66;\n"
            "    transition: all 0.4s ease;\n"
            "`;\n"
            "const ringSize = Math.max(srcR.width, srcR.height) + 20;\n"
            "ring.style.width = ringSize + 'px';\n"
            "ring.style.height = ringSize + 'px';\n"
            "ring.style.left = (srcR.x + srcR.width/2 - ringSize/2) + 'px';\n"
            "ring.style.top = (srcR.y + srcR.height/2 - ringSize/2) + 'px';\n"
            "document.body.appendChild(ring);\n"
            # Phase 1: appear at source
            "requestAnimationFrame(() => {\n"
            "    ghost.style.opacity = '1';\n"
            "    ring.style.opacity = '0.8';\n"
            "    ring.style.transform = 'scale(1.3)';\n"
            "});\n"
            # Phase 2: morph to destination
            f"setTimeout(() => {{\n"
            f"    ghost.style.transition = 'all {half}ms cubic-bezier(0.4,0,0.2,1)';\n"
            "    ghost.style.left = dstR.x + 'px';\n"
            "    ghost.style.top = dstR.y + 'px';\n"
            "    ghost.style.width = dstR.width + 'px';\n"
            "    ghost.style.height = dstR.height + 'px';\n"
            f"    ghost.style.transform = 'scale({scale})';\n"
            f"    ghost.style.boxShadow = '0 0 50px {color}66, inset 0 0 30px {color}33';\n"
            "    ring.style.opacity = '0';\n"
            "    ring.style.transform = 'scale(2)';\n"
            f"}}, 400);\n"
            # Phase 3: fade out
            f"setTimeout(() => {{\n"
            "    ghost.style.opacity = '0';\n"
            "    ghost.style.transform += ' scale(0.95)';\n"
            f"}}, {morph_ms - 400});\n"
            + auto_remove_multi(
                [
                    ("ghost", morph_ms),
                    ("ring", morph_ms),
                ]
            )
        )
        evaluate_js(iife(js))
