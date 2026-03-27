"""DemoEngine — main orchestrator for DemoDSL."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import yaml

from demodsl.commands import get_command
from demodsl.effects.browser_effects import register_all_browser_effects
from demodsl.effects.cursor import CursorOverlay
from demodsl.effects.glow_select import GlowSelectOverlay
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig, Effect, Scenario, Step
from demodsl.pipeline.stages import PipelineContext, build_chain
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import (
    BrowserProvider,
    BrowserProviderFactory,
    VoiceProvider,
    VoiceProviderFactory,
)

logger = logging.getLogger(__name__)


class DemoEngine:
    """Orchestrator: loads config, runs scenarios, executes the pipeline."""

    def __init__(
        self,
        config_path: Path,
        *,
        dry_run: bool = False,
        skip_voice: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        self.config_path = config_path
        self.dry_run = dry_run
        self.skip_voice = skip_voice

        text = config_path.read_text()
        if config_path.suffix.lower() == ".json":
            raw = json.loads(text)
        else:
            raw = yaml.safe_load(text)
        self.config = DemoConfig(**raw)
        self._output_dir = output_dir or Path(
            self.config.output.directory if self.config.output else "output"
        )

        # Effects
        self._effects = EffectRegistry()
        register_all_browser_effects(self._effects)
        register_all_post_effects(self._effects)

        # Step-level timing for narration alignment
        self._step_timestamps: list[float] = []

        logger.info("Loaded config: %s", self.config.metadata.title)

    # ── Public API ────────────────────────────────────────────────────────

    def validate(self) -> DemoConfig:
        """Parse + validate only (already done in __init__)."""
        logger.info("Validation OK: %s", self.config.metadata.title)
        return self.config

    def run(self) -> Path | None:
        """Execute the full demo pipeline."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        with Workspace() as ws:
            # Pass 1: Voice — generate narration clips FIRST (need durations for recording)
            narration_map = self._generate_narrations(ws)
            narration_durations = self._measure_narration_durations(narration_map)

            # Pass 2: Scenarios — browser capture (waits ≥ narration duration per step)
            self._step_timestamps.clear()
            raw_videos = self._run_scenarios(ws, narration_durations=narration_durations)

            # Pass 2.5: Build combined narration audio track
            narration_audio: Path | None = None
            if narration_map:
                narration_audio = self._build_narration_track(
                    narration_map, ws.root / "narration_combined.mp3"
                )

            # Pass 3: Pipeline — chain of responsibility
            ctx = PipelineContext(
                workspace_root=ws.root,
                raw_video=raw_videos[0] if raw_videos else None,
                narration_map=narration_map,
                config={
                    "background_music": (
                        self.config.audio.background_music.model_dump()
                        if self.config.audio and self.config.audio.background_music
                        else None
                    ),
                },
            )

            pipeline_dicts = [
                {"stage_type": s.stage_type, "params": s.params}
                for s in self.config.pipeline
            ]
            chain = build_chain(pipeline_dicts)
            if chain:
                ctx = chain.handle(ctx)

            # Copy final output
            final = ctx.processed_video or ctx.raw_video
            if final and final.exists():
                out_name = self.config.output.filename if self.config.output else "output.mp4"
                dest = self._output_dir / out_name
                self._export_video(final, dest, audio=narration_audio)
                logger.info("Final output: %s", dest)
                return dest

            logger.info("Pipeline completed (no output video produced in dry-run)")
            return None

    # ── Pass 1: Scenarios ─────────────────────────────────────────────────

    def _run_scenarios(
        self, ws: Workspace, *, narration_durations: dict[int, float] | None = None,
    ) -> list[Path]:
        if self.dry_run:
            return self._dry_run_scenarios()

        # Import to trigger factory registration
        import demodsl.providers.browser  # noqa: F401

        videos: list[Path] = []
        for scenario in self.config.scenarios:
            video = self._execute_scenario(
                scenario, ws, narration_durations=narration_durations or {}
            )
            if video:
                videos.append(video)
        return videos

    def _execute_scenario(
        self,
        scenario: Scenario,
        ws: Workspace,
        *,
        narration_durations: dict[int, float],
    ) -> Path | None:
        browser: BrowserProvider = BrowserProviderFactory.create("playwright")
        browser.launch(
            browser_type=scenario.browser,
            viewport=scenario.viewport,
            video_dir=ws.raw_video,
        )
        logger.info("Running scenario: %s", scenario.name)

        # Cursor overlay setup
        cursor: CursorOverlay | None = None
        if scenario.cursor and scenario.cursor.visible:
            cursor = CursorOverlay(scenario.cursor.model_dump())

        # Glow-select overlay setup
        glow: GlowSelectOverlay | None = None
        if scenario.glow_select and scenario.glow_select.enabled:
            glow = GlowSelectOverlay(scenario.glow_select.model_dump())

        t0 = time.monotonic()
        # Global step offset for narration duration lookup
        step_offset = len(self._step_timestamps)
        try:
            for i, step in enumerate(scenario.steps):
                logger.info("  Step %d: %s", i + 1, step.action)
                self._step_timestamps.append(time.monotonic() - t0)
                global_idx = step_offset + i
                nar_dur = narration_durations.get(global_idx, 0.0)
                self._execute_step(
                    browser, step, ws,
                    cursor=cursor, glow=glow,
                    narration_duration=nar_dur,
                )
        finally:
            video_path = browser.close()

        if video_path:
            logger.info("Recorded video: %s", video_path)
        return video_path

    def _execute_step(
        self,
        browser: BrowserProvider,
        step: Step,
        ws: Workspace,
        *,
        cursor: CursorOverlay | None = None,
        glow: GlowSelectOverlay | None = None,
        narration_duration: float = 0.0,
    ) -> None:
        # Apply browser effects before action
        if step.effects:
            self._apply_browser_effects(browser, step.effects)

        # Glow-select: highlight target element
        if glow and step.locator and step.action in ("click", "type"):
            bbox = browser.get_element_bbox(step.locator)
            if bbox:
                glow.show(browser.evaluate_js, bbox)

        # Animate cursor towards target element
        if cursor and step.locator:
            center = browser.get_element_center(step.locator)
            if center:
                cursor.move_to(browser.evaluate_js, center[0], center[1])

        # Click visual effect
        if cursor and step.action == "click":
            cursor.trigger_click(browser.evaluate_js)

        # Execute action command
        cmd = get_command(step.action, output_dir=ws.frames)
        cmd.execute(browser, step)

        # Glow-select: fade out after action
        if glow and step.locator and step.action in ("click", "type"):
            glow.hide(browser.evaluate_js)

        # Re-inject overlays after navigation (page JS is destroyed)
        if step.action == "navigate":
            time.sleep(0.3)
            if cursor:
                cursor.inject(browser.evaluate_js)
            if glow:
                glow.inject(browser.evaluate_js)

        # Wait: at least enough for narration to finish, or step.wait if longer
        effective_wait = max(step.wait or 0.0, narration_duration)
        if effective_wait > 0:
            time.sleep(effective_wait)

    def _apply_browser_effects(self, browser: BrowserProvider, effects: list[Effect]) -> None:
        for effect in effects:
            if self._effects.is_browser_effect(effect.type):
                handler = self._effects.get_browser_effect(effect.type)
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                handler.inject(browser.evaluate_js, params)
                if effect.duration:
                    time.sleep(effect.duration)

    def _dry_run_scenarios(self) -> list[Path]:
        for scenario in self.config.scenarios:
            logger.info("[DRY-RUN] Scenario: %s", scenario.name)
            for i, step in enumerate(scenario.steps):
                cmd = get_command(step.action, output_dir=Path("."))
                logger.info("  [DRY-RUN] Step %d: %s", i + 1, cmd.describe(step))
                if step.effects:
                    for e in step.effects:
                        logger.info("    [DRY-RUN] Effect: %s", e.type)
        return []

    # ── Pass 2: Narration ─────────────────────────────────────────────────

    def _generate_narrations(self, ws: Workspace) -> dict[int, Path]:
        if self.skip_voice or self.dry_run:
            if not self.dry_run:
                logger.info("Voice skipped (--skip-voice)")
            return self._dry_run_narrations()

        voice_config = self.config.voice
        engine = voice_config.engine if voice_config else "dummy"

        # Try to create the requested provider, fall back to dummy
        import demodsl.providers.voice  # noqa: F401
        try:
            voice: VoiceProvider = VoiceProviderFactory.create(
                engine, output_dir=ws.audio_clips
            )
        except (EnvironmentError, ValueError):
            logger.warning("Cannot create '%s' provider, falling back to dummy", engine)
            voice = VoiceProviderFactory.create("dummy", output_dir=ws.audio_clips)

        narration_map: dict[int, Path] = {}
        step_idx = 0
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    path = voice.generate(
                        text=step.narration,
                        voice_id=voice_config.voice_id if voice_config else "josh",
                        speed=voice_config.speed if voice_config else 1.0,
                        pitch=voice_config.pitch if voice_config else 0,
                    )
                    narration_map[step_idx] = path
                step_idx += 1

        voice.close()
        logger.info("Generated %d narration clips", len(narration_map))
        return narration_map

    @staticmethod
    def _measure_narration_durations(narration_map: dict[int, Path]) -> dict[int, float]:
        """Return the duration in seconds of each narration clip."""
        from pydub import AudioSegment

        durations: dict[int, float] = {}
        for step_idx, clip_path in narration_map.items():
            if clip_path.exists():
                clip = AudioSegment.from_file(str(clip_path))
                durations[step_idx] = len(clip) / 1000.0
        return durations

    def _dry_run_narrations(self) -> dict[int, Path]:
        step_idx = 0
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    logger.info(
                        "  [DRY-RUN] Narration step %d: %s...",
                        step_idx, step.narration[:60].strip(),
                    )
                step_idx += 1
        return {}

    # ── Audio mixing ──────────────────────────────────────────────────────

    def _build_narration_track(
        self, narration_map: dict[int, Path], output: Path
    ) -> Path | None:
        """Combine narration clips into a single audio track aligned to step timestamps."""
        from pydub import AudioSegment

        if not narration_map:
            return None

        # Determine total video duration from last timestamp + generous padding
        timestamps = self._step_timestamps
        if not timestamps:
            logger.warning("No step timestamps recorded, cannot build narration track")
            return None

        # Get the duration of the raw video for the total length
        total_ms = int((timestamps[-1] + 10) * 1000)  # fallback

        # Build combined track: place each clip at its step timestamp
        combined = AudioSegment.silent(duration=total_ms)

        for step_idx, clip_path in sorted(narration_map.items()):
            if not clip_path.exists():
                continue
            clip = AudioSegment.from_file(str(clip_path))
            if step_idx < len(timestamps):
                offset_ms = int(timestamps[step_idx] * 1000)
            else:
                # Step beyond recorded timestamps — append at end
                offset_ms = total_ms - len(clip)

            # Ensure combined is long enough
            end_ms = offset_ms + len(clip)
            if end_ms > len(combined):
                combined += AudioSegment.silent(duration=end_ms - len(combined))

            combined = combined.overlay(clip, position=offset_ms)
            logger.debug("Narration step %d at %.1fs (%.1fs long)",
                         step_idx, offset_ms / 1000, len(clip) / 1000)

        combined.export(str(output), format="mp3")
        logger.info("Combined narration track: %s (%.1fs)", output.name, len(combined) / 1000)
        return output

    # ── Export & Verification ─────────────────────────────────────────────

    def _export_video(
        self,
        source: Path,
        dest: Path,
        *,
        audio: Path | None = None,
    ) -> None:
        """Export video to *dest*, converting to MP4 H.264 and merging audio if provided."""
        import shutil
        import subprocess

        needs_conversion = self._needs_conversion(source, dest)

        if needs_conversion or audio:
            logger.info("Converting %s → MP4 H.264 (%s)%s",
                        source.name, dest.name,
                        " + narration audio" if audio else "")
            cmd = [
                "ffmpeg", "-y", "-i", str(source),
            ]
            if audio and audio.exists():
                cmd += ["-i", str(audio)]
            cmd += [
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            ]
            if audio and audio.exists():
                # Map video from input 0, audio from input 1
                cmd += ["-map", "0:v:0", "-map", "1:a:0",
                        "-c:a", "aac", "-b:a", "128k", "-shortest"]
            else:
                cmd += ["-an"]
            cmd.append(str(dest))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("ffmpeg conversion failed: %s", result.stderr[-200:])
                logger.info("Falling back to raw copy")
                shutil.copy2(source, dest)
        else:
            shutil.copy2(source, dest)

        self._verify_video(dest)

    @staticmethod
    def _needs_conversion(source: Path, dest: Path) -> bool:
        """Check if source is WebM/VP8 but dest expects MP4."""
        import subprocess

        if dest.suffix.lower() != ".mp4":
            return False
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=format_name",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
                capture_output=True, text=True, timeout=10,
            )
            fmt = result.stdout.strip()
            return "webm" in fmt or "matroska" in fmt
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _verify_video(path: Path) -> None:
        """Verify output video is valid — log result."""
        import subprocess

        if not path.exists():
            logger.error("VERIFY FAIL: file does not exist: %s", path)
            return

        size = path.stat().st_size
        if size == 0:
            logger.error("VERIFY FAIL: file is empty: %s", path)
            return

        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error",
                 "-show_entries", "format=format_name,duration",
                 "-show_entries", "stream=codec_name,width,height",
                 "-of", "default=noprint_wrappers=1", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            lines = result.stdout.strip().split("\n")
            info = dict(line.split("=", 1) for line in lines if "=" in line)

            fmt = info.get("format_name", "unknown")
            codec = info.get("codec_name", "unknown")
            w = info.get("width", "?")
            h = info.get("height", "?")
            dur = info.get("duration", "?")

            # Check MP4 extension matches MP4 format
            if path.suffix.lower() == ".mp4" and "mp4" not in fmt and "mov" not in fmt:
                logger.error(
                    "VERIFY FAIL: %s has extension .mp4 but format is '%s' (codec=%s)",
                    path.name, fmt, codec,
                )
                return

            logger.info(
                "VERIFY OK: %s → %s/%s %sx%s %.1fs (%s)",
                path.name, fmt, codec, w, h,
                float(dur) if dur != "?" else 0,
                _human_size(size),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("VERIFY SKIP: ffprobe not available, cannot verify %s", path.name)


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.0f}{unit}"
        nbytes /= 1024
    return f"{nbytes:.1f}TB"
