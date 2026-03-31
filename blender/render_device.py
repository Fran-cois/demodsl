"""Blender render script — executed by ``blender --background --python``.

Creates a detailed 3D device mockup from the manifest, maps the recorded
video onto its screen, applies camera animation and lighting, then renders
to an MP4 via ffmpeg.

Supports four device categories with varying geometry:

* **phone** — slab body + screen + Dynamic Island / punch-hole / notch +
  camera island + side buttons
* **tablet** — same as phone but scaled, no side buttons
* **laptop** — two-part body (lid + base with keyboard/trackpad) joined by
  hinge
* **monitor** — screen panel + stand neck + circular base

If a ``.blend`` file is listed in the manifest for a device it is loaded
instead of procedural generation.

Usage (called by blender_bridge.py, not directly)::

    blender --background --python blender/render_device.py -- \
        --params /tmp/params.json --output /tmp/output.mp4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Blender's embedded Python provides ``bpy``
import bpy  # type: ignore[import-untyped]

# ── Paths ─────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEVICES_DIR = _SCRIPT_DIR / "devices"
_MANIFEST_PATH = _DEVICES_DIR / "manifest.json"

# ── Lighting presets ──────────────────────────────────────────────────────────

_LIGHTING_PRESETS: dict[str, list[dict]] = {
    "studio": [
        {
            "type": "AREA",
            "energy": 200,
            "size": 2.0,
            "location": (1, -1, 2),
            "rotation": (0.8, 0, 0.5),
        },
        {
            "type": "AREA",
            "energy": 80,
            "size": 1.5,
            "location": (-1, -0.5, 1.5),
            "rotation": (0.6, 0, -0.4),
        },
        {
            "type": "AREA",
            "energy": 40,
            "size": 1.0,
            "location": (0, 1, 0.5),
            "rotation": (-0.3, 0, 0),
        },
    ],
    "natural": [
        {
            "type": "SUN",
            "energy": 5,
            "size": 0.0,
            "location": (2, -2, 4),
            "rotation": (0.6, 0, 0.3),
        },
    ],
    "dramatic": [
        {
            "type": "SPOT",
            "energy": 500,
            "size": 0.0,
            "location": (1.5, -1, 2.5),
            "rotation": (0.7, 0, 0.4),
        },
        {
            "type": "AREA",
            "energy": 20,
            "size": 1.0,
            "location": (-1, 1, 1),
            "rotation": (-0.4, 0, -0.3),
        },
    ],
    "cinematic": [
        # Key light — large soft area, slightly warm
        {
            "type": "AREA",
            "energy": 350,
            "size": 3.0,
            "location": (1.2, -1.5, 2.5),
            "rotation": (0.75, 0, 0.4),
            "color": (1.0, 0.95, 0.90),
        },
        # Fill light — cooler, lower energy
        {
            "type": "AREA",
            "energy": 60,
            "size": 2.0,
            "location": (-1.5, -0.8, 1.5),
            "rotation": (0.5, 0, -0.5),
            "color": (0.85, 0.90, 1.0),
        },
        # Rim / back light — edge separation
        {
            "type": "AREA",
            "energy": 200,
            "size": 1.2,
            "location": (-0.3, 1.5, 2.0),
            "rotation": (-0.6, 0, -0.1),
            "color": (1.0, 1.0, 1.0),
        },
        # Under-fill — subtle bounce from below
        {
            "type": "AREA",
            "energy": 25,
            "size": 2.5,
            "location": (0, -0.5, -0.3),
            "rotation": (math.pi, 0, 0),
            "color": (0.90, 0.92, 1.0),
        },
        # Top kicker — specular highlight on device top edge
        {
            "type": "SPOT",
            "energy": 120,
            "size": 0.0,
            "location": (0.2, -0.3, 3.0),
            "rotation": (0.15, 0, 0),
            "color": (1.0, 0.98, 0.95),
        },
    ],
}

# ── Material colour look-up ──────────────────────────────────────────────────

_MATERIAL_PROPS: dict[str, dict] = {
    "titanium": {
        "color": (0.55, 0.53, 0.50, 1.0),
        "metallic": 0.95,
        "roughness": 0.25,
    },
    "aluminum": {
        "color": (0.70, 0.70, 0.72, 1.0),
        "metallic": 0.90,
        "roughness": 0.30,
    },
    "plastic": {
        "color": (0.12, 0.12, 0.12, 1.0),
        "metallic": 0.00,
        "roughness": 0.50,
    },
    "glass": {
        "color": (0.90, 0.90, 0.92, 1.0),
        "metallic": 0.00,
        "roughness": 0.05,
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    """Parse arguments after the ``--`` separator in Blender's argv."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", required=True, help="Path to JSON params file")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    return parser.parse_args(argv)


def _load_manifest() -> dict:
    """Load device manifest from ``blender/devices/manifest.json``."""
    if _MANIFEST_PATH.exists():
        with open(_MANIFEST_PATH) as fh:
            return json.load(fh).get("devices", {})
    return {}


def _mm(val: float) -> float:
    """Convert millimetres to Blender units (metres)."""
    return val / 1000.0


def _clear_scene() -> None:
    """Remove all default objects."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)


def _hex_to_linear(hex_color: str) -> tuple[float, float, float, float]:
    """Convert hex colour string to linear sRGB tuple ``(r, g, b, a)``."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r**2.2, g**2.2, b**2.2, 1.0)


def _make_material(name: str, mat_type: str) -> bpy.types.Material:
    """Create a PBR material for *mat_type* (titanium / aluminum / …)."""
    props = _MATERIAL_PROPS.get(mat_type, _MATERIAL_PROPS["aluminum"])
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = props["color"]
    bsdf.inputs["Metallic"].default_value = props["metallic"]
    bsdf.inputs["Roughness"].default_value = props["roughness"]
    return mat


