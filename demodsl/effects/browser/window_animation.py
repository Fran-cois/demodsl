"""Window animations — macOS genie, open, close, minimize, maximize.

The animation targets either the main browser window (``body`` with its
pinned OS frame) or one of the secondary_windows by index.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


_VALID_ANIMS = {"minimize", "maximize", "close", "open", "restore"}


class WindowAnimationEffect(BrowserEffect):
    """Animate a window (genie minimize, open, close, etc.).

    Params
    ------
    animation : str
        One of ``"minimize"`` (genie to dock), ``"maximize"`` (expand to
        fullscreen), ``"close"`` (fade+shrink), ``"open"`` (pop in with
        overshoot), or ``"restore"`` (reverse maximize).  Default ``"open"``.
    target : int | str
        Either a secondary window index (0, 1, …) or ``"main"`` for the
        primary browser window.  Default ``"main"``.
    duration : float
        Animation duration in seconds (default ``0.5``).
    """

    effect_id = "window_animation"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        anim = str(params.get("animation", "open"))
        if anim not in _VALID_ANIMS:
            anim = "open"

        duration = sanitize_number(
            params.get("duration", 0.5), default=0.5, min_val=0.1, max_val=4.0
        )
        dur_ms = int(duration * 1000)

        target = params.get("target", "main")
        if isinstance(target, str) and target.isdigit():
            target = int(target)
        if not isinstance(target, int):
            target = "main"

        # Resolve the target selector
        if target == "main":
            selector = "document.body"
        else:
            selector = f"document.querySelectorAll('.__demodsl_secondary_window')[{int(target)}]"

        # Dock x for genie effect — center of dock approx
        dock_x = "(window.innerWidth/2)"
        dock_y = "(window.innerHeight - 30)"

        css = self._keyframes_css(duration)
        if anim == "minimize":
            js_body = self._js_minimize(selector, dur_ms, dock_x, dock_y)
        elif anim == "maximize":
            js_body = self._js_maximize(selector, dur_ms)
        elif anim == "close":
            js_body = self._js_close(selector, dur_ms)
        elif anim == "restore":
            js_body = self._js_restore(selector, dur_ms)
        else:  # open
            js_body = self._js_open(selector, dur_ms)

        js = inject_style("__demodsl_window_animation_style", css) + js_body
        evaluate_js(iife(js))

    # ── CSS keyframes ─────────────────────────────────────────────

    @staticmethod
    def _keyframes_css(duration: float) -> str:
        return (
            "@keyframes __demodsl_win_open {"
            "  0% { opacity:0; transform: scale(0.5); }"
            "  60% { opacity:1; transform: scale(1.05); }"
            "  100% { opacity:1; transform: scale(1); }"
            "}"
            "@keyframes __demodsl_win_close {"
            "  0% { opacity:1; transform: scale(1); }"
            "  100% { opacity:0; transform: scale(0.95); }"
            "}"
            "@keyframes __demodsl_win_maximize {"
            "  0% { transform: scale(0.92); border-radius: 10px; }"
            "  100% { transform: scale(1); border-radius: 0; }"
            "}"
            "@keyframes __demodsl_win_restore {"
            "  0% { transform: scale(1); border-radius: 0; }"
            "  100% { transform: scale(0.92); border-radius: 10px; }"
            "}"
        )

    # ── Per-animation JS builders ────────────────────────────────

    @staticmethod
    def _js_open(selector: str, dur_ms: int) -> str:
        return (
            f"const tgt = {selector};\n"
            "if(tgt){\n"
            f"  tgt.style.animation = '__demodsl_win_open {dur_ms}ms cubic-bezier(0.34,1.56,0.64,1)';\n"
            f"  setTimeout(function(){{ tgt.style.animation = ''; }}, {dur_ms + 50});\n"
            "}\n"
        )

    @staticmethod
    def _js_close(selector: str, dur_ms: int) -> str:
        return (
            f"const tgt = {selector};\n"
            "if(tgt){\n"
            f"  tgt.style.animation = '__demodsl_win_close {dur_ms}ms ease-in forwards';\n"
            "}\n"
        )

    @staticmethod
    def _js_maximize(selector: str, dur_ms: int) -> str:
        return (
            f"const tgt = {selector};\n"
            "if(tgt){\n"
            f"  tgt.style.animation = '__demodsl_win_maximize {dur_ms}ms cubic-bezier(0.4,0,0.2,1) forwards';\n"
            "}\n"
        )

    @staticmethod
    def _js_restore(selector: str, dur_ms: int) -> str:
        return (
            f"const tgt = {selector};\n"
            "if(tgt){\n"
            f"  tgt.style.animation = '__demodsl_win_restore {dur_ms}ms cubic-bezier(0.4,0,0.2,1) forwards';\n"
            "}\n"
        )

    @staticmethod
    def _js_minimize(selector: str, dur_ms: int, dock_x: str, dock_y: str) -> str:
        # Genie effect — scale down + translate toward the dock center
        # while skewing slightly for the classic macOS trapezoid look.
        return (
            f"const tgt = {selector};\n"
            "if(tgt){\n"
            "  var rect = tgt.getBoundingClientRect();\n"
            f"  var dx = {dock_x} - (rect.left + rect.width/2);\n"
            f"  var dy = {dock_y} - (rect.top + rect.height/2);\n"
            "  tgt.style.transformOrigin = 'center bottom';\n"
            f"  tgt.style.transition = 'transform {dur_ms}ms cubic-bezier(0.55,0.085,0.68,0.53), opacity {dur_ms}ms ease-in';\n"
            "  requestAnimationFrame(function(){\n"
            "    tgt.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(0.05,0.01) skewX(10deg)';\n"
            "    tgt.style.opacity = '0';\n"
            "  });\n"
            f"  setTimeout(function(){{ tgt.style.visibility = 'hidden'; }}, {dur_ms});\n"
            "}\n"
        )
