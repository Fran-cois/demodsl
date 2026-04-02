"""mesh_picker.py — Visual mesh picker for DemoDSL 3D device rendering.

Imports a GLB model, renders each significant mesh solo (highlighted in green)
against the rest of the model (dimmed), and assembles a numbered contact sheet.
The user picks the mesh number that corresponds to the screen.

Usage (standalone):
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python mesh_picker.py -- \
        --model path/to/model.glb \
        --output /tmp/mesh_picker_sheet.png

The script prints a numbered legend and saves individual thumbnails + a montage.
"""

import sys
import math
import subprocess
from pathlib import Path

# ── Parse CLI args after "--" ─────────────────────────────────────────────────
argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
model_path = None
output_path = "/tmp/mesh_picker_sheet.png"
i = 0
while i < len(argv):
    if argv[i] == "--model" and i + 1 < len(argv):
        model_path = argv[i + 1]
        i += 2
    elif argv[i] == "--output" and i + 1 < len(argv):
        output_path = argv[i + 1]
        i += 2
    else:
        i += 1

if not model_path:
    print("ERROR: --model <path> is required")
    sys.exit(1)

import bpy  # noqa: E402
import mathutils  # noqa: E402

# ── Setup scene ───────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 1
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 8
scene.render.resolution_x = 480
scene.render.resolution_y = 320
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.world = bpy.data.worlds.new("World")
scene.world.use_nodes = True
bg_node = scene.world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.02, 0.02, 0.04, 1.0)
    bg_node.inputs["Strength"].default_value = 0.3

# ── Import model ──────────────────────────────────────────────────────────────
ext = Path(model_path).suffix.lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=model_path)
elif ext in (".usdz", ".usd"):
    bpy.ops.wm.usd_import(filepath=model_path)
else:
    print(f"ERROR: unsupported format {ext}")
    sys.exit(1)

all_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
# Remove placeholder cubes
for obj in list(all_meshes):
    if obj.name == "Cube" and all(abs(d - 2.0) < 0.1 for d in obj.dimensions):
        bpy.data.objects.remove(obj, do_unlink=True)
        all_meshes.remove(obj)

# ── Normalise scale ───────────────────────────────────────────────────────────
ws_pts = [o.matrix_world @ mathutils.Vector(c) for o in all_meshes for c in o.bound_box]
bb_min = mathutils.Vector(
    (min(v.x for v in ws_pts), min(v.y for v in ws_pts), min(v.z for v in ws_pts))
)
bb_max = mathutils.Vector(
    (max(v.x for v in ws_pts), max(v.y for v in ws_pts), max(v.z for v in ws_pts))
)
max_dim = max(bb_max - bb_min)
if max_dim > 0:
    sf = 0.35 / max_dim
    for obj in all_meshes:
        obj.scale *= sf
    bpy.context.view_layer.update()

# ── Filter significant meshes ─────────────────────────────────────────────────
# Only show meshes whose max dimension is > 3% of the model size (skip screws etc)
threshold = 0.35 * 0.03  # ~0.01
significant = []
for obj in all_meshes:
    if max(obj.dimensions) > threshold:
        significant.append(obj)
significant.sort(key=lambda o: max(o.dimensions), reverse=True)

print(f"\nModel: {Path(model_path).name}")
print(
    f"Total meshes: {len(all_meshes)}, significant (>{threshold:.4f}): {len(significant)}"
)