def _get_video_frame_count(video_path: str) -> int:
    """Probe video for frame count via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-count_packets",
        "-show_entries",
        "stream=nb_read_packets",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        return 300


def _get_video_fps(video_path: str) -> float:
    """Probe video for frame rate via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        num, den = result.stdout.strip().split("/")
        return int(num) / int(den)
    except (subprocess.TimeoutExpired, ValueError, ZeroDivisionError):
        return 30.0


# ── Video texture material ────────────────────────────────────────────────────


def _apply_video_material(obj: bpy.types.Object, video_path: str) -> None:
    """Replace (or add) a video-texture material on *obj*."""
    mat = bpy.data.materials.new(name="ScreenMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)

    tex = nodes.new(type="ShaderNodeTexImage")
    img = bpy.data.images.load(video_path)
    img.source = "MOVIE"
    tex.image = img

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    bsdf.inputs["Emission Strength"].default_value = 1.0

    out = nodes.new(type="ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ── .blend loader ─────────────────────────────────────────────────────────────


def _build_from_blend(blend_path: Path, video_path: str) -> None:
    """Load an external ``.blend`` file and map the video onto **Screen**."""
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    screen = bpy.data.objects.get("Screen")
    if not screen:
        print(  # noqa: T201
            f"WARNING: No 'Screen' object in {blend_path}, skipping video mapping"
        )
        return
    _apply_video_material(screen, video_path)


# ── Phone / tablet builder ────────────────────────────────────────────────────


def _build_phone_tablet(
    spec: dict, video_path: str, mat_type: str, *, add_buttons: bool = True
) -> bpy.types.Object:
    """Build a phone or tablet with body, screen, notch and camera island."""
    bw = _mm(spec["body_mm"]["w"])
    bh = _mm(spec["body_mm"]["h"])
    bd = _mm(spec["body_mm"]["d"])
    sw = _mm(spec["screen_mm"]["w"])
    sh = _mm(spec["screen_mm"]["h"])
    cr = _mm(spec.get("corner_radius_mm", 6.0))

    # ── Body ──────────────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    body = bpy.context.active_object
    body.name = "DeviceBody"
    body.scale = (bw / 2, bd / 2, bh / 2)
    bpy.ops.object.transform_apply(scale=True)

    bevel = body.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = cr
    bevel.segments = 12
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(60)

    body_mat = _make_material("BodyMat", mat_type)
    body.data.materials.append(body_mat)

    # ── Screen ────────────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, -(bd / 2 + 0.00005), 0),
        rotation=(math.pi / 2, 0, 0),
    )
    screen = bpy.context.active_object
    screen.name = "DeviceScreen"
    screen.scale = (sw / 2, sh / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    _apply_video_material(screen, video_path)
    screen.parent = body

    # ── Dynamic Island / Punch Hole / Notch ───────────────────────────────
    notch_type = spec.get("notch", "none")
    if notch_type == "dynamic_island":
        _add_dynamic_island(body, bw, bh, bd)
    elif notch_type == "punch_hole":
        _add_punch_hole(body, bw, bh, bd)
    elif notch_type == "notch_top":
        _add_notch(body, bw, bh, bd)

    # ── Camera island (back) ──────────────────────────────────────────────
    cam_island = spec.get("camera_island")
    if cam_island:
        _add_camera_island(body, bw, bh, bd, cam_island)

    # ── Side buttons (phones only) ────────────────────────────────────────
    if add_buttons:
        _add_side_buttons(body, bw, bh, bd, mat_type)

    return body


# ── Front-face features ──────────────────────────────────────────────────────


def _add_dynamic_island(
    body: bpy.types.Object, bw: float, bh: float, bd: float
) -> None:
    """Add a Dynamic Island pill shape on the front face near the top."""
    pill_w = bw * 0.25
    pill_h = bw * 0.05
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, -(bd / 2 + 0.0001), bh / 2 - bh * 0.04),
    )
    pill = bpy.context.active_object
    pill.name = "DynamicIsland"
    pill.scale = (pill_w / 2, 0.0004, pill_h / 2)
    bpy.ops.object.transform_apply(scale=True)

    bevel = pill.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = pill_h * 0.45
    bevel.segments = 8

    mat = bpy.data.materials.new(name="DynIslandMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.1
    pill.data.materials.append(mat)
    pill.parent = body


def _add_punch_hole(body: bpy.types.Object, bw: float, bh: float, bd: float) -> None:
    """Add a small circular punch-hole camera cutout on the front."""
    radius = bw * 0.015
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=0.0008,
        location=(0, -(bd / 2 + 0.0001), bh / 2 - bh * 0.03),
        rotation=(math.pi / 2, 0, 0),
    )
    hole = bpy.context.active_object
    hole.name = "PunchHole"
    mat = bpy.data.materials.new(name="PunchHoleMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
    hole.data.materials.append(mat)
    hole.parent = body


def _add_notch(body: bpy.types.Object, bw: float, bh: float, bd: float) -> None:
    """Add a classic notch (MacBook-style) at the top of the screen."""
    notch_w = bw * 0.20
    notch_h = bh * 0.015
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, -(bd / 2 + 0.0001), bh / 2 - notch_h / 2),
    )
    notch = bpy.context.active_object
    notch.name = "Notch"
    notch.scale = (notch_w / 2, 0.0004, notch_h / 2)
    bpy.ops.object.transform_apply(scale=True)

    bevel = notch.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = notch_h * 0.3
    bevel.segments = 6

    mat = bpy.data.materials.new(name="NotchMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
    notch.data.materials.append(mat)
    notch.parent = body


# ── Camera island (back face) ────────────────────────────────────────────────


def _add_camera_island(
    body: bpy.types.Object,
    bw: float,
    bh: float,
    bd: float,
    cfg: dict,
) -> None:
    """Add a camera island on the back of the device."""
    style = cfg.get("style", "single")
    side = cfg.get("side", "back_top_left")

    # Position on the back face
    x_off = -bw * 0.28 if "left" in side else (bw * 0.28 if "right" in side else 0)
    z_off = bh / 2 - bh * 0.12

    if style == "triple_vertical":
        island_w = bw * 0.22
        island_h = bh * 0.22
    elif style == "quad_grid":
        island_w = bw * 0.25
        island_h = bh * 0.20
    elif style == "dual_vertical":
        island_w = bw * 0.18
        island_h = bh * 0.18
    elif style == "pill_horizontal":
        island_w = bw * 0.55
        island_h = bh * 0.06
        x_off = 0  # centred for pill style
        z_off = bh / 2 - bh * 0.08
    else:  # single
        island_w = bw * 0.12
        island_h = bw * 0.12

    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(x_off, bd / 2 + 0.0003, z_off),
    )
    island = bpy.context.active_object
    island.name = "CameraIsland"
    island.scale = (island_w / 2, 0.001, island_h / 2)
    bpy.ops.object.transform_apply(scale=True)

    bevel = island.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = min(island_w, island_h) * 0.2
    bevel.segments = 8

    mat = bpy.data.materials.new(name="CamIslandMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.15
    island.data.materials.append(mat)
    island.parent = body

    # Lens circles
    lens_positions = _get_lens_positions(style, island_w, island_h)
    for i, (lx, lz) in enumerate(lens_positions):
        lens_r = min(island_w, island_h) * 0.12
        bpy.ops.mesh.primitive_cylinder_add(
            radius=lens_r,
            depth=0.0005,
            location=(x_off + lx, bd / 2 + 0.0008, z_off + lz),
            rotation=(math.pi / 2, 0, 0),
        )
        lens = bpy.context.active_object
        lens.name = f"Lens_{i}"
        lens_mat = bpy.data.materials.new(name=f"LensMat_{i}")
        lens_mat.use_nodes = True
        bsdf = lens_mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.05, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.3
        bsdf.inputs["Roughness"].default_value = 0.05
        lens.data.materials.append(lens_mat)
        lens.parent = body


def _get_lens_positions(style: str, iw: float, ih: float) -> list[tuple[float, float]]:
    """Return ``(x_offset, z_offset)`` for each lens relative to island centre."""
    if style == "triple_vertical":
        s = min(iw, ih) * 0.28
        return [(0, s), (-s * 0.5, -s * 0.4), (s * 0.5, -s * 0.4)]
    if style == "quad_grid":
        s = min(iw, ih) * 0.25
        return [(-s, s), (s, s), (-s, -s), (s, -s)]
    if style == "dual_vertical":
        s = ih * 0.22
        return [(0, s), (0, -s)]
    if style == "pill_horizontal":
        s = iw * 0.28
        return [(-s, 0), (s, 0)]
    return [(0, 0)]  # single


# ── Side buttons ──────────────────────────────────────────────────────────────


def _add_side_buttons(
    body: bpy.types.Object, bw: float, bh: float, bd: float, mat_type: str
) -> None:
    """Add power + volume buttons on the sides of a phone."""
    btn_mat = _make_material("ButtonMat", mat_type)
    btn_w = 0.0005

    # Power button — right side
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(bw / 2 + btn_w / 2, 0, bh * 0.12),
    )
    pwr = bpy.context.active_object
    pwr.name = "PowerButton"
    pwr.scale = (btn_w / 2, bd * 0.15, bh * 0.06 / 2)
    bpy.ops.object.transform_apply(scale=True)
    bevel = pwr.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = 0.0002
    bevel.segments = 4
    pwr.data.materials.append(btn_mat)
    pwr.parent = body

    # Volume up — left side
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(-(bw / 2 + btn_w / 2), 0, bh * 0.18),
    )
    vol_up = bpy.context.active_object
    vol_up.name = "VolUp"
    vol_up.scale = (btn_w / 2, bd * 0.12, bh * 0.04)
    bpy.ops.object.transform_apply(scale=True)
    vol_up.data.materials.append(btn_mat)
    vol_up.parent = body

    # Volume down — left side
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(-(bw / 2 + btn_w / 2), 0, bh * 0.10),
    )
    vol_dn = bpy.context.active_object
    vol_dn.name = "VolDown"
    vol_dn.scale = (btn_w / 2, bd * 0.12, bh * 0.04)
    bpy.ops.object.transform_apply(scale=True)
    vol_dn.data.materials.append(btn_mat)
    vol_dn.parent = body


