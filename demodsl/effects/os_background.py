"""OS desktop background overlay — wraps the page in a simulated desktop."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class OsBackgroundOverlay:
    """Injects a desktop OS simulation around the browser viewport.

    When active the viewport content is visually framed inside a window
    sitting on a desktop with wallpaper, a menu bar / taskbar, and a dock.
    The overlay re-injects cleanly after page reloads.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.enabled: bool = config.get("enabled", True)
        self.os: str = config.get("os", "macos")
        self.theme: str = config.get("theme", "dark")
        self.wallpaper_color: str = config.get("wallpaper_color", "#1a1a2e")
        self.window_title: str = config.get("window_title", "Demo App")
        self.show_dock: bool = config.get("show_dock", True)
        self.show_menu_bar: bool = config.get("show_menu_bar", True)
        self.apps: list[dict[str, Any]] | None = config.get("apps")
        self.window: dict[str, Any] | None = config.get("window")
        self.secondary_windows: list[dict[str, Any]] | None = config.get(
            "secondary_windows"
        )

    # ── public API (same signature as CursorOverlay) ──────────────

    def inject(self, evaluate_js: Any) -> None:
        if not self.enabled:
            return
        if self.os == "windows":
            js = self._build_windows_js()
        else:
            js = self._build_macos_js()
        evaluate_js(js)

    # ── helpers: window framing & secondary windows ───────────────

    def _window_body_css(self, default_top: int, default_bottom: int) -> str:
        """CSS rules applied to body to constrain the real browser window.

        When ``self.window`` is set, body is pinned to a fixed rectangle
        (x, y, width, height) with rounded corners and a drop shadow.
        Otherwise returns the default padding rules.
        """
        if not self.window:
            return (
                f" html {{ overflow: hidden !important; height: 100% !important; }}"
                f" body {{ padding-top: {default_top}px !important;"
                f" padding-bottom: {default_bottom}px !important;"
                f" overflow: auto !important; height: 100% !important; }}"
            )
        w = self.window
        x = int(w.get("x", 0))
        y = int(w.get("y", default_top))
        width = w.get("width")
        height = w.get("height")
        # width/height: None = compute via right/bottom offsets
        w_rule = f"width:{int(width)}px !important;" if width else "right:0 !important;"
        h_rule = (
            f"height:{int(height)}px !important;"
            if height
            else f"bottom:{default_bottom}px !important;"
        )
        return (
            f" html {{ overflow: hidden !important; }}"
            f" body {{ position: fixed !important; top:{y}px !important;"
            f" left:{x}px !important; {w_rule} {h_rule}"
            f" margin:0 !important; padding:0 !important;"
            f" overflow:auto !important; border-radius:10px !important;"
            f" box-shadow:0 20px 60px rgba(0,0,0,0.5),"
            f" 0 0 0 0.5px rgba(255,255,255,0.08) !important;"
            f" z-index:99991 !important; }}"
        )

    def _secondary_windows_js(self, is_dark: bool) -> str:
        """Build JS that injects static window mockups as overlays."""
        if not self.secondary_windows:
            return ""
        title_bg = "rgba(40,40,45,0.95)" if is_dark else "rgba(232,232,232,0.95)"
        title_fg = "#e0e0e0" if is_dark else "#333"
        js_parts: list[str] = []
        for idx, sw in enumerate(self.secondary_windows):
            title = (
                str(sw.get("title", "Window"))[:80]
                .replace("'", "\\'")
                .replace("<", "&lt;")
            )
            x = int(sw.get("x", 0))
            y = int(sw.get("y", 0))
            width = int(sw.get("width", 600))
            height = int(sw.get("height", 400))
            bg = str(sw.get("background_color", "#1a1a2e"))
            screenshot = sw.get("screenshot")
            iframe_url = sw.get("url")
            video_path = sw.get("_video_path")
            app_color = str(sw.get("app_color", "#6366f1"))

            content_style = f"background:{bg};"
            content_inner = ""
            if video_path:
                # Blocked URL → fallback to pre-recorded clip embedded as
                # base64 data URL (avoids cross-origin file:// restrictions).
                # Muted + looped + playsinline so it plays silently without
                # conflicting with main demo audio or subtitles.
                try:
                    import base64 as _b64
                    from pathlib import Path as _Path

                    video_bytes = _Path(str(video_path)).read_bytes()
                    video_b64 = _b64.b64encode(video_bytes).decode("ascii")
                    content_inner = (
                        f"<video autoplay muted loop playsinline "
                        f'style="width:100%;height:100%;object-fit:cover;'
                        f'display:block;background:{bg}">'
                        f'<source src="data:video/mp4;base64,{video_b64}" '
                        f'type="video/mp4"></video>'
                    )
                except Exception:
                    # If the file disappeared or can't be read, fall through
                    # to the static-background branch below.
                    video_path = None
            if not content_inner and iframe_url:
                safe_iframe_url = (
                    str(iframe_url).replace("\\", "\\\\").replace('"', "&quot;")
                )
                # Use iframe for live URL — fills content area
                content_inner = (
                    f'<iframe src="{safe_iframe_url}" '
                    f'style="width:100%;height:100%;border:0;display:block;'
                    f'background:{bg};" '
                    f'loading="lazy" referrerpolicy="no-referrer" '
                    f'sandbox="allow-scripts allow-same-origin allow-popups '
                    f'allow-forms"></iframe>'
                )
            elif not content_inner and screenshot:
                safe_url = str(screenshot).replace("\\", "\\\\").replace("'", "\\'")
                content_style = (
                    f"background:{bg} url('{safe_url}') center/cover no-repeat;"
                )

            # Window with traffic lights + title + content area
            js_parts.append(
                f"var _sw{idx} = document.createElement('div');\n"
                f"_sw{idx}.className = '__demodsl_secondary_window';\n"
                f"_sw{idx}.style.cssText = 'position:absolute;"
                f"left:{x}px;top:{y}px;width:{width}px;height:{height}px;"
                f"border-radius:10px;overflow:hidden;z-index:99989;"
                f"box-shadow:0 16px 40px rgba(0,0,0,0.45),"
                f"0 0 0 0.5px rgba(255,255,255,0.08);"
                f"font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
                f"pointer-events:none;';\n"
                f"_sw{idx}.innerHTML = `"
                f'<div style="height:30px;background:{title_bg};'
                f"backdrop-filter:blur(12px);display:flex;align-items:center;"
                f'padding:0 12px;border-bottom:0.5px solid rgba(0,0,0,0.15)">'
                f'<div style="display:flex;gap:6px;margin-right:12px">'
                f'<div style="width:11px;height:11px;border-radius:50%;'
                f'background:#ff5f57"></div>'
                f'<div style="width:11px;height:11px;border-radius:50%;'
                f'background:#febc2e"></div>'
                f'<div style="width:11px;height:11px;border-radius:50%;'
                f'background:#28c840"></div></div>'
                f'<span style="flex:1;text-align:center;font-size:12px;'
                f"font-weight:500;color:{title_fg};opacity:0.85;"
                f'margin-right:50px">{title}</span></div>'
                f'<div style="width:100%;height:calc(100% - 30px);'
                f"{content_style}"
                f'border-top:1px solid {app_color}22;overflow:hidden">'
                f"{content_inner}</div>"
                f"`;\n"
                f"root.appendChild(_sw{idx});\n"
            )
        return "".join(js_parts)

    # ── macOS desktop builder ─────────────────────────────────────

    def _build_macos_js(self) -> str:
        is_dark = self.theme == "dark"
        bar_bg = "rgba(30,30,30,0.85)" if is_dark else "rgba(240,240,240,0.85)"
        bar_fg = "#e0e0e0" if is_dark else "#333"
        dock_bg = "rgba(40,40,50,0.65)" if is_dark else "rgba(220,220,230,0.65)"
        wp = self.wallpaper_color
        title = self.window_title.replace("'", "\\'").replace("<", "&lt;")

        # Menu bar height, title bar height, dock height
        menu_h = 28
        title_h = 38
        dock_h = 58
        dock_icon_size = 40

        content_top = menu_h + title_h
        content_bottom = dock_h + 8 if self.show_dock else 0

        menu_bar_js = ""
        if self.show_menu_bar:
            menu_bar_js = (
                "const menuBar = document.createElement('div');\n"
                f"menuBar.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:{menu_h}px;"
                f"background:{bar_bg};backdrop-filter:blur(20px) saturate(180%);"
                f"-webkit-backdrop-filter:blur(20px) saturate(180%);"
                f"z-index:99995;display:flex;align-items:center;padding:0 12px;"
                f"font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;"
                f"font-weight:500;color:{bar_fg};border-bottom:0.5px solid rgba(255,255,255,0.08);';\n"
                # Apple logo (SVG) + menu items
                "menuBar.innerHTML = `"
                "<svg width='14' height='17' viewBox='0 0 814 1000' style='margin-right:18px;opacity:0.85'>"
                f"<path fill='{bar_fg}' d='M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 "
                "0 148.4 130.3 200.9 134.2 202.2-0.6 3.2-20.7 71.9-68.7 141.9-42.8 62.3-87.5 "
                "124.3-155.5 124.3s-85.5-39.5-164-39.5c-76.5 0-103.7 40.8-165.9 40.8s-105.6-57.8-155.5"
                "-127.4c-58.4-81-105.9-207.6-105.9-328.5 0-193 125.8-295.6 249.4-295.6 65.8 0 "
                "120.5 43.4 161.6 43.4 39.8 0 101.9-46 176.3-46 28.5 0 130.9 2.6 198.3 99.5z "
                "M554.1 159.4c31.1-36.9 53.1-88.1 53.1-139.3 0-7.1-0.6-14.3-1.9-20.1-50.6 "
                "1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 7.8 1.3 15.6 "
                "1.9 18.1 3.2 0.6 8.4 1.3 13.6 1.3 45.4 0 103.7-30.4 135.5-71.3z'/>"
                "</svg>"
                f"<span style='font-weight:700;margin-right:20px'>{title}</span>"
                "<span style='margin-right:16px;opacity:0.7'>File</span>"
                "<span style='margin-right:16px;opacity:0.7'>Edit</span>"
                "<span style='margin-right:16px;opacity:0.7'>View</span>"
                "<span style='margin-right:16px;opacity:0.7'>Window</span>"
                "<span style='margin-right:16px;opacity:0.7'>Help</span>"
                # Right side: clock + wifi + battery
                "<div style='margin-left:auto;display:flex;align-items:center;gap:14px;opacity:0.7'>"
                "<svg width='14' height='14' viewBox='0 0 24 24' fill='none' "
                f"stroke='{bar_fg}' stroke-width='2'><path d='M1 1l22 22M16.72 11.06A10.94 10.94 0 0112.55 "
                "10M5 12.55a10.94 10.94 0 015-3.94m.99 6.36A6 6 0 0112.12 14m-4.24 1.88a6 6 0 "
                "015.66-3.94'/></svg>"
                "<svg width='16' height='10' viewBox='0 0 16 10' fill='none'>"
                f"<rect x='0.5' y='0.5' width='13' height='9' rx='1.5' stroke='{bar_fg}'/>"
                f"<rect x='14' y='3' width='2' height='4' rx='0.5' fill='{bar_fg}' opacity='0.5'/>"
                f"<rect x='2' y='2' width='8' height='6' rx='0.5' fill='{bar_fg}' opacity='0.6'/>"
                "</svg>"
                "<span style='font-size:12px;font-variant-numeric:tabular-nums'>14:32</span>"
                "</div>"
                "`;\n"
                "root.appendChild(menuBar);\n"
            )

        # Title bar with traffic lights — follows the configured window frame
        # when self.window is set, otherwise spans the full viewport width.
        if self.window:
            tb_left = int(self.window.get("x", 0))
            tb_top = max(menu_h, int(self.window.get("y", menu_h)) - title_h)
            tb_width_val = self.window.get("width")
            tb_width = f"{int(tb_width_val)}px" if tb_width_val else "calc(100% - 0px)"
            tb_radius = "border-radius:10px 10px 0 0;"
        else:
            tb_left = 0
            tb_top = menu_h
            tb_width = "100%"
            tb_radius = ""

        title_bar_js = (
            "const titleBar = document.createElement('div');\n"
            f"titleBar.style.cssText = 'position:absolute;top:{tb_top}px;left:{tb_left}px;"
            f"width:{tb_width};"
            f"height:{title_h}px;"
            f"background:{('rgba(40,40,45,0.95)' if is_dark else 'rgba(232,232,232,0.95)')};"
            f"backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);"
            f"z-index:99996;display:flex;align-items:center;padding:0 14px;{tb_radius}"
            f"border-bottom:0.5px solid {('rgba(255,255,255,0.06)' if is_dark else 'rgba(0,0,0,0.1)')};';\n"
            # Traffic lights
            "titleBar.innerHTML = `"
            "<div style='display:flex;gap:8px;margin-right:16px'>"
            "<div style='width:12px;height:12px;border-radius:50%;background:#ff5f57;"
            "box-shadow:inset 0 -1px 1px rgba(0,0,0,0.15)'></div>"
            "<div style='width:12px;height:12px;border-radius:50%;background:#febc2e;"
            "box-shadow:inset 0 -1px 1px rgba(0,0,0,0.15)'></div>"
            "<div style='width:12px;height:12px;border-radius:50%;background:#28c840;"
            "box-shadow:inset 0 -1px 1px rgba(0,0,0,0.15)'></div>"
            "</div>"
            f"<span style='flex:1;text-align:center;font-family:-apple-system,sans-serif;"
            f"font-size:13px;font-weight:500;color:{bar_fg};opacity:0.8;"
            f"margin-right:60px'>{title}</span>"
            "`;\n"
            "root.appendChild(titleBar);\n"
        )

        dock_js = ""
        if self.show_dock:
            # Use custom apps if configured, otherwise fall back to defaults
            if self.apps:
                dock_icons = [
                    (
                        a.get("name", "App")[:20],
                        a.get("color", "#6366f1"),
                        a.get("icon", "M12 2a10 10 0 100 20 10 10 0 000-20z")[:200],
                    )
                    for a in self.apps
                ]
            else:
                dock_icons = [
                    ("Finder", "#2196F3", "M4 4h16v16H4z"),
                    (
                        "Safari",
                        "#3B82F6",
                        "M12 2a10 10 0 100 20 10 10 0 000-20zm0 3l3 7-7 3 3-7z",
                    ),
                    ("Terminal", "#333", "M4 17l6-5-6-5M12 19h8"),
                    (
                        "Code",
                        "#007ACC",
                        "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6z",
                    ),
                    (
                        "Notes",
                        "#FFCA28",
                        "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6M8 13h8M8 17h8",
                    ),
                    (
                        "Music",
                        "#FC3C44",
                        "M9 18V5l12-2v13M9 18a3 3 0 11-6 0 3 3 0 016 0zM21 16a3 3 0 11-6 0 3 3 0 016 0z",
                    ),
                ]
            icons_html = ""
            for name, color, path in dock_icons:
                icons_html += (
                    f"<div style='width:{dock_icon_size}px;height:{dock_icon_size}px;"
                    f"border-radius:10px;background:{('rgba(60,60,70,0.7)' if is_dark else 'rgba(250,250,250,0.8)')};"
                    f"display:flex;align-items:center;justify-content:center;"
                    f"box-shadow:0 2px 6px rgba(0,0,0,0.2),inset 0 0 0 0.5px rgba(255,255,255,0.1);"
                    f"transition:transform 0.15s ease' title='{name}'>"
                    f"<svg width='22' height='22' viewBox='0 0 24 24' fill='none' "
                    f"stroke='{color}' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
                    f"<path d='{path}'/></svg>"
                    "</div>"
                )

            dock_js = (
                "const dock = document.createElement('div');\n"
                f"dock.style.cssText = 'position:absolute;bottom:6px;left:0;right:0;"
                f"width:fit-content;margin:0 auto;height:{dock_h}px;"
                f"padding:4px 10px;display:flex;align-items:center;gap:6px;"
                f"background:{dock_bg};backdrop-filter:blur(30px) saturate(200%);"
                f"-webkit-backdrop-filter:blur(30px) saturate(200%);"
                f"border-radius:18px;z-index:99995;"
                f"border:0.5px solid rgba(255,255,255,0.12);"
                f"box-shadow:0 8px 32px rgba(0,0,0,0.3);';\n"
                f"dock.innerHTML = `{icons_html}`;\n"
                "root.appendChild(dock);\n"
            )

        # Desktop wallpaper
        wallpaper_bg = (
            f"radial-gradient(ellipse at 30% 20%, {wp}dd 0%, {wp} 50%, "
            f"rgba(10,10,20,0.98) 100%)"
            if is_dark
            else f"radial-gradient(ellipse at 30% 20%, {wp} 0%, "
            f"color-mix(in srgb, {wp}, white 30%) 100%)"
        )

        # Opaque masks that hide the page background in the menu-bar,
        # title-bar, and dock regions so the wallpaper gradient shows
        # through cleanly instead of the page's own background.
        top_mask_h = content_top  # menu bar + title bar
        top_mask_js = (
            "const topMask = document.createElement('div');\n"
            f"topMask.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            f"height:{top_mask_h}px;background:{wallpaper_bg};"
            f"z-index:99991;pointer-events:none;';\n"
            "root.appendChild(topMask);\n"
        )
        bottom_mask_js = ""
        if self.show_dock:
            bottom_mask_js = (
                "const botMask = document.createElement('div');\n"
                f"botMask.style.cssText = 'position:fixed;bottom:0;left:0;width:100%;"
                f"height:{content_bottom}px;background:{wallpaper_bg};"
                f"z-index:99991;pointer-events:none;';\n"
                "root.appendChild(botMask);\n"
            )

        # Wrap everything in a container — anchored to <html> so that
        # transforms on <body> (e.g. perspective_tilt) cannot break
        # position:fixed.  A <style> with !important keeps padding
        # resilient across scroll and page-initiated style changes.
        #
        # CRITICAL: we also neutralise transform/perspective/filter on
        # <html> itself — if a page sets any of these on the root
        # element, position:fixed children become relative to that
        # transformed ancestor instead of the viewport, causing the
        # overlay to scroll with the page.
        js = (
            "(function(){\n"
            "if(document.getElementById('__demodsl_os_bg')) return;\n"
            # Style element — more resilient than inline body styles
            "var st = document.createElement('style');\n"
            "st.id = '__demodsl_os_bg_style';\n"
            f"st.textContent = '"
            f"html {{ transform: none !important; perspective: none !important;"
            f" filter: none !important; will-change: auto !important; }}"
            f"{self._window_body_css(content_top, content_bottom)}"
            f" #__demodsl_os_bg, #__demodsl_os_bg * {{"
            f" transform: none !important; filter: none !important; }}"
            f"';\n"
            "document.head.appendChild(st);\n"
            # Root container
            "const root = document.createElement('div');\n"
            "root.id = '__demodsl_os_bg';\n"
            f"root.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;"
            f"z-index:99989;pointer-events:none;';\n"
            # Wallpaper layer
            "const wp = document.createElement('div');\n"
            f"wp.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;"
            f"background:{wallpaper_bg};z-index:99989;pointer-events:none;';\n"
            "root.appendChild(wp);\n"
            # Opaque masks over menu/title-bar and dock areas
            + top_mask_js
            + bottom_mask_js
            + self._secondary_windows_js(is_dark)
            + menu_bar_js
            + title_bar_js
            + dock_js
            +
            # Anchor on <html> — immune to body transforms
            "document.documentElement.appendChild(root);\n"
            "document.body.dataset.__demodsl_os_bg = '1';\n"
            # Safety: if a page-level script re-adds a transform on <html>
            # after our style is injected, position:fixed may break again.
            # A scroll listener detects this and compensates by switching to
            # absolute positioning with manual scroll offset.
            "var _osBgScrollFix = function(){\n"
            "  var r = root.getBoundingClientRect();\n"
            "  if(Math.abs(r.top) > 2){\n"
            "    root.style.position = 'absolute';\n"
            "    root.style.top = (window.scrollY||window.pageYOffset||0) + 'px';\n"
            "  } else if(root.style.position === 'absolute'){\n"
            "    root.style.position = 'fixed';\n"
            "    root.style.top = '0';\n"
            "  }\n"
            "};\n"
            "window.addEventListener('scroll', _osBgScrollFix, {passive:true});\n"
            # MutationObserver: re-inject overlay if removed by page JS / SPA
            "var _osBgObs = new MutationObserver(function(){\n"
            "  if(!document.getElementById('__demodsl_os_bg')){\n"
            "    document.documentElement.appendChild(root);\n"
            "  }\n"
            "  if(!document.getElementById('__demodsl_os_bg_style')){\n"
            "    document.head.appendChild(st);\n"
            "  }\n"
            "});\n"
            "_osBgObs.observe(document.documentElement, {childList:true,subtree:true});\n"
            "})();\n"
        )
        return js

    # ── Windows 11 desktop builder ────────────────────────────────

    def _build_windows_js(self) -> str:
        is_dark = self.theme == "dark"
        taskbar_bg = "rgba(32,32,32,0.92)" if is_dark else "rgba(243,243,243,0.92)"
        taskbar_fg = "#e0e0e0" if is_dark else "#333"
        title_bg = "rgba(32,32,32,0.98)" if is_dark else "rgba(255,255,255,0.98)"
        title_fg = "#e0e0e0" if is_dark else "#1a1a1a"
        wp = self.wallpaper_color
        title = self.window_title.replace("'", "\\'").replace("<", "&lt;")

        title_h = 32
        taskbar_h = 48

        content_top = title_h
        content_bottom = taskbar_h + 4 if self.show_dock else 0

        # Title bar with minimize/maximize/close
        title_bar_js = (
            "const titleBar = document.createElement('div');\n"
            f"titleBar.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:{title_h}px;"
            f"background:{title_bg};z-index:99995;display:flex;align-items:center;"
            f"padding:0 0 0 12px;font-family:Segoe UI Variable,Segoe UI,sans-serif;"
            f"font-size:12px;color:{title_fg};';\n"
            # App icon + title
            "titleBar.innerHTML = `"
            f"<svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='{title_fg}' "
            "stroke-width='2' style='margin-right:8px;opacity:0.7'>"
            "<rect x='3' y='3' width='18' height='18' rx='2'/>"
            "<path d='M3 9h18'/></svg>"
            f"<span style='flex:1;opacity:0.8'>{title}</span>"
            # Window control buttons
            "<div style='display:flex;height:100%;margin-left:auto'>"
            # Minimize
            f"<div style='width:46px;display:flex;align-items:center;justify-content:center'>"
            f"<svg width='10' height='1' viewBox='0 0 10 1'>"
            f"<rect width='10' height='1' fill='{title_fg}' opacity='0.7'/></svg></div>"
            # Maximize
            f"<div style='width:46px;display:flex;align-items:center;justify-content:center'>"
            f"<svg width='10' height='10' viewBox='0 0 10 10' fill='none' "
            f"stroke='{title_fg}' stroke-width='1' opacity='0.7'>"
            "<rect x='0.5' y='0.5' width='9' height='9'/></svg></div>"
            # Close (red on hover implied)
            "<div style='width:46px;display:flex;align-items:center;justify-content:center;"
            "background:transparent'>"
            f"<svg width='10' height='10' viewBox='0 0 10 10' fill='none' "
            f"stroke='{title_fg}' stroke-width='1.2' opacity='0.7'>"
            "<path d='M0 0l10 10M10 0L0 10'/></svg></div>"
            "</div>"
            "`;\n"
            "root.appendChild(titleBar);\n"
        )

        taskbar_js = ""
        if self.show_dock:
            # Use custom apps if configured, otherwise fall back to defaults
            if self.apps:
                taskbar_icons = [
                    (
                        a.get("name", "App")[:20],
                        a.get("color", "#0078D4"),
                        a.get("icon", "M12 2a10 10 0 100 20 10 10 0 000-20z")[:200],
                    )
                    for a in self.apps
                ]
            else:
                taskbar_icons = [
                    (
                        "Start",
                        "#0078D4",
                        "M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z",
                    ),
                    ("Search", "#888", "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"),
                    (
                        "Explorer",
                        "#FFCA28",
                        "M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z",
                    ),
                    ("Edge", "#0078D4", "M12 2a10 10 0 100 20 10 10 0 000-20z"),
                    ("Terminal", "#666", "M4 17l6-5-6-5M12 19h8"),
                    (
                        "Code",
                        "#007ACC",
                        "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6z",
                    ),
                ]
            icons_html = ""
            for name, color, path in taskbar_icons:
                icons_html += (
                    f"<div style='width:36px;height:36px;border-radius:4px;"
                    f"display:flex;align-items:center;justify-content:center;"
                    f"transition:background 0.15s' title='{name}'>"
                    f"<svg width='18' height='18' viewBox='0 0 24 24' fill='none' "
                    f"stroke='{color}' stroke-width='1.8' stroke-linecap='round'>"
                    f"<path d='{path}'/></svg>"
                    "</div>"
                )

            taskbar_js = (
                "const taskbar = document.createElement('div');\n"
                f"taskbar.style.cssText = 'position:absolute;bottom:0;left:0;width:100%;"
                f"height:{taskbar_h}px;background:{taskbar_bg};"
                f"backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);"
                f"z-index:99995;display:flex;align-items:center;justify-content:center;"
                f"gap:4px;border-top:1px solid {('rgba(255,255,255,0.06)' if is_dark else 'rgba(0,0,0,0.08)')};';\n"
                f"taskbar.innerHTML = `{icons_html}`;\n"
                # Clock in bottom-right
                "const clock = document.createElement('div');\n"
                f"clock.style.cssText = 'position:absolute;right:12px;text-align:right;"
                f"font-family:Segoe UI Variable,Segoe UI,sans-serif;font-size:11px;"
                f"color:{taskbar_fg};line-height:1.4';\n"
                "clock.innerHTML = '14:32<br>22/04/2026';\n"
                "taskbar.appendChild(clock);\n"
                "root.appendChild(taskbar);\n"
            )

        wallpaper_bg = (
            f"radial-gradient(ellipse at 50% 40%, {wp}dd 0%, rgba(15,15,30,0.98) 100%)"
            if is_dark
            else f"radial-gradient(ellipse at 50% 40%, {wp} 0%, "
            f"color-mix(in srgb, {wp}, white 20%) 100%)"
        )

        # Opaque masks that hide the page background in the title-bar
        # and taskbar regions so the wallpaper gradient shows through.
        top_mask_js = (
            "const topMask = document.createElement('div');\n"
            f"topMask.style.cssText = 'position:fixed;top:0;left:0;width:100%;"
            f"height:{content_top}px;background:{wallpaper_bg};"
            f"z-index:99991;pointer-events:none;';\n"
            "root.appendChild(topMask);\n"
        )
        bottom_mask_js = ""
        if self.show_dock:
            bottom_mask_js = (
                "const botMask = document.createElement('div');\n"
                f"botMask.style.cssText = 'position:fixed;bottom:0;left:0;width:100%;"
                f"height:{content_bottom}px;background:{wallpaper_bg};"
                f"z-index:99991;pointer-events:none;';\n"
                "root.appendChild(botMask);\n"
            )

        js = (
            "(function(){\n"
            "if(document.getElementById('__demodsl_os_bg')) return;\n"
            # Style element — resilient to scroll and page style overrides.
            # Neutralise html transforms that would break position:fixed.
            "var st = document.createElement('style');\n"
            "st.id = '__demodsl_os_bg_style';\n"
            f"st.textContent = '"
            f"html {{ transform: none !important; perspective: none !important;"
            f" filter: none !important; will-change: auto !important; }}"
            f"{self._window_body_css(content_top, content_bottom)}"
            f" #__demodsl_os_bg, #__demodsl_os_bg * {{"
            f" transform: none !important; filter: none !important; }}"
            f"';\n"
            "document.head.appendChild(st);\n"
            # Root container
            "const root = document.createElement('div');\n"
            "root.id = '__demodsl_os_bg';\n"
            f"root.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;"
            f"z-index:99989;pointer-events:none;';\n"
            "const wp = document.createElement('div');\n"
            f"wp.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;"
            f"background:{wallpaper_bg};z-index:99989;pointer-events:none;';\n"
            "root.appendChild(wp);\n"
            # Opaque masks over title-bar and taskbar areas
            + top_mask_js
            + bottom_mask_js
            + self._secondary_windows_js(is_dark)
            + title_bar_js
            + taskbar_js
            +
            # Anchor on <html> — immune to body transforms
            "document.documentElement.appendChild(root);\n"
            "document.body.dataset.__demodsl_os_bg = '1';\n"
            # Scroll safety net (same as macOS builder)
            "var _osBgScrollFix = function(){\n"
            "  var r = root.getBoundingClientRect();\n"
            "  if(Math.abs(r.top) > 2){\n"
            "    root.style.position = 'absolute';\n"
            "    root.style.top = (window.scrollY||window.pageYOffset||0) + 'px';\n"
            "  } else if(root.style.position === 'absolute'){\n"
            "    root.style.position = 'fixed';\n"
            "    root.style.top = '0';\n"
            "  }\n"
            "};\n"
            "window.addEventListener('scroll', _osBgScrollFix, {passive:true});\n"
            # MutationObserver: re-inject overlay if removed by page JS / SPA
            "var _osBgObs = new MutationObserver(function(){\n"
            "  if(!document.getElementById('__demodsl_os_bg')){\n"
            "    document.documentElement.appendChild(root);\n"
            "  }\n"
            "  if(!document.getElementById('__demodsl_os_bg_style')){\n"
            "    document.head.appendChild(st);\n"
            "  }\n"
            "});\n"
            "_osBgObs.observe(document.documentElement, {childList:true,subtree:true});\n"
            "})();\n"
        )
        return js
