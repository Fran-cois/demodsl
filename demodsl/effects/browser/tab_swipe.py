"""Tab swipe — horizontal tab switching with swipe animation."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class TabSwipeEffect(BrowserEffect):
    effect_id = "tab_swipe"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.5, max_val=15.0
        )
        direction = params.get("direction", "left")
        if direction not in ("left", "right"):
            direction = "left"
        lifetime = int(duration * 1000)

        css = (
            ".__demodsl_tab_panel {\n"
            "  position:fixed; top:0; width:100%; height:100%;\n"
            "  z-index:99998; pointer-events:none;\n"
            "  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);\n"
            "}\n"
        )

        # The "other tab" overlay that slides in from the side
        js = (
            inject_style("__demodsl_tab_style", css)
            # Create the incoming "tab" panel
            + "const panel = document.createElement('div');\n"
            "panel.id = '__demodsl_tab_swipe';\n"
            "panel.className = '__demodsl_tab_panel';\n"
        )

        side = "left:100%" if direction == "left" else "right:100%"
        slide_to = "translateX(-100%)" if direction == "left" else "translateX(100%)"

        js += (
            f"panel.style.cssText = panel.style.cssText + '{side};';\n"
            "panel.style.background = 'rgba(20,20,30,0.96)';\n"
            # Content for the "other tab"
            "panel.innerHTML = `\n"
            "    <div style='display:flex;flex-direction:column;align-items:center;"
            "justify-content:center;height:100%;gap:20px'>\n"
            f"        <svg width='48' height='48' viewBox='0 0 24 24' fill='{color}'>\n"
            "            <path d='M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z'/>\n"
            "        </svg>\n"
            f"        <div style='color:#e2e8f0;font-size:18px;font-weight:600'>Dashboard View</div>\n"
            f"        <div style='color:#94a3b8;font-size:13px'>Analytics &amp; Metrics</div>\n"
            "    </div>\n"
            "`;\n"
            "document.body.appendChild(panel);\n"
            # Tab indicator bar
            "const tabBar = document.createElement('div');\n"
            "tabBar.style.cssText = `\n"
            "    position:fixed; bottom:0; left:0; width:100%; height:44px;\n"
            "    z-index:99999; pointer-events:none;\n"
            "    background:rgba(20,20,30,0.95); display:flex;\n"
            "    align-items:center; justify-content:center; gap:32px;\n"
            "    border-top:1px solid rgba(255,255,255,0.08);\n"
            "`;\n"
            "const tabs = ['Home', 'Dashboard', 'Settings'];\n"
            "let activeTab = 0;\n"
            "tabs.forEach((t, i) => {\n"
            "    const tab = document.createElement('div');\n"
            f"    tab.style.cssText = 'font-size:13px;font-weight:600;color:' + "
            f"(i === 0 ? '{color}' : '#64748b') + ';transition:color 0.3s';\n"
            "    tab.textContent = t;\n"
            "    tab.id = '__demodsl_tab_' + i;\n"
            "    tabBar.appendChild(tab);\n"
            "});\n"
            "document.body.appendChild(tabBar);\n"
            # Animate swipe in
            f"setTimeout(() => {{\n"
            f"    panel.style.transform = '{slide_to}';\n"
            # Update tab indicator
            "    const t0 = document.getElementById('__demodsl_tab_0');\n"
            "    const t1 = document.getElementById('__demodsl_tab_1');\n"
            "    if (t0) t0.style.color = '#64748b';\n"
            f"    if (t1) t1.style.color = '{color}';\n"
            "    activeTab = 1;\n"
            f"}}, {int(lifetime * 0.2)});\n"
            # Swipe back
            f"setTimeout(() => {{\n"
            "    panel.style.transform = '';\n"
            "    const t0 = document.getElementById('__demodsl_tab_0');\n"
            "    const t1 = document.getElementById('__demodsl_tab_1');\n"
            f"    if (t0) t0.style.color = '{color}';\n"
            "    if (t1) t1.style.color = '#64748b';\n"
            f"}}, {int(lifetime * 0.6)});\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    panel.remove(); tabBar.remove();\n"
            "    document.getElementById('__demodsl_tab_style')?.remove();\n"
            f"}}, {lifetime});\n"
        )
        evaluate_js(iife(js))