# ── Create materials ──────────────────────────────────────────────────────────
def make_emit_mat(name, color, strength=3.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    emit = nodes.new(type="ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1.0)
    emit.inputs["Strength"].default_value = strength
    out = nodes.new(type="ShaderNodeOutputMaterial")
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


highlight_mat = make_emit_mat("Highlight", (0.0, 1.0, 0.2), 4.0)
dim_mat = make_emit_mat("Dimmed", (0.08, 0.08, 0.10), 0.3)

# ── Camera setup ──────────────────────────────────────────────────────────────
cam_data = bpy.data.cameras.new("PickerCam")
cam_data.type = "PERSP"
cam_data.lens = 50
cam_obj = bpy.data.objects.new("PickerCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj
# Position camera: front-above, looking at model center
center = (bb_min + bb_max) / 2 * sf
cam_obj.location = (center.x, center.y - 0.5, center.z + 0.2)
direction = center - cam_obj.location
rot_quat = direction.to_track_quat("-Z", "Y")
cam_obj.rotation_euler = rot_quat.to_euler()

# Add a key light
light_data = bpy.data.lights.new("KeyLight", "AREA")
light_data.energy = 50
light_data.size = 0.5
light_obj = bpy.data.objects.new("KeyLight", light_data)
light_obj.location = (0.3, -0.4, 0.3)
bpy.context.collection.objects.link(light_obj)

# ── Save original materials ───────────────────────────────────────────────────
orig_mats = {}
for obj in all_meshes:
    orig_mats[obj.name] = list(obj.data.materials)

# ── Render each mesh highlighted ──────────────────────────────────────────────
thumb_dir = Path("/tmp/mesh_picker_thumbs")
thumb_dir.mkdir(exist_ok=True)

# Also render a reference (all meshes with original materials)
scene.render.filepath = str(thumb_dir / "00_reference.png")
bpy.ops.render.render(write_still=True)
print("\n  #00  REFERENCE (original model)")

legend = []
for idx, target in enumerate(significant, start=1):
    # Set all meshes to dim
    for obj in all_meshes:
        obj.hide_render = False
        obj.hide_viewport = False
        obj.data.materials.clear()
        obj.data.materials.append(dim_mat)

    # Highlight the target
    target.data.materials.clear()
    target.data.materials.append(highlight_mat)

    # Render
    fname = f"{idx:02d}_{target.name[:20]}.png"
    scene.render.filepath = str(thumb_dir / fname)
    bpy.ops.render.render(write_still=True)

    dims_str = (
        f"{target.dimensions.x:.3f}x{target.dimensions.y:.3f}x{target.dimensions.z:.3f}"
    )
    legend.append((idx, target.name, dims_str))
    print(f"  #{idx:02d}  {target.name:30s}  dims={dims_str}")

# ── Restore original materials ────────────────────────────────────────────────
for obj in all_meshes:
    obj.data.materials.clear()
    for mat in orig_mats.get(obj.name, []):
        obj.data.materials.append(mat)

# ── Assembly contact sheet with ffmpeg/ImageMagick ────────────────────────────
# Try montage (ImageMagick), fall back to ffmpeg tile filter
thumbs = sorted(thumb_dir.glob("*.png"))
n = len(thumbs)
cols = min(6, n)
rows = math.ceil(n / cols)

print(f"\nAssembling contact sheet: {cols}x{rows} grid from {n} thumbnails")

# Use ImageMagick montage if available
try:
    cmd = [
        "montage",
        *[str(t) for t in thumbs],
        "-tile",
        f"{cols}x{rows}",
        "-geometry",
        "480x320+4+4",
        "-background",
        "#111122",
        "-fill",
        "white",
        "-font",
        "Helvetica",
        "-pointsize",
        "14",
        "-label",
        "%t",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    print(f"\nCONTACT SHEET: {output_path}")
except (FileNotFoundError, subprocess.CalledProcessError):
    # Fallback: just list individual files
    print(f"\nImageMagick not found. Individual thumbnails in: {thumb_dir}/")
    print(f"View them with: open {thumb_dir}")

# ── Print legend ──────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("MESH PICKER LEGEND")
print("=" * 70)
for idx, name, dims in legend:
    print(f"  #{idx:02d}  {name:30s}  {dims}")
print("=" * 70)
print("\nChoose the mesh number that corresponds to the SCREEN.")
print("Then set 'screen_mesh' in manifest.json or pass --screen-mesh <name>")
