"""Quick diagnostic: render one frame with a bright green screen to verify
that the screen plane geometry is visible from the camera."""

import sys
from pathlib import Path

# Blender modules
import bpy  # type: ignore

# Reuse helpers from the main render script
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))
from render_device import (  # noqa: E402
    _clear_scene,
    _build_laptop,
    _setup_camera,
    _setup_lighting,
    _setup_background,
    _setup_shadow_catcher,
    _DEVICE_SPECS,
)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)

    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)

    _clear_scene()
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 1
    scene.render.fps = 25
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 50

    spec = _DEVICE_SPECS["macbook_pro_16"]
    _build_laptop(spec, args.video, "aluminum")

    # NOW: replace the screen material with bright green
    screen_obj = bpy.data.objects.get("DeviceScreen")
    if screen_obj:
        mat = bpy.data.materials.new(name="TestGreen")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        for n in list(nodes):
            nodes.remove(n)
        emission = nodes.new(type="ShaderNodeEmission")
        emission.inputs["Color"].default_value = (0, 1, 0, 1)  # Bright green
        emission.inputs["Strength"].default_value = 5.0
        out = nodes.new(type="ShaderNodeOutputMaterial")
        links.new(emission.outputs["Emission"], out.inputs["Surface"])
        screen_obj.data.materials.clear()
        screen_obj.data.materials.append(mat)
        print(f"Screen obj location: {screen_obj.location}")
        print(f"Screen obj world matrix: {screen_obj.matrix_world}")
    else:
        print("ERROR: DeviceScreen not found!")

    params = {
        "lighting": "dramatic",
        "camera_distance": 1.4,
        "camera_height": 0.0,
        "camera_animation": "static",
        "background_preset": "space_dark",
        "shadow": True,
    }
    _setup_lighting(params["lighting"])
    cam = _setup_camera(params, "laptop")
    _setup_background(params)
    _setup_shadow_catcher(params)

    print(f"Camera location: {cam.location}")

    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = args.output
    bpy.ops.render.render(write_still=True)
    print(f"TEST DONE: {args.output}")


if __name__ == "__main__":
    main()
