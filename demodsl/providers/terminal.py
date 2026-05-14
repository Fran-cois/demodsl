"""Terminal provider — renders a terminal UI in the browser for recording."""

from __future__ import annotations

import base64
import glob
import html
import logging
import os
import platform
import subprocess
from typing import Any

from demodsl.models.terminal import TerminalConfig

logger = logging.getLogger(__name__)


# ── macOS icon resolution ─────────────────────────────────────────────────────

# Well-known app bundle paths on macOS.
_MACOS_APP_PATHS: dict[str, list[str]] = {
    "Finder": ["/System/Library/CoreServices/Finder.app"],
    "Safari": ["/Applications/Safari.app"],
    "Terminal": [
        "/System/Applications/Utilities/Terminal.app",
        "/Applications/Utilities/Terminal.app",
    ],
    "VS Code": ["/Applications/Visual Studio Code.app"],
    "Slack": ["/Applications/Slack.app"],
    "Music": ["/System/Applications/Music.app"],
    "Notes": ["/System/Applications/Notes.app"],
    "Messages": ["/System/Applications/Messages.app"],
    "Mail": ["/System/Applications/Mail.app"],
    "Settings": ["/System/Applications/System Settings.app"],
    "Photos": ["/System/Applications/Photos.app"],
    "Chrome": ["/Applications/Google Chrome.app"],
    "Firefox": ["/Applications/Firefox.app"],
    "Discord": ["/Applications/Discord.app"],
    "Spotify": ["/Applications/Spotify.app"],
    "GitHub Desktop": ["/Applications/GitHub Desktop.app"],
}

_icon_cache: dict[str, str | None] = {}


def _resolve_macos_icon(app_name: str) -> str | None:
    """Return a ``data:image/png;base64,…`` URI for *app_name*, or *None*."""
    if app_name in _icon_cache:
        return _icon_cache[app_name]

    if platform.system() != "Darwin":
        _icon_cache[app_name] = None
        return None

    paths = _MACOS_APP_PATHS.get(app_name, [])
    # Also try a generic /Applications/<name>.app path
    if not paths:
        paths = [f"/Applications/{app_name}.app"]

    icns_path: str | None = None
    for app_path in paths:
        if not os.path.isdir(app_path):
            continue
        plist_path = os.path.join(app_path, "Contents", "Info.plist")
        if not os.path.exists(plist_path):
            continue
        try:
            import plistlib

            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
            icon_name = plist.get("CFBundleIconFile", "AppIcon")
            if not icon_name.endswith(".icns"):
                icon_name += ".icns"
            candidate = os.path.join(app_path, "Contents", "Resources", icon_name)
            if os.path.exists(candidate):
                icns_path = candidate
                break
            # Fallback: any .icns in Resources
            candidates = glob.glob(os.path.join(app_path, "Contents", "Resources", "*.icns"))
            if candidates:
                icns_path = candidates[0]
                break
        except Exception:  # noqa: BLE001
            continue

    if not icns_path:
        _icon_cache[app_name] = None
        return None

    try:
        # Use sips to convert .icns → 64×64 PNG via a temp file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["sips", "-s", "format", "png", "-z", "64", "64", icns_path, "--out", tmp_path],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                data_uri = f"data:image/png;base64,{b64}"
                _icon_cache[app_name] = data_uri
                return data_uri
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception:  # noqa: BLE001
        pass

    _icon_cache[app_name] = None
    return None


# ── Theme definitions ─────────────────────────────────────────────────────────

_THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "prompt_color": "#a6e3a1",
        "title_bg": "#313244",
        "title_fg": "#bac2de",
        "cursor_color": "#f5e0dc",
        "selection_bg": "#45475a",
    },
    "light": {
        "bg": "#eff1f5",
        "fg": "#4c4f69",
        "prompt_color": "#40a02b",
        "title_bg": "#dce0e8",
        "title_fg": "#6c6f85",
        "cursor_color": "#dc8a78",
        "selection_bg": "#ccd0da",
    },
    "dracula": {
        "bg": "#282a36",
        "fg": "#f8f8f2",
        "prompt_color": "#50fa7b",
        "title_bg": "#44475a",
        "title_fg": "#6272a4",
        "cursor_color": "#f8f8f2",
        "selection_bg": "#44475a",
    },
    "monokai": {
        "bg": "#272822",
        "fg": "#f8f8f2",
        "prompt_color": "#a6e22e",
        "title_bg": "#3e3d32",
        "title_fg": "#75715e",
        "cursor_color": "#f8f8f0",
        "selection_bg": "#49483e",
    },
    "solarized": {
        "bg": "#002b36",
        "fg": "#839496",
        "prompt_color": "#859900",
        "title_bg": "#073642",
        "title_fg": "#586e75",
        "cursor_color": "#93a1a1",
        "selection_bg": "#073642",
    },
}


