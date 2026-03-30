"""Pipeline stages — Chain of Responsibility with critical/optional stages."""

from __future__ import annotations

import logging
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
            logger.warning(
                "Optional stage '%s' failed, skipping", self.name, exc_info=True
            )

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
    """Restore audio quality via ffmpeg afftdn (denoise) and loudnorm (normalise).

    Also applies: EQ presets, compression, voice enhancement, de-essing,
    reverb, and silence removal when configured.
    """

    name = "restore_audio"  # type: ignore[assignment]

    # ── EQ presets as ffmpeg equalizer filter chains ──────────────────────
    _EQ_PRESETS: dict[str, str] = {
        "podcast": (
            "highpass=f=80,"
            "equalizer=f=2500:t=q:w=1.5:g=3,"
            "equalizer=f=4000:t=q:w=1.0:g=2"
        ),
        "warm": (
            "equalizer=f=250:t=q:w=1.0:g=3,"
            "equalizer=f=400:t=q:w=1.0:g=2,"
            "equalizer=f=4000:t=q:w=1.5:g=-2"
        ),
        "bright": (
            "equalizer=f=200:t=q:w=1.0:g=-2,"
            "equalizer=f=5000:t=q:w=1.5:g=3,"
            "equalizer=f=8000:t=q:w=1.0:g=2"
        ),
        "telephone": "highpass=f=300,lowpass=f=3400",
        "radio": (
            "equalizer=f=1500:t=q:w=1.0:g=2,"
            "equalizer=f=3000:t=q:w=1.5:g=3,"
            "acompressor=threshold=-18dB:ratio=3:attack=5:release=50"
        ),
        "deep": (
            "equalizer=f=100:t=q:w=1.0:g=4,equalizer=f=200:t=q:w=1.5:g=3,lowpass=f=5000"
        ),
    }

    # ── Compression presets ───────────────────────────────────────────────
    _COMPRESSION_PRESETS: dict[str, dict[str, int | float]] = {
        "voice": {"threshold": -20, "ratio": 3, "attack": 10, "release": 100},
        "podcast": {"threshold": -18, "ratio": 4, "attack": 5, "release": 50},
        "broadcast": {"threshold": -15, "ratio": 6, "attack": 3, "release": 30},
        "gentle": {"threshold": -25, "ratio": 2, "attack": 20, "release": 200},
    }

    # ── Noise reduction strength → afftdn nr value ──────────────────────
    _NOISE_STRENGTH: dict[str, int] = {
        "light": 10,
        "moderate": 20,
        "heavy": 40,
        "auto": 25,
    }

    # ── Reverb presets as ffmpeg aecho params ─────────────────────────────
    _REVERB_PRESETS: dict[str, str] = {
        "none": "",
        "small_room": "aecho=0.8:0.88:20:0.3",
        "large_room": "aecho=0.8:0.85:60|80:0.3|0.25",
        "hall": "aecho=0.8:0.72:100|120|140:0.3|0.25|0.2",
        "cathedral": "aecho=0.8:0.6:200|250|300:0.4|0.35|0.3",
        "plate": "aecho=0.8:0.88:30|40:0.4|0.3",
    }

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("restore_audio: no video to process, skipping")
            return ctx

        filters: list[str] = []
        filters.extend(self._denoise_filters())
        filters.extend(self._deess_filters())
        filters.extend(self._normalize_filters())
        filters.extend(self._voice_enhancement_filters())
        filters.extend(self._eq_filters())
        filters.extend(self._compression_filters())
        filters.extend(self._reverb_filters())
        filters.extend(self._silence_removal_filters())

        if not filters:
            logger.info("restore_audio: no filters enabled, skipping")
            return ctx

        output = ctx.workspace_root / "audio_restored.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-af",
            ",".join(filters),
            "-c:v",
            "copy",
            str(output),
        ]
        logger.info("restore_audio: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        ctx.processed_video = output
        return ctx

    def _denoise_filters(self) -> list[str]:
        if not self.params.get("denoise", True):
            return []
        strength = self.params.get("noise_reduction_strength", "moderate")
        nr = self._NOISE_STRENGTH.get(strength, 20)
        nr_override = self.params.get("noise_reduction")
        if isinstance(nr_override, int):
            nr = nr_override
        return [f"afftdn=nr={nr}"]

    def _deess_filters(self) -> list[str]:
        if not self.params.get("de_ess", False):
            return []
        intensity = float(self.params.get("de_ess_intensity", 0.5))
        freq = 6000
        gain = -int(6 + intensity * 12)  # -6 to -18 dB reduction
        return [f"equalizer=f={freq}:t=q:w=2.0:g={gain}"]

    def _normalize_filters(self) -> list[str]:
        if not self.params.get("normalize", True):
            return []
        target_lufs = int(self.params.get("target_lufs", -16))
        return [f"loudnorm=I={target_lufs}:LRA=11:TP=-1.5"]

    def _voice_enhancement_filters(self) -> list[str]:
        filters: list[str] = []
        if self.params.get("enhance_clarity", False):
            filters.extend(
                [
                    "highpass=f=80",
                    "equalizer=f=3000:t=q:w=1.5:g=3",
                    "equalizer=f=5000:t=q:w=1.0:g=2",
                ]
            )
        if self.params.get("enhance_warmth", False):
            filters.extend(
                [
                    "equalizer=f=200:t=q:w=1.0:g=3",
                    "equalizer=f=300:t=q:w=1.5:g=2",
                    "equalizer=f=5000:t=q:w=1.0:g=-1",
                ]
            )
        return filters

    def _eq_filters(self) -> list[str]:
        eq_preset = self.params.get("eq_preset")
        if eq_preset and eq_preset != "custom":
            preset_filter = self._EQ_PRESETS.get(eq_preset)
            if preset_filter:
                logger.info("restore_audio: applying EQ preset '%s'", eq_preset)
                return [preset_filter]
        elif eq_preset == "custom":
            eq_bands = self.params.get("eq_bands", [])
            return [
                f"equalizer=f={int(b.get('frequency', 1000))}"
                f":t=q:w={float(b.get('q', 1.0))}:g={float(b.get('gain', 0))}"
                for b in eq_bands
            ]
        return []

    def _compression_filters(self) -> list[str]:
        comp = self.params.get("compression")
        if not comp:
            return []
        if isinstance(comp, dict):
            preset_name = comp.get("preset")
            if preset_name and preset_name in self._COMPRESSION_PRESETS:
                c = self._COMPRESSION_PRESETS[preset_name]
            else:
                c = comp
            threshold = int(c.get("threshold", -20))
            ratio = float(c.get("ratio", 3.0))
            attack = int(c.get("attack", 5))
            release = int(c.get("release", 50))
        else:
            threshold, ratio, attack, release = -20, 3.0, 5, 50
        logger.info("restore_audio: applying compression (threshold=%ddB)", threshold)
        return [
            f"acompressor=threshold={threshold}dB"
            f":ratio={ratio}:attack={attack}:release={release}"
        ]

    def _reverb_filters(self) -> list[str]:
        reverb = self.params.get("reverb_preset")
        if not reverb or reverb == "none":
            return []
        reverb_filter = self._REVERB_PRESETS.get(reverb)
        if reverb_filter:
            logger.info("restore_audio: applying reverb preset '%s'", reverb)
            return [reverb_filter]
        return []

    def _silence_removal_filters(self) -> list[str]:
        if not self.params.get("remove_silence", False):
            return []
        threshold_db = int(self.params.get("silence_threshold", -40))
        min_dur = float(self.params.get("min_silence_duration", 0.5))
        logger.info("restore_audio: removing silences (threshold=%ddB)", threshold_db)
        return [
            f"silenceremove=stop_periods=-1"
            f":stop_duration={min_dur}"
            f":stop_threshold={threshold_db}dB"
        ]


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
                "ffmpeg",
                "-y",
                "-i",
                str(video),
                "-vf",
                f"vidstabdetect=result={transforms_file}",
                "-f",
                "null",
                "-",
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
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            ",".join(vfilters),
            "-c:a",
            "copy",
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
        logger.info(
            "apply_effects: ordering stage — actual work in PostProcessingOrchestrator"
        )
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
            logger.warning(
                "render_device_mockup: frame image not found: %s", frame_path
            )
            return ctx

        vx, vy, vw, vh = (int(v) for v in viewport_rect)

        # Extract first frame to get dimensions, compose with Pillow, then
        # overlay via ffmpeg.
        output = ctx.workspace_root / "device_mockup.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(frame_file),
            "-filter_complex",
            f"[0:v]scale={vw}:{vh}[scaled];[1:v][scaled]overlay={vx}:{vy}[out]",
            "-map",
            "[out]",
            "-map",
            "0:a?",
            "-c:a",
            "copy",
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
            total_dur = (
                sum(
                    len(AudioSegment.from_file(str(p)))
                    for p in ctx.narration_map.values()
                )
                if ctx.narration_map
                else 30000
            )
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
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            return None


# ── Color correction stage ────────────────────────────────────────────────────


class ColorCorrectionStage(PipelineStageHandler):
    """Apply color correction (brightness, contrast, saturation, gamma, white balance)."""

    name = "color_correction"  # type: ignore[assignment]

    # White balance presets as ffmpeg colortemperature values
    _WB_TEMPS: dict[str, int] = {
        "daylight": 5600,
        "tungsten": 3200,
        "fluorescent": 4000,
        "cloudy": 6500,
    }

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("color_correction: no video to process, skipping")
            return ctx

        brightness = float(self.params.get("brightness", 0.0))
        contrast = float(self.params.get("contrast", 0.0))
        saturation = float(self.params.get("saturation", 1.0))
        gamma = float(self.params.get("gamma", 1.0))
        temperature = self.params.get("temperature")
        white_balance = self.params.get("white_balance")

        vfilters: list[str] = []

        # Map our -1..1 range to ffmpeg eq filter ranges
        if brightness != 0.0 or contrast != 0.0 or saturation != 1.0 or gamma != 1.0:
            # ffmpeg eq: brightness [-1,1], contrast [-1000,1000] (1=normal),
            # saturation [0,3], gamma [0.1,10]
            eq_contrast = 1.0 + contrast  # -1..1 → 0..2
            vfilters.append(
                f"eq=brightness={brightness}"
                f":contrast={eq_contrast}"
                f":saturation={saturation}"
                f":gamma={gamma}"
            )

        # White balance / color temperature
        if temperature:
            vfilters.append(f"colortemperature=temperature={int(temperature)}")
        elif white_balance and white_balance != "auto":
            temp = self._WB_TEMPS.get(white_balance)
            if temp:
                vfilters.append(f"colortemperature=temperature={temp}")

        if not vfilters:
            logger.info("color_correction: no adjustments needed, skipping")
            return ctx

        output = ctx.workspace_root / "color_corrected.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            ",".join(vfilters),
            "-c:a",
            "copy",
            str(output),
        ]
        logger.info("color_correction: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Frame rate conversion stage ───────────────────────────────────────────────


class FrameRateStage(PipelineStageHandler):
    """Convert video frame rate (e.g. 24fps, 30fps, 60fps)."""

    name = "frame_rate"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("frame_rate: no video to process, skipping")
            return ctx

        fps = int(self.params.get("fps", 30))
        interpolate = self.params.get("interpolate", False)

        output = ctx.workspace_root / "framerate_converted.mp4"

        if interpolate:
            # Motion-interpolated frame rate conversion
            vf = f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1"
        else:
            vf = f"fps={fps}"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            vf,
            "-c:a",
            "copy",
            str(output),
        ]
        logger.info(
            "frame_rate: converting to %dfps (interpolate=%s)", fps, interpolate
        )
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Speed control stage ──────────────────────────────────────────────────────


