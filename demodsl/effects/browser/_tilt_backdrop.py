"""Shared animated backdrops for the `background:` param on `perspective_tilt`
and `rotation_3d` (demodsl/effects/browser/perspective_tilt.py, rotation_3d.py).

Everything here is attached to `<html>` (`document.documentElement`), which
those two effects never transform — so the backdrop stays still while
`document.body` tilts/rotates in front of it, showing through in the space
around the clipped "window card".

`background:` accepts either a plain CSS color (validated, existing
behaviour) or one of these preset keywords for an animated look:
  - "stars" / "starfield" — a twinkling night sky
  - "aurora"               — drifting northern-light ribbons
"""

from __future__ import annotations

from demodsl.effects.sanitize import sanitize_css_color

_PRESETS = frozenset({"stars", "starfield", "aurora"})


def is_backdrop_preset(background: str) -> bool:
    return background.strip().lower() in _PRESETS


def build_tilt_backdrop(background: str | None) -> tuple[str, str]:
    """Return ``(setup_js, cleanup_js)`` for an optional tilt backdrop.

    Empty strings when *background* is falsy (no-op, matches prior
    behaviour). Unknown keywords fall back to :func:`sanitize_css_color`
    (a plain solid color, or its safe default on invalid input).
    """
    if not background:
        return "", ""
    key = str(background).strip().lower()
    if key in ("stars", "starfield"):
        return _stars_js()
    if key == "aurora":
        return _aurora_js()
    color = sanitize_css_color(background)
    setup = f"document.documentElement.style.background = '{color}';\n"
    cleanup = "document.documentElement.style.background = '';\n"
    return setup, cleanup


def _stars_js() -> tuple[str, str]:
    setup = (
        "document.documentElement.style.background = '#05070F';\n"
        "const __tsCanvas = document.createElement('canvas');\n"
        "__tsCanvas.id = '__demodsl_tilt_bg';\n"
        "__tsCanvas.style.cssText = 'position:fixed;top:0;left:0;width:100vw;"
        "height:100vh;z-index:0;pointer-events:none;';\n"
        "document.documentElement.appendChild(__tsCanvas);\n"
        "__tsCanvas.width = window.innerWidth;\n"
        "__tsCanvas.height = window.innerHeight;\n"
        "const __tsCtx = __tsCanvas.getContext('2d');\n"
        "const __tsStars = Array.from({length: 200}, () => ({\n"
        "    x: Math.random()*__tsCanvas.width, y: Math.random()*__tsCanvas.height,\n"
        "    r: Math.random()*1.6+0.4, phase: Math.random()*Math.PI*2, speed: 0.6+Math.random()*1.2\n"
        "}));\n"
        "function __tsDraw(t){\n"
        "    __tsCtx.clearRect(0,0,__tsCanvas.width,__tsCanvas.height);\n"
        "    __tsStars.forEach(s => {\n"
        "        const a = 0.3 + 0.7*Math.abs(Math.sin(t*0.0015*s.speed + s.phase));\n"
        "        __tsCtx.globalAlpha = a;\n"
        "        __tsCtx.fillStyle = '#FFFFFF';\n"
        "        __tsCtx.beginPath(); __tsCtx.arc(s.x, s.y, s.r, 0, Math.PI*2); __tsCtx.fill();\n"
        "    });\n"
        "    window.__demodsl_tilt_bg_raf = requestAnimationFrame(__tsDraw);\n"
        "}\n"
        "__tsDraw(0);\n"
    )
    cleanup = (
        "document.documentElement.style.background = '';\n"
        "if (window.__demodsl_tilt_bg_raf) cancelAnimationFrame(window.__demodsl_tilt_bg_raf);\n"
        "const __tsEl = document.getElementById('__demodsl_tilt_bg');\n"
        "if (__tsEl) __tsEl.remove();\n"
    )
    return setup, cleanup


def _aurora_js() -> tuple[str, str]:
    setup = (
        "document.documentElement.style.background = '#050B14';\n"
        "const __auStyle = document.createElement('style');\n"
        "__auStyle.id = '__demodsl_tilt_bg_style';\n"
        "__auStyle.textContent = `\n"
        "#__demodsl_tilt_bg {\n"
        "    position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:0;\n"
        "    pointer-events:none; opacity:0.55;\n"
        "    background:\n"
        "        radial-gradient(ellipse 80% 40% at 20% 8%, #00FFA3, transparent 60%),\n"
        "        radial-gradient(ellipse 70% 35% at 72% 4%, #00C2FF, transparent 60%),\n"
        "        radial-gradient(ellipse 95% 45% at 48% 0%, #8A5CFF, transparent 65%);\n"
        "    filter: blur(34px) saturate(1.3);\n"
        "    animation: __demodsl_tilt_aurora_drift 6s ease-in-out infinite alternate;\n"
        "}\n"
        "@keyframes __demodsl_tilt_aurora_drift {\n"
        "    0%   { transform: translateX(-6%) scaleY(1.0); }\n"
        "    50%  { transform: translateX(4%)  scaleY(1.18); }\n"
        "    100% { transform: translateX(6%)  scaleY(0.92); }\n"
        "}`;\n"
        "document.head.appendChild(__auStyle);\n"
        "const __auDiv = document.createElement('div');\n"
        "__auDiv.id = '__demodsl_tilt_bg';\n"
        "document.documentElement.appendChild(__auDiv);\n"
    )
    cleanup = (
        "document.documentElement.style.background = '';\n"
        "const __auEl = document.getElementById('__demodsl_tilt_bg');\n"
        "if (__auEl) __auEl.remove();\n"
        "const __auStyleEl = document.getElementById('__demodsl_tilt_bg_style');\n"
        "if (__auStyleEl) __auStyleEl.remove();\n"
    )
    return setup, cleanup