# ── Laptop builder ────────────────────────────────────────────────────────────


def _build_laptop(spec: dict, video_path: str, mat_type: str) -> bpy.types.Object:
    """Build laptop: lid (screen) + base (keyboard / trackpad) + hinge."""
    bw = _mm(spec["body_mm"]["w"])
    bh = _mm(spec["body_mm"]["h"])
    bd = _mm(spec["body_mm"]["d"])
    sw = _mm(spec["screen_mm"]["w"])
    sh = _mm(spec["screen_mm"]["h"])
    bezel = _mm(spec.get("bezel_mm", 5.0))
    cr = _mm(spec.get("corner_radius_mm", 4.0))
    hinge_angle = math.radians(spec.get("hinge_angle_deg", 110))

    body_mat = _make_material("LaptopBodyMat", mat_type)
    half_d = bd / 2

    # ── Base (keyboard tray) ──────────────────────────────────────────────
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    base = bpy.context.active_object
    base.name = "LaptopBase"
    base.scale = (bw / 2, bh / 2, half_d / 2)
    bpy.ops.object.transform_apply(scale=True)
    base.rotation_euler = (math.pi / 2, 0, 0)

    bevel = base.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = cr
    bevel.segments = 6
    base.data.materials.append(body_mat)

    # ── Keyboard area ─────────────────────────────────────────────────────
    kb_w = bw * 0.85
    kb_h = bh * 0.45
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, -bh * 0.1, half_d / 2 + 0.0001),
    )
    kb = bpy.context.active_object
    kb.name = "Keyboard"
    kb.scale = (kb_w / 2, kb_h / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    kb.rotation_euler = (math.pi / 2, 0, 0)

    kb_mat = bpy.data.materials.new(name="KBMat")
    kb_mat.use_nodes = True
    kb_bsdf = kb_mat.node_tree.nodes["Principled BSDF"]
    kb_bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1.0)
    kb_bsdf.inputs["Roughness"].default_value = 0.6
    kb.data.materials.append(kb_mat)
    kb.parent = base

    # ── Trackpad ──────────────────────────────────────────────────────────
    tp_w = bw * 0.35
    tp_h = bh * 0.22
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, -bh * 0.42, half_d / 2 + 0.0001),
    )
    tp = bpy.context.active_object
    tp.name = "Trackpad"
    tp.scale = (tp_w / 2, tp_h / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    tp.rotation_euler = (math.pi / 2, 0, 0)

    tp_mat = bpy.data.materials.new(name="TrackpadMat")
    tp_mat.use_nodes = True
    tp_bsdf = tp_mat.node_tree.nodes["Principled BSDF"]
    tp_bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.08, 1.0)
    tp_bsdf.inputs["Roughness"].default_value = 0.1
    tp.data.materials.append(tp_mat)
    tp.parent = base

    # ── Lid (screen housing) ──────────────────────────────────────────────
    lid_h = sh + bezel * 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    lid = bpy.context.active_object
    lid.name = "DeviceBody"
    lid.scale = (bw / 2, half_d / 4, lid_h / 2)
    bpy.ops.object.transform_apply(scale=True)

    bevel = lid.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = cr
    bevel.segments = 6
    lid.data.materials.append(body_mat)

    # Hinge rotation at back edge of base
    hinge_y = bh / 2
    lid.location = (0, hinge_y, 0)
    lid.rotation_euler = (-(math.pi - hinge_angle), 0, 0)

    # ── Screen on lid ─────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, -half_d / 4 - 0.0001, 0),
        rotation=(math.pi / 2, 0, 0),
    )
    screen = bpy.context.active_object
    screen.name = "DeviceScreen"
    screen.scale = (sw / 2, sh / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    _apply_video_material(screen, video_path)
    screen.parent = lid

    # Notch on lid (e.g. MacBook)
    if spec.get("notch") == "notch_top":
        _add_notch(lid, bw, lid_h, half_d / 2)

    return lid


# ── Monitor builder ───────────────────────────────────────────────────────────


def _build_monitor(spec: dict, video_path: str, mat_type: str) -> bpy.types.Object:
    """Build a desktop monitor with panel + stand neck + circular base."""
    bw = _mm(spec["body_mm"]["w"])
    bh = _mm(spec["body_mm"]["h"])
    bd = _mm(spec["body_mm"]["d"])
    sw = _mm(spec["screen_mm"]["w"])
    sh = _mm(spec["screen_mm"]["h"])
    cr = _mm(spec.get("corner_radius_mm", 3.0))

    body_mat = _make_material("MonitorMat", mat_type)
    panel_z = bh / 2 + 0.06  # raised above stand

    # ── Panel ─────────────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, panel_z))
    panel = bpy.context.active_object
    panel.name = "DeviceBody"
    panel.scale = (bw / 2, bd / 8, bh / 2)
    bpy.ops.object.transform_apply(scale=True)

    bevel = panel.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = cr
    bevel.segments = 4
    panel.data.materials.append(body_mat)

    # ── Screen ────────────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, -(bd / 8 + 0.0001), panel_z),
        rotation=(math.pi / 2, 0, 0),
    )
    screen = bpy.context.active_object
    screen.name = "DeviceScreen"
    screen.scale = (sw / 2, sh / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    _apply_video_material(screen, video_path)
    screen.parent = panel

    # ── Stand neck ────────────────────────────────────────────────────────
    neck_h = 0.05
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, 0, neck_h / 2),
    )
    neck = bpy.context.active_object
    neck.name = "StandNeck"
    neck.scale = (0.015, 0.015, neck_h / 2)
    bpy.ops.object.transform_apply(scale=True)
    neck.data.materials.append(body_mat)
    neck.parent = panel

    # ── Stand base ────────────────────────────────────────────────────────
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.06, depth=0.005, location=(0, 0, -0.005)
    )
    stand_base = bpy.context.active_object
    stand_base.name = "StandBase"
    stand_base.data.materials.append(body_mat)
    stand_base.parent = panel

    return panel


