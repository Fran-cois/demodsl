"""Control Center — macOS top-right sliding panel (WiFi/Bluetooth/Brightness/…)."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_html_text,
    sanitize_number,
)


class ControlCenterEffect(BrowserEffect):
    """macOS Control Center panel with toggles and sliders.

    Params
    ------
    wifi : bool
        WiFi toggle state (default ``True``).
    wifi_name : str
        WiFi network name shown under the toggle.
    bluetooth : bool
        Bluetooth toggle state (default ``True``).
    airdrop : bool
        AirDrop state (default ``False``).
    focus : bool
        Focus / Do-Not-Disturb state (default ``False``).
    brightness : float
        Slider value ``0.0``-``1.0`` (default ``0.75``).
    volume : float
        Slider value ``0.0``-``1.0`` (default ``0.5``).
    duration : float
        Seconds on screen (default ``5.0``).
    color : str
        Accent color (default ``"#0A84FF"``).
    """

    effect_id = "control_center"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        wifi = bool(params.get("wifi", True))
        wifi_name = sanitize_html_text(str(params.get("wifi_name", "Home-WiFi")))
        bluetooth = bool(params.get("bluetooth", True))
        airdrop = bool(params.get("airdrop", False))
        focus = bool(params.get("focus", False))
        brightness = float(
            sanitize_number(params.get("brightness", 0.75), default=0.75, min_val=0.0, max_val=1.0)
        )
        volume = float(
            sanitize_number(params.get("volume", 0.5), default=0.5, min_val=0.0, max_val=1.0)
        )
        duration = sanitize_number(
            params.get("duration", 5.0), default=5.0, min_val=1.0, max_val=30.0
        )
        color = sanitize_css_color(params.get("color", "#0A84FF"))

        css = (
            "@keyframes __demodsl_cc_in {"
            "  from { opacity:0; transform: translateY(-12px) scale(0.97); }"
            "  to   { opacity:1; transform: translateY(0) scale(1); }"
            "}"
            "#__demodsl_control_center { font-family: -apple-system, "
            "BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif; }"
            ".__demodsl_cc_tile { background:rgba(255,255,255,0.08); "
            "border-radius:12px; padding:10px 12px; display:flex; "
            "align-items:center; gap:10px; }"
            ".__demodsl_cc_tile_on { background: var(--cc-accent); }"
        )
        evaluate_js(inject_style("__demodsl_control_center_style", css))

        def tile(icon: str, label: str, sub: str, on: bool, wide: bool = False) -> str:
            cls = "__demodsl_cc_tile __demodsl_cc_tile_on" if on else "__demodsl_cc_tile"
            width = "100%" if wide else "calc(50% - 4px)"
            bg_circle = "#fff" if on else "rgba(255,255,255,0.15)"
            fg_circle = color if on else "#fff"
            sub_html = (
                f"<div style='font-size:11px;opacity:0.75;margin-top:1px'>{sub}</div>"
                if sub
                else ""
            )
            return (
                f"<div class='{cls}' style='width:{width}'>"
                f"<div style='width:28px;height:28px;border-radius:50%;"
                f"background:{bg_circle};color:{fg_circle};display:flex;"
                f"align-items:center;justify-content:center;font-size:14px;"
                f"flex-shrink:0'>{icon}</div>"
                f"<div style='min-width:0'><div style='font-size:12px;"
                f"font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;"
                f"text-overflow:ellipsis'>{label}</div>{sub_html}</div></div>"
            )

        connectivity = (
            "<div style='display:flex;flex-wrap:wrap;gap:8px;'>"
            f"{tile('📶', 'Wi-Fi', wifi_name if wifi else 'Off', wifi)}"
            f"{tile('🔵', 'Bluetooth', 'On' if bluetooth else 'Off', bluetooth)}"
            f"{tile('✈︎', 'AirDrop', 'Contacts' if airdrop else 'Off', airdrop, wide=True)}"
            "</div>"
        )

        def slider(icon: str, label: str, value: float) -> str:
            pct = int(value * 100)
            return (
                "<div class='__demodsl_cc_tile' style='display:block'>"
                f"<div style='display:flex;align-items:center;gap:8px;"
                f"color:#fff;font-size:12px;font-weight:600;margin-bottom:8px'>"
                f"<span>{icon}</span><span>{label}</span></div>"
                f"<div style='height:24px;background:rgba(255,255,255,0.12);"
                f"border-radius:12px;overflow:hidden;position:relative'>"
                f"<div style='height:100%;width:{pct}%;background:#fff;"
                f"border-radius:12px;transition:width 0.4s ease'></div></div>"
                "</div>"
            )

        focus_tile = tile("🌙", "Focus", "On" if focus else "Off", focus, wide=True)

        lifetime_ms = int(duration * 1000)

        js = iife(f"""
            const old = document.getElementById('__demodsl_control_center');
            if (old) old.remove();

            const panel = document.createElement('div');
            panel.id = '__demodsl_control_center';
            panel.style.cssText = 'position:fixed;top:32px;right:8px;'
                + 'z-index:2147483642;width:312px;padding:12px;'
                + 'background:rgba(40,40,45,0.72);backdrop-filter:blur(40px) saturate(1.8);'
                + '-webkit-backdrop-filter:blur(40px) saturate(1.8);'
                + 'border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,0.45),'
                + '0 0 0 0.5px rgba(255,255,255,0.18) inset;'
                + 'display:flex;flex-direction:column;gap:8px;'
                + 'animation:__demodsl_cc_in 0.25s ease-out;';
            panel.style.setProperty('--cc-accent', {color!r});

            panel.innerHTML = `{connectivity}` + `{focus_tile}`
                + `{slider("☀︎", "Display", brightness)}`
                + `{slider("🔊", "Sound", volume)}`;

            document.body.appendChild(panel);

            setTimeout(() => {{
                panel.style.transition = 'opacity 0.25s, transform 0.25s';
                panel.style.opacity = '0';
                panel.style.transform = 'translateY(-12px) scale(0.97)';
                setTimeout(() => panel.remove(), 280);
            }}, {lifetime_ms});
        """)
        evaluate_js(js)
