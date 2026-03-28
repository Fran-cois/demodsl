"""Pipeline stages — Chain of Responsibility with critical/optional stages."""

from __future__ import annotations

import logging
import shutil
import subprocess
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
    """Restore audio quality via ffmpeg afftdn (denoise) and loudnorm (normalise)."""

    name = "restore_audio"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("restore_audio: no video to process, skipping")
            return ctx

        denoise = self.params.get("denoise", True)
        normalize = self.params.get("normalize", True)
        target_lufs = int(self.params.get("target_lufs", -16))

        filters: list[str] = []
        if denoise:
            nr = int(self.params.get("noise_reduction", 20))
            filters.append(f"afftdn=nr={nr}")
        if normalize:
            filters.append(f"loudnorm=I={target_lufs}:LRA=11:TP=-1.5")

        if not filters:
            logger.info("restore_audio: no filters enabled, skipping")
            return ctx

        output = ctx.workspace_root / "audio_restored.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-af", ",".join(filters),
            "-c:v", "copy",
            str(output),
        ]
        logger.info("restore_audio: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        ctx.processed_video = output
        return ctx


class RestoreVideoStage(PipelineStageHandler):
    """Restore video quality via ffmpeg vidstabtransform and unsharp."""

    name = "restore_video"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("restore_video: no video to process, skipping")
            return ctx

        stabilize = self.params.get("stabilize", True)
        sharpen = self.params.get("sharpen", True)

        if not stabilize and not sharpen:
            logger.info("restore_video: no filters enabled, skipping")
            return ctx

        vfilters: list[str] = []

        if stabilize:
            smoothing = int(self.params.get("smoothing", 10))
            transforms_file = ctx.workspace_root / "transforms.trf"
            # Pass 1: detect motion
            detect_cmd = [
                "ffmpeg", "-y", "-i", str(video),
                "-vf", f"vidstabdetect=result={transforms_file}",
                "-f", "null", "-",
            ]
            logger.info("restore_video: stabilisation pass 1")
            subprocess.run(detect_cmd, check=True, capture_output=True, timeout=600)
            vfilters.append(
                f"vidstabtransform=input={transforms_file}:smoothing={smoothing}"
            )

        if sharpen:
            vfilters.append("unsharp=5:5:0.8:5:5:0.0")

        output = ctx.workspace_root / "video_restored.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-vf", ",".join(vfilters),
            "-c:a", "copy",
            str(output),
        ]
        logger.info("restore_video: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx


class ApplyEffectsStage(PipelineStageHandler):
    """Apply post-processing visual effects via the EffectRegistry.

    The actual effect logic runs in PostProcessingOrchestrator;
    this stage exists to control ordering within the pipeline.
    Set ``ctx.config["post_effects"]`` with the effect list before
    the pipeline runs so other stages can inspect it.
    """

    name = "apply_effects"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("apply_effects: ordering stage — actual work in PostProcessingOrchestrator")
        return ctx


class GenerateNarrationStage(PipelineStageHandler):
    """Ordering-only stage — actual work is done by NarrationOrchestrator."""

    name = "generate_narration"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Generating narration audio clips")
        # Delegates to VoiceProvider — done in engine.py before pipeline runs
        return ctx


class RenderDeviceMockupStage(PipelineStageHandler):
    """Overlay the video into a device frame PNG using Pillow.

    Params:
        frame_image: path to a device frame PNG with a transparent viewport area.
        viewport_rect: [x, y, width, height] — where to place the video inside the frame.
    """

    name = "render_device_mockup"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("render_device_mockup: no video to process, skipping")
            return ctx

        frame_path = self.params.get("frame_image")
        viewport_rect = self.params.get("viewport_rect")
        if not frame_path or not viewport_rect:
            logger.warning(
                "render_device_mockup: 'frame_image' and 'viewport_rect' params "
                "are required — skipping"
            )
            return ctx

        frame_file = Path(frame_path)
        if not frame_file.exists():
            logger.warning("render_device_mockup: frame image not found: %s", frame_path)
            return ctx

        vx, vy, vw, vh = (int(v) for v in viewport_rect)

        # Extract first frame to get dimensions, compose with Pillow, then
        # overlay via ffmpeg.
        output = ctx.workspace_root / "device_mockup.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(frame_file),
            "-filter_complex",
            f"[0:v]scale={vw}:{vh}[scaled];"
            f"[1:v][scaled]overlay={vx}:{vy}[out]",
            "-map", "[out]",
            "-map", "0:a?",
            "-c:a", "copy",
            str(output),
        ]
        logger.info("render_device_mockup: compositing via ffmpeg")
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx


class EditVideoStage(PipelineStageHandler):
    """Ordering-only stage — actual work is done by the engine (intro/outro/watermark)."""

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
    """Re-encode video with target bitrate or CRF quality setting."""

    name = "optimize"  # type: ignore[assignment]

    _CRF_MAP = {"low": 28, "balanced": 23, "high": 18}

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("optimize: no video to process, skipping")
            return ctx

        fmt = self.params.get("format", "mp4")
        codec = self.params.get("codec", "libx264")
        quality = self.params.get("quality", "high")
        target_mb = self.params.get("target_size_mb")

        output = ctx.workspace_root / f"optimized.{fmt}"
        cmd = ["ffmpeg", "-y", "-i", str(video)]

        if target_mb:
            # Calculate target bitrate from file duration
            duration = self._probe_duration(video)
            if duration and duration > 0:
                target_kbps = int(float(target_mb) * 8192 / duration)
                cmd += ["-b:v", f"{target_kbps}k"]
            else:
                crf = self._CRF_MAP.get(quality, 23)
                cmd += ["-crf", str(crf)]
        else:
            crf = self._CRF_MAP.get(quality, 23)
            cmd += ["-crf", str(crf)]

        cmd += ["-c:v", codec, "-c:a", "copy", str(output)]

        logger.info("optimize: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx

    @staticmethod
    def _probe_duration(video: Path) -> float | None:
        """Get video duration in seconds via ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(video),
                ],
                check=True, capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            return None


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

# Stages that are handled directly by the engine, not the pipeline.
# If a user lists them in their YAML, we log a clear warning.
_ENGINE_HANDLED_STAGES: frozenset[str] = frozenset({
    "composite_avatar", "burn_subtitles", "deploy",
})


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

        if name in _ENGINE_HANDLED_STAGES:
            logger.warning(
                "Pipeline stage '%s' is handled directly by the engine, "
                "not the pipeline — ignoring in chain", name,
            )
            continue

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
