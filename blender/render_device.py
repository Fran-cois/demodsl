"""Blender render script — executed by ``blender --background --python``.

This script creates a 3D device mockup, maps the recorded mobile video onto
its screen, applies camera animation and lighting, then renders the result
to a sequence of frames which are assembled into an MP4 via ffmpeg.

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

# Blender's embedded Python provides `bpy`
import bpy  # type: ignore[import-untyped]

# ── Device specs ──────────────────────────────────────────────────────────────
# Screen dimensions in Blender units (metres).  The mesh is built
# parametrically so no external .blend asset is needed for now.

_DEVICE_SPECS: dict[str, dict] = {
    "iphone_15_pro": {
        "body_w": 0.0709,
        "body_h": 0.1469,
        "body_d": 0.0083,
        "screen_w": 0.0645,
        "screen_h": 0.1405,
        "corner_radius": 0.006,
        "bezel": 0.0032,
    },
    "iphone_14": {
        "body_w": 0.0715,
        "body_h": 0.1467,
        "body_d": 0.0078,
        "screen_w": 0.0630,
        "screen_h": 0.1370,
        "corner_radius": 0.006,
        "bezel": 0.0042,
    },
    "pixel_8": {
        "body_w": 0.0707,
        "body_h": 0.1525,
        "body_d": 0.0089,
        "screen_w": 0.0650,
        "screen_h": 0.1445,
        "corner_radius": 0.005,
        "bezel": 0.0028,
    },
}

_LIGHTING_PRESETS: dict[str, list[dict]] = {
    "studio": [
        {
            "type": "AREA",
            "energy": 200,
            "location": (1, -1, 2),
            "rotation": (0.8, 0, 0.5),
        },
        {
            "type": "AREA",
            "energy": 80,
            "location": (-1, -0.5, 1.5),
            "rotation": (0.6, 0, -0.4),
        },
        {
            "type": "AREA",
            "energy": 40,
            "location": (0, 1, 0.5),
            "rotation": (-0.3, 0, 0),
        },
    ],
    "natural": [
        {"type": "SUN", "energy": 5, "location": (2, -2, 4), "rotation": (0.6, 0, 0.3)},
    ],
    "dramatic": [
        {
            "type": "SPOT",
            "energy": 500,
            "location": (1.5, -1, 2.5),
            "rotation": (0.7, 0, 0.4),
        },
        {
            "type": "AREA",
            "energy": 20,
            "location": (-1, 1, 1),
            "rotation": (-0.4, 0, -0.3),
        },
    ],
}


def _parse_args() -> argparse.Namespace:
    """Parse arguments after the ``--`` separator in Blender's argv."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", required=True, help="Path to JSON params file")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    return parser.parse_args(argv)


def _clear_scene() -> None:
    """Remove all default objects."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Remove orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)


def _hex_to_linear(hex_color: str) -> tuple[float, float, float, float]:
    """Convert hex color string to linear sRGB tuple (r, g, b, a)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    # sRGB → linear approximation
    r, g, b = r**2.2, g**2.2, b**2.2
    return (r, g, b, 1.0)


def _create_device_body(spec: dict) -> bpy.types.Object:
    """Create a rounded-box device body."""
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, 0, 0),
    )
    body = bpy.context.active_object
    body.name = "DeviceBody"
    body.scale = (spec["body_w"] / 2, spec["body_d"] / 2, spec["body_h"] / 2)
    bpy.ops.object.transform_apply(scale=True)

    # Bevel for rounded corners
    bevel = body.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = spec.get("corner_radius", 0.005)
    bevel.segments = 8

    # Dark metallic material for the body
    mat = bpy.data.materials.new(name="DeviceBodyMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.15, 0.15, 0.15, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.3
    body.data.materials.append(mat)

    return body


def _create_screen_plane(spec: dict, video_path: str) -> bpy.types.Object:
    """Create a plane for the screen and apply the video as a texture."""
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, -(spec["body_d"] / 2 + 0.0001), 0),
        rotation=(math.pi / 2, 0, 0),
    )
    screen = bpy.context.active_object
    screen.name = "DeviceScreen"
    screen.scale = (spec["screen_w"] / 2, spec["screen_h"] / 2, 1)
    bpy.ops.object.transform_apply(scale=True)

    # Create material with video texture
    mat = bpy.data.materials.new(name="ScreenMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove default nodes
    for node in nodes:
        nodes.remove(node)

    # Build node tree: Image Texture → Principled BSDF → Material Output
    tex_node = nodes.new(type="ShaderNodeTexImage")
    img = bpy.data.images.load(video_path)
    img.source = "MOVIE"
    tex_node.image = img

    bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf_node.inputs["Roughness"].default_value = 0.0
    bsdf_node.inputs["Specular IOR Level"].default_value = 0.0

    output_node = nodes.new(type="ShaderNodeOutputMaterial")

    links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])
    links.new(tex_node.outputs["Color"], bsdf_node.inputs["Emission Color"])
    bsdf_node.inputs["Emission Strength"].default_value = 1.0
    links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    screen.data.materials.append(mat)

    # Parent screen to body
    screen.parent = bpy.data.objects.get("DeviceBody")

    return screen


