"""Render self-contained ReactJS components to RGBA sprites.

The user provides a single ``.tsx``/``.jsx`` file with a default export.
We bundle it with ``bun`` (auto-installs react/react-dom in a managed
sandbox), mount it in a headless Chromium at the layer's bounding box,
and capture the ``#root`` element with a transparent background.

Two capture modes:
- ``static``  : single screenshot → cached forever on disk by content hash
- ``animated``: sprite sequence over the layer duration (one PNG per frame)

Caching key incorporates source content, props, css, width, height, mode,
fps and scale factor — any change invalidates the cache automatically.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# ── Sandbox / cache locations ─────────────────────────────────────────────────

_CACHE_ROOT = Path(
    os.environ.get(
        "DEMODSL_REACT_CACHE",
        Path.home() / ".cache" / "demodsl" / "react",
    )
)
_SANDBOX_DIR = _CACHE_ROOT / "sandbox"
_BUNDLE_DIR = _CACHE_ROOT / "bundles"
_SPRITE_DIR = _CACHE_ROOT / "sprites"

_SANDBOX_PACKAGE_JSON = {
    "name": "demodsl-react-sandbox",
    "private": True,
    "type": "module",
    "dependencies": {
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
    },
}

# In-process sprite cache so re-using the same component across many frames
# of the same render avoids re-reading the PNG from disk.
_SPRITE_MEM_CACHE: dict[str, Image.Image] = {}
_FRAME_SEQ_MEM_CACHE: dict[str, list[Image.Image]] = {}


def _ensure_sandbox() -> Path:
    """Create (idempotently) the bun sandbox with react + react-dom installed."""
    _SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    _BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    _SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    pkg = _SANDBOX_DIR / "package.json"
    needs_install = False
    if not pkg.exists():
        pkg.write_text(json.dumps(_SANDBOX_PACKAGE_JSON, indent=2))
        needs_install = True
    if not (_SANDBOX_DIR / "node_modules" / "react").exists():
        needs_install = True
    if needs_install:
        bun = shutil.which("bun")
        if bun is None:
            raise RuntimeError(
                "ReactLayer requires `bun` on PATH. Install via "
                "`brew install bun` or https://bun.sh."
            )
        logger.info("Installing react/react-dom in demodsl react sandbox…")
        subprocess.run(
            [bun, "install", "--silent"],
            cwd=_SANDBOX_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    return _SANDBOX_DIR


# ── Hashing / cache key ───────────────────────────────────────────────────────


def _content_hash(parts: list[str | bytes]) -> str:
    h = hashlib.blake2b(digest_size=12)
    for p in parts:
        if isinstance(p, str):
            p = p.encode("utf-8")
        h.update(p)
        h.update(b"\x00")
    return h.hexdigest()


def _resolve_path(p: str, base_dir: Path | None) -> Path:
    path = Path(p)
    if not path.is_absolute() and base_dir is not None:
        path = (base_dir / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"ReactLayer source not found: {path}")
    return path


# ── Bundling ─────────────────────────────────────────────────────────────────


_ENTRY_TEMPLATE = """\
import React from "react";
import { createRoot } from "react-dom/client";
import UserComponent from "USER_COMPONENT_PATH";

const mount = document.getElementById("root");
if (!mount) {
  throw new Error("#root not found");
}
const root = createRoot(mount);
const props = (window as any).__DEMODSL_PROPS__ || {};
root.render(React.createElement(UserComponent as any, props));
(window as any).__DEMODSL_READY__ = true;
"""


def _bundle(src_path: Path, cache_key: str) -> Path:
    """Bundle the user component into a single self-contained JS file."""
    out_js = _BUNDLE_DIR / f"{cache_key}.js"
    if out_js.exists():
        return out_js
    sandbox = _ensure_sandbox()
    # Copy the user's component INTO the sandbox so all resolutions (react,
    # react/jsx-dev-runtime, react-dom, etc.) succeed via sandbox/node_modules.
    user_copy = sandbox / f"user_{cache_key}{src_path.suffix}"
    user_copy.write_text(src_path.read_text())
    entry_path = sandbox / f"entry_{cache_key}.tsx"
    entry_path.write_text(_ENTRY_TEMPLATE.replace("USER_COMPONENT_PATH", f"./{user_copy.name}"))
    bun = shutil.which("bun")
    try:
        subprocess.run(
            [
                bun,
                "build",
                str(entry_path),
                "--outfile",
                str(out_js),
                "--target",
                "browser",
                "--format",
                "iife",
                "--minify",
            ],
            cwd=sandbox,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"bun build failed for {src_path}:\nSTDOUT:\n{exc.stdout}\nSTDERR:\n{exc.stderr}"
        ) from exc
    finally:
        for p in (entry_path, user_copy):
            try:
                p.unlink()
            except OSError:
                pass
    return out_js


# ── HTML wrapper ──────────────────────────────────────────────────────────────


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{ margin: 0; padding: 0; background: transparent; }}
#root {{ width: {w}px; height: {h}px; overflow: hidden; }}
{user_css}
</style>
</head>
<body>
<div id="root"></div>
<script>window.__DEMODSL_PROPS__ = {props_json};</script>
<script src="{bundle_src}"></script>
</body>
</html>
"""


def _build_html(bundle_path: Path, css: str, props: dict, width: int, height: int) -> str:
    return _HTML_TEMPLATE.format(
        w=width,
        h=height,
        user_css=css or "",
        props_json=json.dumps(props),
        bundle_src=bundle_path.name,
    )


# ── Capture (Playwright) ──────────────────────────────────────────────────────


