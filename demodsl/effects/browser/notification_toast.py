"""Notification toast — system notifications (macOS / Windows style)."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_number


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

        if style == "macos":
            css = self._macos_css(slide_from)
            notifications_js = self._macos_notifications()
            toast_builder = self._macos_toast_builder()
        else:
            css = self._windows_css(slide_from)
            notifications_js = self._windows_notifications()
            toast_builder = self._windows_toast_builder()

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

    # ── macOS Notification Center ─────────────────────────────────

    @staticmethod
    def _macos_css(slide_from: str) -> str:
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
            "  background: rgba(40,40,45,0.82);\n"
            "  backdrop-filter: blur(40px) saturate(180%);\n"
            "  -webkit-backdrop-filter: blur(40px) saturate(180%);\n"
            "  border-radius: 16px;\n"
            "  border: 0.5px solid rgba(255,255,255,0.12);\n"
            "  padding: 12px 14px;\n"
            "  width: 345px;\n"
            "  font-family: -apple-system, 'SF Pro Display', BlinkMacSystemFont, sans-serif;\n"
            "  box-shadow: 0 12px 40px rgba(0,0,0,0.35), 0 0 0 0.5px rgba(255,255,255,0.06);\n"
            "  animation: __demodsl_toast_in 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;\n"
            "  margin-bottom: 8px;\n"
            "  pointer-events: none;\n"
            "  color: #f0f0f0;\n"
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
    def _macos_toast_builder() -> str:
        return (
            "function buildToast(n) {\n"
            "    const toast = document.createElement('div');\n"
            "    toast.className = '__demodsl_toast';\n"
            "    toast.innerHTML = `\n"
            '        <div style="display:flex;align-items:flex-start;gap:10px">\n'
            # App icon (rounded macOS-style square)
            '            <div style="flex-shrink:0;width:34px;height:34px;'
            "border-radius:8px;overflow:hidden;display:flex;align-items:center;"
            'justify-content:center;background:rgba(255,255,255,0.05)">\n'
            '                <div style="transform:scale(2.4);display:flex;'
            'align-items:center;justify-content:center">${n.icon}</div>\n'
            "            </div>\n"
            '            <div style="flex:1;min-width:0">\n'
            # App name + timestamp
            '                <div style="display:flex;align-items:center;'
            'justify-content:space-between;margin-bottom:2px">\n'
            '                    <span style="font-size:12px;font-weight:600;'
            "color:rgba(255,255,255,0.55);text-transform:uppercase;"
            'letter-spacing:0.3px">${n.app}</span>\n'
            '                    <span style="font-size:11px;color:rgba(255,255,255,0.35)">now</span>\n'
            "                </div>\n"
            # Title
            '                <div style="font-size:13px;font-weight:600;'
            "color:#f5f5f5;margin-bottom:1px;white-space:nowrap;overflow:hidden;"
            'text-overflow:ellipsis">${n.title}</div>\n'
            # Body
            '                <div style="font-size:12.5px;color:rgba(255,255,255,0.6);'
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
    def _windows_css(slide_from: str) -> str:
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
            "  background: rgba(44,44,44,0.96);\n"
            "  backdrop-filter: blur(20px);\n"
            "  -webkit-backdrop-filter: blur(20px);\n"
            "  border-radius: 8px;\n"
            "  border: 1px solid rgba(255,255,255,0.08);\n"
            "  padding: 14px 16px 12px 16px;\n"
            "  width: 360px;\n"
            "  font-family: 'Segoe UI Variable', 'Segoe UI', Roboto, sans-serif;\n"
            "  box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(0,0,0,0.18);\n"
            "  animation: __demodsl_toast_in 0.35s cubic-bezier(0.1, 0.9, 0.2, 1) forwards;\n"
            "  margin-bottom: 6px;\n"
            "  pointer-events: none;\n"
            "  color: #e4e4e4;\n"
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
    def _windows_toast_builder() -> str:
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
            '            <span style="font-size:12px;color:rgba(255,255,255,0.5);'
            'font-weight:400">${n.app}</span>\n'
            '            <span style="margin-left:auto;font-size:11px;'
            'color:rgba(255,255,255,0.3)">Just now</span>\n'
            # Close X (decorative)
            '            <svg width="12" height="12" viewBox="0 0 12 12" '
            'style="opacity:0.35;margin-left:4px">'
            '<path d="M3 3l6 6M9 3l-6 6" stroke="white" stroke-width="1.5"/></svg>\n'
            "        </div>\n"
            # Title
            '        <div style="font-size:14px;font-weight:600;color:#f0f0f0;'
            'margin-bottom:4px">${n.title}</div>\n'
            # Body
            '        <div style="font-size:13px;color:rgba(255,255,255,0.6);'
            'line-height:1.4">${n.body}</div>\n'
            # Action buttons row (Windows toast style)
            '        <div style="display:flex;gap:8px;margin-top:10px">\n'
            '            <div style="flex:1;text-align:center;padding:5px 0;'
            "background:rgba(255,255,255,0.06);border-radius:4px;"
            'font-size:12px;color:rgba(255,255,255,0.7)">Dismiss</div>\n'
            '            <div style="flex:1;text-align:center;padding:5px 0;'
            "background:rgba(255,255,255,0.06);border-radius:4px;"
            'font-size:12px;color:rgba(255,255,255,0.7)">Open</div>\n'
            "        </div>\n"
            "    `;\n"
            "    return toast;\n"
            "}\n"
        )