class SpeedStage(PipelineStageHandler):
    """Global video speed adjustment (e.g. 0.5x slow-mo, 2x fast)."""

    name = "speed"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("speed: no video to process, skipping")
            return ctx

        speed = float(self.params.get("speed", 1.0))
        if speed == 1.0:
            logger.info("speed: 1.0x — no change, skipping")
            return ctx

        output = ctx.workspace_root / "speed_adjusted.mp4"
        # Video: setpts=PTS/speed (faster = smaller PTS)
        video_filter = f"setpts={1.0 / speed}*PTS"
        # Audio: atempo accepts 0.5-2.0; chain for values outside range
        audio_filters = self._build_atempo(speed)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            video_filter,
            "-af",
            audio_filters,
            str(output),
        ]
        logger.info("speed: adjusting to %.2fx", speed)
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx

    @staticmethod
    def _build_atempo(speed: float) -> str:
        """Build chained atempo filters for ffmpeg (each limited to 0.5-2.0)."""
        filters: list[str] = []
        remaining = speed
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")
        return ",".join(filters)


# ── Picture-in-Picture stage ─────────────────────────────────────────────────


class PiPStage(PipelineStageHandler):
    """Overlay a secondary video (e.g. webcam) in picture-in-picture."""

    name = "pip"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("pip: no video to process, skipping")
            return ctx

        source = self.params.get("source")
        if not source or not Path(source).exists():
            logger.warning("pip: source video not found: %s — skipping", source)
            return ctx

        # Validate source path against directory traversal
        from demodsl.models import _validate_safe_path

        try:
            _validate_safe_path(source)
        except ValueError:
            logger.warning("pip: source path rejected (unsafe): %s — skipping", source)
            return ctx

        position = self.params.get("position", "bottom-right")
        size_frac = float(self.params.get("size", 0.25))
        shape = self.params.get("shape", "rounded")
        opacity = float(self.params.get("opacity", 1.0))
        border_width = int(self.params.get("border_width", 2))

        output = ctx.workspace_root / "pip_composited.mp4"

        # Build overlay position string
        pip_w = f"main_w*{size_frac}"
        pos_map = {
            "top-left": (f"{border_width}", f"{border_width}"),
            "top-right": (f"main_w-overlay_w-{border_width}", f"{border_width}"),
            "bottom-left": (f"{border_width}", f"main_h-overlay_h-{border_width}"),
            "bottom-right": (
                f"main_w-overlay_w-{border_width}",
                f"main_h-overlay_h-{border_width}",
            ),
        }
        x, y = pos_map.get(position, pos_map["bottom-right"])

        filter_parts = [f"[1:v]scale={pip_w}:-1"]
        if shape == "circle":
            filter_parts.append("format=yuva420p")
            filter_parts.append(
                "geq=lum='lum(X,Y)':a='if(lt(pow(X-W/2,2)+pow(Y-H/2,2),pow(min(W,H)/2,2)),255,0)'"
            )
        if opacity < 1.0:
            filter_parts.append(f"colorchannelmixer=aa={opacity}")

        filter_complex = (
            ";".join(filter_parts) + f"[pip];[0:v][pip]overlay={x}:{y}[out]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(source),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-map",
            "0:a?",
            "-c:a",
            "copy",
            str(output),
        ]
        logger.info("pip: compositing PiP overlay (position=%s)", position)
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Thumbnail extraction stage ────────────────────────────────────────────────


