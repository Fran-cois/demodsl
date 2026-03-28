"""Popup card overlay — shows synced text/list cards over the browser page."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Position mapping ──────────────────────────────────────────────────────────

_POSITION_CSS = {
    "bottom-right": "bottom:24px; right:24px;",
    "bottom-left": "bottom:24px; left:24px;",
    "top-right": "top:24px; right:24px;",
    "top-left": "top:24px; left:24px;",
    "bottom-center": "bottom:24px; left:50%; transform:translateX(-50%);",
    "top-center": "top:24px; left:50%; transform:translateX(-50%);",
}

# ── Theme background/text styles ─────────────────────────────────────────────

_THEME_CSS = {
    "glass": (
        "background:rgba(15,15,25,0.75); backdrop-filter:blur(16px) saturate(1.6); "
        "border:1px solid rgba(255,255,255,0.12); color:#e2e8f0;"
    ),
    "dark": ("background:#111827; border:1px solid #1f2937; color:#e5e7eb;"),
    "light": ("background:#ffffff; border:1px solid #e5e7eb; color:#111827;"),
    "gradient": (
        "background:linear-gradient(135deg,rgba(99,102,241,0.9),rgba(168,85,247,0.9)); "
        "border:1px solid rgba(255,255,255,0.15); color:#ffffff;"
    ),
}

# ── Animation keyframes per style ────────────────────────────────────────────

_ENTRANCE_ANIMATION = {
    "slide": "__demodsl_card_slidein 0.4s cubic-bezier(0.22,1,0.36,1) forwards",
    "fade": "__demodsl_card_fadein 0.35s ease-out forwards",
    "scale": "__demodsl_card_scalein 0.35s cubic-bezier(0.22,1,0.36,1) forwards",
}

_EXIT_ANIMATION = {
    "slide": "__demodsl_card_slideout 0.3s ease-in forwards",
    "fade": "__demodsl_card_fadeout 0.3s ease-in forwards",
    "scale": "__demodsl_card_scaleout 0.25s ease-in forwards",
}


class PopupCardOverlay:
    """Manages popup card overlays injected into the browser page.

    Shows a styled card with optional title, body text, and bullet-point
    items list.  Items can be revealed incrementally (one per tick) to
    sync with the narrator enumerating features.

    JS globals injected:

    * ``window.__demodsl_card_show(data)`` — show card with content
    * ``window.__demodsl_card_reveal_next()`` — reveal next list item
    * ``window.__demodsl_card_hide()``     — dismiss card
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.enabled = config.get("enabled", True)
        self.position = config.get("position", "bottom-right")
        self.theme = config.get("theme", "glass")
        self.max_width = config.get("max_width", 420)
        self.animation = config.get("animation", "slide")
        self.accent_color = config.get("accent_color", "#818cf8")
        self.show_icon = config.get("show_icon", True)
        self.show_progress = config.get("show_progress", True)

    # ── Injection ─────────────────────────────────────────────────────────

    def inject(self, evaluate_js: Any) -> None:
        """Inject styles, container div, and JS helpers into the page."""
        if not self.enabled:
            return

        pos_css = _POSITION_CSS.get(self.position, _POSITION_CSS["bottom-right"])
        theme_css = _THEME_CSS.get(self.theme, _THEME_CSS["glass"])
        accent = self.accent_color
        mw = self.max_width

        # Determine slide direction from position for slide animation
        slide_from = (
            "translateY(30px)" if "bottom" in self.position else "translateY(-30px)"
        )
        slide_to = "translateY(0)"
        if "center" in self.position:
            slide_from_full = f"translateX(-50%) {slide_from.split(')')[0]})"
            slide_to_full = "translateX(-50%) translateY(0)"
        else:
            slide_from_full = slide_from
            slide_to_full = slide_to

        evaluate_js(f"""(() => {{
            // Cleanup previous
            document.getElementById('__demodsl_card_container')?.remove();
            document.getElementById('__demodsl_card_style')?.remove();

            const style = document.createElement('style');
            style.id = '__demodsl_card_style';
            style.textContent = `
                @keyframes __demodsl_card_slidein {{
                    0%   {{ opacity:0; transform:{slide_from_full}; }}
                    100% {{ opacity:1; transform:{slide_to_full}; }}
                }}
                @keyframes __demodsl_card_slideout {{
                    0%   {{ opacity:1; transform:{slide_to_full}; }}
                    100% {{ opacity:0; transform:{slide_from_full}; }}
                }}
                @keyframes __demodsl_card_fadein {{
                    0%   {{ opacity:0; }}
                    100% {{ opacity:1; }}
                }}
                @keyframes __demodsl_card_fadeout {{
                    0%   {{ opacity:1; }}
                    100% {{ opacity:0; }}
                }}
                @keyframes __demodsl_card_scalein {{
                    0%   {{ opacity:0; transform:scale(0.85); }}
                    100% {{ opacity:1; transform:scale(1); }}
                }}
                @keyframes __demodsl_card_scaleout {{
                    0%   {{ opacity:1; transform:scale(1); }}
                    100% {{ opacity:0; transform:scale(0.85); }}
                }}
                @keyframes __demodsl_card_progress {{
                    0%   {{ width:0%; }}
                    100% {{ width:100%; }}
                }}
                @keyframes __demodsl_card_item_in {{
                    0%   {{ opacity:0; transform:translateX(-8px); }}
                    100% {{ opacity:1; transform:translateX(0); }}
                }}
                #__demodsl_card_container .card-item {{
                    opacity:0;
                    padding: 6px 0;
                    display: flex;
                    align-items: flex-start;
                    gap: 8px;
                    font-size: 14px;
                    line-height: 1.4;
                }}
                #__demodsl_card_container .card-item.visible {{
                    opacity:1;
                    animation: __demodsl_card_item_in 0.3s ease-out forwards;
                }}
                #__demodsl_card_container .card-item .bullet {{
                    flex-shrink:0;
                    width: 6px; height: 6px;
                    margin-top: 6px;
                    border-radius: 50%;
                    background: {accent};
                }}
            `;
            document.head.appendChild(style);

            const container = document.createElement('div');
            container.id = '__demodsl_card_container';
            container.style.cssText = `
                position:fixed; z-index:199999; pointer-events:none;
                {pos_css}
                max-width:{mw}px;
                {theme_css}
                border-radius: 16px;
                padding: 0;
                box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05);
                opacity:0; display:none;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                overflow:hidden;
            `;
            document.body.appendChild(container);

            let _revealIdx = 0;
            let _totalItems = 0;

            window.__demodsl_card_show = function(data) {{
                _revealIdx = 0;
                let html = '<div style="padding:16px 20px 12px">';

                // Icon + title row
                if (data.title) {{
                    html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">';
                    if (data.icon) {{
                        html += '<span style="font-size:20px">' + data.icon + '</span>';
                    }}
                    html += '<span style="font-weight:600;font-size:15px;letter-spacing:-0.01em">'
                         + data.title + '</span></div>';
                }}

                // Body text
                if (data.body) {{
                    html += '<p style="margin:0 0 8px;font-size:13px;opacity:0.8;line-height:1.5">'
                         + data.body + '</p>';
                }}

                // Items list (hidden initially for progressive reveal)
                if (data.items && data.items.length) {{
                    _totalItems = data.items.length;
                    html += '<div class="card-items-list">';
                    const reveal_all = !data.progressive;
                    for (let i = 0; i < data.items.length; i++) {{
                        const vis = reveal_all ? ' visible' : '';
                        html += '<div class="card-item' + vis + '">'
                             + '<span class="bullet"></span>'
                             + '<span>' + data.items[i] + '</span></div>';
                    }}
                    html += '</div>';
                    if (reveal_all) _revealIdx = _totalItems;
                }} else {{
                    _totalItems = 0;
                }}

                html += '</div>';

                // Progress bar
                if (data.duration && {str(self.show_progress).lower()}) {{
                    html += '<div style="height:3px;background:rgba(255,255,255,0.08);overflow:hidden">'
                        + '<div style="height:100%;background:{accent};'
                        + 'animation:__demodsl_card_progress ' + data.duration + 's linear forwards">'
                        + '</div></div>';
                }}

                container.innerHTML = html;
                container.style.display = 'block';
                container.style.animation = '{_ENTRANCE_ANIMATION[self.animation]}';
            }};

            window.__demodsl_card_reveal_next = function() {{
                const items = container.querySelectorAll('.card-item');
                if (_revealIdx < items.length) {{
                    items[_revealIdx].classList.add('visible');
                    _revealIdx++;
                    return _revealIdx;
                }}
                return -1;
            }};

            window.__demodsl_card_hide = function() {{
                container.style.animation = '{_EXIT_ANIMATION[self.animation]}';
                setTimeout(() => {{
                    container.style.display = 'none';
                    container.style.opacity = '0';
                    container.innerHTML = '';
                }}, 400);
            }};
        }})()""")
        logger.debug("Popup card overlay injected")

    # ── Show / reveal / hide ──────────────────────────────────────────────

    def show(
        self,
        evaluate_js: Any,
        *,
        title: str | None = None,
        body: str | None = None,
        items: list[str] | None = None,
        icon: str | None = None,
        duration: float = 0.0,
        progressive: bool = True,
    ) -> None:
        """Show the card with the given content."""
        if not self.enabled:
            return
        data = {
            "title": title,
            "body": body,
            "items": items or [],
            "icon": icon or ("💡" if self.show_icon else None),
            "duration": duration if duration > 0 else None,
            "progressive": progressive and bool(items),
        }
        evaluate_js(f"window.__demodsl_card_show({json.dumps(data)})")
        time.sleep(0.45)  # wait for entrance animation

    def reveal_next(self, evaluate_js: Any) -> int:
        """Reveal the next list item. Returns the new index, or -1 if done."""
        if not self.enabled:
            return -1
        result = evaluate_js("window.__demodsl_card_reveal_next()")
        time.sleep(0.35)  # let the item animate in
        return int(result) if result is not None else -1

    def hide(self, evaluate_js: Any) -> None:
        """Dismiss the card with the exit animation."""
        if not self.enabled:
            return
        evaluate_js("window.__demodsl_card_hide()")
        time.sleep(0.4)
