"""Animated annotation — hand-drawn marker ellipse, motion-design grade.

The mark reads like a motion designer drew it in After Effects: an organic
ellipse (seeded low-frequency wobble, slight tilt, a second marker pass that
drifts outward), felt-tip rendering (round caps, ink-bleed under-stroke, soft
drop shadow), an ease-out draw-on, a barely-there breathing loop while it
holds, an uppercase pill label that springs in once the stroke lands, and a
clean fade-out before removal.
"""

from __future__ import annotations

import math
from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class AnimatedAnnotationEffect(BrowserEffect):
    effect_id = "animated_annotation"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        color = sanitize_css_color(params.get("color", "#ef4444"))
        rx = int(sanitize_number(params.get("radius", 60), default=60, min_val=20, max_val=700))
        # Ellipse aspect: ratio = rx/ry — the anchor fills it from the element
        # bbox so the loop hugs a wide headline as well as a square badge.
        ratio = sanitize_number(params.get("ratio", 1.0), default=1.0, min_val=0.2, max_val=20.0)
        ry = int(max(18, min(320, rx / ratio)))
        angle_deg = sanitize_number(
            params.get("angle", -4.0), default=-4.0, min_val=-45.0, max_val=45.0
        )
        rot = round(math.radians(angle_deg), 4)
        duration = sanitize_number(
            params.get("duration", 2.5), default=2.5, min_val=0.5, max_val=30.0
        )
        text_raw = params.get("text") or ""

        lifetime = int(duration * 1000)
        # Draw snappily (~1s) regardless of how long the mark persists.
        draw_ms = min(1100, int(duration * 550))
        fade_ms = 300 if lifetime > 900 else 0

        label_js = ""
        if text_raw:
            safe = (
                str(text_raw)
                .replace("\\", "\\\\")
                .replace("`", "")
                .replace("'", "\\'")
                .replace("\n", " ")
            )
            label_js = (
                "const label = document.createElement('div');\n"
                f"label.textContent = '{safe}';\n"
                "label.style.cssText = `\n"
                "    position:absolute; pointer-events:none; z-index:99999;\n"
                f"    background:{color}; color:#fff;\n"
                "    font:700 12px/1.4 -apple-system,'SF Pro Text',system-ui,sans-serif;\n"
                "    letter-spacing:.08em; text-transform:uppercase; white-space:nowrap;\n"
                "    padding:5px 13px; border-radius:999px;\n"
                "    box-shadow:0 4px 14px rgba(0,0,0,.28);\n"
                "    transform:translate(-50%, 8px); opacity:0;\n"
                f"    transition:opacity .35s ease {draw_ms}ms,\n"
                f"        transform .45s cubic-bezier(.34,1.56,.64,1) {draw_ms}ms;\n"
                "`;\n"
                "label.style.left = cx + 'px';\n"
                f"label.style.top = (cy + {ry} + 18) + 'px';\n"
                "document.body.appendChild(label);\n"
                "requestAnimationFrame(() => {\n"
                "    label.style.opacity = '1';\n"
                "    label.style.transform = 'translate(-50%, 0)';\n"
                "});\n"
                + (
                    f"setTimeout(() => {{ label.style.transition = 'opacity .28s ease';"
                    f" label.style.opacity = '0'; }}, {lifetime - fade_ms});\n"
                    if fade_ms
                    else ""
                )
                + f"setTimeout(() => label.remove(), {lifetime});\n"
            )

        js = (
            "const NS = 'http://www.w3.org/2000/svg';\n"
            "const svg = document.createElementNS(NS, 'svg');\n"
            "svg.id = '__demodsl_annotation';\n"
            # position:absolute in PAGE coords (not fixed/viewport): under the
            # virtual-camera transform on <html>, fixed overlays are re-rooted
            # to the transformed page anyway — absolute + scroll offsets keeps
            # the mark glued to the element on scrolled AND zoomed pages.
            "svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;"
            "height:100%;z-index:99999;pointer-events:none;overflow:visible;';\n"
            f"const cx = window.innerWidth * {target_x} + window.scrollX;\n"
            f"const cy = window.innerHeight * {target_y} + window.scrollY;\n"
            f"const rx = {rx}, ry = {ry}, rot = {rot};\n"
            # Deterministic per-position wobble (reproducible renders).
            "let sd = (Math.floor(cx * 7 + cy * 13) + 97) >>> 0;\n"
            "const rnd = () => ((sd = (sd * 1664525 + 1013904223) >>> 0) / 4294967296);\n"
            "const ph1 = rnd() * 6.283, ph2 = rnd() * 6.283, ph3 = rnd() * 6.283;\n"
            # Low-frequency amplitudes — organic, never jittery.
            "const a1 = rx * 0.020 + 1.2, a2 = rx * 0.012 + 0.8, a3 = 1.1;\n"
            "const start = 3.6;\n"  # ≈206°: markers start lower-left
            "const total = start + Math.PI * 2 * 1.68;\n"  # 1.68 loops = double pass
            "const cosR = Math.cos(rot), sinR = Math.sin(rot);\n"
            "let d = '';\n"
            "for (let i = 0; i <= 160; i++) {\n"
            "    const t = start + (total - start) * (i / 160);\n"
            "    const wob = a1 * Math.sin(3 * t + ph1) + a2 * Math.sin(5 * t + ph2)"
            " + a3 * Math.sin(11 * t + ph3);\n"
            # The second pass drifts outward so the overlap reads as two strokes.
            "    const sep = Math.max(0, t - start - Math.PI * 2) * 1.9;\n"
            "    const ex = (rx + wob + sep) * Math.cos(t);\n"
            "    const ey = (ry + wob * 0.8 + sep * 0.75) * Math.sin(t);\n"
            "    const x = cx + ex * cosR - ey * sinR;\n"
            "    const y = cy + ex * sinR + ey * cosR;\n"
            "    d += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);\n"
            "}\n"
            # Soft shadow lifts the ink off the page.
            "const defs = document.createElementNS(NS, 'defs');\n"
            "defs.innerHTML = `<filter id='__dslAnnotShadow' x='-20%' y='-20%'"
            " width='140%' height='140%'>"
            "<feDropShadow dx='0' dy='1.5' stdDeviation='1.6' flood-opacity='0.35'/>"
            "</filter>`;\n"
            "svg.appendChild(defs);\n"
            "const g = document.createElementNS(NS, 'g');\n"
            "svg.appendChild(g);\n"
            # Ink bleed: wider, faint copy of the stroke under the main line.
            "const bleed = document.createElementNS(NS, 'path');\n"
            "bleed.setAttribute('d', d);\n"
            "bleed.setAttribute('fill', 'none');\n"
            f"bleed.setAttribute('stroke', '{color}');\n"
            "bleed.setAttribute('stroke-width', '7.5');\n"
            "bleed.setAttribute('stroke-linecap', 'round');\n"
            "bleed.setAttribute('stroke-linejoin', 'round');\n"
            "bleed.setAttribute('opacity', '0.16');\n"
            "g.appendChild(bleed);\n"
            "const main = document.createElementNS(NS, 'path');\n"
            "main.setAttribute('d', d);\n"
            "main.setAttribute('fill', 'none');\n"
            f"main.setAttribute('stroke', '{color}');\n"
            "main.setAttribute('stroke-width', '4');\n"
            "main.setAttribute('stroke-linecap', 'round');\n"
            "main.setAttribute('stroke-linejoin', 'round');\n"
            "main.setAttribute('filter', 'url(#__dslAnnotShadow)');\n"
            "g.appendChild(main);\n"
            "document.body.appendChild(svg);\n"
            "const L = main.getTotalLength();\n"
            "for (const p of [bleed, main]) {\n"
            "    p.style.strokeDasharray = L;\n"
            "    p.style.strokeDashoffset = L;\n"
            "}\n"
            # Ease-out draw-on: fast attack, soft landing — the AE default.
            "let t0 = null;\n"
            f"const drawDur = {draw_ms};\n"
            "function draw(ts) {\n"
            "    if (!t0) t0 = ts;\n"
            "    const prog = Math.min((ts - t0) / drawDur, 1);\n"
            "    const ease = 1 - Math.pow(1 - prog, 3);\n"
            "    const off = L * (1 - ease);\n"
            "    bleed.style.strokeDashoffset = off;\n"
            "    main.style.strokeDashoffset = off;\n"
            "    if (prog < 1) requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
            # Barely-there breathing while the mark holds (kept alive, not loud).
            "const st = document.createElement('style');\n"
            "st.id = '__dslAnnotBreatheStyle';\n"
            "st.textContent = '@keyframes __dslAnnotBreathe"
            "{from{transform:scale(1)}to{transform:scale(1.012)}}';\n"
            "document.head.appendChild(st);\n"
            "g.style.transformOrigin = cx + 'px ' + cy + 'px';\n"
            f"g.style.animation = '__dslAnnotBreathe 2.2s ease-in-out {draw_ms}ms"
            " infinite alternate';\n"
            + label_js
            + (
                f"setTimeout(() => {{ svg.style.transition = 'opacity .3s ease';"
                f" svg.style.opacity = '0'; }}, {lifetime - fade_ms});\n"
                if fade_ms
                else ""
            )
            + f"setTimeout(() => {{ svg.remove(); st.remove(); }}, {lifetime});\n"
        )
        evaluate_js(iife(js))
