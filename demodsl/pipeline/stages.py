"""Pipeline stages — Chain of Responsibility with critical/optional stages."""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from demodsl.color_lut import CubeLutError, escape_ffmpeg_filter_path, load_cube_lut
from demodsl.effects._ffmpeg import run_ffmpeg
from demodsl.effects.sanitize import sanitize_css_color
from demodsl.validators import _validate_safe_path

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
    scroll_positions: list[tuple[float, int]] = field(default_factory=list)
    """Captured (timestamp_seconds, scrollY_px) pairs from browser recording.

    Populated by the scenario orchestrator during scroll steps. Plugin stages
    (e.g. ``render_device_3d``) can use these to synchronise camera movement
    with the page scroll position.
    """
    device_rendering: Any = None
    theme: Any = None
    """Resolved :class:`~demodsl.models.theme.ThemeConfig`, or ``None``.

    ``apply_theme`` only reaches the engine's own overlay models. A plugin
    stage draws its own pixels, so it reads the theme from here instead —
    ``demodsl.theme.theme_palette(ctx.theme)`` flattens it into ready-to-use
    tokens and returns ``{}`` when the demo has no theme.
    """
    scenario_name: str = ""
    """Name of the scenario currently being processed (for diagnostics)."""
    step_index: int = -1
    """Zero-based index of the current step, or -1 when not in a step."""


