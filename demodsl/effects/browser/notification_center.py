"""Notification Center — right slide-in panel with notifications and widgets."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_html_text,
    sanitize_number,
)


_DEFAULT_NOTIFS = [
    {
        "app": "Messages",
        "icon": "💬",
        "title": "Alice",
        "body": "Hey, did you see the new release?",
        "time": "now",
    },
    {
        "app": "Calendar",
        "icon": "📅",
        "title": "Team sync",
        "body": "In 15 minutes · Zoom",
        "time": "9:45 AM",
    },
    {
        "app": "Mail",
        "icon": "✉︎",
        "title": "GitHub",
        "body": "Your PR #42 has been reviewed",
        "time": "8:12 AM",
    },
]


class NotificationCenterEffect(BrowserEffect):
    """Slide-in right panel showing stacked notifications + widgets.

    Params
    ------
    notifications : list[dict]
        Each dict may contain ``app``, ``icon``, ``title``, ``body``, ``time``.
    show_widgets : bool
        Whether to include the Weather / Calendar widgets at the bottom
        (default ``True``).
    duration : float
        Seconds on screen (default ``6.0``).
    """

    effect_id = "notification_center"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 6.0), default=6.0, min_val=1.0, max_val=30.0
        )
        show_widgets = bool(params.get("show_widgets", True))

        notifs_param = params.get("notifications")
        if notifs_param and isinstance(notifs_param, list):
            notifs = []
            for n in notifs_param:
                if isinstance(n, dict):
                    notifs.append(
                        {
                            "app": sanitize_html_text(str(n.get("app", ""))),
                            "icon": sanitize_html_text(str(n.get("icon", "🔔"))),
                            "title": sanitize_html_text(str(n.get("title", ""))),
                            "body": sanitize_html_text(str(n.get("body", ""))),
                            "time": sanitize_html_text(str(n.get("time", "now"))),
                        }
                    )
        else:
            notifs = _DEFAULT_NOTIFS

        notifs_html = ""
        for n in notifs:
            notifs_html += (
                "<div class='__demodsl_nc_card' style='background:"
                "rgba(60,60,65,0.72);backdrop-filter:blur(30px);"
                "-webkit-backdrop-filter:blur(30px);border-radius:14px;"
                "padding:12px 14px;box-shadow:0 4px 16px rgba(0,0,0,0.3),"
                "0 0 0 0.5px rgba(255,255,255,0.12) inset;"
                "font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif'>"
                "<div style='display:flex;align-items:center;gap:8px;"
                "font-size:11px;color:rgba(255,255,255,0.65);"
                "margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px'>"
                f"<span style='font-size:14px'>{n['icon']}</span>"
                f"<span style='flex:1;font-weight:600'>{n['app']}</span>"
                f"<span>{n['time']}</span></div>"
                f"<div style='color:#fff;font-size:13px;font-weight:600;"
                f"margin-bottom:2px'>{n['title']}</div>"
                f"<div style='color:rgba(255,255,255,0.75);font-size:12px;"
                f"line-height:1.3'>{n['body']}</div>"
                "</div>"
            )

        widgets_html = ""
        if show_widgets:
            widgets_html = (
                "<div style='display:flex;gap:10px;margin-top:4px'>"
                # Weather widget
                "<div style='flex:1;background:linear-gradient(145deg,"
                "#4A90E2,#6BB6FF);border-radius:14px;padding:12px;"
                "color:#fff;box-shadow:0 4px 16px rgba(0,0,0,0.25)'>"
                "<div style='font-size:11px;opacity:0.9;text-transform:uppercase;"
                "letter-spacing:0.5px'>Weather</div>"
                "<div style='font-size:28px;font-weight:300;margin-top:4px'>"
                "☀︎ 72°</div>"
                "<div style='font-size:11px;opacity:0.85;margin-top:2px'>"
                "Sunny · Paris</div></div>"
                # Calendar widget
                "<div style='flex:1;background:rgba(60,60,65,0.72);"
                "backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);"
                "border-radius:14px;padding:12px;color:#fff;"
                "box-shadow:0 4px 16px rgba(0,0,0,0.25)'>"
                "<div style='font-size:11px;color:#FF3B30;font-weight:700;"
                "text-transform:uppercase'>Today</div>"
                "<div style='font-size:28px;font-weight:300;margin-top:4px'>"
                "20</div>"
                "<div style='font-size:11px;opacity:0.75;margin-top:2px'>"
                "3 events</div></div>"
                "</div>"
            )

        css = (
            "@keyframes __demodsl_nc_slide_in {"
            "  from { transform: translateX(100%); opacity: 0; }"
            "  to   { transform: translateX(0); opacity: 1; }"
            "}"
            "@keyframes __demodsl_nc_slide_out {"
            "  from { transform: translateX(0); opacity: 1; }"
            "  to   { transform: translateX(100%); opacity: 0; }"
            "}"
        )
        evaluate_js(inject_style("__demodsl_notification_center_style", css))

        lifetime_ms = int(duration * 1000)

        js = iife(f"""
            const old = document.getElementById('__demodsl_notification_center');
            if (old) old.remove();

            const panel = document.createElement('div');
            panel.id = '__demodsl_notification_center';
            panel.style.cssText = 'position:fixed;top:36px;right:8px;bottom:90px;'
                + 'z-index:2147483642;width:340px;padding:10px;'
                + 'display:flex;flex-direction:column;gap:10px;'
                + 'overflow-y:auto;animation:__demodsl_nc_slide_in 0.4s '
                + 'cubic-bezier(0.2, 0.9, 0.3, 1.2);';

            panel.innerHTML = `{notifs_html}` + `{widgets_html}`;

            document.body.appendChild(panel);

            setTimeout(() => {{
                panel.style.animation = '__demodsl_nc_slide_out 0.3s ease-in forwards';
                setTimeout(() => panel.remove(), 320);
            }}, {lifetime_ms});
        """)
        evaluate_js(js)
