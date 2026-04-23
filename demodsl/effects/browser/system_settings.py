"""System Settings — macOS Ventura-style settings window with sidebar."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_html_text,
    sanitize_number,
)


_CATEGORIES = [
    ("👤", "Apple ID", "#0A84FF"),
    ("📶", "Wi-Fi", "#0A84FF"),
    ("🔵", "Bluetooth", "#0A84FF"),
    ("🌐", "Network", "#6B7280"),
    ("🔔", "Notifications", "#EF4444"),
    ("🔊", "Sound", "#EF4444"),
    ("🌙", "Focus", "#8B5CF6"),
    ("⏳", "Screen Time", "#8B5CF6"),
    ("⚙︎", "General", "#6B7280"),
    ("👁", "Appearance", "#3B82F6"),
    ("♿︎", "Accessibility", "#3B82F6"),
    ("🖥", "Displays", "#3B82F6"),
    ("🔋", "Battery", "#22C55E"),
    ("🔐", "Privacy & Security", "#3B82F6"),
]


_DEFAULT_PANELS: dict[str, list[dict[str, Any]]] = {
    "Wi-Fi": [
        {"label": "Wi-Fi", "value": "On", "type": "toggle", "on": True},
        {"label": "Network", "value": "Home-WiFi", "type": "row"},
        {"label": "Ask to join networks", "type": "toggle", "on": True},
        {"label": "Auto-join hotspot", "value": "Ask to Join", "type": "row"},
    ],
    "Appearance": [
        {
            "label": "Appearance",
            "type": "segmented",
            "options": ["Light", "Dark", "Auto"],
            "selected": 1,
        },
        {
            "label": "Accent color",
            "type": "colors",
            "colors": [
                "#6B7280",
                "#EF4444",
                "#F97316",
                "#EAB308",
                "#22C55E",
                "#0A84FF",
                "#8B5CF6",
                "#EC4899",
            ],
            "selected": 5,
        },
        {"label": "Show scroll bars", "value": "When scrolling", "type": "row"},
    ],
    "General": [
        {"label": "About", "value": "MacBook Pro", "type": "row"},
        {"label": "Software Update", "value": "Up to date", "type": "row"},
        {"label": "Storage", "value": "512 GB available", "type": "row"},
        {"label": "AirDrop & Handoff", "type": "row"},
    ],
    "Battery": [
        {"label": "Battery Level", "value": "87%", "type": "row"},
        {"label": "Low Power Mode", "type": "toggle", "on": False},
        {"label": "Optimize video streaming", "type": "toggle", "on": True},
    ],
}


class SystemSettingsEffect(BrowserEffect):
    """macOS Ventura-style System Settings window.

    Params
    ------
    category : str
        Active category name (default ``"Wi-Fi"``).  Must match a sidebar
        label; falls back to ``"General"`` if unknown.
    items : list[dict]
        Override panel contents.  Each dict may be a toggle, row,
        segmented or colors control.
    duration : float
        Seconds on screen (default ``5.0``).
    color : str
        Accent color (default ``"#0A84FF"``).
    """

    effect_id = "system_settings"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        raw_cat = str(params.get("category", "Wi-Fi"))
        category = sanitize_html_text(raw_cat)
        duration = sanitize_number(
            params.get("duration", 5.0), default=5.0, min_val=1.0, max_val=20.0
        )
        color = sanitize_css_color(params.get("color", "#0A84FF"))

        items_param = params.get("items")
        if items_param and isinstance(items_param, list):
            panel_items = items_param
        else:
            panel_items = _DEFAULT_PANELS.get(raw_cat, _DEFAULT_PANELS["General"])

        # Sidebar
        sidebar_html = ""
        for icon, name, col in _CATEGORIES:
            active = name == raw_cat
            bg = f"background:{color};color:#fff" if active else "color:#e8e8e8"
            sidebar_html += (
                "<div class='__demodsl_ss_cat' style='display:flex;align-items:center;"
                f"gap:8px;padding:6px 10px;border-radius:6px;font-size:13px;{bg};"
                "cursor:default'>"
                f"<span style='width:22px;height:22px;background:{col};"
                "border-radius:5px;display:flex;align-items:center;"
                f"justify-content:center;font-size:12px;color:#fff'>{icon}</span>"
                f"<span>{name}</span></div>"
            )

        # Panel content
        panel_html = ""
        for item in panel_items:
            if not isinstance(item, dict):
                continue
            label = sanitize_html_text(str(item.get("label", "")))
            kind = item.get("type", "row")
            if kind == "toggle":
                on = bool(item.get("on", False))
                thumb = "right:2px" if on else "left:2px"
                bg = color if on else "rgba(120,120,128,0.32)"
                panel_html += (
                    "<div class='__demodsl_ss_row' style='display:flex;"
                    "align-items:center;padding:12px 16px;"
                    "border-bottom:0.5px solid rgba(0,0,0,0.08)'>"
                    f"<div style='flex:1;font-size:13px;color:#1d1d1f'>{label}</div>"
                    f"<div style='width:51px;height:31px;background:{bg};"
                    f"border-radius:16px;position:relative'>"
                    f"<div style='position:absolute;top:2px;{thumb};"
                    "width:27px;height:27px;background:#fff;border-radius:50%;"
                    "box-shadow:0 2px 4px rgba(0,0,0,0.2)'></div></div></div>"
                )
            elif kind == "segmented":
                opts = item.get("options", ["Light", "Dark", "Auto"])
                sel = int(item.get("selected", 0))
                segs = ""
                for i, o in enumerate(opts):
                    o_safe = sanitize_html_text(str(o))
                    active_style = (
                        "background:#fff;color:#1d1d1f;"
                        "box-shadow:0 1px 3px rgba(0,0,0,0.12)"
                        if i == sel
                        else "background:transparent;color:#86868b"
                    )
                    segs += (
                        f"<div style='flex:1;padding:5px 12px;text-align:center;"
                        f"font-size:12px;border-radius:6px;{active_style}'>{o_safe}</div>"
                    )
                panel_html += (
                    "<div class='__demodsl_ss_row' style='display:flex;"
                    "align-items:center;padding:12px 16px;"
                    "border-bottom:0.5px solid rgba(0,0,0,0.08)'>"
                    f"<div style='flex:1;font-size:13px;color:#1d1d1f'>{label}</div>"
                    f"<div style='display:flex;background:rgba(120,120,128,0.12);"
                    f"border-radius:8px;padding:2px;gap:2px'>{segs}</div></div>"
                )
            elif kind == "colors":
                cols = item.get("colors", [])
                sel = int(item.get("selected", 0))
                dots = ""
                for i, c in enumerate(cols):
                    c_safe = sanitize_css_color(str(c))
                    ring = (
                        "box-shadow:0 0 0 2px #fff,0 0 0 4px #1d1d1f"
                        if i == sel
                        else "box-shadow:0 0 0 0.5px rgba(0,0,0,0.15)"
                    )
                    dots += (
                        f"<div style='width:20px;height:20px;border-radius:50%;"
                        f"background:{c_safe};{ring};cursor:default'></div>"
                    )
                panel_html += (
                    "<div class='__demodsl_ss_row' style='display:flex;"
                    "align-items:center;padding:12px 16px;"
                    "border-bottom:0.5px solid rgba(0,0,0,0.08)'>"
                    f"<div style='flex:1;font-size:13px;color:#1d1d1f'>{label}</div>"
                    f"<div style='display:flex;gap:8px'>{dots}</div></div>"
                )
            else:  # row
                value = sanitize_html_text(str(item.get("value", "")))
                panel_html += (
                    "<div class='__demodsl_ss_row' style='display:flex;"
                    "align-items:center;padding:12px 16px;"
                    "border-bottom:0.5px solid rgba(0,0,0,0.08)'>"
                    f"<div style='flex:1;font-size:13px;color:#1d1d1f'>{label}</div>"
                    f"<div style='font-size:13px;color:#86868b'>{value}</div>"
                    "<div style='margin-left:8px;color:#c7c7cc;font-size:16px'>›</div>"
                    "</div>"
                )

        css = (
            "@keyframes __demodsl_ss_in {"
            "  from { opacity:0; transform: translate(-50%,-46%) scale(0.96); }"
            "  to   { opacity:1; transform: translate(-50%,-50%) scale(1); }"
            "}"
        )
        evaluate_js(inject_style("__demodsl_system_settings_style", css))

        lifetime_ms = int(duration * 1000)

        js = iife(f"""
            const old = document.getElementById('__demodsl_system_settings');
            if (old) old.remove();

            const win = document.createElement('div');
            win.id = '__demodsl_system_settings';
            win.style.cssText = 'position:fixed;top:50%;left:50%;'
                + 'transform:translate(-50%,-50%);width:820px;height:560px;'
                + 'max-width:92vw;max-height:88vh;z-index:2147483641;'
                + 'background:#fff;border-radius:12px;overflow:hidden;'
                + 'box-shadow:0 30px 80px rgba(0,0,0,0.4);'
                + 'display:grid;grid-template-columns:220px 1fr;'
                + 'font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;'
                + 'animation:__demodsl_ss_in 0.3s cubic-bezier(0.2,0.9,0.3,1.2);';

            // Sidebar
            const sidebar = document.createElement('div');
            sidebar.style.cssText = 'background:rgba(246,246,247,0.85);'
                + 'border-right:0.5px solid rgba(0,0,0,0.1);'
                + 'padding:40px 8px 8px;overflow-y:auto;';
            sidebar.innerHTML = `
                <div style="display:flex;gap:6px;padding:0 10px 12px">
                    <span style="width:12px;height:12px;border-radius:50%;background:#FF5F56"></span>
                    <span style="width:12px;height:12px;border-radius:50%;background:#FFBD2E"></span>
                    <span style="width:12px;height:12px;border-radius:50%;background:#27C93F"></span>
                </div>
                {sidebar_html}
            `;
            win.appendChild(sidebar);

            // Panel
            const panel = document.createElement('div');
            panel.style.cssText = 'padding:40px 0 0;overflow-y:auto;background:#fff;';
            panel.innerHTML = `
                <h1 style="margin:0 24px 20px;font-size:22px;font-weight:700;
                    color:#1d1d1f">{category}</h1>
                <div style="margin:0 24px;background:#fff;border-radius:10px;
                    box-shadow:0 0 0 0.5px rgba(0,0,0,0.08);overflow:hidden">
                    {panel_html}
                </div>
            `;
            win.appendChild(panel);

            document.body.appendChild(win);

            setTimeout(() => {{
                win.style.transition = 'opacity 0.3s, transform 0.3s';
                win.style.opacity = '0';
                win.style.transform = 'translate(-50%,-46%) scale(0.96)';
                setTimeout(() => win.remove(), 320);
            }}, {lifetime_ms});
        """)
        evaluate_js(js)
