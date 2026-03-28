"""NarrationOrchestrator — voice generation, timing, and audio mixing."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from demodsl.models import DemoConfig
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import VoiceProvider, VoiceProviderFactory

logger = logging.getLogger(__name__)

_TTS_THROTTLE_DELAY = 0.5  # seconds between consecutive TTS API calls


class NarrationOrchestrator:
    """Handles all narration-related work: TTS generation, duration measurement,
    text extraction, and combined audio track building."""

    def __init__(self, config: DemoConfig, *, skip_voice: bool = False) -> None:
        self.config = config
        self.skip_voice = skip_voice

    # ── Public API ────────────────────────────────────────────────────────

    def generate_narrations(
        self, ws: Workspace, *, dry_run: bool = False,
    ) -> dict[int, Path]:
        if self.skip_voice or dry_run:
            if not dry_run:
                logger.info("Voice skipped (--skip-voice)")
            return self._dry_run_narrations()

        voice_config = self.config.voice
        engine = voice_config.engine if voice_config else "dummy"

        import demodsl.providers.voice  # noqa: F401

        try:
            voice: VoiceProvider = VoiceProviderFactory.create(
                engine, output_dir=ws.audio_clips,
            )
        except (EnvironmentError, ValueError):
            logger.warning("Cannot create '%s' provider, falling back to dummy", engine)
            voice = VoiceProviderFactory.create("dummy", output_dir=ws.audio_clips)

        narration_map: dict[int, Path] = {}
        step_idx = 0
        ref_audio: Path | None = None
        if voice_config and voice_config.reference_audio:
            ref_audio = Path(voice_config.reference_audio)
            if not ref_audio.is_file():
                logger.warning("reference_audio '%s' not found, ignoring", ref_audio)
                ref_audio = None
        call_count = 0
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    if call_count > 0:
                        time.sleep(_TTS_THROTTLE_DELAY)
                    path = voice.generate(
                        text=step.narration,
                        voice_id=voice_config.voice_id if voice_config else "josh",
                        speed=voice_config.speed if voice_config else 1.0,
                        pitch=voice_config.pitch if voice_config else 0,
                        reference_audio=ref_audio,
                    )
                    narration_map[step_idx] = path
                    call_count += 1
                step_idx += 1

        voice.close()
        logger.info("Generated %d narration clips", len(narration_map))
        return narration_map

    @staticmethod
    def measure_narration_durations(narration_map: dict[int, Path]) -> dict[int, float]:
        """Return the duration in seconds of each narration clip."""
        from pydub import AudioSegment

        durations: dict[int, float] = {}
        for step_idx, clip_path in narration_map.items():
            if clip_path.exists():
                clip = AudioSegment.from_file(str(clip_path))
                durations[step_idx] = len(clip) / 1000.0
        return durations

    def build_narration_texts(self) -> dict[int, str]:
        """Build a mapping of step_index → narration text."""
        texts: dict[int, str] = {}
        step_idx = 0
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    texts[step_idx] = step.narration
                step_idx += 1
        return texts

    def build_narration_track(
        self,
        narration_map: dict[int, Path],
        output: Path,
        step_timestamps: list[float],
    ) -> Path | None:
        """Combine narration clips into a single audio track aligned to step timestamps."""
        from pydub import AudioSegment

        if not narration_map:
            return None

        if not step_timestamps:
            logger.warning("No step timestamps recorded, cannot build narration track")
            return None

        total_ms = int((step_timestamps[-1] + 10) * 1000)
        combined = AudioSegment.silent(duration=total_ms)

        for step_idx, clip_path in sorted(narration_map.items()):
            if not clip_path.exists():
                continue
            clip = AudioSegment.from_file(str(clip_path))
            if step_idx < len(step_timestamps):
                offset_ms = int(step_timestamps[step_idx] * 1000)
            else:
                offset_ms = total_ms - len(clip)

            end_ms = offset_ms + len(clip)
            if end_ms > len(combined):
                combined += AudioSegment.silent(duration=end_ms - len(combined))

            combined = combined.overlay(clip, position=offset_ms)
            logger.debug(
                "Narration step %d at %.1fs (%.1fs long)",
                step_idx, offset_ms / 1000, len(clip) / 1000,
            )

        combined.export(str(output), format="mp3")
        logger.info("Combined narration track: %s (%.1fs)", output.name, len(combined) / 1000)
        return output

    # ── Private helpers ───────────────────────────────────────────────────

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
