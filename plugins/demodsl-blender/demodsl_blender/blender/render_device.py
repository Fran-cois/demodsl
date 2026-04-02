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

    blender --background --python blender/render_device.py -- \\
        --params /tmp/params.json --output /tmp/output.mp4
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy  # type: ignore[import-untyped]

# Ensure this script's directory is importable (Blender --background
# does not always add the script's parent to sys.path).
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from blender._helpers import (  # noqa: E402
    _DEVICES_DIR,
    _clear_scene,
    _extract_video_frames,
    _get_video_fps,
    _get_video_frame_count,
    _load_manifest,
)
from blender._backgrounds import _setup_background  # noqa: E402
from blender._camera import _setup_camera, _setup_camera_animation  # noqa: E402
from blender._devices import (  # noqa: E402
    _build_from_model,
    _build_laptop,
    _build_monitor,
    _build_phone_tablet,
)
from blender._scene import (  # noqa: E402
    _setup_compositing,
    _setup_depth_of_field,
    _setup_lighting,
    _setup_motion_blur,
    _setup_shadow_catcher,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    """Parse arguments after the ``--`` separator in Blender's argv."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", required=True, help="Path to JSON params file")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    return parser.parse_args(argv)


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

    # Check for external model file (GLB, USDZ, or legacy .blend)
    model_file = spec.get("blend_file") or spec.get("model_file")
    model_path = _DEVICES_DIR / model_file if model_file else None
    if model_path and not model_path.exists():
        alt = _DEVICES_DIR / "models" / model_file
        if alt.exists():
            model_path = alt
        else:
            print(  # noqa: T201
                f"WARNING: model file '{model_file}' not found, "
                "using procedural generation"
            )
            model_path = None

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
    if model_path and model_path.exists():
        _build_from_model(model_path, video_path, screen_name=spec.get("screen_mesh"))
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

    # Get the extracted frame directory for per-frame texture swap
    _frame_sequence_dir, _ = _extract_video_frames(video_path)

    try:
        screen_mat = bpy.data.materials.get("ScreenMat")
        screen_tex_node = None
        if screen_mat:
            for node in screen_mat.node_tree.nodes:
                if node.type == "TEX_IMAGE":
                    screen_tex_node = node
                    break

        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            if screen_tex_node and _frame_sequence_dir:
                target = Path(_frame_sequence_dir) / f"frame_{frame:04d}.png"
                if target.exists():
                    old_img = screen_tex_node.image
                    new_img = bpy.data.images.load(str(target))
                    screen_tex_node.image = new_img
                    screen_tex_node.image.colorspace_settings.name = "sRGB"
                    if screen_tex_node.id_data and hasattr(
                        screen_tex_node.id_data, "update_tag"
                    ):
                        screen_tex_node.id_data.update_tag()
                    bpy.context.view_layer.update()
                    if old_img and old_img.users == 0:
                        bpy.data.images.remove(old_img)
            scene.render.filepath = str(tmp_frames / f"frame_{frame:04d}")
            bpy.ops.render.render(write_still=True)

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
        _ffmpeg_timeout = 1200 if is_cinematic else 300
        subprocess.run(
            ffmpeg_cmd, check=True, capture_output=True, timeout=_ffmpeg_timeout
        )
        print(f"DEMODSL_BLENDER_OK: {output}")  # noqa: T201

    finally:
        shutil.rmtree(tmp_frames, ignore_errors=True)


if __name__ == "__main__":
    main()
