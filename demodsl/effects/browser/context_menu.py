"""macOS right-click context menu.

Shows a native-style floating menu at a given viewport coordinate.
Separators are represented by ``"---"`` in the items list.
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_html_text,
    sanitize_number,
)

_DEFAULT_ITEMS = [
    "New Folder",
    "Get Info",
    "---",
    "Change Desktop Background…",
    "Use Stacks",
    "Sort By",
    "Clean Up",
    "---",
    "Show View Options",
]


class ContextMenuEffect(BrowserEffect):
    """Floating right-click menu at (x, y) viewport %.

    Params
    ------
    x : float
        X position in viewport percent (0.0–1.0).  Default ``0.5``.
    y : float
        Y position in viewport percent (0.0–1.0).  Default ``0.4``.
    items : list[str]
        Custom item list.  Use ``"---"`` for separators.
    highlight : int
        0-based index of item to highlight (default: none).
    color : str
        Accent color for highlighted item (default ``"#0A84FF"``).
    duration : float
        Seconds before auto-dismiss (default ``3.0``).
    """

    effect_id = "context_menu"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        x = sanitize_number(
            params.get("target_x", params.get("x", 0.5)),
            default=0.5,
            min_val=0.0,
            max_val=1.0,
        )
        y = sanitize_number(
            params.get("target_y", params.get("y", 0.4)),
            default=0.4,
            min_val=0.0,
            max_val=1.0,
        )
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=0.5, max_val=15.0
        )
        color = sanitize_css_color(params.get("color", "#0A84FF"))
        highlight = int(
            sanitize_number(
                params.get("highlight", -1),
                default=-1,
                min_val=-1,
                max_val=50,
            )
        )

        items_param = params.get("items")
        if items_param and isinstance(items_param, list):
            items = [str(i) for i in items_param]
        else:
            items = _DEFAULT_ITEMS

        items_html = ""
        real_idx = 0
        for raw in items:
            if raw == "---":
                items_html += (
                    "<div style='height:1px;margin:5px 8px;"
                    "background:rgba(255,255,255,0.08)'></div>"
                )
                continue
            bg = color if real_idx == highlight else "transparent"
            fg = "#fff" if real_idx == highlight else "#e8e8e8"
            label = sanitize_html_text(raw)
            items_html += (
                f"<div class='__demodsl_context_menu_item' "
                f"style='padding:4px 22px 4px 14px;font-size:13px;"
                f"color:{fg};background:{bg};border-radius:4px;margin:0 4px;"
                f"cursor:default;white-space:nowrap;'>{label}</div>"
            )
            real_idx += 1

        lifetime = int(duration * 1000)

        css = (
            "@keyframes __demodsl_context_menu_in {"
            "  from { opacity:0; transform: scale(0.92); }"
            "  to   { opacity:1; transform: scale(1); }"
            "}"
            ".__demodsl_context_menu_item:hover {"
            "  background: rgba(255,255,255,0.08) !important;"
            "}"
        )

        js = (
            inject_style("__demodsl_context_menu_style", css)
            + "const prev = document.getElementById('__demodsl_context_menu');\n"
            "if(prev) prev.remove();\n"
            "const cm = document.createElement('div');\n"
            "cm.id = '__demodsl_context_menu';\n"
            f"cm.style.cssText = `position:fixed;"
            f" left:calc({x * 100:.1f}vw);"
            f" top:calc({y * 100:.1f}vh);"
            " z-index:99998; min-width:220px; padding:4px 0;"
            " background:rgba(40,40,45,0.92);"
            " backdrop-filter:blur(30px) saturate(180%);"
            " -webkit-backdrop-filter:blur(30px) saturate(180%);"
            " border:0.5px solid rgba(255,255,255,0.12);"
            " border-radius:6px;"
            " box-shadow:0 12px 40px rgba(0,0,0,0.45);"
            " transform-origin: top left;"
            " font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
            " animation:__demodsl_context_menu_in 0.15s ease-out;"
            " pointer-events:auto;`;\n"
            f"cm.innerHTML = `{items_html}`;\n"
            "document.body.appendChild(cm);\n"
            # Clamp into viewport — if the menu would overflow right/bottom,
            # flip its position to the left/top of the click point.
            "requestAnimationFrame(function(){\n"
            "  var r = cm.getBoundingClientRect();\n"
            "  if(r.right > window.innerWidth - 4){\n"
            "    cm.style.left = (window.innerWidth - r.width - 4) + 'px';\n"
            "  }\n"
            "  if(r.bottom > window.innerHeight - 4){\n"
            "    cm.style.top = (window.innerHeight - r.height - 4) + 'px';\n"
            "  }\n"
            "});\n"
            f"setTimeout(function(){{\n"
            "  if(cm.parentNode){ cm.style.transition='opacity 0.15s'; cm.style.opacity='0'; }\n"
            "  setTimeout(function(){ if(cm.parentNode) cm.remove(); }, 180);\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
