"""Callout arrow — hand-drawn curved marker arrow, motion-design grade.

Same felt-tip family as ``animated_annotation``: a seeded, gently wobbling
quadratic curve swings from the label down to the target, the arrowhead is
two marker strokes (not a geometric polygon), the ink gets a bleed
under-stroke + soft shadow, the whole thing draws on with an ease-out and
the uppercase pill label springs in when the tip lands.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_js_string,
    sanitize_number,
)


class CalloutArrowEffect(BrowserEffect):
    effect_id = "callout_arrow"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        text = sanitize_js_string(params.get("text", "Look here!"))
        color = sanitize_css_color(params.get("color", "#ef4444"))
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        # Persist as long as the step talks about the element (default 4s).
        lifetime = int(
            sanitize_number(params.get("duration", 4.0), default=4.0, min_val=0.5, max_val=30.0)
            * 1000
        )
        draw_ms = min(750, max(350, lifetime // 4))
        fade_ms = 280 if lifetime > 800 else 0

        js = (
            "const NS = 'http://www.w3.org/2000/svg';\n"
            "const svg = document.createElementNS(NS, 'svg');\n"
            "svg.id = '__demodsl_callout_arrow';\n"
            # absolute + page coords: survives page scroll and rides the
            # virtual-camera transform (see animated_annotation).
            "svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;"
            "z-index:99999;pointer-events:none;overflow:visible;';\n"
            "const defs = document.createElementNS(NS, 'defs');\n"
            "defs.innerHTML = `<filter id='__dslArrowShadow' x='-20%' y='-20%'"
            " width='140%' height='140%'>"
            "<feDropShadow dx='0' dy='1.5' stdDeviation='1.6' flood-opacity='0.35'/>"
            "</filter>`;\n"
            "svg.appendChild(defs);\n"
            f"const tx = window.innerWidth * {target_x} + window.scrollX;\n"
            f"const ty = window.innerHeight * {target_y} + window.scrollY;\n"
            "const dir = (tx - window.scrollX > window.innerWidth / 2 ? 1 : -1);\n"
            # Approach from above, slightly to the side; stop shy of the target.
            "const sx = tx + dir * 150, sy = ty - 110;\n"
            "const ex = tx + dir * 14, ey = ty - 16;\n"
            # Control point bows the curve outward — a wrist flick, not a ruler.
            "let sd = (Math.floor(tx * 3 + ty * 17) + 71) >>> 0;\n"
            "const rnd = () => ((sd = (sd * 1664525 + 1013904223) >>> 0) / 4294967296);\n"
            "const bow = 34 + rnd() * 18;\n"
            "const mx = (sx + ex) / 2 + dir * bow, my = (sy + ey) / 2 + bow * 0.4;\n"
            "const ph = rnd() * 6.283;\n"
            # Sample the quadratic with a light wobble → hand-drawn polyline.
            "let d = '';\n"
            "for (let i = 0; i <= 40; i++) {\n"
            "    const u = i / 40;\n"
            "    const x0 = (1-u)*(1-u)*sx + 2*(1-u)*u*mx + u*u*ex;\n"
            "    const y0 = (1-u)*(1-u)*sy + 2*(1-u)*u*my + u*u*ey;\n"
            "    const w = 1.6 * Math.sin(u * 7 + ph) * (1 - u * 0.7);\n"
            "    d += (i ? 'L' : 'M') + (x0 + w).toFixed(1) + ' ' + (y0 + w).toFixed(1);\n"
            "}\n"
            # Arrowhead: two short marker strokes splayed around the tangent —
            # drawn as separate flicks AFTER the curve lands (pen lift).
            "const ang = Math.atan2(ey - my, ex - mx);\n"
            "function headD(spread) {\n"
            "    const a = ang + Math.PI + spread;\n"
            "    const hx = ex + 16 * Math.cos(a), hy = ey + 16 * Math.sin(a);\n"
            "    return 'M' + hx.toFixed(1) + ' ' + hy.toFixed(1)"
            " + 'L' + ex.toFixed(1) + ' ' + ey.toFixed(1);\n"
            "}\n"
            "const g = document.createElementNS(NS, 'g');\n"
            "svg.appendChild(g);\n"
            "function mkStroke(dd, wMain) {\n"
            "    const bleed = document.createElementNS(NS, 'path');\n"
            "    bleed.setAttribute('d', dd);\n"
            "    bleed.setAttribute('fill', 'none');\n"
            f"    bleed.setAttribute('stroke', '{color}');\n"
            "    bleed.setAttribute('stroke-width', String(wMain + 3.5));\n"
            "    bleed.setAttribute('stroke-linecap', 'round');\n"
            "    bleed.setAttribute('stroke-linejoin', 'round');\n"
            "    bleed.setAttribute('opacity', '0.16');\n"
            "    g.appendChild(bleed);\n"
            "    const main = document.createElementNS(NS, 'path');\n"
            "    main.setAttribute('d', dd);\n"
            "    main.setAttribute('fill', 'none');\n"
            f"    main.setAttribute('stroke', '{color}');\n"
            "    main.setAttribute('stroke-width', String(wMain));\n"
            "    main.setAttribute('stroke-linecap', 'round');\n"
            "    main.setAttribute('stroke-linejoin', 'round');\n"
            "    main.setAttribute('filter', 'url(#__dslArrowShadow)');\n"
            "    g.appendChild(main);\n"
            "    const L = main.getTotalLength();\n"
            "    for (const p of [bleed, main]) {\n"
            "        p.style.strokeDasharray = L;\n"
            "        p.style.strokeDashoffset = L;\n"
            "    }\n"
            "    return { bleed, main, L };\n"
            "}\n"
            "const curve = mkStroke(d, 4);\n"
            "const head1 = mkStroke(headD(0.5), 4.5);\n"
            "const head2 = mkStroke(headD(-0.5), 4.5);\n"
            "document.body.appendChild(svg);\n"
            # Timeline: curve eases in over drawDur → flick 1 (130ms) →
            # flick 2 (130ms), tiny pen-lift gaps between them.
            "let t0 = null;\n"
            f"const drawDur = {draw_ms};\n"
            "const F = 130, GAP = 70;\n"
            "function seg(el, start, dur) { return Math.min(1, Math.max(0, (el - start) / dur)); }\n"
            "function draw(ts) {\n"
            "    if (!t0) t0 = ts;\n"
            "    const el = ts - t0;\n"
            "    const e1 = 1 - Math.pow(1 - seg(el, 0, drawDur), 3);\n"
            "    curve.bleed.style.strokeDashoffset = curve.L * (1 - e1);\n"
            "    curve.main.style.strokeDashoffset = curve.L * (1 - e1);\n"
            "    const e2 = 1 - Math.pow(1 - seg(el, drawDur + GAP, F), 2);\n"
            "    head1.bleed.style.strokeDashoffset = head1.L * (1 - e2);\n"
            "    head1.main.style.strokeDashoffset = head1.L * (1 - e2);\n"
            "    const e3 = 1 - Math.pow(1 - seg(el, drawDur + GAP + F + GAP, F), 2);\n"
            "    head2.bleed.style.strokeDashoffset = head2.L * (1 - e3);\n"
            "    head2.main.style.strokeDashoffset = head2.L * (1 - e3);\n"
            "    if (el < drawDur + 2 * (F + GAP)) requestAnimationFrame(draw);\n"
            "}\n"
            "requestAnimationFrame(draw);\n"
            "const label = document.createElement('div');\n"
            "label.id = '__demodsl_callout_label';\n"
            f"label.textContent = `{text}`;\n"
            "label.style.cssText = `\n"
            f"    position:absolute; left:${{sx - 60}}px; top:${{sy - 40}}px;\n"
            f"    background:{color}; color:#fff; padding:5px 13px;\n"
            "    font:700 12px/1.4 -apple-system,'SF Pro Text',system-ui,sans-serif;\n"
            "    letter-spacing:.08em; text-transform:uppercase; white-space:nowrap;\n"
            "    border-radius:999px;\n"
            "    box-shadow:0 4px 14px rgba(0,0,0,.28);\n"
            "    z-index:99999; pointer-events:none; opacity:0;\n"
            "    transform:translateY(8px);\n"
            f"    transition:opacity .35s ease {draw_ms}ms,\n"
            f"        transform .45s cubic-bezier(.34,1.56,.64,1) {draw_ms}ms;\n"
            "`;\n"
            "document.body.appendChild(label);\n"
            "requestAnimationFrame(() => {\n"
            "    label.style.opacity = '1';\n"
            "    label.style.transform = 'translateY(0)';\n"
            "});\n"
            + (
                f"setTimeout(() => {{\n"
                f"    svg.style.transition = 'opacity .28s ease'; svg.style.opacity = '0';\n"
                f"    label.style.transition = 'opacity .28s ease'; label.style.opacity = '0';\n"
                f"}}, {lifetime - fade_ms});\n"
                if fade_ms
                else ""
            )
            + f"setTimeout(() => {{ svg.remove(); label.remove(); }}, {lifetime});\n"
        )
        evaluate_js(iife(js))