class PipelineStageHandler(ABC):
    """Chain of Responsibility node. Each stage handles then delegates to next."""

    def __init__(self, params: dict[str, Any] | None = None, *, critical: bool = True) -> None:
        self.critical = critical
        self._next: PipelineStageHandler | None = None

    def set_next(self, handler: PipelineStageHandler) -> PipelineStageHandler:
        self._next = handler
        return handler

    def handle(self, ctx: PipelineContext) -> PipelineContext:
        try:
            ctx = self.process(ctx)
        except Exception:
            _ctx_info = ""
            if ctx.scenario_name:
                _ctx_info += f" [scenario={ctx.scenario_name}"
                if ctx.step_index >= 0:
                    _ctx_info += f", step={ctx.step_index}"
                _ctx_info += "]"
            video = ctx.processed_video or ctx.raw_video
            if video:
                _ctx_info += f" input={video.name}"
            if self.critical:
                logger.error(
                    "Critical stage '%s' failed%s",
                    self.name,
                    _ctx_info,
                    exc_info=True,
                )
                raise
            logger.warning(
                "Optional stage '%s' failed, skipping%s",
                self.name,
                _ctx_info,
                exc_info=True,
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

    name = "restore_audio"

    # ── EQ presets as ffmpeg equalizer filter chains ──────────────────────
    _EQ_PRESETS: dict[str, str] = {
        "podcast": ("highpass=f=80,equalizer=f=2500:t=q:w=1.5:g=3,equalizer=f=4000:t=q:w=1.0:g=2"),
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
        "deep": ("equalizer=f=100:t=q:w=1.0:g=4,equalizer=f=200:t=q:w=1.5:g=3,lowpass=f=5000"),
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

    # ── Distortion softclip types (ffmpeg asoftclip) ──────────────────────
    _DISTORTION_TYPES = {"tanh", "hard", "atan", "cubic", "exp", "alg", "quintic", "sin", "erf"}

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
        filters.extend(self._gate_filters())
        filters.extend(self._deess_filters())
        filters.extend(self._normalize_filters())
        filters.extend(self._voice_enhancement_filters())
        filters.extend(self._eq_filters())
        filters.extend(self._compression_filters())
        filters.extend(self._reverb_filters())
        filters.extend(self._silence_removal_filters())
        filters.extend(self._distortion_filters())

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
        run_ffmpeg(cmd, timeout=300)
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
            f"acompressor=threshold={threshold}dB:ratio={ratio}:attack={attack}:release={release}"
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
            f"silenceremove=stop_periods=-1:stop_duration={min_dur}:stop_threshold={threshold_db}dB"
        ]

    def _gate_filters(self) -> list[str]:
        """Noise gate (ffmpeg ``agate``) — attenuates the signal below a
        threshold instead of removing broadband noise like ``afftdn`` does.
        """
        gate = self.params.get("gate")
        if not gate:
            return []
        cfg = gate if isinstance(gate, dict) else {}
        threshold_db = float(cfg.get("threshold", -40))
        ratio = float(cfg.get("ratio", 2.0))
        attack = float(cfg.get("attack", 20))
        release = float(cfg.get("release", 250))
        range_db = float(cfg.get("range", -24))
        # agate's threshold/range are linear amplitude (0..1), not dB.
        threshold_lin = 10 ** (threshold_db / 20)
        range_lin = 10 ** (range_db / 20)
        logger.info("restore_audio: applying noise gate (threshold=%sdB)", threshold_db)
        return [
            f"agate=threshold={threshold_lin:.6f}:ratio={ratio}:"
            f"attack={attack}:release={release}:range={range_lin:.6f}"
        ]

    def _distortion_filters(self) -> list[str]:
        """Overdrive/distortion (ffmpeg ``asoftclip``) — a pre-gain drives the
        signal into the soft-clipper, ``output`` brings the level back down.
        """
        dist = self.params.get("distortion")
        if not dist:
            return []
        cfg = dist if isinstance(dist, dict) else {}
        drive = max(1.0, min(10.0, float(cfg.get("drive", 2.0))))
        dtype = cfg.get("type", "tanh")
        if dtype not in self._DISTORTION_TYPES:
            dtype = "tanh"
        output_gain = float(cfg.get("output_gain", 1.0))
        logger.info("restore_audio: applying distortion (drive=%s, type=%s)", drive, dtype)
        return [f"volume={drive}", f"asoftclip=type={dtype}:output={output_gain}"]


class RestoreVideoStage(PipelineStageHandler):
    """Restore video quality via ffmpeg vidstabtransform and unsharp."""

    name = "restore_video"

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
            run_ffmpeg(detect_cmd, timeout=600)
            vfilters.append(f"vidstabtransform=input={transforms_file}:smoothing={smoothing}")

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
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


class ApplyEffectsStage(PipelineStageHandler):
    """Apply post-processing visual effects via the EffectRegistry.

    The actual effect logic runs in PostProcessingOrchestrator;
    this stage exists to control ordering within the pipeline.
    Set ``ctx.config["post_effects"]`` with the effect list before
    the pipeline runs so other stages can inspect it.
    """

    name = "apply_effects"

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("apply_effects: ordering stage — actual work in PostProcessingOrchestrator")
        return ctx


class CompositeTimelineStage(PipelineStageHandler):
    """Bake an After-Effects-style overlay timeline on the processed video.

    Reads ``ctx.config['_timelines']`` — a list of (scenario_name, Timeline,
    base_dir) tuples set by the scenario orchestrator. If empty, the stage
    is a no-op.
    """

    name = "composite_timeline"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(critical=False)
        self.params = params or {}

    def process(self, ctx: PipelineContext) -> PipelineContext:
        from demodsl.effects.timeline_compositor import composite_timeline

        timelines = ctx.config.get("_timelines") or []
        if not timelines:
            logger.info("composite_timeline: no timelines configured — skip")
            return ctx
        src = ctx.processed_video or ctx.raw_video
        if src is None or not src.exists():
            logger.warning("composite_timeline: no video to composite onto")
            return ctx
        # Apply every configured timeline sequentially. The compositor
        # operates on the *current* processed_video, so each iteration
        # bakes the next scenario's layers on top of the previous output.
        out = ctx.workspace_root / "timeline_baked.mp4"
        current = src
        for idx, (scenario_name, timeline, base_dir) in enumerate(timelines):
            target = (
                out
                if idx == len(timelines) - 1
                else ctx.workspace_root / f"timeline_baked_{idx}.mp4"
            )
            logger.info(
                "composite_timeline: scenario '%s' (%d/%d) -> %s",
                scenario_name,
                idx + 1,
                len(timelines),
                target.name,
            )
            composite_timeline(current, target, timeline, base_dir=base_dir)
            current = target
        ctx.processed_video = out
        return ctx


class GenerateNarrationStage(PipelineStageHandler):
    """Ordering-only stage — actual work is done by NarrationOrchestrator."""

    name = "generate_narration"

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

    name = "render_device_mockup"

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
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


class EditVideoStage(PipelineStageHandler):
    """Ordering-only stage — actual work is done by the engine (intro/outro/watermark)."""

    name = "edit_video"

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=True)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("Editing video (intro, outro, transitions, watermark)")
        # Delegates to VideoBuilder — done in engine.py
        return ctx


class MixAudioStage(PipelineStageHandler):
    name = "mix_audio"

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
                sum(len(AudioSegment.from_file(str(p))) for p in ctx.narration_map.values())
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

    name = "optimize"

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
        run_ffmpeg(cmd, timeout=600)
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
        except (subprocess.SubprocessError, ValueError) as exc:
            logger.warning("optimize: could not probe duration of %s: %s", video, exc)
            return None


# ── Color correction stage ────────────────────────────────────────────────────


