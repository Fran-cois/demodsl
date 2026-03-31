"""Headless Blender provider — renders a video inside a 3D device mockup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.models import DeviceRendering
from demodsl.providers.base import BlenderProvider, BlenderProviderFactory
from demodsl.providers.blender_bridge import (
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
        )
        return render_via_blender(params, output_path)


BlenderProviderFactory.register("headless", HeadlessBlenderProvider)
