"""Remotion-based render provider — alternative to MoviePyRenderProvider."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.providers.base import RenderProvider, RenderProviderFactory
from demodsl.providers.remotion_bridge import (
    build_props,
    convert_effects,
    get_video_duration,
    render_via_remotion,
)

logger = logging.getLogger(__name__)


class RemotionRenderProvider(RenderProvider):
    """Render provider that delegates video composition to Remotion.

    Uses the same interface as MoviePyRenderProvider so it can be swapped
    via RenderProviderFactory.
    """

    def compose(self, segments: list[Path], output: Path) -> Path:
        existing = [s for s in segments if s.exists()]
        if not existing:
            raise ValueError("No video segments to compose")

        seg_data = []
        for s in existing:
            dur = get_video_duration(s)
            seg_data.append({
                "src": str(s.resolve()),
                "durationInSeconds": dur,
            })

        props = build_props(segments=seg_data)
        return render_via_remotion(props, output)

    def add_intro(self, video: Path, intro_config: dict[str, Any]) -> Path:
        dur = get_video_duration(video)
        seg_data = [{"src": str(video.resolve()), "durationInSeconds": dur}]

        props = build_props(segments=seg_data, intro=intro_config)
        out = video.with_name(f"intro_{video.name}")
        return render_via_remotion(props, out)

    def add_outro(self, video: Path, outro_config: dict[str, Any]) -> Path:
        dur = get_video_duration(video)
        seg_data = [{"src": str(video.resolve()), "durationInSeconds": dur}]

        props = build_props(segments=seg_data, outro=outro_config)
        out = video.with_name(f"outro_{video.name}")
        return render_via_remotion(props, out)

    def apply_watermark(self, video: Path, watermark_config: dict[str, Any]) -> Path:
        image_path = watermark_config.get("image", "")
        if not image_path or not Path(image_path).exists():
            logger.warning("Watermark image not found: %s", image_path)
            return video

        dur = get_video_duration(video)
        seg_data = [{"src": str(video.resolve()), "durationInSeconds": dur}]

        props = build_props(segments=seg_data, watermark=watermark_config)
        out = video.with_name(f"wm_{video.name}")
        return render_via_remotion(props, out)

    def export(self, video: Path, fmt: str, output_dir: Path, **kwargs: Any) -> Path:
        # Export/transcode still uses ffmpeg directly — Remotion renders to h264 MP4;
        # format conversion to webm/gif is faster via ffmpeg.
        import ffmpeg

        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"{video.stem}.{fmt}"

        stream = ffmpeg.input(str(video))
        if fmt == "webm":
            stream = ffmpeg.output(stream, str(out), vcodec="libvpx-vp9", crf=30)
        elif fmt == "gif":
            stream = ffmpeg.output(stream, str(out), vf="fps=10,scale=480:-1")
        else:
            bitrate = kwargs.get("bitrate", "5000k")
            stream = ffmpeg.output(
                stream, str(out),
                vcodec="libx264", video_bitrate=bitrate,
                movflags="+faststart",
            )
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return out

    def compose_full(
        self,
        segments: list[Path],
        output: Path,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        intro_config: dict[str, Any] | None = None,
        outro_config: dict[str, Any] | None = None,
        watermark_config: dict[str, Any] | None = None,
        step_effects: list[tuple[float, float, list[dict[str, Any]]]] | None = None,
        avatar_clips: dict[int, Path] | None = None,
        step_timestamps: list[float] | None = None,
        narration_durations: dict[int, float] | None = None,
        avatar_config: dict[str, Any] | None = None,
        subtitle_entries: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Single-pass full composition — leverages Remotion's ability to
        render everything (intro, segments, effects, avatars, subtitles, outro)
        in one render pass instead of multiple sequential passes.

        This is the preferred entry point when using Remotion as the renderer.
        """
        existing = [s for s in segments if s.exists()]
        if not existing:
            raise ValueError("No video segments to compose")

        # Build segment data
        seg_data = []
        for s in existing:
            dur = get_video_duration(s)
            seg_data.append({
                "src": str(s.resolve()),
                "durationInSeconds": dur,
            })

        # Build step effects data
        remotion_step_effects = None
        if step_effects:
            remotion_step_effects = []
            for start_t, end_t, effects in step_effects:
                remotion_step_effects.append({
                    "startTime": start_t,
                    "endTime": end_t,
                    "effects": convert_effects(effects),
                })

        # Build avatar data
        remotion_avatars = None
        if avatar_clips and step_timestamps and narration_durations:
            remotion_avatars = []
            av_cfg = avatar_config or {}
            for step_idx, clip_path in sorted(avatar_clips.items()):
                start_t = step_timestamps[step_idx] if step_idx < len(step_timestamps) else 0.0
                dur = narration_durations.get(step_idx, 3.0)
                remotion_avatars.append({
                    "src": str(clip_path.resolve()),
                    "startTime": start_t,
                    "durationInSeconds": dur,
                    "position": av_cfg.get("position", "bottom-right"),
                    "size": av_cfg.get("size", 120),
                })

        props = build_props(
            segments=seg_data,
            fps=fps,
            width=width,
            height=height,
            intro=intro_config,
            outro=outro_config,
            watermark=watermark_config,
            step_effects=remotion_step_effects,
            avatars=remotion_avatars,
            subtitles=subtitle_entries,
        )
        return render_via_remotion(props, output)


# ── Video Builder (Remotion variant) ─────────────────────────────────────────

class RemotionVideoBuilder:
    """Progressive builder for video composition using Remotion.

    Mirrors the MoviePy VideoBuilder API but delegates to RemotionRenderProvider.
    """

    def __init__(self, render: RemotionRenderProvider) -> None:
        self._render = render
        self._segments: list[Path] = []
        self._intro: dict[str, Any] | None = None
        self._outro: dict[str, Any] | None = None
        self._watermark: dict[str, Any] | None = None
        self._output: Path = Path("output.mp4")

    def add_segment(self, path: Path) -> RemotionVideoBuilder:
        self._segments.append(path)
        return self

    def with_intro(self, config: dict[str, Any]) -> RemotionVideoBuilder:
        self._intro = config
        return self

    def with_outro(self, config: dict[str, Any]) -> RemotionVideoBuilder:
        self._outro = config
        return self

    def with_watermark(self, config: dict[str, Any]) -> RemotionVideoBuilder:
        self._watermark = config
        return self

    def with_output(self, path: Path) -> RemotionVideoBuilder:
        self._output = path
        return self

    def build(self) -> Path:
        if not self._segments:
            raise ValueError("No video segments added")
        video = self._render.compose(self._segments, self._output)
        if self._intro:
            video = self._render.add_intro(video, self._intro)
        if self._outro:
            video = self._render.add_outro(video, self._outro)
        if self._watermark:
            video = self._render.apply_watermark(video, self._watermark)
        return video


RenderProviderFactory.register("remotion", RemotionRenderProvider)
