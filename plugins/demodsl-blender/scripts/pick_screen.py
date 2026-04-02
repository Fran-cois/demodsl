#!/usr/bin/env python3
"""Interactive screen-mesh picker for GLB/USDZ 3D device models.

Usage:
    python pick_screen.py <model_file.glb>

Opens the model in headless Blender via a subprocess, lists every mesh with
its geometry stats, then lets you pick which one should be the screen.  It
renders a small preview for each candidate so you can visually confirm.

The script writes a JSON report to stdout with the chosen mesh name so it
can be pasted into manifest.json.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Blender inner script (runs inside bpy) ──────────────────────────────────

_BLENDER_SCRIPT = r"""
import bpy
import json
import math
import sys
from pathlib import Path

def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for img in bpy.data.images:
        bpy.data.images.remove(img)

def main():
    argv = sys.argv
    sep = argv.index("--") if "--" in argv else len(argv)
    args = argv[sep + 1:]
    
    model_path = args[0]
    output_dir = args[1]
    highlight_mesh = args[2] if len(args) > 3 else None
    mode = args[3] if len(args) > 3 else "list"
    
    _clear_scene()
    
    ext = Path(model_path).suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=model_path)
    elif ext in (".usdz", ".usd", ".usdc", ".usda"):
        bpy.ops.wm.usd_import(filepath=model_path)
    else:
        print(json.dumps({"error": f"Unsupported format: {ext}"}))
        return
    
    # Remove placeholder cubes
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and obj.name == "Cube":
            if all(abs(d - 2.0) < 0.1 for d in obj.dimensions):
                bpy.data.objects.remove(obj, do_unlink=True)
    
    all_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    
    # Normalise — same as render_device.py
    import mathutils
    xs = [o.matrix_world @ mathutils.Vector(c) for o in all_meshes for c in o.bound_box]
    if not xs:
        print(json.dumps({"error": "No meshes found"}))
        return
    min_v = mathutils.Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    max_v = mathutils.Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    max_dim = max(max_v - min_v)
    if max_dim > 0:
        sf = 0.35 / max_dim
        for obj in all_meshes:
            obj.scale *= sf
        bpy.context.view_layer.update()
    
    # Gather mesh info
    meshes_info = []
    for obj in sorted(all_meshes, key=lambda o: o.name):
        d = sorted(obj.dimensions)
        thickness, mid, big = d[0], d[1], d[2]
        area = mid * big
        aspect = big / mid if mid > 1e-6 else 0
        flat = thickness < 0.05 * big if big > 1e-6 else False
        
        # Detect if has image textures
        has_tex = False
        tex_names = []
        for slot in obj.data.materials:
            if not slot or not slot.use_nodes or not slot.node_tree:
                continue
            for node in slot.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    has_tex = True
                    tex_names.append(node.image.name)
        
        meshes_info.append({
            "name": obj.name,
            "dims": [round(obj.dimensions.x, 4), round(obj.dimensions.y, 4), round(obj.dimensions.z, 4)],
            "thickness": round(thickness, 5),
            "area": round(area, 5),
            "aspect": round(aspect, 2),
            "flat": flat,
            "has_tex": has_tex,
            "tex_names": tex_names[:3],
            "vertex_count": len(obj.data.vertices),
        })
    
    if mode == "list":
        print("MESH_JSON_START")
        print(json.dumps(meshes_info, indent=2))
        print("MESH_JSON_END")
        return
    
    # ── Preview mode: render a single mesh highlighted ────────────────────
    # Hide everything, then show only the target mesh in bright green
    target = bpy.data.objects.get(highlight_mesh)
    if not target:
        print(json.dumps({"error": f"Mesh '{highlight_mesh}' not found"}))
        return
    
    # Make all meshes semi-transparent grey
    grey_mat = bpy.data.materials.new(name="GreyGhost")
    grey_mat.use_nodes = True
    bsdf = grey_mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
    bsdf.inputs["Alpha"].default_value = 0.15
    grey_mat.blend_method = "BLEND" if hasattr(grey_mat, "blend_method") else "OPAQUE"
    
    green_mat = bpy.data.materials.new(name="Highlight")
    green_mat.use_nodes = True
    bsdf2 = green_mat.node_tree.nodes.get("Principled BSDF")
    bsdf2.inputs["Base Color"].default_value = (0.0, 1.0, 0.2, 1)
    bsdf2.inputs["Emission Color"].default_value = (0.0, 1.0, 0.2, 1)
    bsdf2.inputs["Emission Strength"].default_value = 3.0
    
    for obj in all_meshes:
        obj.data.materials.clear()
        if obj is target:
            obj.data.materials.append(green_mat)
        else:
            obj.data.materials.append(grey_mat)
    
    # Setup camera
    bpy.ops.object.camera_add(location=(0.4, -0.4, 0.3))
    cam = bpy.context.active_object
    cam.rotation_euler = (math.radians(65), 0, math.radians(45))
    bpy.context.scene.camera = cam
    
    # Light
    bpy.ops.object.light_add(type="SUN", location=(1, -1, 2))
    
    # Render settings
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = 640
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(Path(output_dir) / f"preview_{highlight_mesh}.png")
    
    bpy.ops.render.render(write_still=True)
    print(f"PREVIEW_SAVED:{scene.render.filepath}")


