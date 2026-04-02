"""Pipeline stage — Blender 3D device rendering."""

from __future__ import annotations

import logging
from typing import Any

from demodsl.pipeline.stages import PipelineContext, PipelineStageHandler

logger = logging.getLogger(__name__)


class RenderDevice3DStage(PipelineStageHandler):
    """Render the video inside a 3D device mockup via Blender.

    Reads ``device_rendering`` config and ``scroll_positions`` from the
    pipeline context.  Falls back gracefully to the raw video when Blender
    is not available.
    """

    name = "render_device_3d"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("render_device_3d: no video to process, skipping")
            return ctx

        dr_config = ctx.device_rendering
        if dr_config is None:
            logger.info(
                "render_device_3d: no device_rendering config in context, skipping"
            )
            return ctx

        try:
            from demodsl_blender.provider import HeadlessBlenderProvider

            from demodsl.providers.base import BlenderProviderFactory

            # Ensure registered
            if "headless" not in BlenderProviderFactory._registry:
                BlenderProviderFactory.register("headless", HeadlessBlenderProvider)

            blender = BlenderProviderFactory.create("headless")
            if not blender.check_available():
                logger.warning(
                    "Blender not available — skipping 3D device rendering. "
                    "The pipeline continues with the raw recording."
                )
                return ctx

            output = ctx.workspace_root / "device_rendered.mp4"
            rendered = blender.render(
                video,
                dr_config,
                output,
                scroll_positions=ctx.scroll_positions or None,
            )
            ctx.processed_video = rendered
        except Exception:
            logger.warning(
                "Blender 3D device rendering failed — continuing with raw video.",
                exc_info=True,
            )
        return ctx