# ── Scene furniture ───────────────────────────────────────────────────────────


def _setup_lighting(preset: str) -> None:
    """Add lights according to the chosen preset."""
    lights = _LIGHTING_PRESETS.get(preset, _LIGHTING_PRESETS["studio"])
    for i, cfg in enumerate(lights):
        light_data = bpy.data.lights.new(name=f"Light_{i}", type=cfg["type"])
        light_data.energy = cfg["energy"]
        if hasattr(light_data, "size"):
            light_data.size = cfg.get("size", 1.0)
        if "color" in cfg:
            light_data.color = cfg["color"]
        light_obj = bpy.data.objects.new(name=f"Light_{i}", object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = cfg["location"]
        light_obj.rotation_euler = cfg["rotation"]


def _camera_scale(category: str) -> float:
    """Return a camera distance multiplier per device category."""
    return {"laptop": 0.25, "monitor": 0.40, "tablet": 0.20}.get(category, 0.15)


def _setup_camera(params: dict, category: str) -> bpy.types.Object:
    """Create and position the camera."""
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    dist = params.get("camera_distance", 1.5)
    height = params.get("camera_height", 0.0)
    scale = _camera_scale(category)

    cam_obj.location = (0, -dist * scale, height * 0.05)
    cam_obj.rotation_euler = (math.pi / 2, 0, 0)
    return cam_obj


def _setup_camera_animation(
    cam: bpy.types.Object, params: dict, frame_count: int, category: str
) -> None:
    """Animate the camera based on the chosen animation preset."""
    animation = params.get("camera_animation", "orbit_smooth")
    scale = _camera_scale(category)
    dist = params.get("camera_distance", 1.5) * scale
    height = params.get("camera_height", 0.0) * 0.05
    speed = params.get("rotation_speed", 1.0)

    if animation == "static":
        return

    # Create an empty at origin for the camera to track
    bpy.ops.object.empty_add(location=(0, 0, 0))
    target = bpy.context.active_object
    target.name = "CameraTarget"
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    if animation == "orbit_smooth":
        total_angle = speed * 2 * math.pi * (frame_count / (30 * 8))
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            angle = -total_angle / 2 + total_angle * t
            cam.location = (
                dist * math.sin(angle),
                -dist * math.cos(angle),
                height,
            )
            cam.keyframe_insert(data_path="location", frame=frame + 1)

    elif animation == "zoom_in":
        cam.location = (0, -dist * 1.5, height)
        cam.keyframe_insert(data_path="location", frame=1)
        cam.location = (0, -dist * 0.8, height)
        cam.keyframe_insert(data_path="location", frame=frame_count)

    elif animation == "zoom_out":
        cam.location = (0, -dist * 0.8, height)
        cam.keyframe_insert(data_path="location", frame=1)
        cam.location = (0, -dist * 1.6, height)
        cam.keyframe_insert(data_path="location", frame=frame_count)

    elif animation == "dolly_zoom":
        # Hitchcock effect: camera moves in while FOV widens (or vice-versa)
        cam_data = cam.data
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            # Ease-in-out with smoothstep
            st = t * t * (3.0 - 2.0 * t)
            d = dist * 1.4 - st * dist * 0.6  # dolly in
            fov = 35 + st * 30  # widen FOV from 35mm to 65mm
            cam.location = (0, -d, height)
            cam_data.lens = fov
            cam.keyframe_insert(data_path="location", frame=frame + 1)
            cam_data.keyframe_insert(data_path="lens", frame=frame + 1)

    elif animation == "crane_up":
        # Starts low, rises smoothly while keeping the device framed
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            st = t * t * (3.0 - 2.0 * t)  # smoothstep
            h = height - 0.15 + st * 0.35
            d = dist * (1.0 + 0.1 * (1.0 - st))
            cam.location = (0, -d, h)
            cam.keyframe_insert(data_path="location", frame=frame + 1)

    elif animation == "fly_around":
        # Full 360° orbit with height variation (figure-8 feel)
        total_angle = speed * 2 * math.pi
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            angle = total_angle * t
            h_wave = height + 0.08 * math.sin(t * math.pi * 2)
            d_wave = dist * (1.0 + 0.08 * math.sin(t * math.pi * 4))
            cam.location = (
                d_wave * math.sin(angle),
                -d_wave * math.cos(angle),
                h_wave,
            )
            cam.keyframe_insert(data_path="location", frame=frame + 1)

    elif animation == "push_in":
        # Slow push-in with slight lateral drift for parallax feeling
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            st = t * t * (3.0 - 2.0 * t)
            d = dist * (1.3 - 0.5 * st)
            lateral = 0.06 * math.sin(t * math.pi)
            cam.location = (lateral, -d, height)
            cam.keyframe_insert(data_path="location", frame=frame + 1)

    elif animation == "tilt":
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            tilt = math.sin(t * math.pi) * 0.15
            cam.location = (0, -dist, height + tilt * 0.05)
            cam.rotation_euler = (math.pi / 2 - tilt, 0, 0)
            cam.keyframe_insert(data_path="location", frame=frame + 1)
            cam.keyframe_insert(data_path="rotation_euler", frame=frame + 1)


def _setup_background(params: dict) -> None:
    """Configure scene background using the chosen preset, colour or HDRI.

    Presets build procedural shader-node graphs so no external asset is
    needed.  The ``background_hdri`` parameter always takes priority when
    it points to an existing file.
    """
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear existing nodes for a clean graph
    for n in list(nodes):
        nodes.remove(n)

    bg_node = nodes.new(type="ShaderNodeBackground")
    output_node = nodes.new(type="ShaderNodeOutputWorld")
    links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

    # HDRI takes highest priority
    hdri = params.get("background_hdri")
    if hdri and os.path.isfile(hdri):
        env_tex = nodes.new(type="ShaderNodeTexEnvironment")
        env_tex.image = bpy.data.images.load(hdri)
        links.new(env_tex.outputs["Color"], bg_node.inputs["Color"])
        return

    preset = params.get("background_preset", "solid")
    color1 = _hex_to_linear(params.get("background_color", "#1a1a1a"))
    color2_hex = params.get("background_gradient_color")

    if preset == "solid" or preset not in _BG_PRESET_BUILDERS:
        bg_node.inputs["Color"].default_value = color1
    else:
        _BG_PRESET_BUILDERS[preset](nodes, links, bg_node, color1, color2_hex)


# ── Background preset builders ───────────────────────────────────────────────


def _bg_gradient(
    nodes,
    links,
    bg_node,
    color1,
    color2_hex,
) -> None:
    """Vertical gradient between *color1* and a second colour."""
    color2 = _hex_to_linear(color2_hex) if color2_hex else _lighten(color1, 0.35)

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    sep = nodes.new(type="ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Generated"], sep.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = color1
    ramp.color_ramp.elements[1].color = color2
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])


