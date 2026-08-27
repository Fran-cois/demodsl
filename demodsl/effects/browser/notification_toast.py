"""Notification toast — system notifications (macOS / Windows style)."""

from __future__ import annotations

from typing import Any

from demodsl.color_utils import mix, readable_ink
from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_html_text,
    sanitize_js_string,
    sanitize_number,
)

# Native macOS/Windows notification chrome, used when no theme surface is given.
_DEFAULT_SURFACE = "#282A2D"
_DEFAULT_INK = "#F0F0F0"


def _safe_text(value: Any, limit: int) -> str:
    """Escape caller text for an HTML fragment nested in a JS string literal."""
    return sanitize_js_string(sanitize_html_text(str(value)))[:limit]


class _Palette:
    """Toast chrome colours derived from the theme's surface/ink tokens."""

    def __init__(self, surface: Any, ink: Any) -> None:
        self.surface = sanitize_css_color(surface) if surface else _DEFAULT_SURFACE
        self.ink = (
            sanitize_css_color(ink)
            if ink
            else (readable_ink(self.surface) if surface else _DEFAULT_INK)
        )
        # Secondary/tertiary text and hairlines are blends toward the surface,
        # so they stay legible on both light and dark themes.
        self.ink_muted = mix(self.ink, self.surface, 0.4)
        self.ink_faint = mix(self.ink, self.surface, 0.62)
        self.border = mix(self.ink, self.surface, 0.86)
        self.icon_well = mix(self.ink, self.surface, 0.92)


