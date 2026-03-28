"""MoviePy-based render provider + VideoBuilder."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demodsl.providers.base import RenderProvider, RenderProviderFactory

logger = logging.getLogger(__name__)


class MoviePyRenderProvider(RenderProvider):
    def compose(self, segments: list[Path], output: Path) -> Path:
        from moviepy import VideoFileClip, concatenate_videoclips

        clips = [VideoFileClip(str(s)) for s in segments if s.exists()]
        if not clips:
            raise ValueError("No video segments to compose")
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(str(output), codec="libx264", logger=None)
        for c in clips:
            c.close()
        return output

    def add_intro(self, video: Path, intro_config: dict[str, Any]) -> Path:
        from moviepy import ColorClip, CompositeVideoClip, TextClip, VideoFileClip

        main = VideoFileClip(str(video))
        duration = intro_config.get("duration", 3.0)
        bg_color_hex = intro_config.get("background_color", "#1a1a1a")
        bg_color = _hex_to_rgb(bg_color_hex)
        font_color = intro_config.get("font_color", "#FFFFFF")
        text = intro_config.get("text", "")
        subtitle = intro_config.get("subtitle", "")
        font_size = intro_config.get("font_size", 60)

        bg = ColorClip(size=(main.w, main.h), color=bg_color, duration=duration)
        layers = [bg]

        if text:
            txt = (
                TextClip(
                    text=text,
                    font_size=font_size,
                    color=font_color,
                    font="Arial",
                )
                .with_duration(duration)
                .with_position("center")
            )
            layers.append(txt)

        if subtitle:
            sub = (
                TextClip(
                    text=subtitle,
                    font_size=font_size // 2,
                    color=font_color,
                    font="Arial",
                )
                .with_duration(duration)
                .with_position(("center", main.h * 0.6))
            )
            layers.append(sub)

        intro_clip = CompositeVideoClip(layers, size=(main.w, main.h)).with_effects(
            [lambda c: c.crossfadein(0.5)]
        )
        from moviepy import concatenate_videoclips

        final = concatenate_videoclips([intro_clip, main], method="compose")
        out = video.with_name(f"intro_{video.name}")
        final.write_videofile(str(out), codec="libx264", logger=None)
        main.close()
        return out

    def add_outro(self, video: Path, outro_config: dict[str, Any]) -> Path:
        from moviepy import ColorClip, CompositeVideoClip, TextClip, VideoFileClip

        main = VideoFileClip(str(video))
        duration = outro_config.get("duration", 4.0)
        text = outro_config.get("text", "")
        outro_config.get("subtitle", "")
        cta = outro_config.get("cta", "")

        bg = ColorClip(size=(main.w, main.h), color=(26, 26, 26), duration=duration)
        layers = [bg]

        if text:
            txt = TextClip(text=text, font_size=60, color="white", font="Arial")
            txt = txt.with_duration(duration).with_position("center")
            layers.append(txt)

        if cta:
            cta_clip = TextClip(text=cta, font_size=40, color="#4CAF50", font="Arial")
            cta_clip = cta_clip.with_duration(duration).with_position(
                ("center", main.h * 0.7)
            )
            layers.append(cta_clip)

        outro_clip = CompositeVideoClip(layers, size=(main.w, main.h)).with_effects(
            [lambda c: c.crossfadeout(1.0)]
        )
        from moviepy import concatenate_videoclips

        final = concatenate_videoclips([main, outro_clip], method="compose")
        out = video.with_name(f"outro_{video.name}")
        final.write_videofile(str(out), codec="libx264", logger=None)
        main.close()
        return out

    def apply_watermark(self, video: Path, watermark_config: dict[str, Any]) -> Path:
        from moviepy import CompositeVideoClip, ImageClip, VideoFileClip

        main = VideoFileClip(str(video))
        image_path = watermark_config.get("image", "")
        if not image_path or not Path(image_path).exists():
            logger.warning("Watermark image not found: %s", image_path)
            return video

        opacity = watermark_config.get("opacity", 0.7)
        position = watermark_config.get("position", "bottom_right")
        size = watermark_config.get("size", 100)

        wm = ImageClip(image_path).resized(width=size).with_duration(main.duration)
        wm = wm.with_opacity(opacity)

        pos_map = {
            "top_left": (10, 10),
            "top_right": (main.w - size - 10, 10),
            "bottom_left": (10, main.h - size - 10),
            "bottom_right": (main.w - size - 10, main.h - size - 10),
            "center": "center",
        }
        wm = wm.with_position(pos_map.get(position, "center"))

        final = CompositeVideoClip([main, wm])
        out = video.with_name(f"wm_{video.name}")
        final.write_videofile(str(out), codec="libx264", logger=None)
        main.close()
        return out

    def export(self, video: Path, fmt: str, output_dir: Path, **kwargs: Any) -> Path:
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
                stream,
                str(out),
                vcodec="libx264",
                video_bitrate=bitrate,
                movflags="+faststart",
            )
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return out


# ── Video Builder (Builder pattern) ──────────────────────────────────────────


class VideoBuilder:
    """Progressive builder for the final video composition."""

    def __init__(self, render: MoviePyRenderProvider) -> None:
        self._render = render
        self._segments: list[Path] = []
        self._intro: dict[str, Any] | None = None
        self._outro: dict[str, Any] | None = None
        self._watermark: dict[str, Any] | None = None
        self._output: Path = Path("output.mp4")

    def add_segment(self, path: Path) -> VideoBuilder:
        self._segments.append(path)
        return self

    def with_intro(self, config: dict[str, Any]) -> VideoBuilder:
        self._intro = config
        return self

    def with_outro(self, config: dict[str, Any]) -> VideoBuilder:
        self._outro = config
        return self

    def with_watermark(self, config: dict[str, Any]) -> VideoBuilder:
        self._watermark = config
        return self

    def with_output(self, path: Path) -> VideoBuilder:
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


RenderProviderFactory.register("moviepy", MoviePyRenderProvider)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
