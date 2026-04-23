"""Mission Control — tiled window overview with swoosh-in animation."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_html_text, sanitize_number


_DEFAULT_WINDOWS = [
    {"title": "Safari — demodsl.dev", "color": "#3B82F6"},
    {"title": "VS Code — main.py", "color": "#007ACC"},
    {"title": "Terminal", "color": "#1e1e1e"},
    {"title": "Finder — Documents", "color": "#6BB6FF"},
    {"title": "Messages", "color": "#22C55E"},
    {"title": "Calendar", "color": "#EF4444"},
]


class MissionControlEffect(BrowserEffect):
    """Tile all windows in a grid (macOS Mission Control).

    Params
    ------
    windows : list[dict]
        List of ``{title, color, thumbnail}`` dicts.
    highlight : int
        0-based index of focused window (default ``0``).
    duration : float
        Seconds on screen (default ``4.0``).
    """

    effect_id = "mission_control"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        highlight = int(
            sanitize_number(
                params.get("highlight", 0), default=0, min_val=-1, max_val=50
            )
        )

        wins_param = params.get("windows")
        if wins_param and isinstance(wins_param, list):
            windows = []
            for w in wins_param:
                if isinstance(w, dict):
                    windows.append(
                        {
                            "title": sanitize_html_text(str(w.get("title", ""))),
                            "color": sanitize_html_text(str(w.get("color", "#2d2d2d"))),
                        }
                    )
        else:
            windows = _DEFAULT_WINDOWS

        tiles_html = ""
        for idx, w in enumerate(windows):
            ring = (
                "0 0 0 3px #0A84FF"
                if idx == highlight
                else "0 0 0 0.5px rgba(255,255,255,0.2)"
            )
            delay = idx * 0.04
            tiles_html += (
                "<div class='__demodsl_mc_tile' style='position:relative;"
                f"background:{w['color']};border-radius:10px;"
                "overflow:hidden;aspect-ratio:16/10;"
                f"box-shadow:{ring}, 0 12px 32px rgba(0,0,0,0.45);"
                f"animation:__demodsl_mc_pop 0.45s cubic-bezier(0.2,0.9,0.3,1.2) {delay}s both;"
                "cursor:default'>"
                "<div style='height:24px;background:rgba(0,0,0,0.35);"
                "display:flex;align-items:center;padding:0 8px;gap:6px'>"
                "<span style='width:9px;height:9px;border-radius:50%;background:#FF5F56'></span>"
                "<span style='width:9px;height:9px;border-radius:50%;background:#FFBD2E'></span>"
                "<span style='width:9px;height:9px;border-radius:50%;background:#27C93F'></span>"
                f"<span style='flex:1;text-align:center;color:rgba(255,255,255,0.8);"
                f"font-size:10px;font-weight:500;text-overflow:ellipsis;overflow:hidden;"
                f"white-space:nowrap'>{w['title']}</span></div>"
                "<div style='flex:1;background:linear-gradient(135deg,"
                "rgba(255,255,255,0.08),rgba(0,0,0,0.2))'></div>"
                "</div>"
            )

        css = (
            "@keyframes __demodsl_mc_fade_in {"
            "  from { opacity: 0; backdrop-filter: blur(0px); }"
            "  to   { opacity: 1; backdrop-filter: blur(30px); }"
            "}"
            "@keyframes __demodsl_mc_pop {"
            "  from { opacity: 0; transform: scale(0.7) translateY(40px); }"
            "  to   { opacity: 1; transform: scale(1) translateY(0); }"
            "}"
        )
        evaluate_js(inject_style("__demodsl_mission_control_style", css))

        lifetime_ms = int(duration * 1000)

        js = iife(f"""
            const old = document.getElementById('__demodsl_mission_control');
            if (old) old.remove();

            const overlay = document.createElement('div');
            overlay.id = '__demodsl_mission_control';
            overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483641;'
                + 'background:rgba(20,20,25,0.72);'
                + 'backdrop-filter:blur(30px) saturate(1.6);'
                + '-webkit-backdrop-filter:blur(30px) saturate(1.6);'
                + 'animation:__demodsl_mc_fade_in 0.35s ease-out;'
                + 'padding:60px 80px;display:grid;'
                + 'grid-template-columns:repeat(3, 1fr);gap:24px;'
                + 'align-content:center;font-family:-apple-system,'
                + 'BlinkMacSystemFont,system-ui,sans-serif;';
            overlay.innerHTML = `{tiles_html}`;
            document.body.appendChild(overlay);

            setTimeout(() => {{
                overlay.style.transition = 'opacity 0.3s';
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 320);
            }}, {lifetime_ms});
        """)
        evaluate_js(js)
