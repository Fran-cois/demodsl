"""Spotlight search — macOS ⌘+Space overlay with typing animation and results."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_html_text,
    sanitize_number,
)


_DEFAULT_RESULTS = [
    {"icon": "🔍", "name": "Top Hit", "subtitle": ""},
    {"icon": "📄", "name": "Document.pdf", "subtitle": "Documents"},
    {"icon": "💻", "name": "Visual Studio Code", "subtitle": "Application"},
    {"icon": "🌐", "name": "Search the web", "subtitle": "Safari"},
    {"icon": "📖", "name": "Definition", "subtitle": "Dictionary"},
]


class SpotlightSearchEffect(BrowserEffect):
    """macOS Spotlight overlay with typing animation.

    Params
    ------
    query : str
        Text typed into the search bar (default ``"Visual Studio"``).
    results : list[dict]
        Optional result list with keys ``icon``, ``name``, ``subtitle``.
    typing_speed : float
        Seconds between characters (default ``0.08``).
    highlight : int
        0-based index of highlighted result (default ``0``).
    duration : float
        Total seconds on screen after typing (default ``4.0``).
    color : str
        Accent color (default ``"#0A84FF"``).
    """

    effect_id = "spotlight_search"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        query = sanitize_html_text(str(params.get("query", "Visual Studio")))
        typing_speed = sanitize_number(
            params.get("typing_speed", 0.08), default=0.08, min_val=0.01, max_val=0.5
        )
        highlight = int(
            sanitize_number(
                params.get("highlight", 0), default=0, min_val=-1, max_val=50
            )
        )
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=20.0
        )
        color = sanitize_css_color(params.get("color", "#0A84FF"))

        results_param = params.get("results")
        if results_param and isinstance(results_param, list):
            results = []
            for r in results_param:
                if isinstance(r, dict):
                    results.append(
                        {
                            "icon": sanitize_html_text(str(r.get("icon", "•"))),
                            "name": sanitize_html_text(str(r.get("name", ""))),
                            "subtitle": sanitize_html_text(str(r.get("subtitle", ""))),
                        }
                    )
        else:
            results = _DEFAULT_RESULTS

        results_html = ""
        for idx, r in enumerate(results):
            bg = color if idx == highlight else "transparent"
            fg = "#fff" if idx == highlight else "#e8e8e8"
            sub = (
                f"<div style='font-size:12px;color:rgba(255,255,255,0.55);"
                f"margin-top:2px'>{r['subtitle']}</div>"
                if r["subtitle"]
                else ""
            )
            results_html += (
                f"<div class='__demodsl_sp_row' "
                f"style='display:flex;align-items:center;gap:12px;"
                f"padding:10px 14px;border-radius:8px;background:{bg};"
                f"color:{fg};cursor:default;'>"
                f"<div style='font-size:22px;width:28px;text-align:center'>{r['icon']}</div>"
                f"<div style='flex:1'><div style='font-size:14px;font-weight:500'>"
                f"{r['name']}</div>{sub}</div></div>"
            )

        css = (
            "@keyframes __demodsl_spotlight_in {"
            "  from { opacity:0; transform: translate(-50%, -60%) scale(0.94); }"
            "  to   { opacity:1; transform: translate(-50%, -50%) scale(1); }"
            "}"
            "#__demodsl_spotlight_search { font-family: -apple-system, "
            "BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif; }"
            ".__demodsl_sp_caret { display:inline-block; width:2px; height:28px; "
            "background:#fff; margin-left:3px; vertical-align:middle; "
            "animation: __demodsl_sp_blink 0.9s infinite; }"
            "@keyframes __demodsl_sp_blink { 50% { opacity: 0; } }"
        )
        evaluate_js(inject_style("__demodsl_spotlight_search_style", css))

        lifetime_ms = int(duration * 1000)
        typing_ms = int(typing_speed * 1000)

        js = iife(f"""
            const old = document.getElementById('__demodsl_spotlight_search');
            if (old) old.remove();

            const overlay = document.createElement('div');
            overlay.id = '__demodsl_spotlight_search';
            overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483641;'
                + 'background:rgba(0,0,0,0.25);backdrop-filter:blur(8px);'
                + '-webkit-backdrop-filter:blur(8px);pointer-events:auto;';

            const panel = document.createElement('div');
            panel.style.cssText = 'position:absolute;top:30%;left:50%;'
                + 'transform:translate(-50%, -50%);width:680px;max-width:90vw;'
                + 'background:rgba(40,40,45,0.88);backdrop-filter:blur(40px);'
                + '-webkit-backdrop-filter:blur(40px);border-radius:14px;'
                + 'box-shadow:0 30px 80px rgba(0,0,0,0.55),'
                + '0 0 0 0.5px rgba(255,255,255,0.2) inset;'
                + 'overflow:hidden;animation:__demodsl_spotlight_in 0.22s ease-out;';

            // search bar
            const bar = document.createElement('div');
            bar.style.cssText = 'display:flex;align-items:center;gap:12px;'
                + 'padding:14px 18px;border-bottom:0.5px solid rgba(255,255,255,0.08);';
            bar.innerHTML = '<div style="font-size:22px;opacity:0.6">🔍</div>'
                + '<div id="__demodsl_sp_query" style="flex:1;color:#fff;'
                + 'font-size:22px;font-weight:300;letter-spacing:0.2px">'
                + '<span class="__demodsl_sp_text"></span>'
                + '<span class="__demodsl_sp_caret"></span></div>';
            panel.appendChild(bar);

            // results
            const resultsWrap = document.createElement('div');
            resultsWrap.style.cssText = 'max-height:360px;overflow:hidden;'
                + 'padding:8px 6px;opacity:0;transition:opacity 0.25s;';
            resultsWrap.innerHTML = `{results_html}`;
            panel.appendChild(resultsWrap);

            overlay.appendChild(panel);
            document.body.appendChild(overlay);

            // typing animation
            const target = {query!r};
            const textEl = overlay.querySelector('.__demodsl_sp_text');
            let i = 0;
            const step = () => {{
                if (i <= target.length) {{
                    textEl.textContent = target.slice(0, i);
                    i++;
                    setTimeout(step, {typing_ms});
                }} else {{
                    resultsWrap.style.opacity = '1';
                }}
            }};
            step();

            // cleanup
            setTimeout(() => {{
                overlay.style.transition = 'opacity 0.25s';
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 260);
            }}, {lifetime_ms});

            // dismiss on click outside
            overlay.addEventListener('click', (e) => {{
                if (e.target === overlay) {{
                    overlay.style.opacity = '0';
                    setTimeout(() => overlay.remove(), 200);
                }}
            }});
        """)
        evaluate_js(js)