class ThumbnailStage(PipelineStageHandler):
    """Extract video thumbnail(s) as image files."""

    name = "thumbnail"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("thumbnail: no video to process, skipping")
            return ctx

        thumbnails = self.params.get("thumbnails", [])
        if not thumbnails:
            # Default: extract frame at 25% of duration
            thumbnails = [{"timestamp": None, "auto": True, "format": "png"}]

        for i, thumb in enumerate(thumbnails):
            fmt = thumb.get("format", "png")
            output = ctx.workspace_root / f"thumbnail_{i}.{fmt}"

            if thumb.get("auto", False):
                # Auto: select frame with best contrast at ~25% of video
                duration = self._probe_duration(video)
                ts = duration * 0.25 if duration else 2.0
            elif thumb.get("timestamp") is not None:
                ts = float(thumb["timestamp"])
            else:
                ts = 0.0

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(ts),
                "-i",
                str(video),
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(output),
            ]
            logger.info("thumbnail: extracting at %.1fs → %s", ts, output.name)
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)

            # Store in metadata for export
            ctx.metadata.setdefault("thumbnails", []).append(str(output))

        return ctx

    @staticmethod
    def _probe_duration(video: Path) -> float | None:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            return None


# ── Chapter markers stage ─────────────────────────────────────────────────────


