"""PostProcessingOrchestrator — effects, avatars, subtitles, Remotion composition."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.effects.registry import EffectRegistry
from demodsl.effects.subtitle import (
    SPEED_PRESETS,
    build_subtitle_entries,
    burn_subtitles,
    generate_ass_subtitle,
    get_merged_subtitle_config,
)
from demodsl.models import DemoConfig
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import AvatarProvider, AvatarProviderFactory, RenderProviderFactory

logger = logging.getLogger(__name__)


class PostProcessingOrchestrator:
    """Handles post-processing effects, avatar generation, subtitles,
    and Remotion full-composition."""

    def __init__(self, config: DemoConfig, effects: EffectRegistry, *, renderer: str = "moviepy") -> None:
        self.config = config
        self._effects = effects
        self.renderer = renderer

    # ── Post-effects ──────────────────────────────────────────────────────

    def apply_post_effects_to_video(
        self,
        video_path: Path,
        output_path: Path,
        step_timestamps: list[float],
        step_post_effects: list[list[tuple[str, dict[str, Any]]]],
    ) -> Path:
        """Apply per-step post-processing effects to the recorded video."""
        from moviepy import VideoFileClip, concatenate_videoclips

        has_any = any(efx for efx in step_post_effects)
        if not has_any:
            return video_path

        logger.info("Applying post-processing effects to video")
        clip = VideoFileClip(str(video_path))
        total_duration = clip.duration

        segments: list[Any] = []
        for i in range(len(step_timestamps)):
            start = step_timestamps[i]
            end = step_timestamps[i + 1] if i + 1 < len(step_timestamps) else total_duration
            if end <= start:
                continue

            sub = clip.subclipped(start, min(end, total_duration))

            if i < len(step_post_effects):
                for effect_name, params in step_post_effects[i]:
                    try:
                        handler = self._effects.get_post_effect(effect_name)
                        sub = handler.apply(sub, params)
                        logger.debug("Applied post-effect '%s' to step %d", effect_name, i)
                    except Exception:
                        logger.warning(
                            "Post-effect '%s' failed on step %d, skipping",
                            effect_name, i, exc_info=True,
                        )

            segments.append(sub)

        if not segments:
            clip.close()
            return video_path

        result = concatenate_videoclips(segments)
        result.write_videofile(
            str(output_path), codec="libx264", preset="medium", audio=False, logger=None,
        )
        result.close()
        clip.close()
        logger.info("Post-effects applied: %s", output_path.name)
        return output_path

    # ── Remotion full composition ─────────────────────────────────────────

    def remotion_full_compose(
        self,
        video_path: Path,
        ws: Any,
        narration_durations: dict[int, float],
        step_timestamps: list[float],
        step_post_effects: list[list[tuple[str, dict[str, Any]]]],
        *,
        avatar_clips: dict[int, Path] | None = None,
        narration_texts: dict[int, str] | None = None,
    ) -> Path:
        """Single-pass Remotion composition: segments + effects + avatars + subtitles."""
        from demodsl.providers.remotion_bridge import get_video_duration

        render = self._get_render_provider()
        total_dur = get_video_duration(video_path)

        step_effects_data = []
        for i in range(len(step_timestamps)):
            start = step_timestamps[i]
            end = step_timestamps[i + 1] if i + 1 < len(step_timestamps) else total_dur
            if i < len(step_post_effects) and step_post_effects[i]:
                effects_dicts = [
                    {"type": name, **params}
                    for name, params in step_post_effects[i]
                ]
                step_effects_data.append((start, end, effects_dicts))

        subtitle_entries = None
        subtitle_cfg = self.get_subtitle_config()
        if subtitle_cfg.get("enabled", False) and narration_texts:
            subtitle_entries = []
            for step_idx, text in sorted(narration_texts.items()):
                start_t = step_timestamps[step_idx] if step_idx < len(step_timestamps) else 0.0
                dur = narration_durations.get(step_idx, 3.0)
                subtitle_entries.append({
                    "text": text,
                    "startTime": start_t,
                    "endTime": start_t + dur,
                    "style": {
                        "fontSize": subtitle_cfg.get("font_size", 48),
                        "fontFamily": subtitle_cfg.get("font_family", "Arial"),
                        "fontColor": subtitle_cfg.get("font_color", "#FFFFFF"),
                        "backgroundColor": subtitle_cfg.get("background_color", "rgba(0,0,0,0.6)"),
                        "position": subtitle_cfg.get("position", "bottom"),
                    },
                })

        viewport = self.config.scenarios[0].viewport if self.config.scenarios else None
        width = viewport.width if viewport else 1920
        height = viewport.height if viewport else 1080

        video_cfg = self.config.video
        intro_cfg = video_cfg.intro.model_dump() if video_cfg and video_cfg.intro else None
        outro_cfg = video_cfg.outro.model_dump() if video_cfg and video_cfg.outro else None
        wm_cfg = video_cfg.watermark.model_dump() if video_cfg and video_cfg.watermark else None

        output = ws.root / "remotion_composed.mp4"
        return render.compose_full(
            segments=[video_path],
            output=output,
            fps=30,
            width=width,
            height=height,
            intro_config=intro_cfg,
            outro_config=outro_cfg,
            watermark_config=wm_cfg,
            step_effects=step_effects_data,
            avatar_clips=avatar_clips or {},
            step_timestamps=step_timestamps,
            narration_durations=narration_durations,
            avatar_config=self.get_avatar_config(),
            subtitle_entries=subtitle_entries,
        )

    # ── Avatar generation ─────────────────────────────────────────────────

    def generate_avatar_clips(
        self, ws: Workspace, narration_map: dict[int, Path],
        narration_texts: dict[int, str] | None = None,
        *, dry_run: bool = False,
    ) -> dict[int, Path]:
        """Generate avatar video clips for each narration step."""
        if dry_run or not narration_map:
            return {}

        avatar_cfg = self.get_avatar_config()
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
            logger.warning(
                "Cannot create '%s' avatar provider: %s — skipping avatars",
                provider_name, exc,
            )
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
                    background_shape=avatar_cfg.get("background_shape", "square"),
                    narration_text=(narration_texts or {}).get(step_idx),
                )
                avatar_clips[step_idx] = clip_path
            except Exception:
                logger.warning(
                    "Avatar generation failed for step %d, skipping",
                    step_idx, exc_info=True,
                )

        avatar.close()
        logger.info("Generated %d avatar clips", len(avatar_clips))
        return avatar_clips

    # ── Subtitles ─────────────────────────────────────────────────────────

    def burn_subtitles(
        self,
        video_path: Path,
        ws: Workspace,
        narration_texts: dict[int, str],
        narration_durations: dict[int, float],
        step_timestamps: list[float],
    ) -> Path:
        """Generate ASS subtitle file and burn it into the video."""
        raw_cfg = self.get_subtitle_config()
        cfg = get_merged_subtitle_config(raw_cfg)

        speed_wps = SPEED_PRESETS.get(cfg.get("speed", "normal"), 2.5)

        entries = build_subtitle_entries(
            narration_texts,
            step_timestamps,
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

    # ── Config helpers ────────────────────────────────────────────────────

    def get_avatar_config(self) -> dict[str, Any]:
        """Extract avatar config from the first scenario that has it."""
        for scenario in self.config.scenarios:
            if scenario.avatar and scenario.avatar.enabled:
                return scenario.avatar.model_dump()
        return {"enabled": False}

    def get_subtitle_config(self) -> dict[str, Any]:
        """Extract subtitle config: top-level first, then scenario-level fallback."""
        if self.config.subtitle and self.config.subtitle.enabled:
            return self.config.subtitle.model_dump()
        for scenario in self.config.scenarios:
            if scenario.subtitle and scenario.subtitle.enabled:
                return scenario.subtitle.model_dump()
        return {"enabled": False}

    def _get_render_provider(self) -> Any:
        if self.renderer == "remotion":
            import demodsl.providers.remotion_render  # noqa: F401
        else:
            import demodsl.providers.render  # noqa: F401
        return RenderProviderFactory.create(self.renderer)
