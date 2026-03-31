"""Bridge module — serializes DeviceRendering config to JSON and invokes
Blender in headless mode to render a 3D device mockup."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the blender/ project relative to the demodsl package root
_BLENDER_DIR = Path(__file__).resolve().parent.parent.parent / "blender"

# Quality presets → Blender render settings
_QUALITY_MAP: dict[str, dict[str, Any]] = {
    "low": {"resolution_percentage": 50, "samples": 16},
    "medium": {"resolution_percentage": 75, "samples": 64},
    "high": {"resolution_percentage": 100, "samples": 128},
    "cinematic": {"resolution_percentage": 200, "samples": 512},
}

# Well-known Blender install locations (macOS, Linux, Windows)
_BLENDER_CANDIDATES: list[str] = [
    "blender",
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "/snap/bin/blender",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
]


def _find_blender() -> str | None:
    """Return the path to the Blender binary, or *None*."""
    # Honour explicit env-var override
    env = os.environ.get("DEMODSL_BLENDER_PATH")
    if env and (shutil.which(env) or Path(env).is_file()):
        return env
    for candidate in _BLENDER_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
        if Path(candidate).is_file():
            return candidate
    return None


def check_blender_available() -> bool:
    """Check that the ``blender`` CLI and the render script are available."""
    if not _find_blender():
        logger.error("Blender not found in PATH — required for device rendering")
        return False
    if not (_BLENDER_DIR / "render_device.py").exists():
        logger.error(
            "Blender render script not found at %s",
            _BLENDER_DIR / "render_device.py",
        )
        return False
    return True


def build_blender_params(
    *,
    video_path: Path,
    device: str = "iphone_15_pro",
    orientation: str = "portrait",
    quality: str = "high",
    render_engine: str = "eevee",
    camera_animation: str = "orbit_smooth",
    lighting: str = "studio",
    background_preset: str = "space",
    background_color: str = "#1a1a1a",
    background_gradient_color: str | None = None,
    background_hdri: str | None = None,
    camera_distance: float = 1.5,
    camera_height: float = 0.0,
    rotation_speed: float = 1.0,
    shadow: bool = True,
    depth_of_field: bool = False,
    dof_aperture: float = 2.8,
    motion_blur: bool = False,
    bloom: bool = False,
    film_grain: float = 0.0,
) -> dict[str, Any]:
    """Build a params dict for the Blender render script."""
    quality_settings = _QUALITY_MAP.get(quality, _QUALITY_MAP["high"])
    # Cinematic forces Cycles
    effective_engine = "cycles" if quality == "cinematic" else render_engine
    return {
        "video_path": str(video_path),
        "device": device,
        "orientation": orientation,
        "render_engine": effective_engine,
        "camera_animation": camera_animation,
        "lighting": lighting,
        "background_preset": background_preset,
        "background_color": background_color,
        "background_gradient_color": background_gradient_color,
        "background_hdri": background_hdri,
        "camera_distance": camera_distance,
        "camera_height": camera_height,
        "rotation_speed": rotation_speed,
        "shadow": shadow,
        "depth_of_field": depth_of_field,
        "dof_aperture": dof_aperture,
        "motion_blur": motion_blur,
        "bloom": bloom,
        "film_grain": film_grain,
        **quality_settings,
    }


def render_via_blender(
    params: dict[str, Any],
    output_path: Path,
    *,
    timeout: int = 600,
) -> Path:
    """Write *params* to a temp JSON file and invoke Blender in background
    mode to produce a rendered MP4 at *output_path*.

    Raises:
        RuntimeError: If Blender is unavailable or the render fails.
    """
    if not check_blender_available():
        raise RuntimeError(
            "Blender is not available. Install Blender and ensure it is on your PATH."
        )

    # Write params to a temp file next to the output
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        dir=str(output_path.parent),
    ) as f:
        json.dump(params, f, default=str)
        params_path = Path(f.name)

    try:
        blender_bin = _find_blender()
        cmd = [
            blender_bin,  # type: ignore[list-item]
            "--background",
            "--python",
            str(_BLENDER_DIR / "render_device.py"),
            "--",
            "--params",
            str(params_path),
            "--output",
            str(output_path),
        ]
        logger.info("Running Blender render: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n")[-20:]:
                logger.info("[blender] %s", line)

        if result.returncode != 0:
            error_msg = result.stderr[-1000:] if result.stderr else "Unknown error"
            logger.error("Blender render failed:\n%s", error_msg)
            raise RuntimeError(f"Blender render failed: {error_msg}")

        if not output_path.exists():
            raise RuntimeError(f"Blender render produced no output at {output_path}")

        logger.info("Blender render complete: %s", output_path)
        return output_path

    finally:
        params_path.unlink(missing_ok=True)
