"""Menu bar dropdown — macOS-style dropdown shown when a menu item is clicked.

Also works standalone (triggered by an effect step) so demos can showcase
any menu without simulating a real click.  The dropdown auto-dismisses
after ``duration`` or on outside click.
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


_DEFAULT_ITEMS = {
    "File": [
        "New Window",
        "New Tab",
        "---",
        "Open…",
        "Open Recent",
        "---",
        "Close Tab",
        "Close Window",
        "---",
        "Save…",
        "Save As…",
        "Print…",
    ],
    "Edit": [
        "Undo",
        "Redo",
        "---",
        "Cut",
        "Copy",
        "Paste",
        "Paste and Match Style",
        "Delete",
        "Select All",
        "---",
        "Find",
    ],
    "View": [
        "Show Tab Bar",
        "Show Toolbar",
        "Show Sidebar",
        "---",
        "Enter Full Screen",
        "---",
        "Actual Size",
        "Zoom In",
        "Zoom Out",
    ],
    "Window": [
        "Minimize",
        "Zoom",
        "---",
        "Bring All to Front",
        "Move Window to Left Side of Screen",
        "Move Window to Right Side of Screen",
    ],
    "Help": [
        "Search",
        "---",
        "User Guide",
        "Keyboard Shortcuts",
        "Release Notes",
    ],
    "app": [
        "About",
        "---",
        "Preferences…",
        "---",
        "Hide",
        "Hide Others",
        "Show All",
        "---",
        "Quit",
    ],
}


class MenuDropdownEffect(BrowserEffect):
    """Dropdown menu from the top menu bar.

    Params
    ------
    menu : str
        Name of the menu (``"File"``, ``"Edit"``, ``"View"``, ``"Window"``,
        ``"Help"`` or ``"app"``).  Determines the default item list.
    items : list[str]
        Optional custom item list.  Use ``"---"`` for a separator.
    highlight : int
        0-based index of an item to highlight in blue (default: none).
    color : str
        Accent color for the highlighted item (default ``"#0A84FF"``).
    duration : float
        Seconds the dropdown stays visible (default ``3.5``).
    """

    effect_id = "menu_dropdown"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        menu = str(params.get("menu", "File"))
        items_param = params.get("items")
        if items_param and isinstance(items_param, list):
            items = [str(i) for i in items_param]
        else:
            items = _DEFAULT_ITEMS.get(menu, _DEFAULT_ITEMS["File"])

        highlight = int(
            sanitize_number(
                params.get("highlight", -1),
                default=-1,
                min_val=-1,
                max_val=50,
            )
        )
        color = sanitize_css_color(params.get("color", "#0A84FF"))
        duration = sanitize_number(
            params.get("duration", 3.5), default=3.5, min_val=0.5, max_val=15.0
        )
        lifetime = int(duration * 1000)

        # Position: the JS will try to read the menu bar item's rect from
        # the __demodsl_menu_click event if present; otherwise fall back
        # to a sensible default (below the menu bar, 14px from the left).
        menu_safe = sanitize_html_text(menu)

        # Build HTML for each item
        items_html = ""
        real_idx = 0
        for raw in items:
            if raw == "---":
                items_html += (
                    "<div style='height:1px;margin:4px 8px;"
                    "background:rgba(255,255,255,0.08)'></div>"
                )
                continue
            bg = color if real_idx == highlight else "transparent"
            fg = "#fff" if real_idx == highlight else "#e8e8e8"
            label = sanitize_html_text(raw)
            items_html += (
                f"<div class='__demodsl_menu_dropdown_item' "
                f"style='padding:4px 22px 4px 14px;font-size:13px;"
                f"color:{fg};background:{bg};border-radius:4px;margin:0 4px;"
                f"cursor:default;white-space:nowrap;'>{label}</div>"
            )
            real_idx += 1

        css = (
            "@keyframes __demodsl_menu_dropdown_in {"
            "  from { opacity:0; transform: translateY(-6px) scale(0.96); }"
            "  to   { opacity:1; transform: translateY(0) scale(1); }"
            "}"
            ".__demodsl_menu_dropdown_item:hover {"
            "  background: rgba(255,255,255,0.08) !important;"
            "}"
        )

        js = (
            inject_style("__demodsl_menu_dropdown_style", css)
            + "const prev = document.getElementById('__demodsl_menu_dropdown');\n"
            "if(prev) prev.remove();\n"
            "const dd = document.createElement('div');\n"
            "dd.id = '__demodsl_menu_dropdown';\n"
            f"dd.dataset.menu = '{menu_safe}';\n"
            "dd.style.cssText = `position:fixed; z-index:99998;"
            " min-width:200px; padding:4px 0;"
            " background:rgba(40,40,45,0.92);"
            " backdrop-filter:blur(30px) saturate(180%);"
            " -webkit-backdrop-filter:blur(30px) saturate(180%);"
            " border:0.5px solid rgba(255,255,255,0.12);"
            " border-radius:6px;"
            " box-shadow:0 12px 40px rgba(0,0,0,0.45),0 0 0 0.5px rgba(255,255,255,0.05);"
            " font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
            " animation:__demodsl_menu_dropdown_in 0.18s cubic-bezier(0.34,1.56,0.64,1);"
            " pointer-events:auto;`;\n"
            f"dd.innerHTML = `{items_html}`;\n"
            # Position under the matching menu-bar item if we can find it
            f"var anchor = document.querySelector('.__demodsl_menu_item[data-menu=\"{menu_safe}\"]');\n"
            "if(anchor){\n"
            "  var r = anchor.getBoundingClientRect();\n"
            "  dd.style.top = (r.bottom + 2) + 'px';\n"
            "  dd.style.left = r.left + 'px';\n"
            "} else {\n"
            "  dd.style.top = '30px';\n"
            "  dd.style.left = '14px';\n"
            "}\n"
            "document.body.appendChild(dd);\n"
            # Highlight the anchor briefly
            "if(anchor){\n"
            "  var prevBg = anchor.style.background;\n"
            "  anchor.style.background = 'rgba(255,255,255,0.18)';\n"
            f"  setTimeout(function(){{ anchor.style.background = prevBg; }}, {lifetime});\n"
            "}\n"
            # Auto-dismiss
            f"setTimeout(function(){{\n"
            "  if(dd.parentNode){ dd.style.transition='opacity 0.15s'; dd.style.opacity='0'; }\n"
            "  setTimeout(function(){ if(dd.parentNode) dd.remove(); }, 180);\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