def get_theme(name: str) -> dict[str, str]:
    return _THEMES.get(name, _THEMES["dark"])


# ── HTML generation ───────────────────────────────────────────────────────────


def build_terminal_html(
    config: TerminalConfig,
    *,
    background: Any | None = None,
) -> str:
    """Build a self-contained HTML page that renders a terminal emulator.

    If *background* is provided (a ``BackgroundConfig`` instance), the
    terminal window is rendered inside a macOS/Windows desktop simulation
    with wallpaper, menu bar, and dock.

    The page exposes JS functions on ``window`` that the orchestrator calls
    to type commands and display output:

    - ``typeCommand(text, charsPerSec)`` → types text character-by-character
    - ``showOutput(text)`` → appends output lines below the command
    - ``showPrompt()`` → renders a new prompt line with blinking cursor
    - ``clearTerminal()`` → clears all content and shows a fresh prompt
    """
    theme = get_theme(config.theme)
    title = html.escape(config.title or config.shell)
    prompt_esc = html.escape(config.prompt)

    has_bg = background is not None and getattr(background, "enabled", True)
    bg_css = ""
    bg_html_before = ""
    bg_html_after = ""

    if has_bg:
        bg_css, bg_html_before, bg_html_after = _build_desktop_chrome(background, title, theme)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
    width: 100%; height: 100%;
    overflow: hidden;
    background: {background.wallpaper_color if background is not None and has_bg else theme["bg"]};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}
{bg_css}
/* ── Terminal window ───────────────────────────────────────── */
#term-window {{
    display: flex;
    flex-direction: column;
    {"" if has_bg else "width: 100%; height: 100%;"}
    background: {theme["bg"]};
    {"border-radius: 12px; overflow: hidden; box-shadow: 0 25px 70px rgba(0,0,0,0.55), 0 0 0 0.5px rgba(255,255,255,0.1);" if has_bg else ""}
}}
/* ── Title bar ─────────────────────────────────────────────── */
#titlebar {{
    display: {"flex" if config.window_chrome else "none"};
    align-items: center;
    height: 40px;
    min-height: 40px;
    background: {theme["title_bg"]};
    padding: 0 14px;
    gap: 8px;
    user-select: none;
    -webkit-user-select: none;
    {"border-radius: 12px 12px 0 0;" if has_bg else ""}
}}
.dot {{
    width: 13px; height: 13px;
    border-radius: 50%;
    flex-shrink: 0;
}}
.dot-red   {{ background: #ff5f57; }}
.dot-yel   {{ background: #febc2e; }}
.dot-grn   {{ background: #28c840; }}
#titlebar .title {{
    flex: 1;
    text-align: center;
    font-size: 13px;
    color: {theme["title_fg"]};
    font-weight: 500;
}}
/* ── Terminal body ─────────────────────────────────────────── */
#terminal {{
    flex: 1;
    padding: 16px 20px;
    font-family: {config.font_family};
    font-size: {config.font_size}px;
    line-height: {config.line_height};
    color: {theme["fg"]};
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}}
.prompt {{ color: {theme["prompt_color"]}; font-weight: bold; }}
.cursor {{
    display: inline-block;
    width: 0.6em; height: 1.15em;
    background: {theme["cursor_color"]};
    vertical-align: text-bottom;
    animation: blink 1s step-end infinite;
}}
@keyframes blink {{
    50% {{ opacity: 0; }}
}}
.output-line {{ color: {theme["fg"]}; }}
</style>
</head>
<body>
{bg_html_before}
<div id="term-window">
  <div id="titlebar">
    <span class="dot dot-red"></span>
    <span class="dot dot-yel"></span>
    <span class="dot dot-grn"></span>
    <span class="title">{title}</span>
    <span style="width:54px"></span>
  </div>
  <div id="terminal"><span class="prompt">{prompt_esc}</span><span id="input"></span><span class="cursor" id="cursor"></span></div>
</div>
{bg_html_after}
<script>
const PROMPT = {_js_string(config.prompt)};
const term = document.getElementById('terminal');

/* ── Mutable refs (updated by showPrompt / clearTerminal) ── */
var inputEl = document.getElementById('input');
var cursorEl = document.getElementById('cursor');

/* ── Helpers ──────────────────────────────────────────────── */

function _sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}
function _scrollBottom() {{ term.scrollTop = term.scrollHeight; }}

/* ── Public API (called from Playwright evaluate) ────────── */

window.typeCommand = async function(text, charsPerSec) {{
    const delay = 1000 / charsPerSec;
    for (const ch of text) {{
        inputEl.textContent += ch;
        _scrollBottom();
        const jitter = delay * (0.7 + Math.random() * 0.6);
        await _sleep(jitter);
    }}
}};

window.showOutput = function(text) {{
    cursorEl.style.display = 'none';
    const lines = text.split('\\n');
    for (const line of lines) {{
        const div = document.createElement('div');
        div.className = 'output-line';
        div.textContent = line;
        term.appendChild(div);
    }}
    _scrollBottom();
}};

window.showPrompt = function() {{
    const span = document.createElement('span');
    span.className = 'prompt';
    span.textContent = PROMPT;
    term.appendChild(span);
    const newInput = document.createElement('span');
    newInput.id = 'input';
    term.appendChild(newInput);
    const newCursor = document.createElement('span');
    newCursor.className = 'cursor';
    newCursor.id = 'cursor';
    term.appendChild(newCursor);
    inputEl = newInput;
    cursorEl = newCursor;
    _scrollBottom();
}};

window.clearTerminal = function() {{
    term.innerHTML = '';
    const span = document.createElement('span');
    span.className = 'prompt';
    span.textContent = PROMPT;
    term.appendChild(span);
    const newInput = document.createElement('span');
    newInput.id = 'input';
    term.appendChild(newInput);
    const newCursor = document.createElement('span');
    newCursor.className = 'cursor';
    newCursor.id = 'cursor';
    term.appendChild(newCursor);
    inputEl = newInput;
    cursorEl = newCursor;
}};

window.zoomTerminal = function(scale, durationMs) {{
    return new Promise(resolve => {{
        term.style.transition = `transform ${{durationMs}}ms cubic-bezier(0.4, 0, 0.2, 1), transform-origin 0ms`;
        term.style.transformOrigin = 'left top';
        term.style.transform = `scale(${{scale}})`;
        setTimeout(resolve, durationMs + 50);
    }});
}};
</script>
</body>
</html>"""


def _build_desktop_chrome(
    bg: Any,
    terminal_title: str,
    terminal_theme: dict[str, str],
) -> tuple[str, str, str]:
    """Build CSS + HTML for an OS desktop around the terminal window.

    Returns (css, html_before_window, html_after_window).
    """
    os_type = getattr(bg, "os", "macos")
    bg_theme = getattr(bg, "theme", "dark")
    wallpaper = getattr(bg, "wallpaper_color", "#1a1a2e")
    show_dock = getattr(bg, "show_dock", True)
    show_menu = getattr(bg, "show_menu_bar", True)
    win_title = getattr(bg, "window_title", terminal_title)
    apps = getattr(bg, "apps", None)

    is_dark = bg_theme == "dark"
    menu_bg = "rgba(28,28,30,0.85)" if is_dark else "rgba(242,242,247,0.85)"
    menu_fg = "#e0e0e0" if is_dark else "#333"
    dock_bg = "rgba(40,40,45,0.65)" if is_dark else "rgba(220,220,225,0.65)"

    # Default dock apps
    if not apps:
        apps = [
            {"name": "Finder", "color": "#2196F3"},
            {"name": "Safari", "color": "#3B82F6"},
            {"name": "Terminal", "color": "#4ADE80"},
            {"name": "VS Code", "color": "#007ACC"},
            {"name": "Notes", "color": "#FFCA28"},
            {"name": "Music", "color": "#FC3C44"},
        ]

    # ── SVG icon templates for dock apps ──────────────────────
    _DOCK_ICONS: dict[str, str] = {
        "Finder": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#4AA5F0"/>'
            '<path d="M15 12h18v24H15z" fill="#fff" opacity=".95"/>'
            '<path d="M20 18h8v2h-8zM20 22h8v2h-8zM20 26h5v2h-5z" fill="#4AA5F0"/>'
            '<circle cx="24" cy="36" r="2.5" fill="#4AA5F0"/>'
            "</svg>"
        ),
        "Safari": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="url(#sg)"/>'
            '<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#56CCF2"/>'
            '<stop offset="100%" stop-color="#2F80ED"/>'
            "</linearGradient></defs>"
            '<circle cx="24" cy="24" r="14" fill="none" stroke="#fff" stroke-width="1.5"/>'
            '<polygon points="24,10 28,22 24,24 20,22" fill="#fff"/>'
            '<polygon points="24,38 20,26 24,24 28,26" fill="#E74C3C"/>'
            "</svg>"
        ),
        "Terminal": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#2D2D2D"/>'
            '<path d="M14 16l8 8-8 8" stroke="#4ADE80" stroke-width="2.5" '
            'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
            '<line x1="24" y1="32" x2="34" y2="32" stroke="#ccc" stroke-width="2" '
            'stroke-linecap="round"/>'
            "</svg>"
        ),
        "VS Code": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#1E1E1E"/>'
            '<path d="M34 10v28l-10-5L12 24l12-9 10-5z" fill="#007ACC"/>'
            '<path d="M34 10l-10 9L12 24l12 5 10 9" fill="none" stroke="#fff" '
            'stroke-width="1" opacity=".4"/>'
            "</svg>"
        ),
        "Slack": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#4A154B"/>'
            '<g transform="translate(10,10)">'
            '<rect x="2" y="10" width="6" height="8" rx="3" fill="#E01E5A"/>'
            '<rect x="10" y="2" width="8" height="6" rx="3" fill="#36C5F0"/>'
            '<rect x="20" y="10" width="6" height="8" rx="3" fill="#2EB67D"/>'
            '<rect x="10" y="20" width="8" height="6" rx="3" fill="#ECB22E"/>'
            "</g>"
            "</svg>"
        ),
        "Music": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="url(#mg)"/>'
            '<defs><linearGradient id="mg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#FC3D39"/>'
            '<stop offset="100%" stop-color="#E91E63"/>'
            "</linearGradient></defs>"
            '<path d="M30 14v14a5 5 0 1 1-2-4V18h-8v12a5 5 0 1 1-2-4V14h12z" fill="#fff"/>'
            "</svg>"
        ),
        "Notes": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#FFCA28"/>'
            '<rect x="12" y="10" width="24" height="28" rx="3" fill="#fff"/>'
            '<path d="M16 18h16M16 23h16M16 28h10" stroke="#CCC" stroke-width="1.2"/>'
            "</svg>"
        ),
        "Messages": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="url(#msg)"/>'
            '<defs><linearGradient id="msg" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#5BF675"/>'
            '<stop offset="100%" stop-color="#2DC653"/>'
            "</linearGradient></defs>"
            '<ellipse cx="24" cy="23" rx="13" ry="10" fill="#fff"/>'
            '<path d="M18 31l-3 5 6-3z" fill="#fff"/>'
            "</svg>"
        ),
        "Mail": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#2196F3"/>'
            '<rect x="10" y="14" width="28" height="20" rx="3" fill="#fff"/>'
            '<path d="M10 16l14 10 14-10" fill="none" stroke="#2196F3" stroke-width="2"/>'
            "</svg>"
        ),
        "Settings": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="#8E8E93"/>'
            '<circle cx="24" cy="24" r="8" fill="none" stroke="#fff" stroke-width="2.5"/>'
            '<g stroke="#fff" stroke-width="2.5" stroke-linecap="round">'
            '<line x1="24" y1="8" x2="24" y2="14"/><line x1="24" y1="34" x2="24" y2="40"/>'
            '<line x1="8" y1="24" x2="14" y2="24"/><line x1="34" y1="24" x2="40" y2="24"/>'
            "</g>"
            "</svg>"
        ),
        "Photos": (
            '<svg viewBox="0 0 48 48" width="32" height="32">'
            '<rect width="48" height="48" rx="10" fill="url(#pg)"/>'
            '<defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#FF6B6B"/>'
            '<stop offset="50%" stop-color="#FFA500"/>'
            '<stop offset="100%" stop-color="#FFD93D"/>'
            "</linearGradient></defs>"
            '<circle cx="24" cy="22" r="8" fill="none" stroke="#fff" stroke-width="2"/>'
            '<path d="M12 36l8-10 4 5 6-7 8 12z" fill="#fff" opacity=".8"/>'
            "</svg>"
        ),
    }

    dock_items_html = ""
    for app in apps:
        name = str(app.get("name", "App") if isinstance(app, dict) else getattr(app, "name", "App"))
        color = str(
            app.get("color", "#888") if isinstance(app, dict) else getattr(app, "color", "#888")
        )
        safe_name = html.escape(name)

        # Try to resolve a real macOS icon from the system
        native_icon = _resolve_macos_icon(name)
        if native_icon:
            dock_items_html += (
                f'<div class="dock-icon dock-icon-img" title="{safe_name}">'
                f'<img src="{native_icon}" width="44" height="44" alt="{safe_name}"/>'
                f"</div>\n"
            )
        else:
            # Fallback: inline SVG if available, else colored square with letter
            icon_svg = _DOCK_ICONS.get(name)
            if icon_svg:
                dock_items_html += (
                    f'<div class="dock-icon dock-icon-svg" title="{safe_name}">{icon_svg}</div>\n'
                )
            else:
                dock_items_html += (
                    f'<div class="dock-icon" title="{safe_name}" '
                    f'style="background:{color};">{safe_name[0]}</div>\n'
                )

    # ── Wallpaper gradient ────────────────────────────────────
    wallpaper_css = f"""
body {{
    background: {wallpaper};
    background-image:
        radial-gradient(ellipse 120% 80% at 30% 20%, rgba(88,86,214,0.35), transparent),
        radial-gradient(ellipse 100% 70% at 75% 80%, rgba(52,199,89,0.18), transparent),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(255,149,0,0.10), transparent);
}}
"""

    # ── Menu bar ──────────────────────────────────────────────
    menu_css = f"""
