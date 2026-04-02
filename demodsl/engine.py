"""DemoEngine — main orchestrator for DemoDSL."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from demodsl import __version__
from demodsl.config_loader import load_config
from demodsl.effects.browser_effects import register_all_browser_effects
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig
from demodsl.orchestrators.export import ExportOrchestrator
from demodsl.orchestrators.narration import NarrationOrchestrator
from demodsl.orchestrators.post_processing import PostProcessingOrchestrator
from demodsl.orchestrators.scenario import ScenarioOrchestrator
from demodsl.pipeline.run_cache import RunCache
from demodsl.pipeline.stages import PipelineContext, build_chain
from demodsl.pipeline.workspace import Workspace

logger = logging.getLogger(__name__)


# ── Hook system ───────────────────────────────────────────────────────────

HOOK_EVENTS = (
    "engine_start",
    "engine_end",
    "voice_start",
    "voice_end",
    "record_start",
    "record_end",
    "pipeline_start",
    "pipeline_end",
    "export_start",
    "export_end",
)


def _discover_hooks(
    config_dict: dict[str, Any],
) -> dict[str, list[Callable[..., None]]]:
    """Auto-discover plugins registered under ``demodsl.hooks`` entry-points."""
    from importlib.metadata import entry_points

    hooks: dict[str, list[Callable[..., None]]] = {evt: [] for evt in HOOK_EVENTS}
    for ep in entry_points(group="demodsl.hooks"):
        try:
            cls = ep.load()
            instance = cls(config_dict=config_dict)
            for evt in HOOK_EVENTS:
                method = getattr(instance, f"on_{evt}", None)
                if callable(method):
                    hooks[evt].append(method)
            logger.info("Discovered hook plugin '%s' from %s", ep.name, ep.value)
        except Exception:
            logger.warning("Failed to load hook plugin '%s'", ep.name, exc_info=True)
    return hooks


def _dispatch(
    hooks: dict[str, list[Callable[..., None]]], event: str, **kwargs: Any
) -> None:
    """Fire all callbacks registered for *event*."""
    for cb in hooks.get(event, []):
        try:
            cb(**kwargs)
        except Exception:
            logger.warning("Hook callback %s failed", cb, exc_info=True)


class DemoEngine:
    """Orchestrator: loads config, runs scenarios, executes the pipeline."""

    def __init__(
        self,
        config_path: Path,
        *,
        dry_run: bool = False,
        skip_voice: bool = False,
        skip_deploy: bool = False,
        tts_cache: bool = True,
        run_cache: bool = True,
        cache_dir: Path | None = None,
        force_record: bool = False,
        output_dir: Path | None = None,
        renderer: str = "moviepy",
    ) -> None:
        self.config_path = config_path
        self.dry_run = dry_run
        self.skip_voice = skip_voice
        self.skip_deploy = skip_deploy
        self.tts_cache = tts_cache
        self.renderer = renderer
        self._force_record = force_record

        raw = load_config(config_path)
        self.config = DemoConfig(**raw)
        self._output_dir = output_dir or Path(
            self.config.output.directory if self.config.output else "output"
        )

        # Run cache
        self._cache = RunCache(config_path, enabled=run_cache, cache_dir=cache_dir)

        # Effects
        self._effects = EffectRegistry()
        register_all_browser_effects(self._effects)
        register_all_post_effects(self._effects)

        # Sub-orchestrators
        self._narration = NarrationOrchestrator(
            self.config, skip_voice=skip_voice, tts_cache=tts_cache
        )
        self._scenario = ScenarioOrchestrator(self.config, self._effects)
        self._post = PostProcessingOrchestrator(
            self.config, self._effects, renderer=renderer
        )
        self._export = ExportOrchestrator(self.config)

        logger.info(
            "demodsl v%s — %s (%s)",
            __version__,
            self.config.metadata.title,
            config_path.name,
        )

        # Auto-discover hook plugins (no YAML needed)
        self._hooks = _discover_hooks(raw)

    # ── Public API ────────────────────────────────────────────────────────

    def validate(self) -> DemoConfig:
        """Parse + validate only (already done in __init__)."""
        logger.info("Validation OK: %s", self.config.metadata.title)
        return self.config

    def run(self) -> Path | None:
        """Execute the full demo pipeline."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Compute per-section fingerprints for cache invalidation
        fps = RunCache.fingerprint_config_sections(self.config)

        # Collect pause config for narration track
        pauses: list[dict[str, object]] = []
        if self.config.edit and self.config.edit.pauses:
            pauses = [p.model_dump() for p in self.config.edit.pauses]

        with Workspace() as ws:
            _dispatch(self._hooks, "engine_start", config=self.config)

            # ── Pass 1: Voice ─────────────────────────────────────────────
            narration_map: dict[int, Path] = {}
            narration_durations: dict[int, float] = {}

            cached_voice = self._cache.section_unchanged(
                "voice", fps["voice"]
            ) and self._cache.section_unchanged("scenarios", fps["scenarios"])
            cached_narration = self._cache.get_artifact("narration_map")

            if cached_voice and cached_narration:
                # Restore narration clips from cache
                restored_all = True
                for step_key, rel_path in cached_narration.items():
                    dest = ws.audio_clips / Path(rel_path).name
                    if self._cache.restore_file(rel_path, dest):
                        narration_map[int(step_key)] = dest
                    else:
                        restored_all = False
                        break

                if restored_all:
                    cached_durs = self._cache.get_artifact("narration_durations")
                    if cached_durs:
                        narration_durations = {
                            int(k): v for k, v in cached_durs.items()
                        }
                        logger.info(
                            "Restored %d narration clips from run cache",
                            len(narration_map),
                        )
                    else:
                        narration_durations = (
                            self._narration.measure_narration_durations(narration_map)
                        )
                else:
                    narration_map = {}

            if not narration_map:
                _dispatch(self._hooks, "voice_start")
                narration_map = self._narration.generate_narrations(
                    ws, dry_run=self.dry_run
                )
                narration_durations = self._narration.measure_narration_durations(
                    narration_map
                )
                # Store narration clips in cache
                cached_map: dict[str, str] = {}
                for step_idx, clip_path in narration_map.items():
                    rel = f"audio_clips/{clip_path.name}"
                    self._cache.store_file(clip_path, rel)
                    cached_map[str(step_idx)] = rel
                self._cache.update_manifest(
                    {"voice": fps["voice"], "scenarios": fps["scenarios"]},
                    {
                        "narration_map": cached_map,
                        "narration_durations": {
                            str(k): v for k, v in narration_durations.items()
                        },
                    },
                )

            _dispatch(self._hooks, "voice_end", narration_map=narration_map)

            # Pass 1.5: Avatar
            narration_texts = self._narration.build_narration_texts()
            avatar_clips = self._post.generate_avatar_clips(
                ws,
                narration_map,
                narration_texts,
                dry_run=self.dry_run,
            )

            # ── Pass 2: Scenarios — browser capture ───────────────────────
            raw_videos: list[Path] = []
            step_timestamps: list[float] = []
            step_post_effects: list[list[object]] = []
            scroll_positions: list[tuple[float, int]] = []

            scenarios_cached = (
                self._cache.section_unchanged("scenarios", fps["scenarios"])
                and not self._force_record
            )
            cached_videos = self._cache.get_artifact("raw_videos")

            if scenarios_cached and cached_videos:
                # Try to restore raw videos from cache
                restored_all = True
                for rel_path in cached_videos:
                    dest = ws.raw_video / Path(rel_path).name
                    if self._cache.restore_file(rel_path, dest):
                        # Validate the restored video is not broken
                        if self._is_suspect_video(dest):
                            logger.warning(
                                "Cached video '%s' looks suspect (too small or "
                                "very short). Use --no-run-cache or --force-record "
                                "to re-record.",
                                dest.name,
                            )
                            restored_all = False
                            break
                        raw_videos.append(dest)
                    else:
                        restored_all = False
                        break

                if restored_all:
                    step_timestamps = self._cache.get_artifact("step_timestamps") or []
                    step_post_effects = (
                        self._cache.get_artifact("step_post_effects") or []
                    )
                    logger.info(
                        "Restored %d raw videos from run cache (skipped browser recording)",
                        len(raw_videos),
                    )
                else:
                    raw_videos = []

            if not raw_videos:
                _dispatch(self._hooks, "record_start")
                recording = self._scenario.run_scenarios(
                    ws,
                    narration_durations=narration_durations,
                    dry_run=self.dry_run,
                )
                raw_videos = recording.raw_videos
                step_timestamps = recording.step_timestamps
                step_post_effects = recording.step_post_effects
                scroll_positions = recording.scroll_positions

                # Store in cache
                cached_vids: list[str] = []
                for vid in raw_videos:
                    if vid.exists():
                        rel = f"raw_video/{vid.name}"
                        self._cache.store_file(vid, rel)
                        cached_vids.append(rel)
                self._cache.update_manifest(
                    {"scenarios": fps["scenarios"]},
                    {
                        "raw_videos": cached_vids,
                        "step_timestamps": step_timestamps,
                        "step_post_effects": step_post_effects,
                    },
                )

            _dispatch(self._hooks, "record_end", raw_videos=raw_videos)

            # Concatenate multi-scenario videos into one
            if len(raw_videos) > 1:
                combined = self._concat_videos(raw_videos, ws.root / "combined.mp4")
                raw_videos = [combined]

            # ── Pass 2.75: Device rendering (Blender 3D) ─────────────────
            # Skip if render_device_3d is declared in the pipeline (handled there).
            _pipeline_has_3d = any(
                s.stage_type == "render_device_3d" for s in self.config.pipeline
            )
            if (
                self.config.device_rendering
                and raw_videos
                and raw_videos[0].exists()
                and not _pipeline_has_3d
            ):
                raw_videos = [
                    self._apply_device_rendering(
                        raw_videos[0],
                        self.config.device_rendering,
                        ws.root / "device_rendered.mp4",
                        scroll_positions=scroll_positions,
                    )
                ]

            # ── Pass 2.5: Build combined narration audio track ────────────
            narration_audio: Path | None = None
            if narration_map:
                narration_audio = self._narration.build_narration_track(
                    narration_map,
                    ws.root / "narration_combined.mp3",
                    step_timestamps,
                    pauses=pauses,
                )

            # ── Pass 3: Pipeline — chain of responsibility ────────────────
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
                    "webinar": self.config.webinar,
                },
                scroll_positions=scroll_positions,
                device_rendering=self.config.device_rendering,
            )

            pipeline_dicts = [
                {"stage_type": s.stage_type, "params": s.params}
                for s in self.config.pipeline
            ]
            chain = build_chain(pipeline_dicts)
            _dispatch(self._hooks, "pipeline_start", ctx=ctx)
            if chain:
                ctx = chain.handle(ctx)
            _dispatch(self._hooks, "pipeline_end", ctx=ctx)

            # ── Pass 3.5: Apply post-processing effects ───────────────────
            final = ctx.processed_video or ctx.raw_video

            # Insert freeze-frame pauses if requested
            freeze_pauses = [p for p in pauses if p.get("type") == "freeze"]
            if final and final.exists() and freeze_pauses and step_timestamps:
                final = self._insert_freeze_pauses(
                    final, step_timestamps, freeze_pauses, ws
                )

            if final and final.exists() and step_post_effects:
                if self.renderer == "remotion":
                    final = self._post.remotion_full_compose(
                        final,
                        ws,
                        narration_durations,
                        step_timestamps,
                        step_post_effects,
                        avatar_clips=avatar_clips,
                        narration_texts=narration_texts,
                    )
                else:
                    post_processed = ws.root / "post_effects_applied.mp4"
                    applied = self._post.apply_post_effects_to_video(
                        final,
                        post_processed,
                        step_timestamps,
                        step_post_effects,
                    )
                    if applied and applied.exists():
                        final = applied

            # Copy final output
            if final and final.exists():
                if self.renderer != "remotion":
                    # Composite avatar overlays
                    if avatar_clips:
                        from demodsl.effects.avatar_overlay import composite_avatar

                        avatar_cfg = self._post.get_avatar_config()
                        composited = ws.root / "avatar_composited.mp4"
                        final = composite_avatar(
                            final,
                            avatar_clips,
                            step_timestamps,
                            narration_durations,
                            composited,
                            position=avatar_cfg.get("position", "bottom-right"),
                            size=avatar_cfg.get("size", 120),
                            show_subtitle=avatar_cfg.get("show_subtitle", False),
                            subtitle_font_size=avatar_cfg.get("subtitle_font_size", 18),
                            subtitle_font_color=avatar_cfg.get(
                                "subtitle_font_color", "#FFFFFF"
                            ),
                            subtitle_bg_color=avatar_cfg.get(
                                "subtitle_bg_color", "rgba(0,0,0,0.7)"
                            ),
                            narration_texts=narration_texts or None,
                        )

                    # Burn subtitles
                    subtitle_cfg = self._post.get_subtitle_config()
                    if subtitle_cfg.get("enabled", False) and narration_texts:
                        final = self._post.burn_subtitles(
                            final,
                            ws,
                            narration_texts,
                            narration_durations,
                            step_timestamps,
                        )

                # ── @demodsl branding watermark (opt-out) ────────────
                branding = True
                if self.config.output and self.config.output.branding is False:
                    branding = False
                if branding:
                    watermarked = ws.root / "watermarked.mp4"
                    final = self._burn_watermark(final, watermarked)

                out_name = (
                    self.config.output.filename if self.config.output else "output.mp4"
                )
                if not Path(out_name).suffix:
                    out_name += ".mp4"
                dest = self._output_dir / out_name
                _dispatch(self._hooks, "export_start", video=final, dest=dest)
                self._export.export_video(final, dest, audio=narration_audio)
                logger.info("Final output: %s", dest)
                _dispatch(self._hooks, "export_end", output=dest)

                # Save final pipeline fingerprints
                self._cache.update_manifest(
                    fps,
                    {"final_output": str(dest)},
                )

                if not self.skip_deploy:
                    deploy_url = self._export.deploy_to_cloud(dest)
                    if deploy_url:
                        logger.info("Deployed to: %s", deploy_url)

                _dispatch(self._hooks, "engine_end", output=dest)
                return dest

            _dispatch(self._hooks, "engine_end", output=None)
            logger.info("Pipeline completed (no output video produced in dry-run)")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _burn_watermark(video: Path, output: Path) -> Path:
        """Burn a mandatory '@demodsl' text watermark onto the video."""
        import subprocess

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            (
                "drawtext=text='@demodsl'"
                ":fontsize=24"
                ":fontcolor=white@0.5"
                ":x=w-tw-16"
                ":y=h-th-12"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.warning("Watermark burn failed: %s", result.stderr[-400:])
            return video
        return output

    @staticmethod
    def _apply_device_rendering(
        video: Path,
        config: "DeviceRendering",  # noqa: F821
        output: Path,
        *,
        scroll_positions: list[tuple[float, int]] | None = None,
    ) -> Path:
        """Render *video* inside a 3D device mockup via Blender.

        Falls back gracefully to the original video if Blender is not
        available or the render fails.  The provider is discovered
        automatically from installed plugins (``demodsl-blender``).
        """
        try:
            from demodsl.providers.base import BlenderProviderFactory

            blender = BlenderProviderFactory.create("headless")
            if not blender.check_available():
                logger.warning(
                    "Blender not available — skipping 3D device rendering. "
                    "The pipeline continues with the raw recording."
                )
                return video
            return blender.render(
                video, config, output, scroll_positions=scroll_positions
            )
        except Exception:
            logger.warning(
                "Blender 3D device rendering failed — continuing with raw video.",
                exc_info=True,
            )
            return video

    @staticmethod
    def _insert_freeze_pauses(
        video: Path,
        step_timestamps: list[float],
        freeze_pauses: list[dict[str, object]],
        ws: Workspace,
    ) -> Path:
        """Insert freeze-frame pauses into the video at specified step boundaries."""
        import subprocess

        # Sort pauses by step index descending so offsets stay valid
        sorted_pauses = sorted(
            freeze_pauses,
            key=lambda p: int(p["after_step"]),
            reverse=True,  # type: ignore[arg-type]
        )

        current = video
        for pause in sorted_pauses:
            step_idx = int(pause["after_step"])  # type: ignore[arg-type]
            duration = float(pause["duration"])  # type: ignore[arg-type]

            # Compute the split timestamp (end of step = start of next step)
            if step_idx + 1 < len(step_timestamps):
                split_t = step_timestamps[step_idx + 1]
            elif step_idx < len(step_timestamps):
                # Last step: freeze at end
                split_t = step_timestamps[step_idx] + 2.0
            else:
                continue

            out = ws.root / f"freeze_pause_{step_idx}.mp4"
            # ffmpeg: extract last frame at split_t, loop for duration, then concat
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(current),
                "-filter_complex",
                (
                    f"[0:v]split=2[before][after];"
                    f"[before]trim=0:{split_t},setpts=PTS-STARTPTS[v1];"
                    f"[after]trim={split_t},setpts=PTS-STARTPTS[v2];"
                    f"[0:v]trim={split_t}:{split_t + 0.04},setpts=PTS-STARTPTS,"
                    f"loop=loop={int(duration * 25)}:size=1:start=0,setpts=PTS-STARTPTS[freeze];"
                    f"[v1][freeze][v2]concat=n=3:v=1:a=0[outv]"
                ),
                "-map",
                "[outv]",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(out),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and out.exists():
                logger.info(
                    "Inserted %.1fs freeze pause after step %d at %.1fs",
                    duration,
                    step_idx,
                    split_t,
                )
                current = out
            else:
                logger.warning(
                    "Freeze pause insertion failed for step %d: %s",
                    step_idx,
                    result.stderr[-200:] if result.stderr else "unknown error",
                )

        return current

    @staticmethod
    def _is_suspect_video(path: Path) -> bool:
        """Return ``True`` if the video file looks broken (too small or bad codec)."""
        if not path.exists():
            return True
        size = path.stat().st_size
        # Less than 10 KB is almost certainly a broken file
        if size < 10_240:
            return True
        # Try a quick ffprobe check for duration if available
        try:
            import subprocess

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=duration,codec_name",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json

                info = json.loads(result.stdout)
                streams = info.get("streams", [])
                if streams:
                    stream = streams[0]
                    raw_dur = stream.get("duration")
                    duration = float(raw_dur) if raw_dur and raw_dur != "N/A" else 0.0
                    codec = stream.get("codec_name", "")
                    if duration < 1.0:
                        logger.warning(
                            "Cached video duration=%.1fs — likely broken", duration
                        )
                        return True
                    if codec == "mjpeg":
                        logger.warning(
                            "Cached video uses MJPEG codec — likely a static "
                            "slideshow, not a real recording"
                        )
                        return True
        except Exception:
            pass  # ffprobe not available — rely on file-size check only
        return False

    @staticmethod
    def _concat_videos(videos: list[Path], output: Path) -> Path:
        """Concatenate multiple scenario videos using ffmpeg concat demuxer."""
        import subprocess

        list_file = output.with_suffix(".txt")
        list_file.write_text(
            "\n".join(f"file '{v}'" for v in videos if v.exists()),
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("Video concatenation failed: %s", result.stderr[-300:])
            return videos[0]
        logger.info("Concatenated %d videos → %s", len(videos), output.name)
        return output
