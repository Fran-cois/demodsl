"""Headless Blender provider — renders a video inside a 3D device mockup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.models import DeviceRendering
from demodsl.providers.base import BlenderProvider, BlenderProviderFactory
from demodsl_blender.bridge import (
    build_blender_params,
    check_blender_available,
    render_via_blender,
)

logger = logging.getLogger(__name__)


class HeadlessBlenderProvider(BlenderProvider):
    """Invokes Blender in ``--background`` mode via the bridge module."""

    def check_available(self) -> bool:
        return check_blender_available()

    def render(
        self,
        video_path: Path,
        config: Any,
        output_path: Path,
        *,
        scroll_positions: list[tuple[float, int]] | None = None,
    ) -> Path:
        if not isinstance(config, DeviceRendering):
            raise TypeError(f"Expected DeviceRendering, got {type(config).__name__}")

        params = build_blender_params(
            video_path=video_path,
            device=config.device,
            orientation=config.orientation,
            quality=config.quality,
            render_engine=config.render_engine,
            camera_animation=config.camera_animation,
            lighting=config.lighting,
            background_preset=config.background_preset,
            background_color=config.background_color,
            background_gradient_color=config.background_gradient_color,
            background_hdri=config.background_hdri,
            camera_distance=config.camera_distance,
            camera_height=config.camera_height,
            rotation_speed=config.rotation_speed,
            shadow=config.shadow,
            depth_of_field=config.depth_of_field,
            dof_aperture=config.dof_aperture,
            motion_blur=config.motion_blur,
            bloom=config.bloom,
            film_grain=config.film_grain,
            scroll_data=[{"t": t, "y": y} for t, y in (scroll_positions or [])],
        )
        if params.get("scroll_data"):
            logger.info(
                "Scroll data: %d points, max_y=%d",
                len(params["scroll_data"]),
                max(p["y"] for p in params["scroll_data"]),
            )
        return render_via_blender(params, output_path)


def register() -> None:
    """Register the headless provider in the factory."""
    BlenderProviderFactory.register("headless", HeadlessBlenderProvider)


# Auto-register on import
register()