def _bg_studio_floor(
    nodes,
    links,
    bg_node,
    color1,
    color2_hex,
) -> None:
    """Dark upper half with a slightly lighter lower half — classic product
    studio look.  Also adds a reflective ground plane.
    """
    color_floor = _hex_to_linear(color2_hex) if color2_hex else _lighten(color1, 0.12)

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    sep = nodes.new(type="ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Generated"], sep.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = color_floor
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = color1
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])

    # Reflective ground plane
    _add_reflective_ground()


def _bg_spotlight(
    nodes,
    links,
    bg_node,
    color1,
    color2_hex,
) -> None:
    """Radial falloff centred behind the device — simulates a spot on a
    dark backdrop.
    """
    bright = _hex_to_linear(color2_hex) if color2_hex else _lighten(color1, 0.45)

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.inputs["Location"].default_value = (0.5, 0.35, 0.0)
    links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])

    gradient = nodes.new(type="ShaderNodeTexGradient")
    gradient.gradient_type = "SPHERICAL"
    links.new(mapping.outputs["Vector"], gradient.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = bright
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = color1
    links.new(gradient.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])


def _bg_warm_gradient(
    nodes,
    links,
    bg_node,
    color1,
    _color2_hex,
) -> None:
    """Warm-toned gradient (deep burgundy → amber)."""
    c_bottom = _hex_to_linear("#1a0a0a")
    c_top = _hex_to_linear("#4a2800")

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    sep = nodes.new(type="ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Generated"], sep.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = c_bottom
    ramp.color_ramp.elements[1].color = c_top
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])


