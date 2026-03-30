"""NarrationOrchestrator — voice generation, timing, and audio mixing."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal

from demodsl.models import DemoConfig
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import VoiceProvider, VoiceProviderFactory
from demodsl.providers.tts_cache import TTSCache

logger = logging.getLogger(__name__)

# Type alias for collision tuples: (step_i, step_j, overlap_seconds)
Collision = tuple[int, int, float]

_TTS_THROTTLE_DELAY = 0.5  # seconds between consecutive TTS API calls


class NarrationOrchestrator:
    """Handles all narration-related work: TTS generation, duration measurement,
    text extraction, and combined audio track building."""

    def __init__(
        self,
        config: DemoConfig,
        *,
        skip_voice: bool = False,
        tts_cache: bool = True,
    ) -> None:
        self.config = config
        self.skip_voice = skip_voice
        self._tts_cache = TTSCache(enabled=tts_cache)

    # ── Public API ────────────────────────────────────────────────────────

    def generate_narrations(
        self,
        ws: Workspace,
        *,
        dry_run: bool = False,
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
                engine,
                output_dir=ws.audio_clips,
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
        cache_hits = 0
        clip_counter = 0
        provider_extra = voice.cache_extra()
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    clip_counter += 1
                    v_id = voice_config.voice_id if voice_config else "josh"
                    v_speed = voice_config.speed if voice_config else 1.0
                    v_pitch = voice_config.pitch if voice_config else 0

                    dest_path = ws.audio_clips / f"narration_{clip_counter:03d}.mp3"

                    cached = self._tts_cache.lookup(
                        engine=engine,
                        text=step.narration,
                        voice_id=v_id,
                        speed=v_speed,
                        pitch=v_pitch,
                        reference_audio=ref_audio,
                        extra=provider_extra,
                        dest_path=dest_path,
                    )
                    if cached is not None:
                        narration_map[step_idx] = cached
                        cache_hits += 1
                    else:
                        if call_count > 0:
                            time.sleep(_TTS_THROTTLE_DELAY)
                        path = voice.generate(
                            text=step.narration,
                            voice_id=v_id,
                            speed=v_speed,
                            pitch=v_pitch,
                            reference_audio=ref_audio,
                        )
                        self._tts_cache.store(
                            engine=engine,
                            text=step.narration,
                            voice_id=v_id,
                            speed=v_speed,
                            pitch=v_pitch,
                            reference_audio=ref_audio,
                            extra=provider_extra,
                            generated_path=path,
                        )
                        narration_map[step_idx] = path
                        call_count += 1
                step_idx += 1

        voice.close()
        logger.info(
            "Generated %d narration clips (%d from cache, %d freshly generated)",
            len(narration_map),
            cache_hits,
            call_count,
        )
        return narration_map

    @staticmethod
    def measure_narration_durations(narration_map: dict[int, Path]) -> dict[int, float]:
        """Return the duration in seconds of each narration clip."""
        if not narration_map:
            return {}

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

        voice_config = self.config.voice
        strategy: Literal["warn", "shift", "truncate"] = (
            voice_config.collision_strategy if voice_config else "warn"
        )
        gap_s = voice_config.narration_gap if voice_config else 0.3

        total_ms = int((step_timestamps[-1] + 10) * 1000)
        combined = AudioSegment.silent(duration=total_ms)

        # Pre-load clips and detect collisions
        clips: dict[int, AudioSegment] = {}
        for step_idx, clip_path in sorted(narration_map.items()):
            if clip_path.exists():
                clips[step_idx] = AudioSegment.from_file(str(clip_path))

        durations = {idx: len(clip) / 1000.0 for idx, clip in clips.items()}
        collisions = self.detect_collisions(step_timestamps, durations)

        if collisions:
            for step_a, step_b, overlap in collisions:
                logger.warning(
                    "Narration collision: step %d overlaps step %d by %.2fs",
                    step_a,
                    step_b,
                    overlap,
                )

        # Build offset map (may be adjusted by strategy)
        offsets: dict[int, int] = {}
        sorted_indices = sorted(clips.keys())
        for step_idx in sorted_indices:
            if step_idx < len(step_timestamps):
                offsets[step_idx] = int(step_timestamps[step_idx] * 1000)
            else:
                offsets[step_idx] = total_ms - len(clips[step_idx])

        if collisions and strategy == "shift":
            gap_ms = int(gap_s * 1000)
            for step_a, step_b, _overlap in collisions:
                if step_a in offsets and step_b in offsets and step_a in clips:
                    min_start = offsets[step_a] + len(clips[step_a]) + gap_ms
                    if offsets[step_b] < min_start:
                        shift_ms = min_start - offsets[step_b]
                        logger.warning(
                            "Shifting narration step %d by %dms to avoid collision",
                            step_b,
                            shift_ms,
                        )
                        offsets[step_b] = min_start

        if collisions and strategy == "truncate":
            _FADE_MS = 200
            for step_a, step_b, _overlap in collisions:
                if step_a in clips and step_b in offsets:
                    max_len_ms = offsets[step_b] - offsets.get(step_a, 0)
                    if max_len_ms > _FADE_MS:
                        clip_a = clips[step_a]
                        if len(clip_a) > max_len_ms:
                            clips[step_a] = clip_a[:max_len_ms].fade_out(_FADE_MS)
                            logger.warning(
                                "Truncated narration step %d to %dms with %dms fade-out",
                                step_a,
                                max_len_ms,
                                _FADE_MS,
                            )

        # Place clips
        for step_idx in sorted_indices:
            clip = clips[step_idx]
            offset_ms = offsets[step_idx]

            end_ms = offset_ms + len(clip)
            if end_ms > len(combined):
                combined += AudioSegment.silent(duration=end_ms - len(combined))

            combined = combined.overlay(clip, position=offset_ms)
            logger.debug(
                "Narration step %d at %.1fs (%.1fs long)",
                step_idx,
                offset_ms / 1000,
                len(clip) / 1000,
            )

        combined.export(str(output), format="mp3")
        logger.info(
            "Combined narration track: %s (%.1fs)", output.name, len(combined) / 1000
        )
        return output

    @staticmethod
    def detect_collisions(
        step_timestamps: list[float],
        narration_durations: dict[int, float],
    ) -> list[Collision]:
        """Detect overlapping narration clips.

        Returns a list of ``(step_a, step_b, overlap_seconds)`` for every pair
        of consecutive narrated steps where audio from *step_a* bleeds into
        *step_b*.
        """
        sorted_indices = sorted(narration_durations.keys())
        collisions: list[Collision] = []
        for pos in range(len(sorted_indices) - 1):
            idx_a = sorted_indices[pos]
            idx_b = sorted_indices[pos + 1]
            if idx_a >= len(step_timestamps) or idx_b >= len(step_timestamps):
                continue
            end_a = step_timestamps[idx_a] + narration_durations[idx_a]
            start_b = step_timestamps[idx_b]
            if end_a > start_b:
                collisions.append((idx_a, idx_b, end_a - start_b))
        return collisions

    # ── Private helpers ───────────────────────────────────────────────────

    def _dry_run_narrations(self) -> dict[int, Path]:
        step_idx = 0
        for scenario in self.config.scenarios:
            for step in scenario.steps:
                if step.narration:
                    logger.info(
                        "  [DRY-RUN] Narration step %d: %s...",
                        step_idx,
                        step.narration[:60].strip(),
                    )
                step_idx += 1
        return {}