#menubar {{
    {"display:flex" if show_menu else "display:none"};
    align-items: center;
    height: 28px;
    background: {menu_bg};
    backdrop-filter: blur(30px);
    -webkit-backdrop-filter: blur(30px);
    padding: 0 16px;
    font-size: 13px;
    font-weight: 500;
    color: {menu_fg};
    gap: 18px;
    z-index: 100;
    position: fixed;
    top: 0; left: 0; right: 0;
}}
#menubar .apple {{ font-size: 16px; }}
#menubar .app-name {{ font-weight: 600; }}
#menubar .spacer {{ flex: 1; }}
#menubar .right {{ font-size: 12px; opacity: 0.8; }}
"""

    menu_html = f"""
<div id="menubar">
  <span class="apple"></span>
  <span class="app-name">{html.escape(win_title)}</span>
  <span>File</span><span>Edit</span><span>View</span><span>Window</span><span>Help</span>
  <span class="spacer"></span>
  <span class="right" id="clock"></span>
</div>
"""

    # ── Dock ──────────────────────────────────────────────────
    dock_css = f"""
#dock {{
    {"display:flex" if show_dock else "display:none"};
    align-items: center;
    justify-content: center;
    gap: 6px;
    position: fixed;
    bottom: 8px;
    left: 50%;
    transform: translateX(-50%);
    padding: 6px 10px;
    background: {dock_bg};
    backdrop-filter: blur(30px);
    -webkit-backdrop-filter: blur(30px);
    border: 0.5px solid rgba(255,255,255,0.15);
    border-radius: 18px;
    z-index: 100;
}}
.dock-icon {{
    width: 48px; height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    transition: transform 0.2s;
    cursor: default;
}}
.dock-icon-svg {{
    background: transparent !important;
    box-shadow: none;
}}
.dock-icon-svg svg {{
    width: 44px; height: 44px;
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
}}
.dock-icon-img {{
    background: transparent !important;
    box-shadow: none;
}}
.dock-icon-img img {{
    border-radius: 12px;
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
}}
"""

    dock_html = f"""
<div id="dock">
{dock_items_html}
</div>
"""

    # ── Terminal window positioning ───────────────────────────
    top_offset = 28 if show_menu else 0
    bottom_offset = 72 if show_dock else 0

    window_css = f"""
#term-window {{
    position: fixed;
    top: {top_offset + 40}px;
    left: 60px;
    right: 60px;
    bottom: {bottom_offset + 30}px;
    z-index: 50;
}}
"""

    # ── Clock script ──────────────────────────────────────────
    clock_script = """
<script>
(function updateClock() {
    const el = document.getElementById('clock');
    if (el) {
        const d = new Date();
        const h = d.getHours();
        const m = String(d.getMinutes()).padStart(2, '0');
        const day = d.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
        el.textContent = day + '  ' + h + ':' + m;
    }
    setTimeout(updateClock, 30000);
})();
</script>
"""

    css = wallpaper_css + menu_css + dock_css + window_css
    html_before = menu_html
    html_after = dock_html + clock_script

    return css, html_before, html_after


def _js_string(value: str) -> str:
    """Escape a Python string for safe embedding in JS source."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"
