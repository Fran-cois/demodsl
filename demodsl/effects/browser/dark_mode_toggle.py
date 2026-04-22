"""Dark mode toggle — animated light/dark mode switch with smooth transition."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import auto_remove_multi, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class DarkModeToggleEffect(BrowserEffect):
    effect_id = "dark_mode_toggle"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#1e1e2e"))
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=1.0, max_val=10.0
        )
        # Position for the expanding circle origin
        target_x = sanitize_number(
            params.get("target_x", 0.9), default=0.9, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.05), default=0.05, min_val=0.0, max_val=1.0
        )

        lifetime = int(duration * 1000)
        hold_ms = max(100, lifetime - 1200)  # expand 600ms + hold + contract 600ms

        cx_pct = target_x * 100
        cy_pct = target_y * 100

        js = (
            # Toggle button icon (SVG moon, no emoji — avoids headless Chrome crash)
            "const toggle = document.createElement('div');\n"
            "toggle.id = '__demodsl_dark_toggle';\n"
            f"toggle.style.cssText = `\n"
            f"    position:fixed; z-index:100000; pointer-events:none;\n"
            f"    top:{int(target_y * 100)}vh; left:{int(target_x * 100)}vw;\n"
            f"    width:40px; height:40px; border-radius:50%;\n"
            f"    background:#fff; border:2px solid rgba(0,0,0,0.1);\n"
            f"    display:flex; align-items:center; justify-content:center;\n"
            f"    font-size:18px; font-weight:bold; color:#f59e0b;\n"
            f"    transform:translate(-50%,-50%) scale(0);\n"
            f"    transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1),\n"
            f"               background 0.3s ease, border-color 0.3s ease, color 0.3s ease;\n"
            f"    box-shadow: 0 2px 12px rgba(0,0,0,0.15);\n"
            "`;\n"
            'toggle.innerHTML = \'<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 0 1-4.4 2.26'
            " 5.403 5.403 0 0 1-3.14-9.8A9 9 0 0 0 12 3z\"/></svg>';\n"
            "document.body.appendChild(toggle);\n"
            # Full-screen dark overlay using clip-path circle
            "const overlay = document.createElement('div');\n"
            "overlay.id = '__demodsl_dark_overlay';\n"
            "overlay.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99999; pointer-events:none;\n"
            f"    background: {color}; opacity:0.88;\n"
            f"    clip-path: circle(0% at {cx_pct}% {cy_pct}%);\n"
            "    transition: clip-path 0.6s cubic-bezier(0.4,0,0.2,1),\n"
            "               opacity 0.4s ease;\n"
            "`;\n"
            "document.body.appendChild(overlay);\n"
            # Phase 1: toggle pops in
            "requestAnimationFrame(() => {\n"
            "    toggle.style.transform = 'translate(-50%,-50%) scale(1) rotate(0deg)';\n"
            "});\n"
            # Phase 2: expand dark circle + switch to sun icon
            "setTimeout(() => {\n"
            '    toggle.innerHTML = \'<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">'
            '<circle cx="12" cy="12" r="5"/>'
            '<path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42'
            'M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"'
            ' stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>\';\n'
            "    toggle.style.transform = 'translate(-50%,-50%) scale(1) rotate(180deg)';\n"
            "    toggle.style.background = '#1e1e2e';\n"
            "    toggle.style.borderColor = 'rgba(255,255,255,0.2)';\n"
            "    toggle.style.color = '#fbbf24';\n"
            f"    overlay.style.clipPath = 'circle(150% at {cx_pct}% {cy_pct}%)';\n"
            "}, 300);\n"
            # Phase 3: revert
            f"setTimeout(() => {{\n"
            "    overlay.style.opacity = '0';\n"
            '    toggle.innerHTML = \'<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 0 1-4.4 2.26'
            " 5.403 5.403 0 0 1-3.14-9.8A9 9 0 0 0 12 3z\"/></svg>';\n"
            "    toggle.style.background = '#fff';\n"
            "    toggle.style.borderColor = 'rgba(0,0,0,0.1)';\n"
            "    toggle.style.color = '#f59e0b';\n"
            "    toggle.style.transform = 'translate(-50%,-50%) scale(0) rotate(360deg)';\n"
            f"}}, {300 + hold_ms});\n"
            # Cleanup
            + auto_remove_multi(
                [
                    ("toggle", lifetime),
                    ("overlay", lifetime),
                ]
            )
        )
        evaluate_js(iife(js))
