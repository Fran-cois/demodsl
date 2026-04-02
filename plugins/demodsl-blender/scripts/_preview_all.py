#!/usr/bin/env python3
"""Blender inner script: render a preview for each flat candidate mesh.

Called by pick_screen.py via:
    blender --background --python _preview_all.py -- <model> <outdir>

Produces one PNG per flat candidate: preview_001_<name>.png
The target mesh is highlighted in bright green, everything else is ghost grey.
"""

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
    args = argv[sep + 1 :]
    model_path = args[0]
    output_dir = Path(args[1])
    output_dir.mkdir(parents=True, exist_ok=True)

    _clear_scene()

    ext = Path(model_path).suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=model_path)
    elif ext in (".usdz", ".usd", ".usdc", ".usda"):
        bpy.ops.wm.usd_import(filepath=model_path)

    # Remove placeholder cubes
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and obj.name == "Cube":
            if all(abs(d - 2.0) < 0.1 for d in obj.dimensions):
                bpy.data.objects.remove(obj, do_unlink=True)

    import mathutils

    all_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    xs = [o.matrix_world @ mathutils.Vector(c) for o in all_meshes for c in o.bound_box]
    if not xs:
        return
    min_v = mathutils.Vector(
        (min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs))
    )
    max_v = mathutils.Vector(
        (max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs))
    )
    max_dim = max(max_v - min_v)
    if max_dim > 0:
        sf = 0.35 / max_dim
        for obj in all_meshes:
            obj.scale *= sf
        bpy.context.view_layer.update()

    # Collect ALL meshes with geometry info
    flat = []
    for obj in all_meshes:
        d = sorted(obj.dimensions)
        thickness, mid, big = d[0], d[1], d[2]
        if big < 1e-6:
            continue
        aspect = big / mid if mid > 1e-6 else 0
        area = mid * big
        is_flat = thickness <= 0.05 * big
        # Detect texture name
        tex_name = ""
        for slot in obj.data.materials:
            if not slot or not slot.use_nodes or not slot.node_tree:
                continue
            for node in slot.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    tex_name = node.image.name
                    break
            if tex_name:
                break
        flat.append((obj, area, aspect, is_flat, thickness, tex_name))
    flat.sort(key=lambda x: -x[1])  # largest first

    # Materials
    grey_mat = bpy.data.materials.new(name="GreyGhost")
    grey_mat.use_nodes = True
    bsdf = grey_mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.2, 0.2, 0.2, 1)
    bsdf.inputs["Alpha"].default_value = 0.2

    green_mat = bpy.data.materials.new(name="Highlight")
    green_mat.use_nodes = True
    bsdf2 = green_mat.node_tree.nodes.get("Principled BSDF")
    bsdf2.inputs["Base Color"].default_value = (0.0, 1.0, 0.3, 1)
    bsdf2.inputs["Emission Color"].default_value = (0.0, 1.0, 0.3, 1)
    bsdf2.inputs["Emission Strength"].default_value = 5.0

    # Camera + light
    bpy.ops.object.camera_add(location=(0.35, -0.35, 0.35))
    cam = bpy.context.active_object
    cam.rotation_euler = (math.radians(55), 0, math.radians(45))
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(1, -1, 2))
    sun = bpy.context.active_object
    sun.data.energy = 3

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 8
    scene.render.resolution_x = 480
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    original_mats = {}
    for obj in all_meshes:
        original_mats[obj.name] = list(obj.data.materials)

    report = []
    for idx, (target, area, aspect, is_flat, thickness, tex_name) in enumerate(flat):
        # Set materials: target=green, rest=grey
        for obj in all_meshes:
            obj.data.materials.clear()
            if obj is target:
                obj.data.materials.append(green_mat)
            else:
                obj.data.materials.append(grey_mat)

        fname = f"preview_{idx + 1:03d}_{target.name[:20]}.png"
        scene.render.filepath = str(output_dir / fname)
        bpy.ops.render.render(write_still=True)

        report.append(
            {
                "index": idx + 1,
                "name": target.name,
                "file": fname,
                "area": round(area, 5),
                "aspect": round(aspect, 2),
                "flat": is_flat,
                "thickness": round(thickness, 5),
                "texture": tex_name,
                "verts": len(target.data.vertices),
                "dims": [
                    round(target.dimensions.x, 4),
                    round(target.dimensions.y, 4),
                    round(target.dimensions.z, 4),
                ],
            }
        )
        print(f"PREVIEW:{idx + 1}:{target.name}:{fname}")

    # Write report
    with open(output_dir / "candidates.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"REPORT:{output_dir / 'candidates.json'}")


main()