def _screenshot(
    html: str,
    width: int,
    height: int,
    device_scale_factor: float,
    wait_selector: str | None,
    settle_ms: int,
    out_path: Path,
    *,
    bundle_path: Path,
    frame_times: list[float] | None = None,
    frame_out_paths: list[Path] | None = None,
) -> None:
    """Headless-render the HTML and screenshot the #root element."""
    # Local import keeps Playwright optional for users who never use ReactLayer.
    from playwright.sync_api import sync_playwright

    # Write HTML in the same dir as the bundle so the relative <script src>
    # resolves. Avoids inlining the bundle (which can break if minified JS
    # contains "</script>" sequences).
    tmp_html = bundle_path.with_suffix(".html")
    tmp_html.write_text(html)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=device_scale_factor,
            )
            page = context.new_page()
            page.goto(tmp_html.as_uri(), wait_until="load")
            # Wait until our entry has finished mounting.
            page.wait_for_function("() => window.__DEMODSL_READY__ === true", timeout=10000)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=10000)
            else:
                page.wait_for_function(
                    "() => document.querySelector('#root') && "
                    "document.querySelector('#root').children.length > 0",
                    timeout=10000,
                )
            if settle_ms > 0:
                page.wait_for_timeout(settle_ms)
            root = page.locator("#root")
            if frame_times is None:
                root.screenshot(path=str(out_path), omit_background=True)
            else:
                assert frame_out_paths is not None and len(frame_out_paths) == len(frame_times)
                # Animated capture: wall-clock pacing inside the headless
                # browser. We don't manipulate time — the component
                # animates with the page's real clock.
                t0_ms = frame_times[0] * 1000
                for t, path in zip(frame_times, frame_out_paths, strict=True):
                    delta = max(0, int(t * 1000 - t0_ms))
                    if delta > 0:
                        page.wait_for_timeout(delta)
                    root.screenshot(path=str(path), omit_background=True)
                    t0_ms = t * 1000
            context.close()
            browser.close()
    finally:
        try:
            tmp_html.unlink()
        except OSError:
            pass


# ── Public API ────────────────────────────────────────────────────────────────


def render_static(
    src: str,
    props: dict,
    width: int,
    height: int,
    *,
    css_path: str | None = None,
    base_dir: Path | None = None,
    device_scale_factor: float = 2.0,
    wait_selector: str | None = None,
    settle_ms: int = 120,
) -> Image.Image:
    """Render a React component to a single transparent PIL Image."""
    src_path = _resolve_path(src, base_dir)
    css_text = ""
    css_p = None
    if css_path:
        css_p = _resolve_path(css_path, base_dir)
        css_text = css_p.read_text()
    src_text = src_path.read_text()
    cache_key = _content_hash(
        [
            "static",
            src_text,
            json.dumps(props, sort_keys=True),
            css_text,
            str(width),
            str(height),
            str(device_scale_factor),
            wait_selector or "",
        ]
    )
    if cache_key in _SPRITE_MEM_CACHE:
        return _SPRITE_MEM_CACHE[cache_key]
    sprite_path = _SPRITE_DIR / f"{cache_key}.png"
    if not sprite_path.exists():
        bundle_path = _bundle(src_path, _content_hash(["bundle", src_text]))
        html = _build_html(bundle_path, css_text, props, width, height)
        _screenshot(
            html,
            width,
            height,
            device_scale_factor,
            wait_selector,
            settle_ms,
            sprite_path,
            bundle_path=bundle_path,
        )
    img = Image.open(sprite_path).convert("RGBA")
    # Browser captures at device_scale_factor — resize back down to the
    # logical layer bounding box.
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    _SPRITE_MEM_CACHE[cache_key] = img
    return img


def render_animated(
    src: str,
    props: dict,
    width: int,
    height: int,
    duration: float,
    *,
    fps: int = 30,
    css_path: str | None = None,
    base_dir: Path | None = None,
    device_scale_factor: float = 2.0,
    wait_selector: str | None = None,
    settle_ms: int = 120,
) -> list[Image.Image]:
    """Render an animated React component to a list of RGBA frames."""
    src_path = _resolve_path(src, base_dir)
    css_text = ""
    if css_path:
        css_p = _resolve_path(css_path, base_dir)
        css_text = css_p.read_text()
    src_text = src_path.read_text()
    n_frames = max(1, int(round(duration * fps)))
    cache_key = _content_hash(
        [
            "animated",
            src_text,
            json.dumps(props, sort_keys=True),
            css_text,
            str(width),
            str(height),
            str(device_scale_factor),
            str(fps),
            str(n_frames),
            wait_selector or "",
        ]
    )
    if cache_key in _FRAME_SEQ_MEM_CACHE:
        return _FRAME_SEQ_MEM_CACHE[cache_key]
    frame_dir = _SPRITE_DIR / cache_key
    paths = [frame_dir / f"f_{i:05d}.png" for i in range(n_frames)]
    if not all(p.exists() for p in paths):
        frame_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = _bundle(src_path, _content_hash(["bundle", src_text]))
        html = _build_html(bundle_path, css_text, props, width, height)
        times = [i / fps for i in range(n_frames)]
        _screenshot(
            html,
            width,
            height,
            device_scale_factor,
            wait_selector,
            settle_ms,
            paths[0],
            bundle_path=bundle_path,
            frame_times=times,
            frame_out_paths=paths,
        )
    frames: list[Image.Image] = []
    for p in paths:
        img = Image.open(p).convert("RGBA")
        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)
        frames.append(img)
    _FRAME_SEQ_MEM_CACHE[cache_key] = frames
    return frames