main()
"""


def _find_blender() -> str | None:
    import shutil

    candidates = [
        "blender",
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/snap/bin/blender",
    ]
    env = os.environ.get("DEMODSL_BLENDER_PATH")
    if env:
        candidates.insert(0, env)
    for c in candidates:
        if shutil.which(c) or Path(c).is_file():
            return c
    return None


def _run_blender(
    model_path: str, output_dir: str, mesh_name: str = "", mode: str = "list"
) -> str:
    blender = _find_blender()
    if not blender:
        print("ERROR: Blender not found. Set DEMODSL_BLENDER_PATH.", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(_BLENDER_SCRIPT)
        script_path = f.name

    try:
        cmd = [
            blender,
            "--background",
            "--python",
            script_path,
            "--",
            model_path,
            output_dir,
            mesh_name,
            mode,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout
    finally:
        os.unlink(script_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pick the screen mesh from a 3D model for DemoDSL rendering"
    )
    parser.add_argument("model", help="Path to .glb or .usdz model file")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Render a preview for each flat candidate",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for preview images (default: temp dir)",
    )
    args = parser.parse_args()

    model_path = str(Path(args.model).resolve())
    if not Path(model_path).exists():
        print(f"ERROR: File not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or tempfile.mkdtemp(prefix="demodsl_pick_")

    print(f"\n  Loading model: {Path(model_path).name}")
    print("  Analyzing meshes with Blender...\n")

    stdout = _run_blender(model_path, output_dir)

    # Parse mesh list
    if "MESH_JSON_START" not in stdout:
        print("ERROR: Failed to analyze model. Blender output:", file=sys.stderr)
        print(stdout, file=sys.stderr)
        sys.exit(1)

    json_str = stdout.split("MESH_JSON_START")[1].split("MESH_JSON_END")[0].strip()
    meshes = json.loads(json_str)

    # Display table
    flat_meshes = [m for m in meshes if m["flat"]]
    other_meshes = [m for m in meshes if not m["flat"]]

    print(f"  Found {len(meshes)} meshes total, {len(flat_meshes)} flat candidates:\n")
    print(
        f"  {'#':>3}  {'Name':<30}  {'Dims (X×Y×Z)':>20}  {'Area':>8}  {'Aspect':>7}  {'Verts':>6}  {'Texture':>10}"
    )
    print(
        f"  {'─' * 3}  {'─' * 30}  {'─' * 20}  {'─' * 8}  {'─' * 7}  {'─' * 6}  {'─' * 10}"
    )

    for i, m in enumerate(flat_meshes, 1):
        dims_str = f"{m['dims'][0]:.3f}×{m['dims'][1]:.3f}×{m['dims'][2]:.3f}"
        tex_str = m["tex_names"][0][:10] if m["tex_names"] else "—"
        marker = " ◀ likely" if i == len(flat_meshes) else ""  # largest
        print(
            f"  {i:>3}  {m['name']:<30}  {dims_str:>20}  {m['area']:>8.4f}  {m['aspect']:>7.2f}  {m['vertex_count']:>6}  {tex_str:>10}{marker}"
        )

    if other_meshes:
        print(f"\n  + {len(other_meshes)} non-flat meshes (body, hinge, buttons, etc.)")

    # Interactive pick
    print()
    choice = input("  Pick screen mesh # (or name, or Enter for largest): ").strip()

    if not choice:
        picked = flat_meshes[-1]  # largest
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(flat_meshes):
            picked = flat_meshes[idx]
        else:
            print(f"  Invalid index: {choice}")
            sys.exit(1)
    else:
        # Search by name
        picked = next((m for m in meshes if m["name"] == choice), None)
        if not picked:
            print(f"  Mesh '{choice}' not found")
            sys.exit(1)

    print(
        f"\n  Selected: '{picked['name']}' (area={picked['area']:.4f}, aspect={picked['aspect']:.1f})"
    )

    # Generate preview if requested
    if args.preview:
        print("  Rendering preview...")
        preview_out = _run_blender(model_path, output_dir, picked["name"], "preview")
        for line in preview_out.split("\n"):
            if line.startswith("PREVIEW_SAVED:"):
                preview_path = line.split(":", 1)[1]
                print(f"  Preview saved: {preview_path}")
                # Try to open it
                if sys.platform == "darwin":
                    subprocess.run(["open", preview_path], check=False)
                elif sys.platform.startswith("linux"):
                    subprocess.run(["xdg-open", preview_path], check=False)

    # Output for manifest
    print("\n  ┌─────────────────────────────────────────────┐")
    print("  │  Add to manifest.json:                      │")
    print(f'  │  "screen_mesh": "{picked["name"]}"')
    print("  └─────────────────────────────────────────────┘\n")


if __name__ == "__main__":
    main()
