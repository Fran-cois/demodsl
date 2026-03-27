"""DemoEngine — main orchestrator for DemoDSL."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import yaml

from demodsl.commands import get_command
from demodsl.effects.browser_effects import register_all_browser_effects
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

        raw = yaml.safe_load(config_path.read_text())
        self.config = DemoConfig(**raw)
        self._output_dir = output_dir or Path(
            self.config.output.directory if self.config.output else "output"
        )

        # Effects
        self._effects = EffectRegistry()
        register_all_browser_effects(self._effects)
        register_all_post_effects(self._effects)

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
            # Pass 1: Scenarios — browser capture
            raw_videos = self._run_scenarios(ws)

            # Pass 2: Voice — narration
            narration_map = self._generate_narrations(ws)

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
                import shutil
                out_name = self.config.output.filename if self.config.output else "output.mp4"
                dest = self._output_dir / out_name
                shutil.copy2(final, dest)
                logger.info("Final output: %s", dest)
                return dest

            logger.info("Pipeline completed (no output video produced in dry-run)")
            return None

    # ── Pass 1: Scenarios ─────────────────────────────────────────────────

    def _run_scenarios(self, ws: Workspace) -> list[Path]:
        if self.dry_run:
            return self._dry_run_scenarios()

        # Import to trigger factory registration
        import demodsl.providers.browser  # noqa: F401

        videos: list[Path] = []
        for scenario in self.config.scenarios:
            video = self._execute_scenario(scenario, ws)
            if video:
                videos.append(video)
        return videos

    def _execute_scenario(self, scenario: Scenario, ws: Workspace) -> Path | None:
        browser: BrowserProvider = BrowserProviderFactory.create("playwright")
        browser.launch(
            browser_type=scenario.browser,
            viewport=scenario.viewport,
            video_dir=ws.raw_video,
        )
        logger.info("Running scenario: %s", scenario.name)

        try:
            for i, step in enumerate(scenario.steps):
                logger.info("  Step %d: %s", i + 1, step.action)
                self._execute_step(browser, step, ws)
        finally:
            video_path = browser.close()

        if video_path:
            logger.info("Recorded video: %s", video_path)
        return video_path

    def _execute_step(self, browser: BrowserProvider, step: Step, ws: Workspace) -> None:
        # Apply browser effects before action
        if step.effects:
            self._apply_browser_effects(browser, step.effects)

        # Execute action command
        cmd = get_command(step.action, output_dir=ws.frames)
        cmd.execute(browser, step)

        # Wait if specified
        if step.wait:
            time.sleep(step.wait)

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
