"""Cursor overlay — injects a visible fake cursor into the browser page."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# SVG pointer arrow (classic cursor shape), URL-encoded for use in CSS
_POINTER_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28' "
    "viewBox='0 0 28 28'%3E%3Cpath d='M2 2l10 24 3-9 9-3z' fill='{color}' "
    "stroke='white' stroke-width='1.5' stroke-linejoin='round'/%3E%3C/svg%3E"
)

# Windows XP cursor — classic white arrow with black outline and shadow
_XP_CURSOR_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' "
    "viewBox='0 0 32 32'%3E"
    "%3Cdefs%3E%3Cfilter id='s'%3E%3CfeDropShadow dx='1' dy='1' "
    "stdDeviation='0.5' flood-opacity='0.35'/%3E%3C/filter%3E%3C/defs%3E"
    "%3Cpath d='M3 1L3 27L9.5 20L15 30L19 28L13.5 18L22 18Z' "
    "fill='white' stroke='black' stroke-width='1.2' "
    "stroke-linejoin='miter' filter='url(%23s)'/%3E%3C/svg%3E"
)


class CursorOverlay:
    """Manages a fake CSS cursor overlay injected into the browser page.

    The cursor is a ``position: fixed`` element captured by Playwright's
    built-in video recording.  It exposes two JS globals:

    * ``window.__demodsl_cursor_move(x, y)`` — animate cursor to (x, y)
    * ``window.__demodsl_cursor_click()``     — play click visual effect
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.visible = config.get("visible", True)
        self.style = config.get("style", "dot")
        self.color = config.get("color", "#ef4444")
        self.size = config.get("size", 20)
        self.click_effect = config.get("click_effect", "ripple")
        self.smooth = config.get("smooth", 0.4)
        self.bezier = config.get("bezier", True)

    def inject(self, evaluate_js: Any) -> None:
        """Inject the cursor overlay element and helper JS functions."""
        if not self.visible:
            return

        if self.style == "xp":
            cursor_css = (
                f"width:{self.size}px; height:{self.size}px; "
                f'background:url("{_XP_CURSOR_SVG}") no-repeat top left/contain; '
                "border-radius:0;"
            )
        elif self.style == "pointer":
            svg_url = _POINTER_SVG.replace("{color}", self.color.replace("#", "%23"))
            cursor_css = (
                f"width:{self.size}px; height:{self.size}px; "
                f'background:url("{svg_url}") no-repeat center/contain; '
                "border-radius:0;"
            )
        else:  # dot
            cursor_css = (
                f"width:{self.size}px; height:{self.size}px; "
                f"background:{self.color}; border-radius:50%; "
                f"box-shadow: 0 0 6px {self.color}80, 0 0 12px {self.color}40;"
            )

        click_ripple_js = ""
        if self.click_effect == "ripple":
            click_ripple_js = f"""
                const rect = el.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const ripple = document.createElement('div');
                ripple.style.cssText = `
                    position:fixed; z-index:199998; pointer-events:none;
                    left:${{cx}}px; top:${{cy}}px;
                    width:0; height:0; border-radius:50%;
                    border:2px solid {self.color};
                    transform:translate(-50%,-50%);
                    animation: __demodsl_click_ripple 0.5s ease-out forwards;
                `;
                document.body.appendChild(ripple);
                setTimeout(() => ripple.remove(), 600);
            """
        elif self.click_effect == "pulse":
            click_ripple_js = """
                el.style.transform = 'translate(-50%,-50%) scale(1.8)';
                setTimeout(() => { el.style.transform = 'translate(-50%,-50%) scale(1)'; }, 200);
            """

        transition_css = (
            ""
            if self.bezier
            else f"transition: left {self.smooth}s ease-out, top {self.smooth}s ease-out;"
        )

        bezier_helpers = ""
        bezier_move = ""
        if self.bezier:
            bezier_helpers = """
            function __cbez(t, p0, p1, p2, p3) {
                var u = 1 - t;
                return u*u*u*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t*t*t*p3;
            }
            function __easeOut(t) { return 1 - Math.pow(1 - t, 3); }
            var __animId = 0;
            """
            bezier_move = f"""
                var startX = parseFloat(el.style.left) || 0;
                var startY = parseFloat(el.style.top) || 0;
                var dx = x - startX, dy = y - startY;
                var dist = Math.sqrt(dx*dx + dy*dy);
                if (dist < 1) {{ el.style.left = x+'px'; el.style.top = y+'px'; return; }}
                var offset = dist * 0.15 * (Math.random() > 0.5 ? 1 : -1);
                var nx = -dy / dist, ny = dx / dist;
                var cp1x = startX + dx*0.3 + nx*offset;
                var cp1y = startY + dy*0.3 + ny*offset;
                var cp2x = startX + dx*0.7 + nx*offset*0.5;
                var cp2y = startY + dy*0.7 + ny*offset*0.5;
                var dur = {self.smooth} * 1000;
                var start = performance.now();
                var myId = ++__animId;
                function frame(now) {{
                    if (myId !== __animId) return;
                    var t = Math.min((now - start) / dur, 1);
                    var et = __easeOut(t);
                    el.style.left = __cbez(et, startX, cp1x, cp2x, x) + 'px';
                    el.style.top  = __cbez(et, startY, cp1y, cp2y, y) + 'px';
                    if (t < 1) requestAnimationFrame(frame);
                }}
                requestAnimationFrame(frame);
                return;
            """

        evaluate_js(f"""(() => {{
            // Clean up previous injection if any
            document.getElementById('__demodsl_cursor')?.remove();
            document.getElementById('__demodsl_cursor_style')?.remove();

            const style = document.createElement('style');
            style.id = '__demodsl_cursor_style';
            style.textContent = `
                @keyframes __demodsl_click_ripple {{
                    0%   {{ width:0; height:0; opacity:1; }}
                    100% {{ width:60px; height:60px; opacity:0; }}
                }}
            `;
            document.head.appendChild(style);

            const el = document.createElement('div');
            el.id = '__demodsl_cursor';
            el.style.cssText = `
                position:fixed; z-index:199999; pointer-events:none;
                {cursor_css}
                left:50%; top:50%;
                transform:translate(-50%,-50%);
                {transition_css}
            `;
            document.body.appendChild(el);

            {bezier_helpers}

            window.__demodsl_cursor_move = function(x, y) {{
                {bezier_move}
                el.style.left = x + 'px';
                el.style.top  = y + 'px';
            }};

            window.__demodsl_cursor_click = function() {{
                {click_ripple_js}
            }};
        }})()""")
        logger.debug(
            "Cursor overlay injected (style=%s, color=%s, bezier=%s)",
            self.style,
            self.color,
            self.bezier,
        )

    def move_to(self, evaluate_js: Any, x: float, y: float) -> None:
        """Animate the cursor to coordinates (x, y) and wait for the transition."""
        if not self.visible:
            return
        evaluate_js(f"window.__demodsl_cursor_move({x}, {y})")
        time.sleep(self.smooth + 0.05)

    def trigger_click(self, evaluate_js: Any) -> None:
        """Play the click visual effect at the cursor's current position."""
        if not self.visible or self.click_effect == "none":
            return
        evaluate_js("window.__demodsl_cursor_click()")
        time.sleep(0.35)
