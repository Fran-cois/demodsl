"""Tests for demodsl.providers.render — MoviePyRenderProvider + VideoBuilder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demodsl.providers.render import MoviePyRenderProvider, VideoBuilder, _hex_to_rgb


class TestHexToRgb:
    def test_with_hash(self) -> None:
        assert _hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_without_hash(self) -> None:
        assert _hex_to_rgb("00FF00") == (0, 255, 0)

    def test_blue(self) -> None:
        assert _hex_to_rgb("#0000FF") == (0, 0, 255)

    def test_mixed(self) -> None:
        assert _hex_to_rgb("#1a1a1a") == (26, 26, 26)

    def test_white(self) -> None:
        assert _hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_black(self) -> None:
        assert _hex_to_rgb("#000000") == (0, 0, 0)


class TestVideoBuilder:
    def _make_builder(self) -> VideoBuilder:
        mock_render = MagicMock(spec=MoviePyRenderProvider)
        return VideoBuilder(mock_render)

    def test_add_segment_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.add_segment(Path("a.mp4"))
        assert result is builder

    def test_with_intro_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_intro({"text": "Intro"})
        assert result is builder

    def test_with_outro_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_outro({"text": "Thanks"})
        assert result is builder

    def test_with_watermark_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_watermark({"image": "logo.png"})
        assert result is builder

    def test_with_output_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_output(Path("out.mp4"))
        assert result is builder

    def test_build_no_segments_raises(self) -> None:
        builder = self._make_builder()
        with pytest.raises(ValueError, match="No video segments"):
            builder.build()

    def test_build_calls_compose(self) -> None:
        mock_render = MagicMock(spec=MoviePyRenderProvider)
        mock_render.compose.return_value = Path("composed.mp4")
        builder = VideoBuilder(mock_render)
        builder.add_segment(Path("a.mp4"))
        builder.build()
        mock_render.compose.assert_called_once()

    def test_build_with_intro_outro_watermark(self) -> None:
        mock_render = MagicMock(spec=MoviePyRenderProvider)
        mock_render.compose.return_value = Path("composed.mp4")
        mock_render.add_intro.return_value = Path("intro.mp4")
        mock_render.add_outro.return_value = Path("outro.mp4")
        mock_render.apply_watermark.return_value = Path("wm.mp4")

        builder = VideoBuilder(mock_render)
        builder.add_segment(Path("a.mp4"))
        builder.with_intro({"text": "Hi"})
        builder.with_outro({"text": "Bye"})
        builder.with_watermark({"image": "logo.png"})
        result = builder.build()

        mock_render.compose.assert_called_once()
        mock_render.add_intro.assert_called_once()
        mock_render.add_outro.assert_called_once()
        mock_render.apply_watermark.assert_called_once()
        assert result == Path("wm.mp4")

    def test_fluent_api_chaining(self) -> None:
        mock_render = MagicMock(spec=MoviePyRenderProvider)
        mock_render.compose.return_value = Path("out.mp4")
        builder = VideoBuilder(mock_render)
        result = (
            builder
            .add_segment(Path("a.mp4"))
            .with_intro({"text": "Hi"})
            .with_outro({"text": "Bye"})
            .with_output(Path("final.mp4"))
        )
        assert result is builder

    def test_default_output_path(self) -> None:
        builder = self._make_builder()
        assert builder._output == Path("output.mp4")


class TestMoviePyRenderProvider:
    @pytest.mark.skip(reason="not ready — requires MoviePy + FFmpeg")
    def test_compose_real(self) -> None:
        pass

    @pytest.mark.skip(reason="not ready — requires MoviePy + FFmpeg")
    def test_export_real(self) -> None:
        pass
