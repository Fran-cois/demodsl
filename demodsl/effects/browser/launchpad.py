"""Launchpad — full-screen grid of app icons."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_html_text,
    sanitize_number,
)

_DEFAULT_APPS = [
    ("Safari", "#3B82F6", "🧭"),
    ("Mail", "#0EA5E9", "✉︎"),
    ("Messages", "#22C55E", "💬"),
    ("Maps", "#10B981", "🗺️"),
    ("Photos", "#F97316", "🖼️"),
    ("Calendar", "#EF4444", "📅"),
    ("Notes", "#EAB308", "📝"),
    ("Reminders", "#EC4899", "✓"),
    ("Music", "#F43F5E", "♪"),
    ("TV", "#1F2937", "📺"),
    ("Podcasts", "#8B5CF6", "🎙️"),
    ("News", "#DC2626", "📰"),
    ("Weather", "#06B6D4", "☀︎"),
    ("Calculator", "#111827", "🔢"),
    ("Terminal", "#0F172A", "⌨︎"),
    ("VS Code", "#007ACC", "▣"),
    ("Figma", "#A855F7", "◆"),
    ("Finder", "#2196F3", "🙂"),
    ("Settings", "#6B7280", "⚙︎"),
    ("App Store", "#3B82F6", "A"),
]


class LaunchpadEffect(BrowserEffect):
    """Full-screen grid of app icons (macOS Launchpad).

    Params
    ------
    apps : list[dict]
        List of ``{name, color, icon}`` dicts.  Defaults to 20 macOS apps.
    highlight : int
        0-based index of an app to glow (default ``-1``).
    duration : float
        Seconds on screen (default ``4.0``).
    """

    effect_id = "launchpad"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        highlight = int(
            sanitize_number(params.get("highlight", -1), default=-1, min_val=-1, max_val=50)
        )

        apps_param = params.get("apps")
        if apps_param and isinstance(apps_param, list):
            apps = []
            for a in apps_param:
                if isinstance(a, dict):
                    apps.append(
                        (
                            sanitize_html_text(str(a.get("name", ""))),
                            sanitize_css_color(str(a.get("color", "#444"))),
                            sanitize_html_text(str(a.get("icon", "•"))),
                        )
                    )
        else:
            apps = _DEFAULT_APPS

        tiles_html = ""
        for idx, (name, color, icon) in enumerate(apps):
            delay = idx * 0.025
            glow = (
                "box-shadow:0 0 40px #0A84FF,0 0 0 3px #0A84FF,0 8px 20px rgba(0,0,0,0.5);"
                if idx == highlight
                else "box-shadow:0 8px 20px rgba(0,0,0,0.35);"
            )
            tiles_html += (
                "<div class='__demodsl_lp_app' style='display:flex;"
                "flex-direction:column;align-items:center;gap:8px;"
                f"animation:__demodsl_lp_in 0.35s cubic-bezier(0.2,0.9,0.3,1.3) {delay}s both'>"
                f"<div style='width:72px;height:72px;background:{color};"
                f"border-radius:18px;display:flex;align-items:center;"
                f"justify-content:center;font-size:36px;color:#fff;{glow}'>"
                f"{icon}</div>"
                f"<div style='color:#fff;font-size:12px;font-weight:500;"
                f"text-shadow:0 1px 4px rgba(0,0,0,0.6)'>{name}</div>"
                "</div>"
            )

        css = (
            "@keyframes __demodsl_lp_bg {"
            "  from { opacity: 0; backdrop-filter: blur(0px); }"
            "  to   { opacity: 1; backdrop-filter: blur(40px); }"
            "}"
            "@keyframes __demodsl_lp_in {"
            "  from { opacity: 0; transform: scale(0.6); }"
            "  to   { opacity: 1; transform: scale(1); }"
            "}"
        )
        evaluate_js(inject_style("__demodsl_launchpad_style", css))

        lifetime_ms = int(duration * 1000)

        js = iife(f"""
            const old = document.getElementById('__demodsl_launchpad');
            if (old) old.remove();

            const overlay = document.createElement('div');
            overlay.id = '__demodsl_launchpad';
            overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483641;'
                + 'background:rgba(25,25,30,0.5);'
                + 'backdrop-filter:blur(40px) saturate(1.8);'
                + '-webkit-backdrop-filter:blur(40px) saturate(1.8);'
                + 'animation:__demodsl_lp_bg 0.4s ease-out;'
                + 'padding:60px 90px;display:grid;'
                + 'grid-template-columns:repeat(7, 1fr);gap:32px 24px;'
                + 'align-content:start;justify-content:center;'
                + 'font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;';
            overlay.innerHTML = `{tiles_html}`;
            document.body.appendChild(overlay);

            setTimeout(() => {{
                overlay.style.transition = 'opacity 0.3s';
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 320);
            }}, {lifetime_ms});
        """)
        evaluate_js(js)
