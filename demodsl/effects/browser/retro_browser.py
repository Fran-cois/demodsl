"""Retro browser chrome — overlay a classic (IE6, Firefox 3, Netscape) or a
modern Safari-style browser UI around the live page."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_html_text, sanitize_number


class RetroBrowserEffect(BrowserEffect):
    effect_id = "retro_browser"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        browser_name = params.get("text", "ie6")
        if browser_name not in ("ie6", "firefox", "netscape", "safari"):
            browser_name = "ie6"
        fake_url = sanitize_html_text(params.get("url", "http://www.example.com"))
        duration = sanitize_number(
            params.get("duration", 8.0), default=8.0, min_val=1.0, max_val=30.0
        )
        lifetime = int(duration * 1000)

        if browser_name == "safari":
            self._inject_safari(evaluate_js, fake_url, lifetime)
            return

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
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  z-index: 2147483646;
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
  position: fixed; top: 0; left: 0; width: 100vw;
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

        # `position: fixed` normally pins to the viewport, but once a sibling
        # effect (perspective_tilt / rotation_3d) puts an ANIMATED `transform`
        # on `document.body`, body becomes the containing block for fixed
        # descendants — its box spans the WHOLE document, not the viewport,
        # so a plain `top:0;left:0` would place the chrome far off-screen.
        # (`position: sticky` looks tempting here but produces an
        # intermittent floating/disconnected render glitch mid-transition
        # when the ancestor's transform is itself animating — a documented
        # browser-engine rough edge, not a compositing order we control.)
        # Poll and compensate with the current scroll offset whenever body is
        # transformed, so the chrome stays pinned to the visible viewport
        # (and tilts along with the page, since it's still a body child).
        js = inject_style("__retro_browser_style", css) + iife(f"""
var d=document.createElement('div');
d.innerHTML={repr(html)};
document.body.appendChild(d);
function __demodslSyncRetro(){{
  var transformed = getComputedStyle(document.body).transform !== 'none';
  var sx = transformed ? window.scrollX : 0;
  var sy = transformed ? window.scrollY : 0;
  var el=document.getElementById('__retro_browser');
  if(el){{ el.style.left = sx+'px'; el.style.top = sy+'px'; }}
  var sb=document.getElementById('__retro_statusbar');
  if(sb){{ sb.style.left = sx+'px'; sb.style.top = (sy+window.innerHeight-22)+'px'; }}
}}
__demodslSyncRetro();
window.__demodsl_retro_iv = setInterval(__demodslSyncRetro, 50);
setTimeout(function(){{
  clearInterval(window.__demodsl_retro_iv);
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
            "if(window.__demodsl_retro_iv)clearInterval(window.__demodsl_retro_iv);"
            "if(window.__demodsl_safari_iv)clearInterval(window.__demodsl_safari_iv);"
            "var e=document.getElementById('__retro_browser');"
            "if(e)e.remove();"
            "var s=document.getElementById('__retro_statusbar');"
            "if(s)s.remove();"
            "var sa=document.getElementById('__safari_browser');"
            "if(sa)sa.remove();"
            "})()"
        )

    def _inject_safari(self, evaluate_js: Any, fake_url: str, lifetime: int) -> None:
        """Modern Safari-style chrome: traffic-light dots, a single rounded
        tab and a pill-shaped URL bar — no menu bar, no status bar."""
        page_title = sanitize_html_text(fake_url.split("//", 1)[-1].split("/", 1)[0] or "Untitled")

        css = """
.__safari_browser {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  z-index: 2147483646;
  pointer-events: none; font-family: -apple-system, "SF Pro Text", "Helvetica Neue", sans-serif;
  animation: __retro_fadein 0.3s ease;
}
.__safari_titlebar {
  height: 38px; background: #ECECEC; display: flex; align-items: flex-end;
  padding: 0 12px; gap: 8px; border-bottom: 1px solid #D3D3D3;
}
.__safari_dots { display: flex; gap: 8px; margin-bottom: 11px; }
.__safari_dots span {
  width: 12px; height: 12px; border-radius: 50%; display: inline-block;
}
.__safari_dots .red { background: #FF5F57; }
.__safari_dots .yellow { background: #FEBC2E; }
.__safari_dots .green { background: #28C840; }
.__safari_tab {
  height: 30px; min-width: 180px; max-width: 260px; background: #FBFBFB;
  border-radius: 8px 8px 0 0; display: flex; align-items: center; gap: 6px;
  padding: 0 12px; font-size: 12px; color: #333; margin-left: 8px;
}
.__safari_tab_favicon {
  width: 8px; height: 8px; border-radius: 50%; background: #7C7C7C; flex: none;
}
.__safari_tab_title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.__safari_toolbar {
  height: 44px; background: #FBFBFB; display: flex; align-items: center;
  padding: 0 12px; gap: 12px; border-bottom: 1px solid #E4E4E4;
}
.__safari_nav { display: flex; gap: 10px; color: #B0B0B0; font-size: 16px; }
.__safari_urlbar {
  flex: 1; max-width: 640px; margin: 0 auto; height: 28px; background: #E9E9E9;
  border-radius: 7px; display: flex; align-items: center; justify-content: center;
  gap: 6px; font-size: 12px; color: #444;
}
.__safari_lock { font-size: 11px; }
.__safari_actions { display: flex; gap: 10px; color: #8A8A8A; font-size: 14px; }
@keyframes __retro_fadein { from { opacity: 0; } to { opacity: 1; } }
"""

        html = f"""
<div class="__safari_browser" id="__safari_browser">
  <div class="__safari_titlebar">
    <div class="__safari_dots"><span class="red"></span><span class="yellow"></span><span class="green"></span></div>
    <div class="__safari_tab">
      <span class="__safari_tab_favicon"></span>
      <span class="__safari_tab_title">{page_title}</span>
    </div>
  </div>
  <div class="__safari_toolbar">
    <div class="__safari_nav">&#8249; &#8250;</div>
    <div class="__safari_urlbar">
      <span class="__safari_lock">&#128274;</span>
      <span>{fake_url}</span>
    </div>
    <div class="__safari_actions">&#8682; &#8942;</div>
  </div>
</div>
"""

        js = inject_style("__safari_browser_style", css) + iife(f"""
var d=document.createElement('div');
d.innerHTML={html!r};
document.body.appendChild(d.firstElementChild);
function __demodslSyncSafari(){{
  var el=document.getElementById('__safari_browser');
  if(!el)return;
  var transformed = getComputedStyle(document.body).transform !== 'none';
  el.style.left = (transformed ? window.scrollX : 0)+'px';
  el.style.top = (transformed ? window.scrollY : 0)+'px';
}}
__demodslSyncSafari();
window.__demodsl_safari_iv = setInterval(__demodslSyncSafari, 50);
setTimeout(function(){{
  clearInterval(window.__demodsl_safari_iv);
  var el=document.getElementById('__safari_browser');
  if(el)el.remove();
}},{lifetime});
""")
        evaluate_js(js)