class ColorCorrectionStage(PipelineStageHandler):
    """Apply color correction (brightness, contrast, saturation, gamma, white balance)."""

    name = "color_correction"

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
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Color wheels stage ──────────────────────────────────────────────────


class ColorWheelsStage(PipelineStageHandler):
    """Independent shadows/midtones/highlights color balance (OpenShot-style
    color wheels), via ffmpeg's ``colorbalance`` filter.

    Each tonal range takes its own ``r``/``g``/``b`` offset (-1..1) so shadows
    can be pushed cool while highlights are warmed without touching the rest
    of the image, unlike the flat ``color_correction`` stage.
    """

    name = "color_wheels"

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("color_wheels: no video to process, skipping")
            return ctx

        shadows = self.params.get("shadows") or {}
        midtones = self.params.get("midtones") or {}
        highlights = self.params.get("highlights") or {}
        preserve_lightness = bool(self.params.get("preserve_lightness", False))

        def _channel(source: dict[str, Any], key: str) -> float:
            return max(-1.0, min(1.0, float(source.get(key, 0.0))))

        values = {
            "rs": _channel(shadows, "r"),
            "gs": _channel(shadows, "g"),
            "bs": _channel(shadows, "b"),
            "rm": _channel(midtones, "r"),
            "gm": _channel(midtones, "g"),
            "bm": _channel(midtones, "b"),
            "rh": _channel(highlights, "r"),
            "gh": _channel(highlights, "g"),
            "bh": _channel(highlights, "b"),
        }
        if not any(values.values()):
            logger.info("color_wheels: no adjustments needed, skipping")
            return ctx

        vf = "colorbalance=" + ":".join(f"{k}={v}" for k, v in values.items())
        if preserve_lightness:
            vf += ":pl=1"

        output = ctx.workspace_root / "color_wheels.mp4"
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
        logger.info("color_wheels: %s", " ".join(cmd))
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


# ── LUT (3D color lookup table) stage ─────────────────────────────────────────


class LutStage(PipelineStageHandler):
    """Apply a ``.cube`` 3D LUT (Adobe/DaVinci Resolve format) via ffmpeg's
    native ``lut3d`` filter.

    ``intensity`` blends the graded result back with the original instead of
    always applying the LUT at full strength (same idea as OpenShot 4.0's
    LUT intensity control) via a ``split`` + ``blend`` filtergraph.
    """

    name = "lut"

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("lut: no video to process, skipping")
            return ctx

        file_param = self.params.get("file")
        if not file_param:
            logger.info("lut: no file specified, skipping")
            return ctx

        try:
            safe_path = _validate_safe_path(str(file_param))
            load_cube_lut(safe_path)
        except (ValueError, CubeLutError) as exc:
            logger.warning("lut: %s — skipping", exc)
            return ctx

        intensity = max(0.0, min(1.0, float(self.params.get("intensity", 1.0))))
        if intensity <= 0.0:
            logger.info("lut: intensity is 0, skipping")
            return ctx

        escaped = escape_ffmpeg_filter_path(str(Path(safe_path).resolve()))
        cmd = ["ffmpeg", "-y", "-i", str(video)]
        if intensity >= 0.999:
            cmd += ["-vf", f"lut3d=file='{escaped}'"]
        else:
            graph = (
                f"split=2[__lut_base][__lut_in];"
                f"[__lut_in]lut3d=file='{escaped}'[__lut_out];"
                f"[__lut_base][__lut_out]blend=all_mode=normal:all_opacity={intensity}"
            )
            cmd += ["-filter_complex", graph]
        output = ctx.workspace_root / "lut_graded.mp4"
        cmd += ["-c:a", "copy", str(output)]

        logger.info("lut: %s", " ".join(cmd))
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Region mask stage ──────────────────────────────────────────────────────