class ChapterStage(PipelineStageHandler):
    """Generate chapter markers from step timestamps or manual config."""

    name = "chapters"  # type: ignore[assignment]

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        chapters = self.params.get("chapters", [])
        auto = self.params.get("auto", False)

        if auto and not chapters:
            # Auto-generate from scenario metadata
            step_timestamps = ctx.metadata.get("step_timestamps", [])
            scenarios = ctx.config.get("scenarios", [])
            if scenarios:
                offset = 0
                for scenario in scenarios:
                    name = scenario.get("name", f"Scene {offset + 1}")
                    ts = (
                        step_timestamps[offset]
                        if offset < len(step_timestamps)
                        else float(offset * 10)
                    )
                    chapters.append({"title": name, "timestamp": ts})
                    offset += len(scenario.get("steps", []))

        if not chapters:
            logger.info("chapters: no chapters to generate, skipping")
            return ctx

        # Write ffmpeg metadata file for chapter embedding
        metadata_file = ctx.workspace_root / "chapters.txt"
        lines = [";FFMETADATA1"]
        for i, ch in enumerate(chapters):
            start_ms = int(float(ch["timestamp"]) * 1000)
            # End = start of next chapter, or video duration for last chapter
            if i + 1 < len(chapters):
                end_ms = int(float(chapters[i + 1]["timestamp"]) * 1000)
            else:
                # Probe video duration for the last chapter's END
                video = ctx.processed_video or ctx.raw_video
                fallback_end = start_ms + 3600 * 1000  # 1h fallback
                if video and video.exists():
                    dur = ThumbnailStage._probe_duration(video)
                    end_ms = int(dur * 1000) if dur else fallback_end
                else:
                    end_ms = fallback_end
            lines.append("[CHAPTER]")
            lines.append("TIMEBASE=1/1000")
            lines.append(f"START={start_ms}")
            lines.append(f"END={end_ms}")
            lines.append(f"title={ch['title']}")

        metadata_file.write_text("\n".join(lines), encoding="utf-8")
        ctx.metadata["chapters_file"] = str(metadata_file)
        ctx.metadata["chapters"] = chapters

        # Also generate YouTube-format timestamps
        yt_lines = []
        for ch in chapters:
            ts = float(ch["timestamp"])
            m, s = divmod(int(ts), 60)
            h, m = divmod(m, 60)
            if h > 0:
                yt_lines.append(f"{h}:{m:02d}:{s:02d} {ch['title']}")
            else:
                yt_lines.append(f"{m}:{s:02d} {ch['title']}")

        yt_file = ctx.workspace_root / "chapters_youtube.txt"
        yt_file.write_text("\n".join(yt_lines), encoding="utf-8")
        ctx.metadata["chapters_youtube"] = str(yt_file)
        logger.info("chapters: generated %d chapter markers", len(chapters))

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
    "color_correction": ColorCorrectionStage,
    "frame_rate": FrameRateStage,
    "speed": SpeedStage,
    "pip": PiPStage,
    "thumbnail": ThumbnailStage,
    "chapters": ChapterStage,
}

# Stages that are handled directly by the engine, not the pipeline.
# If a user lists them in their YAML, we log a clear warning.
_ENGINE_HANDLED_STAGES: frozenset[str] = frozenset(
    {
        "composite_avatar",
        "burn_subtitles",
        "deploy",
    }
)


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
                "not the pipeline — ignoring in chain",
                name,
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
