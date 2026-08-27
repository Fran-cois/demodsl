"""PostProcessingOrchestrator — effects, avatars, subtitles, Remotion composition."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from demodsl.compose_plan import (
    coverage_ratio,
    is_worthwhile,
    plan_windows,
    shift_effects,
)
from demodsl.effects.registry import EffectRegistry
from demodsl.effects.subtitle import (
    MAX_BLOCK_RATIO,
    SAFE_MARGIN_RATIO,
    SPEED_PRESETS,
    build_subtitle_entries,
    burn_subtitles,
    clamp_subtitle_entries,
    generate_ass_subtitle,
    get_merged_subtitle_config,
    max_chars_per_line,
    safe_horizontal_margins,
)
from demodsl.models import DemoConfig
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import (
    AvatarProvider,
    AvatarProviderFactory,
    RenderProviderFactory,
)

logger = logging.getLogger(__name__)


def _cut_segment(source: Path, dest: Path, start: float, end: float) -> None:
    """Extract ``[start, end)`` as a standalone clip.

    Re-encoded rather than stream-copied: a copy can only cut on keyframes,
    which would shift the seams by up to a whole GOP and desynchronise the
    windows from the narration timeline.
    """
    from demodsl.encoding import x264_args

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{max(0.0, end - start):.3f}",
        *x264_args(),
        "-an",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=900)


def _concat_chunks(chunks: list[Path], dest: Path, *, fps: int) -> None:
    """Join the windows back into one file, normalising them on the way.

    Stream-copying looks tempting and is wrong: ffmpeg cuts inherit the source's
    frame rate, pixel format and timebase, while Remotion always emits 30 fps /
    yuvj420p / 1-90000. The concat demuxer cannot reconcile that and silently
    produces a bogus duration — a 47 s demo came out at 6.6 s in production.
    The concat filter re-encodes, which normalises every parameter.
    """
    from demodsl.encoding import x264_args

    cmd: list[str] = ["ffmpeg", "-y"]
    for chunk in chunks:
        cmd += ["-i", str(chunk)]
    streams = "".join(f"[{i}:v]" for i in range(len(chunks)))
    cmd += [
        "-filter_complex",
        f"{streams}concat=n={len(chunks)}:v=1:a=0[v]",
        "-map",
        "[v]",
        "-r",
        str(fps),
        *x264_args(),
        "-an",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=900)


class PostProcessingOrchestrator:
    """Handles post-processing effects, avatar generation, subtitles,
    and Remotion full-composition."""

    def __init__(
        self, config: DemoConfig, effects: EffectRegistry, *, renderer: str = "remotion"
    ) -> None:
        if renderer != "remotion":
            raise ValueError(
                f"Unsupported renderer {renderer!r}. Since v3.0, only 'remotion' "
                "is supported (MoviePy was removed)."
            )
        self.config = config
        self._effects = effects
        self.renderer = renderer

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

        # A step boundary past the end of the clip means the recording is
        # shorter than the run that produced it — an over-eager blank-lead-in
        # trim is the usual culprit. Clamping keeps Remotion from being handed
        # a negative segment; the warning keeps the cause visible.
        if step_timestamps and total_dur and step_timestamps[-1] > total_dur + 0.5:
            logger.warning(
                "The recording (%.1fs) is shorter than the last step boundary (%.1fs) — "
                "%d step(s) fall past the end of the clip and their effects are dropped. "
                "The head of the video was most likely over-trimmed as 'blank'.",
                total_dur,
                step_timestamps[-1],
                sum(1 for t in step_timestamps if t >= total_dur),
            )

        step_effects_data = []
        for i in range(len(step_timestamps)):
            start = step_timestamps[i]
            end = step_timestamps[i + 1] if i + 1 < len(step_timestamps) else total_dur
            if total_dur:
                start = min(start, total_dur)
                end = min(end, total_dur)
            if end <= start:
                continue
            if i < len(step_post_effects) and step_post_effects[i]:
                effects_dicts = [{"type": name, **params} for name, params in step_post_effects[i]]
                step_effects_data.append((start, end, effects_dicts))

        subtitle_entries = None
        raw_subtitle_cfg = self.get_subtitle_config()
        subtitle_cfg = get_merged_subtitle_config(raw_subtitle_cfg)
        frame_w, frame_h = self.frame_size()
        if subtitle_cfg.get("enabled", False) and narration_texts:
            # Same chunking/word-timing pipeline as the ASS burn-in path, so
            # `style`, `speed` and `max_words_per_line` behave identically no
            # matter which renderer is active.
            position = subtitle_cfg.get("position", "bottom")
            reserved = self.reserved_corners()
            margin_l, margin_r = safe_horizontal_margins(frame_w, position, subtitle_cfg, reserved)
            font_size = int(subtitle_cfg.get("font_size", 48))
            chunks = build_subtitle_entries(
                narration_texts,
                step_timestamps,
                narration_durations,
                speed_wps=SPEED_PRESETS.get(subtitle_cfg.get("speed", "normal"), 2.5),
                max_words_per_line=subtitle_cfg.get("max_words_per_line", 8),
                style_name=subtitle_cfg.get("style", "classic"),
                max_chars=max_chars_per_line(font_size, frame_w, margin_l, margin_r),
            )
            clamp_subtitle_entries(chunks)
            shared_style = {
                "style": subtitle_cfg.get("style", "classic"),
                "fontSize": font_size,
                "fontFamily": subtitle_cfg.get("font_family", "Arial"),
                "fontColor": subtitle_cfg.get("font_color", "#FFFFFF"),
                "backgroundColor": subtitle_cfg.get("background_color", "rgba(0,0,0,0.6)"),
                "position": position,
                "highlightColor": subtitle_cfg.get("highlight_color", "#FFD700"),
                # Safe area (issue #32): a floor the burn cannot grow past, and
                # gutters that keep it clear of the reviewer badge / avatar.
                "bottomOffset": max(
                    24,
                    int(round(frame_h * float(subtitle_cfg.get("safe_margin", SAFE_MARGIN_RATIO)))),
                ),
                "marginLeft": margin_l,
                "marginRight": margin_r,
                "maxHeight": int(round(frame_h * MAX_BLOCK_RATIO)),
            }
            subtitle_entries = [
                {
                    "text": c["text"],
                    "startTime": c["start"],
                    "endTime": c["end"],
                    "words": [
                        {"word": w["word"], "start": w["start"], "end": w["end"]}
                        for w in c.get("words", [])
                    ],
                    "style": shared_style,
                }
                for c in chunks
            ]
            logger.info(
                "Subtitles: %d chunk(s), style=%s, %d words/line",
                len(subtitle_entries),
                subtitle_cfg.get("style", "classic"),
                subtitle_cfg.get("max_words_per_line", 8),
            )

        width, height = frame_w, frame_h

        video_cfg = self.config.video
        intro_cfg = video_cfg.intro.model_dump() if video_cfg and video_cfg.intro else None
        outro_cfg = video_cfg.outro.model_dump() if video_cfg and video_cfg.outro else None
        wm_cfg = video_cfg.watermark.model_dump() if video_cfg and video_cfg.watermark else None
        rev_cfg = None
        if video_cfg and video_cfg.reviewer and video_cfg.reviewer.enabled:
            rev_cfg = video_cfg.reviewer.model_dump()
        la_cfg = None
        if video_cfg and video_cfg.live_avatar and video_cfg.live_avatar.enabled:
            la_cfg = video_cfg.live_avatar.model_dump()
            # The mouth follows the combined narration track's loudness; a
            # missing track (--skip-voice) leaves an empty envelope → idle.
            from demodsl.effects.audio_envelope import amplitude_envelope

            la_cfg["mouth"] = amplitude_envelope(ws.root / "narration_combined.mp3", fps=30)
        pb_cfg = None
        if video_cfg and video_cfg.progress_bar and video_cfg.progress_bar.enabled:
            pb_cfg = video_cfg.progress_bar.model_dump()

        output = ws.root / "remotion_composed.mp4"
        composed = self._windowed_compose(
            render,
            video_path,
            ws,
            total_dur,
            step_effects_data,
            fps=30,
            width=width,
            height=height,
            has_full_frame_layer=any(
                (intro_cfg, outro_cfg, wm_cfg, rev_cfg, la_cfg, pb_cfg, subtitle_entries)
            )
            or bool(avatar_clips)
            or self._wants_vertical_social(),
        )
        if composed is None:
            composed = render.compose_full(
                segments=[video_path],
                output=output,
                fps=30,
                width=width,
                height=height,
                intro_config=intro_cfg,
                outro_config=outro_cfg,
                watermark_config=wm_cfg,
                reviewer_config=rev_cfg,
                live_avatar_config=la_cfg,
                progress_bar_config=pb_cfg,
                step_effects=step_effects_data,
                avatar_clips=avatar_clips or {},
                step_timestamps=step_timestamps,
                narration_durations=narration_durations,
                avatar_config=self.get_avatar_config(),
                subtitle_entries=subtitle_entries,
            )

        # Native vertical composition for 9:16 social exports: the same
        # timeline re-laid-out on a 1080x1920 canvas (blur-pad segments,
        # overlays reposition themselves) — far better than cropping 16:9.
        self.vertical_composition: Path | None = None
        if self._wants_vertical_social():
            # Safe area: lift subtitles above the avatar/badge bubbles so
            # long wrapped lines never sit behind them on the small canvas.
            vert_subtitles = None
            if subtitle_entries:
                vert_subtitles = [
                    {**e, "style": {**(e.get("style") or {}), "bottomOffset": 250}}
                    for e in subtitle_entries
                ]
            try:
                self.vertical_composition = render.compose_full(
                    segments=[video_path],
                    output=ws.root / "remotion_composed_vertical.mp4",
                    fps=30,
                    width=1080,
                    height=1920,
                    intro_config=intro_cfg,
                    outro_config=outro_cfg,
                    watermark_config=wm_cfg,
                    reviewer_config=rev_cfg,
                    live_avatar_config=la_cfg,
                    progress_bar_config=pb_cfg,
                    segment_fit="contain_blur",
                    step_effects=step_effects_data,
                    avatar_clips=avatar_clips or {},
                    step_timestamps=step_timestamps,
                    narration_durations=narration_durations,
                    avatar_config=self.get_avatar_config(),
                    subtitle_entries=vert_subtitles,
                )
            except Exception as exc:  # shorts must never sink the main render
                logger.warning("Vertical composition failed: %s", exc)
        return composed

    def _wants_vertical_social(self) -> bool:
        social = self.config.output.social if self.config.output else None
        if not social:
            return False
        return any(
            s.platform in ("tiktok", "instagram_reels") or s.aspect_ratio == "9:16" for s in social
        )

    # ── Windowed composition ──────────────────────────────────────────────

    def _windowed_compose(
        self,
        render: Any,
        video_path: Path,
        ws: Workspace,
        total_dur: float,
        step_effects_data: list[tuple[float, float, list[dict[str, Any]]]],
        *,
        fps: int,
        width: int,
        height: int,
        has_full_frame_layer: bool,
    ) -> Path | None:
        """Rasterise only the stretches that carry an effect, copy the rest.

        Remotion costs the same per frame whether it composites an effect or
        replays the recorded screencast untouched, so one effect on a twelve-step
        demo used to send the entire timeline through headless Chrome.

        Returns ``None`` whenever the plain single-pass composition should be
        used instead — including on any failure, since this is only ever a
        shortcut.
        """
        if has_full_frame_layer:
            # Subtitles, avatars, watermark, intro/outro and the vertical
            # export all span the whole timeline: nothing can be skipped.
            return None

        plan = plan_windows(step_effects_data, total_dur)
        if not is_worthwhile(plan, total_dur):
            return None

        try:
            chunks_dir = ws.root / "windows"
            chunks_dir.mkdir(parents=True, exist_ok=True)
            chunks: list[Path] = []

            for index, (start, end, effects) in enumerate(plan):
                cut = chunks_dir / f"cut_{index:03d}.mp4"
                _cut_segment(video_path, cut, start, end)
                if not effects:
                    chunks.append(cut)
                    continue
                rendered = chunks_dir / f"fx_{index:03d}.mp4"
                chunks.append(
                    render.compose_full(
                        segments=[cut],
                        output=rendered,
                        fps=fps,
                        width=width,
                        height=height,
                        step_effects=[(0.0, end - start, shift_effects(effects, start))],
                    )
                )

            output = ws.root / "remotion_windowed.mp4"
            _concat_chunks(chunks, output, fps=fps)
        except Exception as exc:  # never let the shortcut sink the render
            logger.warning("Windowed composition failed, falling back: %s", exc)
            return None

        logger.info(
            "Windowed composition: %d window(s), %.0f%% of the timeline rasterised",
            len(plan),
            100 * coverage_ratio(plan, total_dur),
        )
        return output

    # ── Avatar generation ─────────────────────────────────────────────────

    def generate_avatar_clips(
        self,
        ws: Workspace,
        narration_map: dict[int, Path],
        narration_texts: dict[int, str] | None = None,
        *,
        dry_run: bool = False,
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
                **{
                    k: v
                    for k, v in avatar_cfg.items()
                    if k in ("api_key", "sadtalker_path") and v is not None
                },
            )
        except (OSError, ValueError) as exc:
            logger.warning(
                "Cannot create '%s' avatar provider: %s — skipping avatars",
                provider_name,
                exc,
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
                    step_idx,
                    exc_info=True,
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
        frame_w, frame_h = self.frame_size()
        reserved = self.reserved_corners()
        margin_l, margin_r = safe_horizontal_margins(
            frame_w, cfg.get("position", "bottom"), cfg, reserved
        )

        entries = build_subtitle_entries(
            narration_texts,
            step_timestamps,
            narration_durations,
            speed_wps=speed_wps,
            max_words_per_line=cfg.get("max_words_per_line", 8),
            style_name=cfg.get("style", "classic"),
            max_chars=max_chars_per_line(
                int(cfg.get("font_size", 48)), frame_w, margin_l, margin_r
            ),
        )

        clamp_subtitle_entries(entries)

        if not entries:
            logger.info("No subtitle entries to burn, skipping")
            return video_path

        ass_path = ws.root / "subtitles.ass"
        generate_ass_subtitle(
            entries, cfg, ass_path, frame_size=(frame_w, frame_h), reserved_corners=reserved
        )

        output = ws.root / "subtitled.mp4"
        return burn_subtitles(video_path, ass_path, output)

    def generate_subtitle_file(
        self,
        ws: Workspace,
        narration_texts: dict[int, str],
        narration_durations: dict[int, float],
        step_timestamps: list[float],
        lang: str,
    ) -> Path | None:
        """Generate an ASS subtitle file for *lang* without burning it.

        Returns the path to ``subtitles_<lang>.ass`` (or None when no
        narration text is available).
        """
        if not narration_texts:
            return None

        raw_cfg = self.get_subtitle_config()
        cfg = get_merged_subtitle_config(raw_cfg)

        speed_wps = SPEED_PRESETS.get(cfg.get("speed", "normal"), 2.5)
        frame_w, frame_h = self.frame_size()
        reserved = self.reserved_corners()
        margin_l, margin_r = safe_horizontal_margins(
            frame_w, cfg.get("position", "bottom"), cfg, reserved
        )

        entries = build_subtitle_entries(
            narration_texts,
            step_timestamps,
            narration_durations,
            speed_wps=speed_wps,
            max_words_per_line=cfg.get("max_words_per_line", 8),
            style_name=cfg.get("style", "classic"),
            max_chars=max_chars_per_line(
                int(cfg.get("font_size", 48)), frame_w, margin_l, margin_r
            ),
        )
        clamp_subtitle_entries(entries)

        if not entries:
            return None

        ass_path = ws.root / f"subtitles_{lang}.ass"
        generate_ass_subtitle(
            entries, cfg, ass_path, frame_size=(frame_w, frame_h), reserved_corners=reserved
        )
        return ass_path

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

    def frame_size(self) -> tuple[int, int]:
        """The rendered frame in pixels — the subtitle safe area depends on it."""
        viewport = self.config.scenarios[0].viewport if self.config.scenarios else None
        return (viewport.width if viewport else 1920, viewport.height if viewport else 1080)

    def reserved_corners(self) -> dict[str, int]:
        """Corners already owned by an overlay, and how wide they are.

        The reviewer badge and the live-avatar bubble sit in the bottom band,
        exactly where the subtitle burn grows. Reporting their footprint lets
        the burn inset itself instead of running underneath them (issue #32).
        """
        video = self.config.video
        if video is None:
            return {}
        reserved: dict[str, int] = {}
        for attr in ("reviewer", "live_avatar", "avatar", "watermark"):
            overlay = getattr(video, attr, None)
            if overlay is None or not getattr(overlay, "enabled", False):
                continue
            corner = str(getattr(overlay, "position", "") or "")
            if "-" not in corner:
                continue
            size = int(getattr(overlay, "size", 0) or 0)
            if size <= 0:
                continue
            # A badge is wider than it is tall (name + title next to the mark).
            width = size * 3 if attr == "reviewer" else size
            reserved[corner] = max(reserved.get(corner, 0), width)
        return reserved

    def _get_render_provider(self) -> Any:
        import demodsl.providers.remotion_render  # noqa: F401

        return RenderProviderFactory.create(self.renderer)
