#!/usr/bin/env python3
"""Mini web app to annotate flat mesh planes from a 3D model.

Usage:
    python mesh_annotator.py <model.glb>                 # generate previews + launch
    python mesh_annotator.py --previews /tmp/screen_picks # reuse existing previews

Opens a browser with a grid of mesh previews.  Click a label to tag each
mesh (screen, bezel, keyboard, trackpad, chassis, other).  The "screen"
tag updates the device manifest automatically.
"""

from __future__ import annotations

import argparse
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path

_PORT = 8457
_HERE = Path(__file__).resolve().parent
_PLUGIN_ROOT = _HERE.parent
_MANIFEST = _PLUGIN_ROOT / "demodsl_blender" / "blender" / "devices" / "manifest.json"
_ROOT_MANIFEST = _PLUGIN_ROOT.parent.parent / "blender" / "devices" / "manifest.json"

# ── HTML template ─────────────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DemoDSL – Mesh Annotator</title>
<style>
  :root { --bg: #111; --card: #1a1a1a; --accent: #7c3aed; --green: #22c55e; --border: #333; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: #e5e5e5; font-family: system-ui,-apple-system,sans-serif; padding: 24px; }
  h1 { font-size: 1.4rem; margin-bottom: 4px; }
  .subtitle { color: #888; font-size: .85rem; margin-bottom: 20px; }
  .toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
  .toolbar label { font-size: .85rem; color: #aaa; }
  .toolbar select, .toolbar input { background: #222; color: #e5e5e5; border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; font-size: .85rem; }
  .toolbar button { background: var(--accent); color: #fff; border: none; border-radius: 6px;
    padding: 8px 18px; font-size: .85rem; cursor: pointer; font-weight: 600; }
  .toolbar button:hover { opacity: .9; }
  .toolbar button.secondary { background: #333; }
  .toolbar .save-ok { color: var(--green); font-weight: 600; font-size: .85rem; opacity: 0; transition: opacity .3s; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .card { background: var(--card); border: 2px solid var(--border); border-radius: 12px;
    overflow: hidden; transition: border-color .2s, box-shadow .2s; }
  .card.tagged-screen { border-color: var(--green); box-shadow: 0 0 12px rgba(34,197,94,.3); }
  .card.tagged-bezel { border-color: #f59e0b; }
  .card.tagged-keyboard { border-color: #3b82f6; }
  .card.tagged-trackpad { border-color: #8b5cf6; }
  .card.tagged-chassis { border-color: #6b7280; }
  .card.tagged-other { border-color: #555; }
  .card img { width: 100%; aspect-ratio: 4/3; object-fit: contain; background: #0a0a0a; cursor: zoom-in; }
  .card img.zoomed { position: fixed; inset: 0; z-index: 100; width: 100vw; height: 100vh;
    object-fit: contain; background: rgba(0,0,0,.92); cursor: zoom-out; border-radius: 0; aspect-ratio: auto; }
  .card-info { padding: 10px 14px; }
  .card-info .name { font-family: 'SF Mono', Menlo, monospace; font-size: .82rem; color: #ccc; margin-bottom: 6px; word-break: break-all; }
  .card-info .meta { font-size: .75rem; color: #777; margin-bottom: 8px; }
  .tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { padding: 3px 10px; border-radius: 999px; font-size: .72rem; font-weight: 600;
    cursor: pointer; border: 1.5px solid transparent; transition: all .15s; text-transform: uppercase; letter-spacing: .5px; }
  .tag:hover { opacity: .85; }
  .tag[data-t="screen"]   { background: #22c55e22; color: #22c55e; border-color: #22c55e55; }
  .tag[data-t="bezel"]    { background: #f59e0b22; color: #f59e0b; border-color: #f59e0b55; }
  .tag[data-t="keyboard"] { background: #3b82f622; color: #3b82f6; border-color: #3b82f655; }
  .tag[data-t="trackpad"] { background: #8b5cf622; color: #8b5cf6; border-color: #8b5cf655; }
  .tag[data-t="chassis"]  { background: #6b728022; color: #9ca3af; border-color: #6b728055; }
  .tag[data-t="other"]    { background: #55555522; color: #888; border-color: #55555555; }
  .tag.active { border-width: 2.5px; filter: brightness(1.3); }
  .toast { position: fixed; bottom: 24px; right: 24px; background: var(--green); color: #000;
    padding: 12px 24px; border-radius: 10px; font-weight: 600; font-size: .9rem;
    opacity: 0; transform: translateY(10px); transition: all .3s; z-index: 200; pointer-events: none; }
  .toast.visible { opacity: 1; transform: translateY(0); }
  #export-panel { display: none; position: fixed; inset: 0; z-index: 300; background: rgba(0,0,0,.8);
    align-items: center; justify-content: center; }
  #export-panel.visible { display: flex; }
  #export-panel pre { background: #1e1e1e; color: #e5e5e5; padding: 24px; border-radius: 12px;
    max-width: 700px; width: 90vw; max-height: 70vh; overflow: auto; font-size: .82rem;
    border: 1px solid #444; position: relative; }
  #export-panel .close { position: absolute; top: 8px; right: 12px; background: none; color: #888;
    border: none; font-size: 1.2rem; cursor: pointer; }
</style>
</head>
<body>

<h1>Mesh Annotator</h1>
<p class="subtitle">Model: <strong id="model-name">—</strong> &middot; <span id="count">0</span> meshes (<span id="shown">0</span> shown)</p>

<div class="toolbar">
  <label>Device:
    <select id="device-select"></select>
  </label>
  <label>Show:
    <select id="filter-select" onchange="render()">
      <option value="all">All meshes</option>
      <option value="flat">Flat only</option>
      <option value="textured">With texture</option>
      <option value="untagged">Untagged</option>
      <option value="tagged">Tagged</option>
    </select>
  </label>
  <label>Sort:
    <select id="sort-select" onchange="render()">
      <option value="area">Area ↓</option>
      <option value="verts">Vertices ↓</option>
      <option value="index">Index</option>
    </select>
  </label>
  <button onclick="saveAnnotations()">Save annotations</button>
  <button class="secondary" onclick="applyToManifest()">Apply screen → manifest</button>
  <button class="secondary" onclick="showExport()">Export JSON</button>
  <span class="save-ok" id="save-ok">Saved ✓</span>
</div>

<div class="grid" id="grid"></div>

<div class="toast" id="toast"></div>

<div id="export-panel">
  <pre id="export-content"><button class="close" onclick="document.getElementById('export-panel').classList.remove('visible')">&times;</button></pre>
</div>

<script>
const TAGS = ["screen","bezel","keyboard","trackpad","chassis","other"];
let candidates = [];
let annotations = {};  // name -> tag

async function init() {
  const r = await fetch("/api/data");
  const data = await r.json();
  candidates = data.candidates;
  annotations = data.annotations || {};
  document.getElementById("model-name").textContent = data.model || "unknown";
  document.getElementById("count").textContent = candidates.length;

  // populate device select
  const sel = document.getElementById("device-select");
  for (const d of data.devices || []) {
    const opt = document.createElement("option");
    opt.value = d; opt.textContent = d;
    if (d === data.current_device) opt.selected = true;
    sel.appendChild(opt);
  }

  render();
}

function render() {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  const filter = document.getElementById("filter-select").value;
  const sortBy = document.getElementById("sort-select").value;
  let items = [...candidates];
  if (filter === "flat") items = items.filter(c => c.flat);
  else if (filter === "textured") items = items.filter(c => c.texture);
  else if (filter === "untagged") items = items.filter(c => !annotations[c.name]);
  else if (filter === "tagged") items = items.filter(c => !!annotations[c.name]);
  if (sortBy === "area") items.sort((a,b) => b.area - a.area);
  else if (sortBy === "verts") items.sort((a,b) => (b.verts||0) - (a.verts||0));
  document.getElementById("shown").textContent = items.length;
  for (const c of items) {
    const tag = annotations[c.name] || "";
    const flatBadge = c.flat ? '<span style="background:#22c55e33;color:#22c55e;padding:1px 6px;border-radius:4px;font-size:.65rem">FLAT</span>' : '<span style="background:#ef444433;color:#ef4444;padding:1px 6px;border-radius:4px;font-size:.65rem">3D</span>';
    const texBadge = c.texture ? `<span style="background:#3b82f633;color:#3b82f6;padding:1px 6px;border-radius:4px;font-size:.65rem">${c.texture}</span>` : '';
    const dims = c.dims ? `${c.dims[0].toFixed(3)}\u00d7${c.dims[1].toFixed(3)}\u00d7${c.dims[2].toFixed(3)}` : '';
    const card = document.createElement("div");
    card.className = "card" + (tag ? ` tagged-${tag}` : "");
    card.innerHTML = `
      <img src="/previews/${c.file}" alt="${c.name}" onclick="toggleZoom(this)">
      <div class="card-info">
        <div class="name">#${c.index} ${c.name} ${flatBadge} ${texBadge}</div>
        <div class="meta">area ${c.area.toFixed(4)} &middot; aspect ${c.aspect.toFixed(2)} &middot; ${c.verts||'?'} verts &middot; ${dims}</div>
        <div class="tags">
          ${TAGS.map(t => `<span class="tag${tag===t?' active':''}" data-t="${t}" onclick="setTag('${c.name}','${t}',this)">${t}</span>`).join("")}
        </div>
      </div>`;
    grid.appendChild(card);
  }
}

function setTag(name, tag, el) {
  if (annotations[name] === tag) {
    delete annotations[name];
  } else {
    // Only one screen allowed
    if (tag === "screen") {
      for (const k of Object.keys(annotations)) {
        if (annotations[k] === "screen") delete annotations[k];
      }
    }
    annotations[name] = tag;
  }
  render();
}

function toggleZoom(img) {
  img.classList.toggle("zoomed");
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    document.querySelectorAll(".zoomed").forEach(el => el.classList.remove("zoomed"));
    document.getElementById("export-panel").classList.remove("visible");
  }
});

async function saveAnnotations() {
  const r = await fetch("/api/annotations", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(annotations)
  });
  if (r.ok) toast("Annotations saved");
}

async function applyToManifest() {
  const screen = Object.entries(annotations).find(([,v]) => v === "screen");
  if (!screen) { toast("Tag a mesh as 'screen' first", true); return; }
  const device = document.getElementById("device-select").value;
  const r = await fetch("/api/apply", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({device, screen_mesh: screen[0]})
  });
  const data = await r.json();
  if (r.ok) toast(`Manifest updated: ${device}.screen_mesh = "${screen[0]}"`);
  else toast(data.error || "Failed", true);
}

function showExport() {
  const out = {annotations, screen: null};
  const screen = Object.entries(annotations).find(([,v]) => v === "screen");
  if (screen) out.screen = screen[0];
  document.getElementById("export-content").textContent = JSON.stringify(out, null, 2);
  document.getElementById("export-panel").classList.add("visible");
}

function toast(msg, err) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.background = err ? "#ef4444" : "#22c55e";
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 2500);
}

init();
</script>
</body>
</html>"""


# ── Server ────────────────────────────────────────────────────────────────────


class AnnotatorHandler(http.server.BaseHTTPRequestHandler):
    preview_dir: Path
    candidates: list[dict]
    annotations: dict[str, str]
    annotations_path: Path
    model_name: str
    devices: list[str]
    current_device: str

    def log_message(self, fmt, *args):  # quieter logs
        pass

    # ── Routes ────────────────────────────────────────────────────────────

    def do_GET(self):
        if self.path == "/":
            self._respond(200, "text/html", _HTML.encode())
        elif self.path == "/api/data":
            payload = {
                "candidates": self.candidates,
                "annotations": self.annotations,
                "model": self.model_name,
                "devices": self.devices,
                "current_device": self.current_device,
            }
            self._respond(200, "application/json", json.dumps(payload).encode())
        elif self.path.startswith("/previews/"):
            fname = self.path.split("/")[-1]
            fpath = self.preview_dir / fname
            if fpath.is_file():
                self._respond(200, "image/png", fpath.read_bytes())
            else:
                self._respond(404, "text/plain", b"not found")
        else:
            self._respond(404, "text/plain", b"not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/annotations":
            # Validate: only known tag values
            valid_tags = {"screen", "bezel", "keyboard", "trackpad", "chassis", "other"}
            clean = {}
            for k, v in body.items():
                if isinstance(k, str) and isinstance(v, str) and v in valid_tags:
                    clean[k] = v
            AnnotatorHandler.annotations = clean
            self.annotations_path.write_text(json.dumps(clean, indent=2))
            self._respond(200, "application/json", b'{"ok":true}')

        elif self.path == "/api/apply":
            device = body.get("device", "")
            screen_mesh = body.get("screen_mesh", "")
            if not device or not screen_mesh:
                self._respond(
                    400,
                    "application/json",
                    json.dumps({"error": "device and screen_mesh required"}).encode(),
                )
                return
            # Sanitize inputs
            if not all(c.isalnum() or c in "_-" for c in device):
                self._respond(
                    400,
                    "application/json",
                    json.dumps({"error": "invalid device name"}).encode(),
                )
                return
            try:
                updated = []
                for mpath in (_MANIFEST, _ROOT_MANIFEST):
                    if mpath.is_file():
                        manifest = json.loads(mpath.read_text())
                        if device in manifest.get("devices", {}):
                            manifest["devices"][device]["screen_mesh"] = screen_mesh
                            mpath.write_text(json.dumps(manifest, indent=2) + "\n")
                            updated.append(str(mpath))
                self._respond(
                    200,
                    "application/json",
                    json.dumps({"ok": True, "updated": updated}).encode(),
                )
            except Exception as exc:
                self._respond(
                    500, "application/json", json.dumps({"error": str(exc)}).encode()
                )
        else:
            self._respond(404, "text/plain", b"not found")

    def _respond(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── Preview generation ────────────────────────────────────────────────────────


def _generate_previews(model_path: Path, output_dir: Path) -> list[dict]:
    """Run `_preview_all.py` via Blender to generate per-mesh previews."""
    script = _HERE / "_preview_all.py"
    if not script.is_file():
        print(f"ERROR: {script} not found")
        sys.exit(1)

    blender = "/Applications/Blender.app/Contents/MacOS/Blender"
    if not Path(blender).is_file():
        blender = "blender"

    cmd = [
        blender,
        "--background",
        "--python",
        str(script),
        "--",
        str(model_path),
        str(output_dir),
    ]
    print(f"Generating previews…  ({model_path.name})")
    subprocess.run(cmd, capture_output=True, timeout=300)

    cand_path = output_dir / "candidates.json"
    if not cand_path.is_file():
        print("ERROR: candidates.json was not generated")
        sys.exit(1)
    return json.loads(cand_path.read_text())


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Mesh annotator web app")
    parser.add_argument("model", nargs="?", help="Path to .glb/.usdz model")
    parser.add_argument("--previews", type=Path, help="Reuse existing preview dir")
    parser.add_argument(
        "--device", default="macbook_pro_16", help="Default device name"
    )
    parser.add_argument("--port", type=int, default=_PORT)
    args = parser.parse_args()

    # Resolve preview directory
    if args.previews and args.previews.is_dir():
        preview_dir = args.previews
        cand_path = preview_dir / "candidates.json"
        if not cand_path.is_file():
            print(f"ERROR: {cand_path} not found")
            sys.exit(1)
        candidates = json.loads(cand_path.read_text())
        model_name = "from existing previews"
    elif args.model:
        model_path = Path(args.model).resolve()
        if not model_path.is_file():
            print(f"ERROR: {model_path} not found")
            sys.exit(1)
        preview_dir = Path(tempfile.mkdtemp(prefix="mesh_annotator_"))
        candidates = _generate_previews(model_path, preview_dir)
        model_name = model_path.name
    else:
        parser.print_help()
        sys.exit(1)

    # Load manifest devices
    devices = []
    if _MANIFEST.is_file():
        manifest = json.loads(_MANIFEST.read_text())
        devices = list(manifest.get("devices", {}).keys())

    # Load saved annotations
    ann_path = preview_dir / "annotations.json"
    annotations = {}
    if ann_path.is_file():
        annotations = json.loads(ann_path.read_text())

    # Configure handler
    AnnotatorHandler.preview_dir = preview_dir
    AnnotatorHandler.candidates = candidates
    AnnotatorHandler.annotations = annotations
    AnnotatorHandler.annotations_path = ann_path
    AnnotatorHandler.model_name = model_name
    AnnotatorHandler.devices = devices
    AnnotatorHandler.current_device = args.device

    server = http.server.HTTPServer(("127.0.0.1", args.port), AnnotatorHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"\n  Mesh Annotator → {url}")
    print(f"  Previews: {preview_dir}")
    print("  Press Ctrl+C to stop\n")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
