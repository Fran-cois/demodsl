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
from demodsl.effects.popup_card import PopupCardOverlay
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.effects.registry import EffectRegistry
from demodsl.effects.subtitle import (
    SPEED_PRESETS,
    _build_subtitle_entries,
    burn_subtitles,
    generate_ass_subtitle,
    get_merged_subtitle_config,
)
from demodsl.models import DemoConfig, Effect, Scenario, Step
from demodsl.pipeline.stages import PipelineContext, build_chain
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import (
    AvatarProvider,
    AvatarProviderFactory,
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
        # Post-effects per step (collected during recording, applied afterwards)
        self._step_post_effects: list[list[tuple[str, dict[str, Any]]]] = []

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

            # Pass 1.5: Avatar — generate avatar clips synced to narration
            narration_texts = self._build_narration_texts()
            avatar_clips = self._generate_avatar_clips(ws, narration_map, narration_texts)

            # Pass 2: Scenarios — browser capture (waits ≥ narration duration per step)
            self._step_timestamps.clear()
            self._step_post_effects.clear()
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

            # Pass 3.5: Apply post-processing effects (camera, cinematic)
            final = ctx.processed_video or ctx.raw_video
            if final and final.exists() and self._step_post_effects:
                post_processed = ws.root / "post_effects_applied.mp4"
                applied = self._apply_post_effects_to_video(
                    final, post_processed,
                )
                if applied and applied.exists():
                    final = applied

            # Copy final output
            if final and final.exists():
                # Composite avatar overlays if any
                if avatar_clips:
                    from demodsl.effects.avatar_overlay import composite_avatar

                    avatar_cfg = self._get_avatar_config()
                    composited = ws.root / "avatar_composited.mp4"
                    final = composite_avatar(
                        final,
                        avatar_clips,
                        self._step_timestamps,
                        narration_durations,
                        composited,
                        position=avatar_cfg.get("position", "bottom-right"),
                        size=avatar_cfg.get("size", 120),
                        show_subtitle=avatar_cfg.get("show_subtitle", False),
                        subtitle_font_size=avatar_cfg.get("subtitle_font_size", 18),
                        subtitle_font_color=avatar_cfg.get("subtitle_font_color", "#FFFFFF"),
                        subtitle_bg_color=avatar_cfg.get("subtitle_bg_color", "rgba(0,0,0,0.7)"),
                        narration_texts=narration_texts or None,
                    )

                # Burn subtitles if configured
                subtitle_cfg = self._get_subtitle_config()
                if subtitle_cfg.get("enabled", False) and narration_texts:
                    final = self._burn_subtitles(
                        final, ws, narration_texts,
                        narration_durations,
                    )

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

        # Popup card overlay setup
        popup: PopupCardOverlay | None = None
        if scenario.popup_card and scenario.popup_card.enabled:
            popup = PopupCardOverlay(scenario.popup_card.model_dump())

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
                    cursor=cursor, glow=glow, popup=popup,
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
        popup: PopupCardOverlay | None = None,
        narration_duration: float = 0.0,
    ) -> None:
        # Apply browser effects before action & collect post-effects
        if step.effects:
            self._apply_browser_effects(browser, step.effects)
            self._collect_post_effects(step.effects)
        else:
            self._step_post_effects.append([])

        # Determine card state
        has_card = popup and step.card
        card_items = (step.card.items or []) if step.card else []
        progressive = bool(card_items) and narration_duration > 0

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
            if popup:
                popup.inject(browser.evaluate_js)

        # Show popup card (after action + re-inject so JS globals exist)
        if has_card and step.card:
            popup.show(
                browser.evaluate_js,
                title=step.card.title,
                body=step.card.body,
                items=card_items,
                icon=step.card.icon,
                duration=narration_duration,
                progressive=progressive,
            )

        # Progressive reveal of card items synced with narration
        if has_card and progressive and card_items:
            self._reveal_card_items(
                browser, popup, card_items, narration_duration,
                base_wait=step.wait or 0.0,
            )
        else:
            # Wait: at least enough for narration to finish, or step.wait if longer
            effective_wait = max(step.wait or 0.0, narration_duration)
            if effective_wait > 0:
                time.sleep(effective_wait)

        # Hide card after narration/wait ends
        if has_card:
            popup.hide(browser.evaluate_js)

    def _reveal_card_items(
        self,
        browser: BrowserProvider,
        popup: PopupCardOverlay,
        items: list[str],
        narration_duration: float,
        *,
        base_wait: float = 0.0,
    ) -> None:
        """Progressively reveal list items spaced evenly across the narration."""
        n = len(items)
        total_time = max(narration_duration, base_wait)
        # Reserve first 15% for title/body, last 10% for reading last item
        reveal_start = total_time * 0.15
        reveal_end = total_time * 0.90
        interval = (reveal_end - reveal_start) / max(n, 1)

        time.sleep(reveal_start)
        for i in range(n):
            popup.reveal_next(browser.evaluate_js)
            if i < n - 1:
                time.sleep(max(0, interval - 0.35))  # subtract reveal_next sleep
        # Wait remaining time
        elapsed = reveal_start + n * interval
        remaining = total_time - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _apply_browser_effects(self, browser: BrowserProvider, effects: list[Effect]) -> None:
        for effect in effects:
            if self._effects.is_browser_effect(effect.type):
                handler = self._effects.get_browser_effect(effect.type)
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                handler.inject(browser.evaluate_js, params)
                if effect.duration:
                    time.sleep(effect.duration)

    def _collect_post_effects(self, effects: list[Effect]) -> None:
        """Collect post-processing effects for the current step."""
        collected: list[tuple[str, dict[str, Any]]] = []
        for effect in effects:
            if self._effects.is_post_effect(effect.type):
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                collected.append((effect.type, params))
        self._step_post_effects.append(collected)

    def _apply_post_effects_to_video(
        self, video_path: Path, output_path: Path,
    ) -> Path:
        """Apply per-step post-processing effects to the recorded video."""
        from moviepy import VideoFileClip, concatenate_videoclips

        # Check if any step actually has post effects
        has_any = any(efx for efx in self._step_post_effects)
        if not has_any:
            return video_path

        logger.info("Applying post-processing effects to video")

        clip = VideoFileClip(str(video_path))
        total_duration = clip.duration
        timestamps = self._step_timestamps

        # Build segments: each step runs from its timestamp to the next step's timestamp
        segments: list[Any] = []
        for i in range(len(timestamps)):
            start = timestamps[i]
            end = timestamps[i + 1] if i + 1 < len(timestamps) else total_duration
            if end <= start:
                continue

            sub = clip.subclipped(start, min(end, total_duration))

            # Apply post effects for this step
            if i < len(self._step_post_effects):
                for effect_name, params in self._step_post_effects[i]:
                    try:
                        handler = self._effects.get_post_effect(effect_name)
                        sub = handler.apply(sub, params)
                        logger.debug("Applied post-effect '%s' to step %d", effect_name, i)
                    except Exception:
                        logger.warning("Post-effect '%s' failed on step %d, skipping",
                                       effect_name, i, exc_info=True)

            segments.append(sub)

        if not segments:
            clip.close()
            return video_path

        result = concatenate_videoclips(segments)
        result.write_videofile(
            str(output_path),
            codec="libx264",
            preset="medium",
            audio=False,
            logger=None,
        )
        result.close()
        clip.close()
        logger.info("Post-effects applied: %s", output_path.name)
        return output_path

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

    # ── Pass 1.5: Avatar clips ─────────────────────────────────────────

    def _generate_avatar_clips(
        self, ws: Workspace, narration_map: dict[int, Path],
        narration_texts: dict[int, str] | None = None,
    ) -> dict[int, Path]:
        """Generate avatar video clips for each narration step."""
        if self.dry_run or not narration_map:
            return {}

        avatar_cfg = self._get_avatar_config()
        if not avatar_cfg.get("enabled", False):
            return {}

        provider_name = avatar_cfg.get("provider", "animated")

        import demodsl.providers.avatar  # noqa: F401
        try:
            avatar_dir = ws.root / "avatar_clips"
            avatar_dir.mkdir(exist_ok=True)
            avatar: AvatarProvider = AvatarProviderFactory.create(
                provider_name,
                output_dir=avatar_dir,
                **{k: v for k, v in avatar_cfg.items()
                   if k in ("api_key", "sadtalker_path") and v is not None},
            )
        except (EnvironmentError, ValueError) as exc:
            logger.warning("Cannot create '%s' avatar provider: %s — skipping avatars",
                           provider_name, exc)
            return {}

        avatar_clips: dict[int, Path] = {}
        for step_idx, audio_path in sorted(narration_map.items()):
            if not audio_path.exists():
                continue
            try:
                clip_path = avatar.generate(
                    audio_path,
                    image=avatar_cfg.get("image"),
                    size=avatar_cfg.get("size", 120),
                    style=avatar_cfg.get("style", "bounce"),
                    shape=avatar_cfg.get("shape", "circle"),
                    narration_text=(narration_texts or {}).get(step_idx),
                )
                avatar_clips[step_idx] = clip_path
            except Exception:
                logger.warning("Avatar generation failed for step %d, skipping",
                               step_idx, exc_info=True)

        avatar.close()
        logger.info("Generated %d avatar clips", len(avatar_clips))
        return avatar_clips

    def _get_avatar_config(self) -> dict[str, Any]:
        """Extract avatar config from the first scenario that has it, or return empty."""
        for scenario in self.config.scenarios:
            if scenario.avatar and scenario.avatar.enabled:
                return scenario.avatar.model_dump()
        return {"enabled": False}

    def _build_narration_texts(self) -> dict[int, str]:
        """Build a mapping of step_index → narration text."""
        texts: dict[int, str] = {}
        step_idx = 0
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    texts[step_idx] = step.narration
                step_idx += 1
        return texts

    # ── Subtitles ─────────────────────────────────────────────────────────

    def _get_subtitle_config(self) -> dict[str, Any]:
        """Extract subtitle config: top-level first, then scenario-level fallback."""
        if self.config.subtitle and self.config.subtitle.enabled:
            return self.config.subtitle.model_dump()
        for scenario in self.config.scenarios:
            if scenario.subtitle and scenario.subtitle.enabled:
                return scenario.subtitle.model_dump()
        return {"enabled": False}

    def _burn_subtitles(
        self,
        video_path: Path,
        ws: Workspace,
        narration_texts: dict[int, str],
        narration_durations: dict[int, float],
    ) -> Path:
        """Generate ASS subtitle file and burn it into the video."""
        raw_cfg = self._get_subtitle_config()
        cfg = get_merged_subtitle_config(raw_cfg)

        speed_wps = SPEED_PRESETS.get(cfg.get("speed", "normal"), 2.5)

        entries = _build_subtitle_entries(
            narration_texts,
            self._step_timestamps,
            narration_durations,
            speed_wps=speed_wps,
            max_words_per_line=cfg.get("max_words_per_line", 8),
            style_name=cfg.get("style", "classic"),
        )

        if not entries:
            logger.info("No subtitle entries to burn, skipping")
            return video_path

        ass_path = ws.root / "subtitles.ass"
        generate_ass_subtitle(entries, cfg, ass_path)

        output = ws.root / "subtitled.mp4"
        return burn_subtitles(video_path, ass_path, output)

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