def _bg_cool_gradient(
    nodes,
    links,
    bg_node,
    color1,
    _color2_hex,
) -> None:
    """Cool-toned gradient (dark navy → steel blue)."""
    c_bottom = _hex_to_linear("#0a0a1a")
    c_top = _hex_to_linear("#1a2a4a")

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    sep = nodes.new(type="ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Generated"], sep.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = c_bottom
    ramp.color_ramp.elements[1].color = c_top
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])


def _bg_sunset(
    nodes,
    links,
    bg_node,
    color1,
    _color2_hex,
) -> None:
    """Three-stop gradient: deep purple → orange → dark sky."""
    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    sep = nodes.new(type="ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Generated"], sep.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = _hex_to_linear("#1a0520")
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = _hex_to_linear("#0a0a20")
    # Insert middle stop
    mid = ramp.color_ramp.elements.new(0.4)
    mid.color = _hex_to_linear("#cc4400")
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])


def _bg_abstract_noise(
    nodes,
    links,
    bg_node,
    color1,
    color2_hex,
) -> None:
    """Subtle noise-based texture for an abstract backdrop."""
    color2 = _hex_to_linear(color2_hex) if color2_hex else _lighten(color1, 0.20)

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.7
    links.new(tex_coord.outputs["Generated"], noise.inputs["Vector"])

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = color1
    ramp.color_ramp.elements[1].color = color2
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg_node.inputs["Color"])


def _bg_space(
    nodes,
    links,
    bg_node,
    _color1,
    _color2_hex,
) -> None:
    """Deep-space backdrop: star field + nebula clouds + ambient glow."""
    tex_coord = nodes.new(type="ShaderNodeTexCoord")

    # ── Star field (tiny bright dots via high-scale noise + sharp threshold)
    star_noise = nodes.new(type="ShaderNodeTexNoise")
    star_noise.inputs["Scale"].default_value = 800.0
    star_noise.inputs["Detail"].default_value = 0.0
    star_noise.inputs["Roughness"].default_value = 0.0
    links.new(tex_coord.outputs["Generated"], star_noise.inputs["Vector"])

    star_ramp = nodes.new(type="ShaderNodeValToRGB")
    star_ramp.color_ramp.elements[0].position = 0.0
    star_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    star_ramp.color_ramp.elements[1].position = 0.72
    star_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    star_ramp.color_ramp.interpolation = "EASE"
    links.new(star_noise.outputs["Fac"], star_ramp.inputs["Fac"])

    # Star color variation (warm / cool)
    star_color_noise = nodes.new(type="ShaderNodeTexNoise")
    star_color_noise.inputs["Scale"].default_value = 200.0
    star_color_noise.inputs["Detail"].default_value = 2.0
    links.new(tex_coord.outputs["Generated"], star_color_noise.inputs["Vector"])

    star_color_ramp = nodes.new(type="ShaderNodeValToRGB")
    star_color_ramp.color_ramp.elements[0].position = 0.0
    star_color_ramp.color_ramp.elements[0].color = (0.9, 0.92, 1.0, 1)  # cool white
    star_color_ramp.color_ramp.elements[1].position = 1.0
    star_color_ramp.color_ramp.elements[1].color = (1.0, 0.85, 0.7, 1)  # warm yellow
    links.new(star_color_noise.outputs["Fac"], star_color_ramp.inputs["Fac"])

    star_multiply = nodes.new(type="ShaderNodeMixRGB")
    star_multiply.blend_type = "MULTIPLY"
    star_multiply.inputs["Fac"].default_value = 1.0
    links.new(star_ramp.outputs["Color"], star_multiply.inputs["Color1"])
    links.new(star_color_ramp.outputs["Color"], star_multiply.inputs["Color2"])

    # Boost star brightness
    star_bright = nodes.new(type="ShaderNodeMixRGB")
    star_bright.blend_type = "MULTIPLY"
    star_bright.inputs["Fac"].default_value = 1.0
    star_bright.inputs["Color2"].default_value = (3.0, 3.0, 3.0, 1.0)
    links.new(star_multiply.outputs["Color"], star_bright.inputs["Color1"])

    # ── Nebula (large-scale coloured clouds)
    nebula_noise = nodes.new(type="ShaderNodeTexNoise")
    nebula_noise.inputs["Scale"].default_value = 1.5
    nebula_noise.inputs["Detail"].default_value = 8.0
    nebula_noise.inputs["Roughness"].default_value = 0.65
    links.new(tex_coord.outputs["Generated"], nebula_noise.inputs["Vector"])

    nebula_ramp = nodes.new(type="ShaderNodeValToRGB")
    nebula_ramp.color_ramp.elements[0].position = 0.35
    nebula_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    nebula_ramp.color_ramp.elements[1].position = 0.65
    nebula_ramp.color_ramp.elements[1].color = _hex_to_linear("#1a0530")  # deep purple
    mid = nebula_ramp.color_ramp.elements.new(0.85)
    mid.color = _hex_to_linear("#0a1535")  # dark blue
    links.new(nebula_noise.outputs["Fac"], nebula_ramp.inputs["Fac"])

    # ── Combine: nebula base + stars on top (screen blend)
    combine = nodes.new(type="ShaderNodeMixRGB")
    combine.blend_type = "SCREEN"
    combine.inputs["Fac"].default_value = 1.0
    links.new(nebula_ramp.outputs["Color"], combine.inputs["Color1"])
    links.new(star_bright.outputs["Color"], combine.inputs["Color2"])

    # ── Subtle ambient glow behind device
    glow_gradient = nodes.new(type="ShaderNodeTexGradient")
    glow_gradient.gradient_type = "SPHERICAL"
    glow_mapping = nodes.new(type="ShaderNodeMapping")
    glow_mapping.inputs["Location"].default_value = (0.5, 0.4, 0.0)
    glow_mapping.inputs["Scale"].default_value = (1.5, 1.5, 1.0)
    links.new(tex_coord.outputs["Generated"], glow_mapping.inputs["Vector"])
    links.new(glow_mapping.outputs["Vector"], glow_gradient.inputs["Vector"])

    glow_ramp = nodes.new(type="ShaderNodeValToRGB")
    glow_ramp.color_ramp.elements[0].position = 0.0
    glow_ramp.color_ramp.elements[0].color = _hex_to_linear("#0d0825")  # faint blue
    glow_ramp.color_ramp.elements[1].position = 0.6
    glow_ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    links.new(glow_gradient.outputs["Fac"], glow_ramp.inputs["Fac"])

    final = nodes.new(type="ShaderNodeMixRGB")
    final.blend_type = "ADD"
    final.inputs["Fac"].default_value = 1.0
    links.new(combine.outputs["Color"], final.inputs["Color1"])
    links.new(glow_ramp.outputs["Color"], final.inputs["Color2"])

    links.new(final.outputs["Color"], bg_node.inputs["Color"])
    bg_node.inputs["Strength"].default_value = 1.0


