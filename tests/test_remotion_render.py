"""Tests for demodsl.providers.remotion_render — RemotionRenderProvider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.providers.remotion_render import (
    RemotionRenderProvider,
    RemotionVideoBuilder,
)


class TestRemotionRenderProvider:
    def test_compose_no_segments(self) -> None:
        provider = RemotionRenderProvider()
        with pytest.raises(ValueError, match="No video segments"):
            provider.compose([], Path("out.mp4"))

    def test_compose_nonexistent_segments(self) -> None:
        provider = RemotionRenderProvider()
        with pytest.raises(ValueError, match="No video segments"):
            provider.compose([Path("/nonexistent/a.mp4")], Path("out.mp4"))

    @patch("demodsl.providers.remotion_render.render_via_remotion")
    @patch("demodsl.providers.remotion_render.get_video_duration", return_value=5.0)
    def test_compose_calls_remotion(
        self, mock_dur: MagicMock, mock_render: MagicMock, tmp_path: Path
    ) -> None:
        seg = tmp_path / "seg.mp4"
        seg.write_bytes(b"fake")
        out = tmp_path / "output.mp4"
        mock_render.return_value = out

        provider = RemotionRenderProvider()
        result = provider.compose([seg], out)

        mock_render.assert_called_once()
        props = mock_render.call_args[0][0]
        assert len(props["segments"]) == 1
        assert props["segments"][0]["durationInSeconds"] == 5.0
        assert result == out

    @patch("demodsl.providers.remotion_render.render_via_remotion")
    @patch("demodsl.providers.remotion_render.get_video_duration", return_value=10.0)
    def test_add_intro(
        self, mock_dur: MagicMock, mock_render: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "main.mp4"
        video.write_bytes(b"fake")
        expected_out = video.with_name("intro_main.mp4")
        mock_render.return_value = expected_out

        provider = RemotionRenderProvider()
        provider.add_intro(video, {"duration": 3.0, "text": "Hello"})

        props = mock_render.call_args[0][0]
        assert props["intro"]["durationInSeconds"] == 3.0
        assert props["intro"]["text"] == "Hello"

    @patch("demodsl.providers.remotion_render.render_via_remotion")
    @patch("demodsl.providers.remotion_render.get_video_duration", return_value=10.0)
    def test_add_outro(
        self, mock_dur: MagicMock, mock_render: MagicMock, tmp_path: Path
    ) -> None:
        video = tmp_path / "main.mp4"
        video.write_bytes(b"fake")
        expected_out = video.with_name("outro_main.mp4")
        mock_render.return_value = expected_out

        provider = RemotionRenderProvider()
        provider.add_outro(video, {"duration": 4.0, "cta": "Try now"})

        props = mock_render.call_args[0][0]
        assert props["outro"]["durationInSeconds"] == 4.0
        assert props["outro"]["cta"] == "Try now"

    def test_apply_watermark_missing_image(self, tmp_path: Path) -> None:
        video = tmp_path / "main.mp4"
        video.write_bytes(b"fake")

        provider = RemotionRenderProvider()
        # Should return original path if image not found
        result = provider.apply_watermark(video, {"image": "/nonexistent.png"})
        assert result == video

    @patch("demodsl.providers.remotion_render.render_via_remotion")
    @patch("demodsl.providers.remotion_render.get_video_duration", return_value=5.0)
    def test_compose_full(
        self, mock_dur: MagicMock, mock_render: MagicMock, tmp_path: Path
    ) -> None:
        seg = tmp_path / "seg.mp4"
        seg.write_bytes(b"fake")
        out = tmp_path / "composed.mp4"
        mock_render.return_value = out

        provider = RemotionRenderProvider()
        result = provider.compose_full(
            segments=[seg],
            output=out,
            fps=30,
            width=1920,
            height=1080,
            intro_config={"duration": 3.0, "text": "Hi"},
            outro_config={"duration": 4.0},
            step_effects=[(0.0, 2.0, [{"type": "ken_burns", "scale": 1.2}])],
        )

        props = mock_render.call_args[0][0]
        assert props["intro"]["durationInSeconds"] == 3.0
        assert len(props["stepEffects"]) == 1
        assert result == out


class TestRemotionVideoBuilder:
    def _make_builder(self) -> RemotionVideoBuilder:
        mock_render = MagicMock(spec=RemotionRenderProvider)
        return RemotionVideoBuilder(mock_render)

    def test_add_segment_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.add_segment(Path("a.mp4"))
        assert result is builder

    def test_with_intro_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_intro({"text": "Hi"})
        assert result is builder

    def test_with_outro_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_outro({"text": "Bye"})
        assert result is builder

    def test_with_watermark_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_watermark({"image": "logo.png"})
        assert result is builder

    def test_with_output_returns_self(self) -> None:
        builder = self._make_builder()
        result = builder.with_output(Path("output.mp4"))
        assert result is builder

    def test_build_no_segments_raises(self) -> None:
        builder = self._make_builder()
        with pytest.raises(ValueError, match="No video segments"):
            builder.build()

    def test_build_calls_compose(self) -> None:
        builder = self._make_builder()
        builder.add_segment(Path("a.mp4"))
        builder._render.compose.return_value = Path("composed.mp4")
        builder.build()
        builder._render.compose.assert_called_once()


class TestRenderProviderRegistration:
    def test_remotion_is_registered(self) -> None:
        from demodsl.providers.base import RenderProviderFactory

        provider = RenderProviderFactory.create("remotion")
        assert isinstance(provider, RemotionRenderProvider)