class RegionMaskStage(PipelineStageHandler):
    """Blur, pixelate or solid-fill a rectangular region of the recorded video.

    A pragmatic, non-AI subset of OpenShot's interactive video masks: useful
    to redact a real on-screen element (an address, an account number) that
    should never have been visible in the recording. Each region is a plain
    rectangle (``x``/``y``/``width``/``height`` in pixels) and can optionally
    be scoped to a ``start``/``end`` time window — omitting both covers the
    whole clip. Point-prompted AI subject tracking is out of scope here.
    """

    name = "region_mask"

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("region_mask: no video to process, skipping")
            return ctx

        regions = self.params.get("regions") or []
        if not regions:
            logger.info("region_mask: no regions specified, skipping")
            return ctx

        filters: list[str] = []
        current = "0:v"
        for i, region in enumerate(regions):
            try:
                x, y = int(region["x"]), int(region["y"])
                w, h = int(region["width"]), int(region["height"])
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "region_mask: region %d missing x/y/width/height (%s) — skipping it", i, exc
                )
                continue
            if w <= 0 or h <= 0:
                logger.warning("region_mask: region %d has a non-positive size — skipping it", i)
                continue

            enable = ""
            start, end = region.get("start"), region.get("end")
            if start is not None or end is not None:
                lo = float(start) if start is not None else 0.0
                hi = float(end) if end is not None else 1e9
                enable = f":enable='between(t,{lo},{hi})'"

            style = region.get("style", "blur")
            nxt = f"vout{i}"
            if style == "solid":
                color = sanitize_css_color(str(region.get("color") or "#000000"))
                filters.append(
                    f"[{current}]drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t=fill{enable}[{nxt}]"
                )
            else:
                intensity = max(1, int(region.get("intensity", 20)))
                filters.append(f"[{current}]split=2[base{i}][src{i}]")
                filters.append(f"[src{i}]crop={w}:{h}:{x}:{y}[crop{i}]")
                if style == "pixelate":
                    block = max(2, intensity)
                    sw, sh = max(1, w // block), max(1, h // block)
                    filters.append(
                        f"[crop{i}]scale={sw}:{sh}:flags=neighbor,"
                        f"scale={w}:{h}:flags=neighbor[proc{i}]"
                    )
                else:  # "blur" (default)
                    # ffmpeg's boxblur rejects a radius that isn't strictly
                    # smaller than half the PLANE it applies to — the chroma
                    # plane is downsampled by 2 in yuv420p, so a radius that's
                    # safe for luma can still crash on chroma. Clamp each
                    # independently instead of trusting one requested value.
                    luma_max = max(1, min(w, h) // 2 - 1)
                    chroma_max = max(1, (min(w, h) // 2) // 2 - 1)
                    luma_r = min(intensity, luma_max)
                    chroma_r = min(intensity, chroma_max)
                    filters.append(
                        f"[crop{i}]boxblur=luma_radius={luma_r}:luma_power=2:"
                        f"chroma_radius={chroma_r}:chroma_power=2[proc{i}]"
                    )
                filters.append(f"[base{i}][proc{i}]overlay=x={x}:y={y}{enable}[{nxt}]")
            current = nxt

        if not filters:
            logger.info("region_mask: no valid regions, skipping")
            return ctx

        output = ctx.workspace_root / "region_masked.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-filter_complex",
            ";".join(filters),
            "-map",
            f"[{current}]",
            "-map",
            "0:a?",
            "-c:a",
            "copy",
            str(output),
        ]
        logger.info("region_mask: %s", " ".join(cmd))
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Frame rate conversion stage ───────────────────────────────────────────────


class FrameRateStage(PipelineStageHandler):
    """Convert video frame rate (e.g. 24fps, 30fps, 60fps)."""

    name = "frame_rate"

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
        logger.info("frame_rate: converting to %dfps (interpolate=%s)", fps, interpolate)
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Speed control stage ──────────────────────────────────────────────────────


class SpeedStage(PipelineStageHandler):
    """Global video speed adjustment (e.g. 0.5x slow-mo, 2x fast)."""

    name = "speed"

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
        run_ffmpeg(cmd, timeout=600)
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


# ── Fit Duration stage ────────────────────────────────────────────────────────


class FitDurationStage(PipelineStageHandler):
    """Adjust video speed so that it fits a target duration.

    Probes the current video duration and computes the speed factor needed
    to match ``target_duration`` (in seconds).  An optional ``strategy``
    parameter controls the allowed direction:

    * ``any``      – speed up *or* slow down (default)
    * ``speed_up`` – only make the video shorter (skip if already shorter)
    * ``slow_down``– only make the video longer  (skip if already longer)

    ``max_speed`` and ``min_speed`` clamp the computed factor so the result
    stays watchable (defaults: 0.25x – 4.0x).
    """

    name = "fit_duration"

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(critical=False)
        self.params = params

    # ──────────────────────────────────────────────────────────────────────

    def process(self, ctx: PipelineContext) -> PipelineContext:
        video = ctx.processed_video or ctx.raw_video
        if not video or not video.exists():
            logger.info("fit_duration: no video to process, skipping")
            return ctx

        target = self.params.get("target_duration")
        if target is None:
            logger.warning("fit_duration: 'target_duration' param is required — skipping")
            return ctx
        target = float(target)
        if target <= 0:
            logger.warning("fit_duration: target_duration must be > 0 — skipping")
            return ctx

        current = self._probe_duration(video)
        if current is None or current <= 0:
            logger.warning("fit_duration: could not determine video duration — skipping")
            return ctx

        speed = current / target  # >1 = speed-up, <1 = slow-down

        strategy = self.params.get("strategy", "any")
        if strategy == "speed_up" and speed < 1.0:
            logger.info(
                "fit_duration: video (%.1fs) already shorter than target (%.1fs) "
                "and strategy=speed_up — skipping",
                current,
                target,
            )
            return ctx
        if strategy == "slow_down" and speed > 1.0:
            logger.info(
                "fit_duration: video (%.1fs) already longer than target (%.1fs) "
                "and strategy=slow_down — skipping",
                current,
                target,
            )
            return ctx

        min_speed = float(self.params.get("min_speed", 0.25))
        max_speed = float(self.params.get("max_speed", 4.0))
        speed = max(min_speed, min(max_speed, speed))

        if abs(speed - 1.0) < 0.01:
            logger.info("fit_duration: speed ≈ 1.0x — no change needed")
            return ctx

        logger.info(
            "fit_duration: %.1fs → %.1fs (speed=%.2fx)",
            current,
            target,
            speed,
        )

        output = ctx.workspace_root / "fit_duration.mp4"
        video_filter = f"setpts={1.0 / speed}*PTS"
        audio_filters = SpeedStage._build_atempo(speed)

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
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx

    @staticmethod
    def _probe_duration(video: Path) -> float | None:
        """Return video duration in seconds via ffprobe, or *None* on failure."""
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
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            logger.warning("fit_duration: ffprobe failed", exc_info=True)
            return None


# ── Picture-in-Picture stage ─────────────────────────────────────────────────


class PiPStage(PipelineStageHandler):
    """Overlay a secondary video (e.g. webcam) in picture-in-picture."""

    name = "pip"

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
        from demodsl.validators import _validate_safe_path

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

        filter_complex = ";".join(filter_parts) + f"[pip];[0:v][pip]overlay={x}:{y}[out]"

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
        run_ffmpeg(cmd, timeout=600)
        ctx.processed_video = output
        return ctx


# ── Thumbnail extraction stage ────────────────────────────────────────────────


class ThumbnailStage(PipelineStageHandler):
    """Extract video thumbnail(s) as image files."""

    name = "thumbnail"

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
            run_ffmpeg(cmd, timeout=30)

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
        except (subprocess.SubprocessError, ValueError) as exc:
            logger.warning("thumbnail: could not probe duration of %s: %s", video, exc)
            return None


# ── Chapter markers stage ─────────────────────────────────────────────────────


class ChapterStage(PipelineStageHandler):
    """Generate chapter markers from step timestamps or manual config."""

    name = "chapters"

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
    "composite_timeline": CompositeTimelineStage,
    "generate_narration": GenerateNarrationStage,
    "render_device_mockup": RenderDeviceMockupStage,
    "edit_video": EditVideoStage,
    "mix_audio": MixAudioStage,
    "optimize": OptimizeStage,
    "color_correction": ColorCorrectionStage,
    "color_wheels": ColorWheelsStage,
    "lut": LutStage,
    "region_mask": RegionMaskStage,
    "frame_rate": FrameRateStage,
    "speed": SpeedStage,
    "fit_duration": FitDurationStage,
    "pip": PiPStage,
    "thumbnail": ThumbnailStage,
    "chapters": ChapterStage,
}


def _discover_plugin_stages() -> dict[str, type[PipelineStageHandler]]:
    """Discover extra pipeline stages from installed plugins via entry_points."""
    from importlib.metadata import entry_points

    stages: dict[str, type[PipelineStageHandler]] = {}
    for ep in entry_points(group="demodsl.stages"):
        try:
            cls = ep.load()
            stages[ep.name] = cls
            logger.info("Discovered plugin stage '%s' from %s", ep.name, ep.value)
        except Exception:
            logger.warning(
                "Failed to load plugin stage '%s' from %s",
                ep.name,
                ep.value,
                exc_info=True,
            )
    return stages


def get_stage_map() -> dict[str, type[PipelineStageHandler]]:
    """Return the full stage map including plugin-provided stages."""
    combined = dict(_STAGE_MAP)
    combined.update(_discover_plugin_stages())
    return combined


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
    stage_map = get_stage_map()
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

        cls = stage_map.get(name)
        if cls is None:
            logger.warning("Unknown pipeline stage: %s — skipping", name)
            continue
        handlers.append(cls(params))

    if not handlers:
        return None

    for i in range(len(handlers) - 1):
        handlers[i].set_next(handlers[i + 1])

    return handlers[0]
