"""Pipeline stages — Chain of Responsibility with critical/optional stages."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Accumulated state passed through the pipeline chain."""

    workspace_root: Path
    raw_video: Path | None = None
    processed_video: Path | None = None
    audio_clips: list[Path] = field(default_factory=list)
    narration_map: dict[int, Path] = field(default_factory=dict)
    final_audio: Path | None = None
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineStageHandler(ABC):
    """Chain of Responsibility node. Each stage handles then delegates to next."""

    def __init__(self, *, critical: bool = True) -> None:
        self.critical = critical
        self._next: PipelineStageHandler | None = None

    def set_next(self, handler: PipelineStageHandler) -> PipelineStageHandler:
        self._next = handler
        return handler

    def handle(self, ctx: PipelineContext) -> PipelineContext:
        try:
            ctx = self.process(ctx)
        except Exception:
            if self.critical:
                logger.error("Critical stage '%s' failed", self.name, exc_info=True)
                raise
            logger.warning("Optional stage '%s' failed, skipping", self.name, exc_info=True)

        if self._next:
            return self._next.handle(ctx)
        return ctx

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def process(self, ctx: PipelineContext) -> PipelineContext: ...


# ── Concrete stages ──────────────────────────────────────────────────────────

class RestoreAudioStage(PipelineStageHandler):
    name = "restore_audio"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Restoring audio: denoise=%s, normalize=%s",
                     self.params.get("denoise"), self.params.get("normalize"))
        # Would call ffmpeg afftdn / loudnorm filters on raw audio
        return ctx


class RestoreVideoStage(PipelineStageHandler):
    name = "restore_video"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Restoring video: stabilize=%s, sharpen=%s",
                     self.params.get("stabilize"), self.params.get("sharpen"))
        # Would call ffmpeg vidstab / unsharp filters
        return ctx


class ApplyEffectsStage(PipelineStageHandler):
    name = "apply_effects"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Applying post-processing visual effects")
        # Would iterate over post-effects from the effect registry
        return ctx


class GenerateNarrationStage(PipelineStageHandler):
    name = "generate_narration"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Generating narration audio clips")
        # Delegates to VoiceProvider — done in engine.py before pipeline runs
        return ctx


class RenderDeviceMockupStage(PipelineStageHandler):
    name = "render_device_mockup"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Rendering device mockup (v1: PNG overlay)")
        # v1: Overlay video into a device frame PNG using Pillow
        # v2: Blender headless subprocess
        return ctx


class EditVideoStage(PipelineStageHandler):
    name = "edit_video"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Editing video (intro, outro, transitions, watermark)")
        # Delegates to VideoBuilder — done in engine.py
        return ctx


class MixAudioStage(PipelineStageHandler):
    name = "mix_audio"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Mixing audio (voice + background music with ducking)")
        if not ctx.audio_clips and not ctx.narration_map:
            logger.info("No audio clips to mix, skipping")
            return ctx

        from pydub import AudioSegment

        bg_config = ctx.config.get("background_music")
        if bg_config and Path(bg_config["file"]).exists():
            music = AudioSegment.from_file(bg_config["file"])
            volume_db = bg_config.get("volume", 0.3)
            # Convert 0-1 scale to dB reduction
            music = music - (1 - volume_db) * 20

            # Loop to cover total duration
            total_dur = sum(
                len(AudioSegment.from_file(str(p)))
                for p in ctx.narration_map.values()
            ) if ctx.narration_map else 30000
            while len(music) < total_dur:
                music = music + music
            music = music[:total_dur]

            # Ducking: lower music during narration
            ducking_db = {"none": 0, "light": -6, "moderate": -12, "heavy": -20}.get(
                bg_config.get("ducking_mode", "moderate"), -12
            )
            # Would apply ducking at narration timestamps
            logger.info("Background music loaded, ducking=%ddB", ducking_db)

        return ctx


class OptimizeStage(PipelineStageHandler):
    name = "optimize"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        fmt = self.params.get("format", "mp4")
        codec = self.params.get("codec", "h264")
        quality = self.params.get("quality", "high")
        target_mb = self.params.get("target_size_mb")
        logger.info("Optimizing: format=%s, codec=%s, quality=%s, target=%sMB",
                     fmt, codec, quality, target_mb)
        # Would call ffmpeg for final encoding with target bitrate
        return ctx


# ── Chain builder ─────────────────────────────────────────────────────────────

_STAGE_MAP: dict[str, type[PipelineStageHandler]] = {
    "restore_audio": RestoreAudioStage,
    "restore_video": RestoreVideoStage,
    "apply_effects": ApplyEffectsStage,
    "generate_narration": GenerateNarrationStage,
    "render_device_mockup": RenderDeviceMockupStage,
    "edit_video": EditVideoStage,
    "mix_audio": MixAudioStage,
    "optimize": OptimizeStage,
}


def build_chain(stages: list[dict[str, Any]]) -> PipelineStageHandler | None:
    """Build a Chain of Responsibility from the pipeline config list."""
    handlers: list[PipelineStageHandler] = []
    for stage_def in stages:
        if isinstance(stage_def, dict) and "stage_type" in stage_def:
            name = stage_def["stage_type"]
            params = stage_def.get("params", {})
        else:
            # raw dict from YAML
            name = next(iter(stage_def))
            params = stage_def[name] if isinstance(stage_def[name], dict) else {}

        cls = _STAGE_MAP.get(name)
        if cls is None:
            logger.warning("Unknown pipeline stage: %s — skipping", name)
            continue
        handlers.append(cls(params))

    if not handlers:
        return None

    for i in range(len(handlers) - 1):
        handlers[i].set_next(handlers[i + 1])

    return handlers[0]
