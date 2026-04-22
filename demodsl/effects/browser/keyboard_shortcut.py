"""Keyboard shortcut effect — animated keycap display overlay."""

from __future__ import annotations

import html
from typing import Any

from demodsl.effects.js_builder import auto_remove_multi, inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_css_position,
    sanitize_number,
)


class KeyboardShortcutEffect(BrowserEffect):
    effect_id = "keyboard_shortcut"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        keys_raw = params.get("text") or params.get("keys", "⌘+S")
        # Sanitise — escape HTML to prevent injection
        keys_str = html.escape(str(keys_raw))
        keys = [k.strip() for k in keys_str.split("+") if k.strip()]

        color = sanitize_css_color(params.get("color", "#FFFFFF"))
        bg = sanitize_css_color(params.get("background", "#1e1e2e"))
        accent = sanitize_css_color(params.get("accent", "#6366f1"))
        position = sanitize_css_position(
            params.get("position", "center"),
            allowed=frozenset(
                {
                    "center",
                    "top",
                    "bottom",
                    "top-right",
                    "top-left",
                    "bottom-right",
                    "bottom-left",
                }
            ),
        )
        size = int(
            sanitize_number(params.get("size", 56), default=56, min_val=20, max_val=120)
        )
        duration = sanitize_number(
            params.get("duration", 2.0), default=2.0, min_val=0.5, max_val=10.0
        )
        lifetime = int(duration * 1000)

        pos_map = {
            "center": "top:50%;left:50%;transform:translate(-50%,-50%)",
            "top": "top:80px;left:50%;transform:translateX(-50%)",
            "bottom": "bottom:80px;left:50%;transform:translateX(-50%)",
            "top-right": "top:40px;right:40px",
            "top-left": "top:40px;left:40px",
            "bottom-right": "bottom:40px;right:40px",
            "bottom-left": "bottom:40px;left:40px",
        }
        pos_css = pos_map.get(position, pos_map["center"])

        # Build individual key cap HTML
        key_html_parts = []
        for i, key in enumerate(keys):
            key_html_parts.append(
                f'<span class="__demodsl_kbd_key" style="animation-delay:{i * 0.12}s">{key}</span>'
            )
            if i < len(keys) - 1:
                key_html_parts.append('<span class="__demodsl_kbd_plus">+</span>')
        keys_html = "".join(key_html_parts)

        css = (
            f".demodsl-kbd-container {{"
            f"  display:inline-flex; align-items:center; gap:8px;"
            f"  padding:16px 28px; border-radius:16px;"
            f"  background:{bg}ee; backdrop-filter:blur(12px);"
            f"  box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.08);"
            f"  animation: demodsl-kbd-appear 0.4s cubic-bezier(.34,1.56,.64,1) forwards,"
            f"             demodsl-kbd-fade {duration}s ease forwards;"
            f"}}"
            f".__demodsl_kbd_key {{"
            f"  display:inline-flex; align-items:center; justify-content:center;"
            f"  min-width:{size}px; height:{size}px; padding:0 14px;"
            f"  border-radius:10px; font-size:{int(size * 0.45)}px;"
            f"  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',system-ui,sans-serif;"
            f"  font-weight:600; color:{color}; letter-spacing:0.5px;"
            f"  background: linear-gradient(180deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.03) 100%),"
            f"              {bg};"
            f"  border: 1px solid rgba(255,255,255,0.15);"
            f"  border-bottom: 3px solid rgba(0,0,0,0.3);"
            f"  box-shadow: 0 2px 8px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1);"
            f"  animation: demodsl-kbd-press 0.3s ease forwards;"
            f"  transform: translateY(0);"
            f"}}"
            f".__demodsl_kbd_plus {{"
            f"  font-size:{int(size * 0.35)}px; color:{accent}; font-weight:700;"
            f"  font-family:monospace; opacity:0.8;"
            f"}}"
            f"@keyframes demodsl-kbd-appear {{"
            f"  0% {{ opacity:0; transform:{{}};scale:0.7; }}"
            f"  100% {{ opacity:1; transform:{{}};scale:1; }}"
            f"}}"
            f"@keyframes demodsl-kbd-press {{"
            f"  0% {{ transform:translateY(-8px);opacity:0; }}"
            f"  50% {{ transform:translateY(2px); }}"
            f"  100% {{ transform:translateY(0);opacity:1; }}"
            f"}}"
            f"@keyframes demodsl-kbd-fade {{"
            f"  0%,75% {{ opacity:1; }}"
            f"  100% {{ opacity:0; }}"
            f"}}"
        )

        # Fix the CSS transform in @keyframes for center position
        if position == "center":
            css = css.replace(
                "transform:{};scale",
                "transform:translate(-50%,-50%) scale",
            )
        else:
            css = css.replace("transform:{};scale", "transform:scale")

        js = (
            "const container = document.createElement('div');\n"
            "container.id = '__demodsl_keyboard_shortcut';\n"
            f"container.style.cssText = 'position:fixed;{pos_css};z-index:99999;pointer-events:none;';\n"
            f"container.innerHTML = '<div class=\"demodsl-kbd-container\">{keys_html}</div>';\n"
            + inject_style("__demodsl_keyboard_shortcut_style", css)
            + "document.body.appendChild(container);\n"
            + auto_remove_multi([("container", lifetime), ("style", lifetime)])
        )
        evaluate_js(iife(js))
