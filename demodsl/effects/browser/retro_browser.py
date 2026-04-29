"""Retro browser chrome — overlay a classic browser UI (IE6, Firefox 3, Netscape)."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_html_text, sanitize_number


class RetroBrowserEffect(BrowserEffect):
    effect_id = "retro_browser"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        browser_name = params.get("text", "ie6")
        if browser_name not in ("ie6", "firefox", "netscape"):
            browser_name = "ie6"
        fake_url = sanitize_html_text(params.get("url", "http://www.example.com"))
        duration = sanitize_number(
            params.get("duration", 8.0), default=8.0, min_val=1.0, max_val=30.0
        )
        lifetime = int(duration * 1000)

        configs = {
            "ie6": {
                "title_bg": "#0054E3",
                "title_text": "#fff",
                "toolbar_bg": "#ECE9D8",
                "toolbar_border": "#ACA899",
                "address_bg": "#fff",
                "btn_text": "Go",
                "title_label": "Microsoft Internet Explorer",
                "icon": "e",
                "status_text": "Done",
                "menu": "File  Edit  View  Favorites  Tools  Help",
            },
            "firefox": {
                "title_bg": "#3B3B3B",
                "title_text": "#fff",
                "toolbar_bg": "#E8E6DF",
                "toolbar_border": "#B4B2A8",
                "address_bg": "#fff",
                "btn_text": "▶",
                "title_label": "Mozilla Firefox",
                "icon": "🦊",
                "status_text": "Done",
                "menu": "File  Edit  View  History  Bookmarks  Tools  Help",
            },
            "netscape": {
                "title_bg": "#6E6E6E",
                "title_text": "#fff",
                "toolbar_bg": "#C0C0C0",
                "toolbar_border": "#808080",
                "address_bg": "#fff",
                "btn_text": "Go",
                "title_label": "Netscape Navigator",
                "icon": "N",
                "status_text": "Document: Done",
                "menu": "File  Edit  View  Go  Communicator  Help",
            },
        }
        cfg = configs[browser_name]

        css = f"""
.__retro_browser {{
  position: fixed; inset: 0; z-index: 2147483646;
  pointer-events: none;
  animation: __retro_fadein 0.3s ease;
}}
.__retro_titlebar {{
  height: 28px; background: {cfg["title_bg"]};
  display: flex; align-items: center; padding: 0 8px;
  font: bold 12px "Tahoma", "MS Sans Serif", sans-serif;
  color: {cfg["title_text"]};
}}
.__retro_titlebar_btns {{
  margin-left: auto; display: flex; gap: 2px;
}}
.__retro_titlebar_btns span {{
  width: 18px; height: 16px; background: {cfg["toolbar_bg"]};
  border: 1px outset {cfg["toolbar_border"]};
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: #000; cursor: default;
}}
.__retro_menubar {{
  height: 22px; background: {cfg["toolbar_bg"]};
  border-bottom: 1px solid {cfg["toolbar_border"]};
  display: flex; align-items: center; padding: 0 6px;
  font: 12px "Tahoma", "MS Sans Serif", sans-serif;
  color: #000;
}}
.__retro_toolbar {{
  height: 34px; background: {cfg["toolbar_bg"]};
  border-bottom: 1px solid {cfg["toolbar_border"]};
  display: flex; align-items: center; padding: 0 6px; gap: 4px;
}}
.__retro_addressbar {{
  flex: 1; height: 22px; background: {cfg["address_bg"]};
  border: 1px inset {cfg["toolbar_border"]};
  display: flex; align-items: center; padding: 0 4px;
  font: 12px "Tahoma", "MS Sans Serif", sans-serif;
  color: #000;
}}
.__retro_go_btn {{
  height: 22px; padding: 0 8px; background: {cfg["toolbar_bg"]};
  border: 1px outset {cfg["toolbar_border"]};
  font: 12px "Tahoma", "MS Sans Serif", sans-serif;
  cursor: default;
}}
.__retro_statusbar {{
  position: fixed; bottom: 0; left: 0; right: 0;
  height: 22px; background: {cfg["toolbar_bg"]};
  border-top: 1px solid {cfg["toolbar_border"]};
  display: flex; align-items: center; padding: 0 8px;
  font: 12px "Tahoma", "MS Sans Serif", sans-serif;
  color: #000; z-index: 2147483646;
}}
@keyframes __retro_fadein {{
  from {{ opacity: 0; }} to {{ opacity: 1; }}
}}
"""
        html = f"""
<div class="__retro_browser" id="__retro_browser">
  <div class="__retro_titlebar">
    <span style="margin-right:6px">{cfg["icon"]}</span>
    <span>{cfg["title_label"]}</span>
    <div class="__retro_titlebar_btns">
      <span>_</span><span>□</span><span>×</span>
    </div>
  </div>
  <div class="__retro_menubar">{cfg["menu"]}</div>
  <div class="__retro_toolbar">
    <span style="font-size:11px">Address</span>
    <div class="__retro_addressbar">{fake_url}</div>
    <button class="__retro_go_btn">{cfg["btn_text"]}</button>
  </div>
</div>
<div class="__retro_statusbar" id="__retro_statusbar">{cfg["status_text"]}</div>
"""

        js = inject_style("__retro_browser_style", css) + iife(f"""
var d=document.createElement('div');
d.innerHTML={repr(html)};
document.body.appendChild(d);
setTimeout(function(){{
  var el=document.getElementById('__retro_browser');
  if(el)el.remove();
  var sb=document.getElementById('__retro_statusbar');
  if(sb)sb.remove();
}},{lifetime});
""")
        evaluate_js(js)

    def cleanup(self, evaluate_js: Any) -> None:
        evaluate_js(
            "(function(){"
            "var e=document.getElementById('__retro_browser');"
            "if(e)e.remove();"
            "var s=document.getElementById('__retro_statusbar');"
            "if(s)s.remove();"
            "})()"
        )
