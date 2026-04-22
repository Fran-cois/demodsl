"""App switcher — macOS ⌘+Tab / Windows Alt+Tab visual overlay."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class AppSwitcherEffect(BrowserEffect):
    """Displays an animated app-switcher overlay (⌘Tab / AltTab).

    Params
    ------
    style : str
        ``"macos"`` (default) or ``"windows"`` — visual theme.
    selected : int
        0-based index of the app to highlight as "selected" (default 1).
    apps : list[dict]
        Optional list of ``{"name": "App", "color": "#hex"}`` entries.
        Falls back to a sensible default set if not provided.
    color : str
        Accent color for the selection ring (default ``"#6366f1"``).
    duration : float
        How long the overlay stays visible (seconds, default 3.0).
    """

    effect_id = "app_switcher"

    # Default app set when the user doesn't specify ``apps``
    _DEFAULT_APPS_MACOS = [
        {
            "name": "Safari",
            "color": "#3B82F6",
            "icon": "M12 2a10 10 0 100 20 10 10 0 000-20zm0 3l3 7-7 3 3-7z",
        },
        {
            "name": "VS Code",
            "color": "#007ACC",
            "icon": "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6z",
        },
        {"name": "Terminal", "color": "#333333", "icon": "M4 17l6-5-6-5M12 19h8"},
        {"name": "Finder", "color": "#2196F3", "icon": "M4 4h16v16H4z"},
        {
            "name": "Notes",
            "color": "#FFCA28",
            "icon": "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6M8 13h8M8 17h8",
        },
        {
            "name": "Music",
            "color": "#FC3C44",
            "icon": "M9 18V5l12-2v13M9 18a3 3 0 11-6 0 3 3 0 016 0zM21 16a3 3 0 11-6 0 3 3 0 016 0z",
        },
    ]

    _DEFAULT_APPS_WINDOWS = [
        {
            "name": "Edge",
            "color": "#0078D4",
            "icon": "M12 2a10 10 0 100 20 10 10 0 000-20z",
        },
        {
            "name": "VS Code",
            "color": "#007ACC",
            "icon": "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6z",
        },
        {"name": "Terminal", "color": "#666666", "icon": "M4 17l6-5-6-5M12 19h8"},
        {
            "name": "Explorer",
            "color": "#FFCA28",
            "icon": "M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z",
        },
        {
            "name": "Notepad",
            "color": "#1976D2",
            "icon": "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6M8 13h8M8 17h8",
        },
        {
            "name": "Spotify",
            "color": "#1DB954",
            "icon": "M12 2a10 10 0 100 20 10 10 0 000-20zm4.6 14.4a.6.6 0 01-.84.2c-2.3-1.4-5.2-1.7-8.6-.9a.6.6 0 11-.28-1.2c3.7-.9 6.9-.5 9.5 1.1a.6.6 0 01.2.8z",
        },
    ]

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        style = params.get("style", "macos")
        if style not in ("macos", "windows"):
            style = "macos"

        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=1.0, max_val=15.0
        )
        selected = int(
            sanitize_number(params.get("selected", 1), default=1, min_val=0, max_val=20)
        )

        apps_param = params.get("apps")
        if apps_param and isinstance(apps_param, list):
            apps = []
            for app in apps_param:
                if isinstance(app, dict):
                    apps.append(
                        {
                            "name": str(app.get("name", "App"))[:30],
                            "color": sanitize_css_color(app.get("color", "#6366f1")),
                            "icon": str(
                                app.get("icon", "M12 2a10 10 0 100 20 10 10 0 000-20z")
                            )[:200],
                        }
                    )
            if not apps:
                apps = (
                    self._DEFAULT_APPS_MACOS
                    if style == "macos"
                    else self._DEFAULT_APPS_WINDOWS
                )
        else:
            apps = (
                self._DEFAULT_APPS_MACOS
                if style == "macos"
                else self._DEFAULT_APPS_WINDOWS
            )

        selected = min(selected, len(apps) - 1)
        lifetime = int(duration * 1000)

        if style == "macos":
            js = self._build_macos_js(apps, selected, color, lifetime)
        else:
            js = self._build_windows_js(apps, selected, color, lifetime)

        evaluate_js(iife(js))

    def _build_macos_js(
        self,
        apps: list[dict[str, str]],
        selected: int,
        color: str,
        lifetime: int,
    ) -> str:
        """macOS ⌘+Tab style — frosted glass bar with app icons."""
        icon_size = 72
        gap = 16
        pad = 24
        anim_delay = 120  # ms between each icon "popping in"
        select_delay = anim_delay * len(apps) + 200  # when the selection ring appears

        # Build icons HTML
        icons_html = ""
        for i, app in enumerate(apps):
            name = app["name"].replace("'", "\\'").replace("<", "&lt;")
            app_color = app.get("color", "#6366f1")
            icon_path = app.get("icon", "M12 2a10 10 0 100 20 10 10 0 000-20z")
            delay = anim_delay * i
            icons_html += (
                f"<div style='display:flex;flex-direction:column;align-items:center;"
                f"gap:6px;opacity:0;transform:scale(0.6);transition:opacity 0.25s ease,transform 0.25s ease'"
                f" data-delay='{delay}'>"
                f"<div style='width:{icon_size}px;height:{icon_size}px;border-radius:16px;"
                f"background:rgba(60,60,70,0.6);display:flex;align-items:center;justify-content:center;"
                f"box-shadow:0 4px 12px rgba(0,0,0,0.3),inset 0 0 0 0.5px rgba(255,255,255,0.1);"
                f"position:relative'>"
                f"<svg width='36' height='36' viewBox='0 0 24 24' fill='none' "
                f"stroke='{app_color}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>"
                f"<path d='{icon_path}'/></svg>"
                f"</div>"
                f"<span style='font-size:11px;color:#e0e0e0;font-weight:500;"
                f"font-family:-apple-system,BlinkMacSystemFont,sans-serif;text-shadow:0 1px 2px rgba(0,0,0,0.5)'>"
                f"{name}</span>"
                f"</div>"
            )

        # Selection ring (will be positioned over the selected icon)
        ring_offset = selected * (icon_size + gap)

        css = (
            "#__demodsl_app_switcher {\n"
            "  position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "  z-index:99999; pointer-events:none;\n"
            "  display:flex; align-items:center; justify-content:center;\n"
            "  background:rgba(0,0,0,0.25);\n"
            "  opacity:0; transition:opacity 0.3s ease;\n"
            "}\n"
            "#__demodsl_app_switcher_bar {\n"
            f"  display:flex; gap:{gap}px; padding:{pad}px;\n"
            "  background:rgba(40,40,50,0.75);\n"
            "  backdrop-filter:blur(40px) saturate(180%);\n"
            "  -webkit-backdrop-filter:blur(40px) saturate(180%);\n"
            "  border-radius:20px; position:relative;\n"
            "  border:0.5px solid rgba(255,255,255,0.12);\n"
            "  box-shadow:0 20px 60px rgba(0,0,0,0.5);\n"
            "}\n"
            "#__demodsl_app_switcher_ring {\n"
            f"  position:absolute; top:{pad - 6}px; width:{icon_size + 12}px;\n"
            f"  height:{icon_size + 24}px; border-radius:18px;\n"
            f"  border:3px solid {color};\n"
            "  opacity:0; transition:opacity 0.3s ease, left 0.3s cubic-bezier(0.4,0,0.2,1);\n"
            "  box-shadow:0 0 20px rgba(99,102,241,0.3);\n"
            "  pointer-events:none;\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_app_switcher_style", css)
            + "const overlay = document.createElement('div');\n"
            "overlay.id = '__demodsl_app_switcher';\n"
            "const bar = document.createElement('div');\n"
            "bar.id = '__demodsl_app_switcher_bar';\n"
            f"bar.innerHTML = `{icons_html}`;\n"
            # Selection ring
            "const ring = document.createElement('div');\n"
            "ring.id = '__demodsl_app_switcher_ring';\n"
            f"ring.style.left = '{pad - 6 + ring_offset}px';\n"
            "bar.appendChild(ring);\n"
            "overlay.appendChild(bar);\n"
            "document.body.appendChild(overlay);\n"
            # Animate in
            "requestAnimationFrame(() => {\n"
            "  overlay.style.opacity = '1';\n"
            "  const icons = bar.querySelectorAll('[data-delay]');\n"
            "  icons.forEach(el => {\n"
            "    const d = parseInt(el.dataset.delay);\n"
            "    setTimeout(() => {\n"
            "      el.style.opacity = '1';\n"
            "      el.style.transform = 'scale(1)';\n"
            "    }, d);\n"
            "  });\n"
            # Show selection ring with delay
            f"  setTimeout(() => {{ ring.style.opacity = '1'; }}, {select_delay});\n"
            "});\n"
            # ⌘+Tab shortcut badge (top-center)
            "const badge = document.createElement('div');\n"
            "badge.style.cssText = 'position:fixed;top:16%;left:50%;transform:translateX(-50%);"
            "z-index:99999;pointer-events:none;display:flex;gap:8px;align-items:center;"
            "padding:8px 16px;background:rgba(30,30,40,0.8);border-radius:10px;"
            "backdrop-filter:blur(12px);border:0.5px solid rgba(255,255,255,0.1);"
            "font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;"
            "color:#e0e0e0;opacity:0;transition:opacity 0.3s ease';\n"
            "badge.innerHTML = `<kbd style='padding:3px 8px;background:rgba(255,255,255,0.1);"
            "border-radius:5px;font-size:13px;border:1px solid rgba(255,255,255,0.15)'>⌘</kbd>"
            "<span>+</span>"
            "<kbd style='padding:3px 8px;background:rgba(255,255,255,0.1);"
            "border-radius:5px;font-size:13px;border:1px solid rgba(255,255,255,0.15)'>Tab</kbd>`;\n"
            "document.body.appendChild(badge);\n"
            "requestAnimationFrame(() => { badge.style.opacity = '1'; });\n"
            # Auto-remove
            f"setTimeout(() => {{\n"
            "  overlay.style.opacity = '0';\n"
            "  badge.style.opacity = '0';\n"
            "  setTimeout(() => {\n"
            "    overlay.remove();\n"
            "    badge.remove();\n"
            "    const st = document.getElementById('__demodsl_app_switcher_style');\n"
            "    if(st) st.remove();\n"
            f"  }}, 400);\n"
            f"}}, {lifetime});\n"
        )
        return js

    def _build_windows_js(
        self,
        apps: list[dict[str, str]],
        selected: int,
        color: str,
        lifetime: int,
    ) -> str:
        """Windows Alt+Tab style — acrylic grid with app thumbnails."""
        thumb_w = 160
        thumb_h = 100
        gap = 12
        pad = 20
        anim_delay = 80

        # Build app cards HTML
        cards_html = ""
        for i, app in enumerate(apps):
            name = app["name"].replace("'", "\\'").replace("<", "&lt;")
            app_color = app.get("color", "#0078D4")
            icon_path = app.get("icon", "M12 2a10 10 0 100 20 10 10 0 000-20z")
            delay = anim_delay * i
            is_selected = i == selected
            border_style = (
                f"border:2px solid {color}"
                if is_selected
                else "border:2px solid transparent"
            )
            cards_html += (
                f"<div style='display:flex;flex-direction:column;align-items:center;gap:8px;"
                f"opacity:0;transform:translateY(10px);transition:opacity 0.2s ease,transform 0.2s ease'"
                f" data-delay='{delay}'>"
                # Thumbnail area
                f"<div style='width:{thumb_w}px;height:{thumb_h}px;border-radius:8px;"
                f"background:rgba(50,50,60,0.6);display:flex;align-items:center;justify-content:center;"
                f"{border_style};transition:border-color 0.2s ease;"
                f"box-shadow:0 2px 8px rgba(0,0,0,0.2)'>"
                f"<svg width='32' height='32' viewBox='0 0 24 24' fill='none' "
                f"stroke='{app_color}' stroke-width='1.5' stroke-linecap='round'>"
                f"<path d='{icon_path}'/></svg>"
                f"</div>"
                # App name
                f"<span style='font-size:12px;color:#e0e0e0;font-weight:400;"
                f"font-family:Segoe UI Variable,Segoe UI,sans-serif'>{name}</span>"
                f"</div>"
            )

        css = (
            "#__demodsl_app_switcher {\n"
            "  position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "  z-index:99999; pointer-events:none;\n"
            "  display:flex; align-items:center; justify-content:center;\n"
            "  background:rgba(0,0,0,0.3);\n"
            "  opacity:0; transition:opacity 0.25s ease;\n"
            "}\n"
            "#__demodsl_app_switcher_grid {\n"
            f"  display:flex; gap:{gap}px; padding:{pad}px;\n"
            "  background:rgba(32,32,32,0.85);\n"
            "  backdrop-filter:blur(30px);\n"
            "  -webkit-backdrop-filter:blur(30px);\n"
            "  border-radius:12px;\n"
            "  border:1px solid rgba(255,255,255,0.06);\n"
            "  box-shadow:0 16px 48px rgba(0,0,0,0.4);\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_app_switcher_style", css)
            + "const overlay = document.createElement('div');\n"
            "overlay.id = '__demodsl_app_switcher';\n"
            "const grid = document.createElement('div');\n"
            "grid.id = '__demodsl_app_switcher_grid';\n"
            f"grid.innerHTML = `{cards_html}`;\n"
            "overlay.appendChild(grid);\n"
            "document.body.appendChild(overlay);\n"
            # Animate in
            "requestAnimationFrame(() => {\n"
            "  overlay.style.opacity = '1';\n"
            "  const cards = grid.querySelectorAll('[data-delay]');\n"
            "  cards.forEach(el => {\n"
            "    const d = parseInt(el.dataset.delay);\n"
            "    setTimeout(() => {\n"
            "      el.style.opacity = '1';\n"
            "      el.style.transform = 'translateY(0)';\n"
            "    }, d);\n"
            "  });\n"
            "});\n"
            # Alt+Tab shortcut badge
            "const badge = document.createElement('div');\n"
            "badge.style.cssText = 'position:fixed;top:16%;left:50%;transform:translateX(-50%);"
            "z-index:99999;pointer-events:none;display:flex;gap:8px;align-items:center;"
            "padding:8px 16px;background:rgba(32,32,40,0.85);border-radius:8px;"
            "backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.06);"
            "font-family:Segoe UI Variable,Segoe UI,sans-serif;font-size:13px;"
            "color:#e0e0e0;opacity:0;transition:opacity 0.25s ease';\n"
            "badge.innerHTML = `<kbd style='padding:3px 8px;background:rgba(255,255,255,0.08);"
            "border-radius:4px;font-size:12px;border:1px solid rgba(255,255,255,0.1)'>Alt</kbd>"
            "<span>+</span>"
            "<kbd style='padding:3px 8px;background:rgba(255,255,255,0.08);"
            "border-radius:4px;font-size:12px;border:1px solid rgba(255,255,255,0.1)'>Tab</kbd>`;\n"
            "document.body.appendChild(badge);\n"
            "requestAnimationFrame(() => { badge.style.opacity = '1'; });\n"
            # Auto-remove
            f"setTimeout(() => {{\n"
            "  overlay.style.opacity = '0';\n"
            "  badge.style.opacity = '0';\n"
            "  setTimeout(() => {\n"
            "    overlay.remove();\n"
            "    badge.remove();\n"
            "    const st = document.getElementById('__demodsl_app_switcher_style');\n"
            "    if(st) st.remove();\n"
            f"  }}, 350);\n"
            f"}}, {lifetime});\n"
        )
        return js