class NotificationToastEffect(BrowserEffect):
    effect_id = "notification_toast"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 5.0), default=5.0, min_val=1.5, max_val=15.0
        )
        position = params.get("position", "top-right")
        if position not in ("top-right", "top-left", "bottom-right", "bottom-left"):
            position = "top-right"
        # style param: "macos" (default) or "windows"
        style = params.get("style", "macos")
        if style not in ("macos", "windows"):
            style = "macos"
        lifetime = int(duration * 1000)

        pos_map = {
            "top-right": "top:16px; right:16px;",
            "top-left": "top:16px; left:16px;",
            "bottom-right": "bottom:16px; right:16px;",
            "bottom-left": "bottom:16px; left:16px;",
        }
        pos_css = pos_map[position]
        slide_from = "translateX(120%)" if "right" in position else "translateX(-120%)"

        custom = self._custom_notifications(params.get("notifications"), params.get("color"))
        palette = _Palette(params.get("surface"), params.get("ink"))

        if style == "macos":
            css = self._macos_css(slide_from, palette)
            notifications_js = custom or self._macos_notifications()
            toast_builder = self._macos_toast_builder(palette)
        else:
            css = self._windows_css(slide_from, palette)
            notifications_js = custom or self._windows_notifications()
            toast_builder = self._windows_toast_builder(palette)

        js = (
            inject_style("__demodsl_toast_style", css)
            + "const stack = document.createElement('div');\n"
            "stack.id = '__demodsl_notification_toast';\n"
            f"stack.style.cssText = 'position:fixed; {pos_css} z-index:99999;"
            " display:flex; flex-direction:column; gap:0;';\n"
            "document.body.appendChild(stack);\n"
            + notifications_js
            + toast_builder
            + "const shown = [];\n"
            "notifs.forEach(n => {\n"
            "    setTimeout(() => {\n"
            "        const toast = buildToast(n);\n"
            "        stack.appendChild(toast);\n"
            "        shown.push(toast);\n"
            "        setTimeout(() => {\n"
            "            toast.classList.add('__demodsl_toast_exit');\n"
            "            setTimeout(() => toast.remove(), 400);\n"
            "        }, 2200);\n"
            "    }, n.delay);\n"
            "});\n"
            f"setTimeout(() => {{\n"
            "    stack.remove();\n"
            "    document.getElementById('__demodsl_toast_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))

    # ── Caller-supplied notifications ─────────────────────────────

    @staticmethod
    def _custom_notifications(items: Any, default_color: Any, *, max_items: int = 6) -> str | None:
        """Build the ``notifs`` JS array from caller-supplied dicts.

        Each item accepts ``app``/``title``/``body``/``delay``/``color``. Icons
        are generated (initial on a coloured tile) rather than accepted as raw
        markup, so no caller HTML ever reaches ``innerHTML``.
        """
        if not isinstance(items, list) or not items:
            return None
        fallback = sanitize_css_color(default_color) if default_color else "#0A84FF"
        rows: list[str] = []
        for i, raw in enumerate(items[:max_items]):
            if not isinstance(raw, dict):
                continue
            app = _safe_text(raw.get("app", "Notification"), 40)
            title = _safe_text(raw.get("title", ""), 80)
            body = _safe_text(raw.get("body", ""), 160)
            color = sanitize_css_color(raw.get("color")) if raw.get("color") else fallback
            delay = int(
                sanitize_number(
                    raw.get("delay", 300 + i * 1100), default=300.0, min_val=0.0, max_val=60000.0
                )
            )
            initial = _safe_text(str(raw.get("app", "N")).strip()[:1].upper(), 8)
            icon = (
                '<svg width="14" height="14" viewBox="0 0 24 24">'
                f'<rect width="24" height="24" rx="5" fill="{color}"/>'
                '<text x="12" y="17" text-anchor="middle" fill="white" '
                f'font-size="13" font-weight="bold">{initial}</text>'
                "</svg>"
            )
            rows.append(
                f"  {{app:'{app}', icon:'{icon}', title:'{title}', body:'{body}', delay:{delay}}},"
            )
        if not rows:
            return None
        return "const notifs = [\n" + "\n".join(rows) + "\n];\n"

    # ── macOS Notification Center ─────────────────────────────────

    @staticmethod
    def _macos_css(slide_from: str, palette: _Palette) -> str:
        return (
            "@keyframes __demodsl_toast_in {\n"
            f"  0%   {{ transform: {slide_from}; opacity: 0; }}\n"
            "  60%  { transform: translateX(-3%); opacity: 1; }\n"
            "  80%  { transform: translateX(1%); }\n"
            "  100% { transform: translateX(0); opacity: 1; }\n"
            "}\n"
            "@keyframes __demodsl_toast_out {\n"
            "  0%   { transform: translateX(0); opacity: 1; }\n"
            f"  100% {{ transform: {slide_from}; opacity: 0; }}\n"
            "}\n"
            ".__demodsl_toast {\n"
            f"  background: {palette.surface};\n"
            "  backdrop-filter: blur(40px) saturate(180%);\n"
            "  -webkit-backdrop-filter: blur(40px) saturate(180%);\n"
            "  border-radius: 16px;\n"
            f"  border: 0.5px solid {palette.border};\n"
            "  padding: 12px 14px;\n"
            "  width: 345px;\n"
            "  font-family: -apple-system, 'SF Pro Display', BlinkMacSystemFont, sans-serif;\n"
            "  box-shadow: 0 12px 40px rgba(0,0,0,0.35), 0 0 0 0.5px rgba(255,255,255,0.06);\n"
            "  animation: __demodsl_toast_in 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;\n"
            "  margin-bottom: 8px;\n"
            "  pointer-events: none;\n"
            f"  color: {palette.ink};\n"
            "}\n"
            ".__demodsl_toast_exit {\n"
            "  animation: __demodsl_toast_out 0.3s ease forwards;\n"
            "}\n"
        )

    @staticmethod
    def _macos_notifications() -> str:
        return (
            "const notifs = [\n"
            '  {app:\'Xcode\', icon:\'<svg width="14" height="14" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="5" fill="#1C8CF9"/>'
            '<path d="M7 7l10 10M17 7L7 17" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
            "</svg>',"
            " title:'Build Succeeded', body:'All 42 tests passed in 3.2s.', delay:300},\n"
            '  {app:\'Slack\', icon:\'<svg width="14" height="14" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="5" fill="#4A154B"/>'
            '<g fill="white"><rect x="6" y="10" width="4" height="8" rx="2"/>'
            '<rect x="10" y="6" width="8" height="4" rx="2"/>'
            '<rect x="14" y="10" width="4" height="8" rx="2"/>'
            '<rect x="6" y="14" width="8" height="4" rx="2"/></g></svg>\','
            " title:'#deployments', body:'Sarah: Deploy to prod is green. Ship it!', delay:1200},\n"
            '  {app:\'Calendar\', icon:\'<svg width="14" height="14" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="5" fill="#FF3B30"/>'
            '<text x="12" y="18" text-anchor="middle" fill="white" '
            'font-size="13" font-weight="bold" font-family="-apple-system">22</text>'
            "</svg>',"
            " title:'Sprint Review', body:'In 15 minutes - Google Meet', delay:2400},\n"
            "];\n"
        )

    @staticmethod
    def _macos_toast_builder(palette: _Palette) -> str:
        return (
            "function buildToast(n) {\n"
            "    const toast = document.createElement('div');\n"
            "    toast.className = '__demodsl_toast';\n"
            "    toast.innerHTML = `\n"
            '        <div style="display:flex;align-items:flex-start;gap:10px">\n'
            # App icon (rounded macOS-style square)
            '            <div style="flex-shrink:0;width:34px;height:34px;'
            "border-radius:8px;overflow:hidden;display:flex;align-items:center;"
            f'justify-content:center;background:{palette.icon_well}">\n'
            '                <div style="transform:scale(2.4);display:flex;'
            'align-items:center;justify-content:center">${n.icon}</div>\n'
            "            </div>\n"
            '            <div style="flex:1;min-width:0">\n'
            # App name + timestamp
            '                <div style="display:flex;align-items:center;'
            'justify-content:space-between;margin-bottom:2px">\n'
            '                    <span style="font-size:12px;font-weight:600;'
            f"color:{palette.ink_muted};text-transform:uppercase;"
            'letter-spacing:0.3px">${n.app}</span>\n'
            '                    <span style="font-size:11px;'
            f'color:{palette.ink_faint}">now</span>\n'
            "                </div>\n"
            # Title
            '                <div style="font-size:13px;font-weight:600;'
            f"color:{palette.ink};margin-bottom:1px;white-space:nowrap;overflow:hidden;"
            'text-overflow:ellipsis">${n.title}</div>\n'
            # Body
            f'                <div style="font-size:12.5px;color:{palette.ink_muted};'
            "line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;"
            '-webkit-box-orient:vertical;overflow:hidden">${n.body}</div>\n'
            "            </div>\n"
            "        </div>\n"
            "    `;\n"
            "    return toast;\n"
            "}\n"
        )

    # ── Windows 11 Toast ──────────────────────────────────────────

    @staticmethod
    def _windows_css(slide_from: str, palette: _Palette) -> str:
        return (
            "@keyframes __demodsl_toast_in {\n"
            "  0%   { transform: translateY(-20px); opacity: 0; }\n"
            "  100% { transform: translateY(0); opacity: 1; }\n"
            "}\n"
            "@keyframes __demodsl_toast_out {\n"
            "  0%   { transform: translateY(0); opacity: 1; }\n"
            "  100% { transform: translateY(-20px); opacity: 0; }\n"
            "}\n"
            ".__demodsl_toast {\n"
            f"  background: {palette.surface};\n"
            "  backdrop-filter: blur(20px);\n"
            "  -webkit-backdrop-filter: blur(20px);\n"
            "  border-radius: 8px;\n"
            f"  border: 1px solid {palette.border};\n"
            "  padding: 14px 16px 12px 16px;\n"
            "  width: 360px;\n"
            "  font-family: 'Segoe UI Variable', 'Segoe UI', Roboto, sans-serif;\n"
            "  box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(0,0,0,0.18);\n"
            "  animation: __demodsl_toast_in 0.35s cubic-bezier(0.1, 0.9, 0.2, 1) forwards;\n"
            "  margin-bottom: 6px;\n"
            "  pointer-events: none;\n"
            f"  color: {palette.ink};\n"
            "}\n"
            ".__demodsl_toast_exit {\n"
            "  animation: __demodsl_toast_out 0.25s ease forwards;\n"
            "}\n"
        )

    @staticmethod
    def _windows_notifications() -> str:
        return (
            "const notifs = [\n"
            '  {app:\'Visual Studio Code\', icon:\'<svg width="14" height="14" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="3" fill="#007ACC"/>'
            '<path d="M17 3L8 11l-3-2.5L3 10l5 5 5-5 4 3V3z" fill="white"/>'
            "</svg>',"
            " title:'Build Complete', body:'Terminal process finished with exit code 0.', delay:300},\n"
            '  {app:\'Microsoft Teams\', icon:\'<svg width="14" height="14" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="3" fill="#5B5FC7"/>'
            '<text x="12" y="17" text-anchor="middle" fill="white" '
            'font-size="12" font-weight="bold">T</text>'
            "</svg>',"
            " title:'Sarah - #deployments', body:'Deploy to prod is green. Ship it!', delay:1200},\n"
            '  {app:\'Windows Security\', icon:\'<svg width="14" height="14" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="3" fill="#0078D4"/>'
            '<path d="M12 3L4 7v5c0 4.5 3.4 8.7 8 10 4.6-1.3 8-5.5 8-10V7l-8-4z" '
            'fill="white" opacity="0.9"/>'
            "</svg>',"
            " title:'Scan Complete', body:'No threats found. Device is protected.', delay:2400},\n"
            "];\n"
        )

    @staticmethod
    def _windows_toast_builder(palette: _Palette) -> str:
        return (
            "function buildToast(n) {\n"
            "    const toast = document.createElement('div');\n"
            "    toast.className = '__demodsl_toast';\n"
            "    toast.innerHTML = `\n"
            # Header: app icon + app name + timestamp + close button
            '        <div style="display:flex;align-items:center;gap:8px;'
            'margin-bottom:8px">\n'
            '            <div style="flex-shrink:0;width:16px;height:16px;'
            "border-radius:3px;overflow:hidden;display:flex;align-items:center;"
            'justify-content:center">\n'
            '                <div style="transform:scale(1.14);display:flex;'
            'align-items:center;justify-content:center">${n.icon}</div>\n'
            "            </div>\n"
            f'            <span style="font-size:12px;color:{palette.ink_muted};'
            'font-weight:400">${n.app}</span>\n'
            '            <span style="margin-left:auto;font-size:11px;'
            f'color:{palette.ink_faint}">Just now</span>\n'
            # Close X (decorative)
            '            <svg width="12" height="12" viewBox="0 0 12 12" '
            'style="opacity:0.35;margin-left:4px">'
            f'<path d="M3 3l6 6M9 3l-6 6" stroke="{palette.ink}" stroke-width="1.5"/></svg>\n'
            "        </div>\n"
            # Title
            f'        <div style="font-size:14px;font-weight:600;color:{palette.ink};'
            'margin-bottom:4px">${n.title}</div>\n'
            # Body
            f'        <div style="font-size:13px;color:{palette.ink_muted};'
            'line-height:1.4">${n.body}</div>\n'
            # Action buttons row (Windows toast style)
            '        <div style="display:flex;gap:8px;margin-top:10px">\n'
            '            <div style="flex:1;text-align:center;padding:5px 0;'
            f"background:{palette.icon_well};border-radius:4px;"
            f'font-size:12px;color:{palette.ink_muted}">Dismiss</div>\n'
            '            <div style="flex:1;text-align:center;padding:5px 0;'
            f"background:{palette.icon_well};border-radius:4px;"
            f'font-size:12px;color:{palette.ink_muted}">Open</div>\n'
            "        </div>\n"
            "    `;\n"
            "    return toast;\n"
            "}\n"
        )