def _lighten(color: tuple, amount: float) -> tuple[float, float, float, float]:
    """Lighten a linear RGBA colour by *amount* (0–1)."""
    return (
        min(color[0] + amount, 1.0),
        min(color[1] + amount, 1.0),
        min(color[2] + amount, 1.0),
        1.0,
    )


def _add_reflective_ground() -> None:
    """Add a glossy ground plane for studio-floor preset."""
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -0.08))
    ground = bpy.context.active_object
    ground.name = "StudioFloor"
    mat = bpy.data.materials.new(name="StudioFloorMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.08
    ground.data.materials.append(mat)


_BG_PRESET_BUILDERS: dict[str, callable] = {
    "gradient": _bg_gradient,
    "studio_floor": _bg_studio_floor,
    "spotlight": _bg_spotlight,
    "warm_gradient": _bg_warm_gradient,
    "cool_gradient": _bg_cool_gradient,
    "sunset": _bg_sunset,
    "abstract_noise": _bg_abstract_noise,
    "space": _bg_space,
}


def _setup_shadow_catcher(params: dict) -> None:
    """Add a shadow-catching ground plane if shadows are enabled."""
    if not params.get("shadow", True):
        return
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, -0.08))
    ground = bpy.context.active_object
    ground.name = "ShadowCatcher"
    ground.is_shadow_catcher = True


# ── Cinematic features ────────────────────────────────────────────────────────


def _setup_depth_of_field(cam: bpy.types.Object, params: dict) -> None:
    """Enable depth-of-field on the camera with a focus target at origin."""
    if not params.get("depth_of_field", False):
        return
    cam_data = cam.data
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = params.get("dof_aperture", 2.8)

    # Focus on the device at origin
    target = bpy.data.objects.get("CameraTarget")
    if target:
        cam_data.dof.focus_object = target
    else:
        cam_data.dof.focus_distance = abs(cam.location.y)


def _setup_motion_blur(params: dict) -> None:
    """Enable per-object motion blur (Cycles or EEVEE)."""
    if not params.get("motion_blur", False):
        return
    scene = bpy.context.scene
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5  # 180° shutter angle