def _setup_lighting(preset: str) -> None:
    """Add lights according to the chosen preset."""
    lights = _LIGHTING_PRESETS.get(preset, _LIGHTING_PRESETS["studio"])
    for i, cfg in enumerate(lights):
        light_data = bpy.data.lights.new(name=f"Light_{i}", type=cfg["type"])
        light_data.energy = cfg["energy"]
        light_obj = bpy.data.objects.new(name=f"Light_{i}", object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = cfg["location"]
        light_obj.rotation_euler = cfg["rotation"]


def _setup_camera(params: dict) -> bpy.types.Object:
    """Create and position the camera."""
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    dist = params.get("camera_distance", 1.5)
    height = params.get("camera_height", 0.0)
    cam_obj.location = (0, -dist * 0.15, height * 0.05)
    cam_obj.rotation_euler = (math.pi / 2, 0, 0)

    return cam_obj


def _setup_camera_animation(
    cam: bpy.types.Object, params: dict, frame_count: int
) -> None:
    """Animate the camera based on the chosen animation preset."""
    animation = params.get("camera_animation", "orbit_smooth")
    dist = params.get("camera_distance", 1.5) * 0.15
    height = params.get("camera_height", 0.0) * 0.05
    speed = params.get("rotation_speed", 1.0)

    if animation == "static":
        return

    if animation == "orbit_smooth":
        # Create an empty at origin for the camera to track
        bpy.ops.object.empty_add(location=(0, 0, 0))
        target = bpy.context.active_object
        target.name = "CameraTarget"

        # Track-to constraint
        track = cam.constraints.new(type="TRACK_TO")
        track.target = target
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        # Keyframe orbit
        total_angle = (
            speed * 2 * math.pi * (frame_count / (30 * 8))
        )  # full orbit per 8s
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

    elif animation == "tilt":
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            tilt = math.sin(t * math.pi) * 0.15
            cam.location = (0, -dist, height + tilt * 0.05)
            cam.rotation_euler = (math.pi / 2 - tilt, 0, 0)
            cam.keyframe_insert(data_path="location", frame=frame + 1)
            cam.keyframe_insert(data_path="rotation_euler", frame=frame + 1)


def _setup_background(params: dict) -> None:
    """Configure scene background color or HDRI."""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes

    bg_node = nodes.get("Background") or nodes.new(type="ShaderNodeBackground")
    hdri = params.get("background_hdri")
    if hdri and os.path.isfile(hdri):
        env_tex = nodes.new(type="ShaderNodeTexEnvironment")
        env_tex.image = bpy.data.images.load(hdri)
        world.node_tree.links.new(env_tex.outputs["Color"], bg_node.inputs["Color"])
    else:
        bg_node.inputs["Color"].default_value = _hex_to_linear(
            params.get("background_color", "#1a1a1a")
        )


def _setup_shadow_catcher(params: dict) -> None:
    """Add a shadow-catching ground plane if shadows are enabled."""
    if not params.get("shadow", True):
        return
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, -0.08))
    ground = bpy.context.active_object
    ground.name = "ShadowCatcher"
    ground.is_shadow_catcher = True


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
        # fallback: assume 30fps × 10s
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


def main() -> None:
    args = _parse_args()

    with open(args.params) as f:
        params = json.load(f)

    video_path = params["video_path"]
    device_name = params.get("device", "iphone_15_pro")
    spec = _DEVICE_SPECS.get(device_name, _DEVICE_SPECS["iphone_15_pro"])

    # Probe source video
    fps = _get_video_fps(video_path)
    frame_count = _get_video_frame_count(video_path)

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
    else:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = params.get("samples", 64)

    # Resolution
    res_pct = params.get("resolution_percentage", 100)
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = res_pct

    # Handle orientation
    orientation = params.get("orientation", "portrait")

    # Build the scene
    _create_device_body(spec)
    _create_screen_plane(spec, video_path)
    _setup_lighting(params.get("lighting", "studio"))
    cam = _setup_camera(params)
    _setup_camera_animation(cam, params, frame_count)
    _setup_background(params)
    _setup_shadow_catcher(params)

    # Rotate device for landscape
    body = bpy.data.objects.get("DeviceBody")
    if body and orientation == "landscape":
        body.rotation_euler = (0, 0, math.pi / 2)

    # Render to frames in a temp directory
    tmp_frames = Path(tempfile.mkdtemp(prefix="demodsl_blender_"))
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(tmp_frames / "frame_")

    try:
        bpy.ops.render.render(animation=True)

        # Assemble frames to MP4 via ffmpeg
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)

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
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, timeout=120)
        print(f"DEMODSL_BLENDER_OK: {output}")  # noqa: T201

    finally:
        shutil.rmtree(tmp_frames, ignore_errors=True)


if __name__ == "__main__":
    main()
