"""DemoEngine — main orchestrator for DemoDSL."""

from __future__ import annotations

import logging
from pathlib import Path

from demodsl.config_loader import load_config
from demodsl.effects.browser_effects import register_all_browser_effects
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig
from demodsl.orchestrators.export import ExportOrchestrator
from demodsl.orchestrators.narration import NarrationOrchestrator
from demodsl.orchestrators.post_processing import PostProcessingOrchestrator
from demodsl.orchestrators.scenario import ScenarioOrchestrator
from demodsl.pipeline.stages import PipelineContext, build_chain
from demodsl.pipeline.workspace import Workspace

logger = logging.getLogger(__name__)


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
        output_dir: Path | None = None,
        renderer: str = "moviepy",
    ) -> None:
        self.config_path = config_path
        self.dry_run = dry_run
        self.skip_voice = skip_voice
        self.skip_deploy = skip_deploy
        self.tts_cache = tts_cache
        self.renderer = renderer

        raw = load_config(config_path)
        self.config = DemoConfig(**raw)
        self._output_dir = output_dir or Path(
            self.config.output.directory if self.config.output else "output"
        )

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
            # Pass 1: Voice
            narration_map = self._narration.generate_narrations(
                ws, dry_run=self.dry_run
            )
            narration_durations = self._narration.measure_narration_durations(
                narration_map
            )

            # Pass 1.5: Avatar
            narration_texts = self._narration.build_narration_texts()
            avatar_clips = self._post.generate_avatar_clips(
                ws,
                narration_map,
                narration_texts,
                dry_run=self.dry_run,
            )

            # Pass 2: Scenarios — browser capture
            recording = self._scenario.run_scenarios(
                ws,
                narration_durations=narration_durations,
                dry_run=self.dry_run,
            )
            raw_videos = recording.raw_videos
            step_timestamps = recording.step_timestamps
            step_post_effects = recording.step_post_effects

            # Concatenate multi-scenario videos into one
            if len(raw_videos) > 1:
                combined = self._concat_videos(raw_videos, ws.root / "combined.mp4")
                raw_videos = [combined]

            # Pass 2.5: Build combined narration audio track
            narration_audio: Path | None = None
            if narration_map:
                narration_audio = self._narration.build_narration_track(
                    narration_map,
                    ws.root / "narration_combined.mp3",
                    step_timestamps,
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

            # Pass 3.5: Apply post-processing effects
            final = ctx.processed_video or ctx.raw_video
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

                out_name = (
                    self.config.output.filename if self.config.output else "output.mp4"
                )
                dest = self._output_dir / out_name
                self._export.export_video(final, dest, audio=narration_audio)
                logger.info("Final output: %s", dest)

                if not self.skip_deploy:
                    deploy_url = self._export.deploy_to_cloud(dest)
                    if deploy_url:
                        logger.info("Deployed to: %s", deploy_url)

                return dest

            logger.info("Pipeline completed (no output video produced in dry-run)")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────

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