def _setup_compositing(params: dict) -> None:
    """Build a compositing node graph for bloom, glare, color grading,
    vignette, and film grain — the post-processing that makes a TV ad."""
    use_bloom = params.get("bloom", False)
    grain_amount = params.get("film_grain", 0.0)

    if not use_bloom and grain_amount <= 0:
        return

    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree
    nodes = tree.nodes
    links = tree.links

    # Clear default compositing nodes
    for n in list(nodes):
        nodes.remove(n)

    # Render Layers → pipeline → Composite
    rl = nodes.new(type="CompositorNodeRLayers")
    rl.location = (0, 300)

    last_output = rl.outputs["Image"]

    # ── Glare / bloom ─────────────────────────────────────────────────────
    if use_bloom:
        glare = nodes.new(type="CompositorNodeGlare")
        glare.glare_type = "FOG_GLOW"
        glare.quality = "HIGH"
        glare.mix = 0.0  # additive
        glare.threshold = 0.8
        glare.size = 7
        glare.location = (300, 300)
        links.new(last_output, glare.inputs["Image"])
        last_output = glare.outputs["Image"]

        # Mix bloom back (screen blend for subtlety)
        mix_bloom = nodes.new(type="CompositorNodeMixRGB")
        mix_bloom.blend_type = "SCREEN"
        mix_bloom.inputs["Fac"].default_value = 0.3
        mix_bloom.location = (500, 300)
        links.new(rl.outputs["Image"], mix_bloom.inputs[1])
        links.new(last_output, mix_bloom.inputs[2])
        last_output = mix_bloom.outputs["Image"]

    # ── Color grading (lift / gamma / gain) ───────────────────────────────
    if use_bloom or grain_amount > 0:
        ccomb = nodes.new(type="CompositorNodeColorCorrection")
        ccomb.location = (700, 300)
        # Subtle warm push in midtones, cool shadows
        ccomb.midtones_gain = 1.05
        ccomb.shadows_saturation = 0.95
        ccomb.highlights_gain = 1.02
        links.new(last_output, ccomb.inputs["Image"])
        last_output = ccomb.outputs["Image"]

    # ── Vignette ──────────────────────────────────────────────────────────
    if use_bloom:
        ellipse = nodes.new(type="CompositorNodeEllipseMask")
        ellipse.width = 0.85
        ellipse.height = 0.85
        ellipse.location = (900, 100)

        blur_vig = nodes.new(type="CompositorNodeBlur")
        blur_vig.size_x = 200
        blur_vig.size_y = 200
        blur_vig.use_relative = False
        blur_vig.location = (1100, 100)
        links.new(ellipse.outputs["Mask"], blur_vig.inputs["Image"])

        mix_vig = nodes.new(type="CompositorNodeMixRGB")
        mix_vig.blend_type = "MULTIPLY"
        mix_vig.inputs["Fac"].default_value = 0.25
        mix_vig.location = (1100, 300)
        links.new(last_output, mix_vig.inputs[1])
        links.new(blur_vig.outputs["Image"], mix_vig.inputs[2])
        last_output = mix_vig.outputs["Image"]

    # ── Film grain ────────────────────────────────────────────────────────
    if grain_amount > 0:
        # Use a noise texture node to simulate grain
        mix_grain = nodes.new(type="CompositorNodeMixRGB")
        mix_grain.blend_type = "OVERLAY"
        mix_grain.inputs["Fac"].default_value = grain_amount * 0.15
        mix_grain.location = (1300, 300)
        links.new(last_output, mix_grain.inputs[1])
        # Reuse last as both inputs — Blender adds temporal noise on each frame
        links.new(last_output, mix_grain.inputs[2])
        last_output = mix_grain.outputs["Image"]

    # ── Output ────────────────────────────────────────────────────────────
    comp = nodes.new(type="CompositorNodeComposite")
    comp.location = (1500, 300)
    links.new(last_output, comp.inputs["Image"])


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _parse_args()

    with open(args.params) as fh:
        params = json.load(fh)

    video_path = params["video_path"]
    device_name = params.get("device", "iphone_15_pro")

    # ── Resolve device spec from manifest ─────────────────────────────────
    manifest = _load_manifest()
    spec = manifest.get(device_name)
    if not spec:
        print(  # noqa: T201
            f"WARNING: device '{device_name}' not in manifest, "
            "falling back to iphone_15_pro"
        )
        spec = manifest.get(
            "iphone_15_pro",
            {
                "category": "phone",
                "body_mm": {"w": 70.6, "h": 146.6, "d": 8.25},
                "screen_mm": {"w": 64.5, "h": 140.5},
                "corner_radius_mm": 6.0,
                "bezel_mm": 3.2,
                "notch": "dynamic_island",
                "material": "titanium",
            },
        )

    category = spec.get("category", "phone")
    mat_type = spec.get("material", "aluminum")

    # Probe source video
    fps = _get_video_fps(video_path)
    frame_count = _get_video_frame_count(video_path)

    # Check for .blend file override
    blend_file = spec.get("blend_file")
    blend_path = _DEVICES_DIR / blend_file if blend_file else None

    # Scene setup
    _clear_scene()
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frame_count
    scene.render.fps = int(round(fps))

    # Render engine
    engine = params.get("render_engine", "eevee")
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = params.get("samples", 128)
        scene.cycles.use_denoising = True
        # Better denoiser for cinematic
        if params.get("samples", 128) >= 256:
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
    else:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = params.get("samples", 64)

    # Resolution — cinematic renders at 4K (3840×2160)
    res_pct = params.get("resolution_percentage", 100)
    is_cinematic = res_pct >= 200
    if is_cinematic:
        scene.render.resolution_x = 3840
        scene.render.resolution_y = 2160
        scene.render.resolution_percentage = 100
    else:
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = res_pct

    orientation = params.get("orientation", "portrait")

    # ── Build device geometry ─────────────────────────────────────────────
    if blend_path and blend_path.exists():
        _build_from_blend(blend_path, video_path)
    elif category == "laptop":
        _build_laptop(spec, video_path, mat_type)
    elif category == "monitor":
        _build_monitor(spec, video_path, mat_type)
    elif category == "tablet":
        _build_phone_tablet(spec, video_path, mat_type, add_buttons=False)
    else:
        _build_phone_tablet(spec, video_path, mat_type)

    # ── Scene furniture ───────────────────────────────────────────────────
    _setup_lighting(params.get("lighting", "studio"))
    cam = _setup_camera(params, category)
    _setup_camera_animation(cam, params, frame_count, category)
    _setup_background(params)
    _setup_shadow_catcher(params)

    # ── Cinematic post-processing ─────────────────────────────────────────
    _setup_depth_of_field(cam, params)
    _setup_motion_blur(params)
    _setup_compositing(params)

    # Rotate body for landscape (phones / tablets only)
    if orientation == "landscape" and category in ("phone", "tablet"):
        body = bpy.data.objects.get("DeviceBody")
        if body:
            body.rotation_euler = (0, 0, math.pi / 2)

    # ── Render ────────────────────────────────────────────────────────────
    tmp_frames = Path(tempfile.mkdtemp(prefix="demodsl_blender_"))
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(tmp_frames / "frame_")

    try:
        bpy.ops.render.render(animation=True)

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Broadcast-quality encoding for cinematic tier
        if is_cinematic:
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-framerate",
                str(scene.render.fps),
                "-i",
                str(tmp_frames / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p10le",
                "-preset",
                "slow",
                "-crf",
                "10",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-colorspace",
                "bt709",
                str(output),
            ]
        else:
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-framerate",
                str(scene.render.fps),
                "-i",
                str(tmp_frames / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "fast",
                "-crf",
                "18",
                str(output),
            ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, timeout=300)
        print(f"DEMODSL_BLENDER_OK: {output}")  # noqa: T201

    finally:
        shutil.rmtree(tmp_frames, ignore_errors=True)


if __name__ == "__main__":
    main()
