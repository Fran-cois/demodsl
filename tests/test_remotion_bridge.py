"""Tests for demodsl.providers.remotion_bridge — JSON bridge to Remotion."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.providers.remotion_bridge import (
    build_props,
    check_remotion_available,
    convert_effects,
    get_video_duration,
    render_via_remotion,
    _convert_intro,
    _convert_outro,
    _convert_watermark,
)


class TestBuildProps:
    def test_minimal_props(self) -> None:
        props = build_props(
            segments=[{"src": "/tmp/a.mp4", "durationInSeconds": 5.0}],
        )
        assert props["fps"] == 30
        assert props["width"] == 1920
        assert props["height"] == 1080
        assert len(props["segments"]) == 1
        assert props["segments"][0]["src"] == "/tmp/a.mp4"
        assert props["stepEffects"] == []
        assert props["avatars"] == []
        assert props["subtitles"] == []
        assert "intro" not in props
        assert "outro" not in props

    def test_custom_resolution(self) -> None:
        props = build_props(
            segments=[],
            fps=60,
            width=1280,
            height=720,
        )
        assert props["fps"] == 60
        assert props["width"] == 1280
        assert props["height"] == 720

    def test_with_intro_and_outro(self) -> None:
        props = build_props(
            segments=[],
            intro={"duration": 3.0, "text": "Hello"},
            outro={"duration": 4.0, "cta": "Get started"},
        )
        assert props["intro"]["durationInSeconds"] == 3.0
        assert props["intro"]["text"] == "Hello"
        assert props["outro"]["durationInSeconds"] == 4.0
        assert props["outro"]["cta"] == "Get started"

    def test_with_watermark(self) -> None:
        props = build_props(
            segments=[],
            watermark={
                "image": "/tmp/logo.png",
                "position": "top_left",
                "opacity": 0.5,
                "size": 80,
            },
        )
        assert props["watermark"]["image"] == "/tmp/logo.png"
        assert props["watermark"]["position"] == "top_left"
        assert props["watermark"]["opacity"] == 0.5

    def test_with_step_effects(self) -> None:
        props = build_props(
            segments=[],
            step_effects=[
                {"startTime": 0.0, "endTime": 2.0, "effects": [{"type": "ken_burns"}]},
            ],
        )
        assert len(props["stepEffects"]) == 1
        assert props["stepEffects"][0]["effects"][0]["type"] == "ken_burns"

    def test_with_avatars(self) -> None:
        props = build_props(
            segments=[],
            avatars=[
                {
                    "src": "/tmp/av.mp4",
                    "startTime": 1.0,
                    "durationInSeconds": 3.0,
                    "position": "bottom-right",
                    "size": 120,
                },
            ],
        )
        assert len(props["avatars"]) == 1
        assert props["avatars"][0]["position"] == "bottom-right"

    def test_with_subtitles(self) -> None:
        props = build_props(
            segments=[],
            subtitles=[
                {"text": "Hello world", "startTime": 0.0, "endTime": 2.0},
            ],
        )
        assert len(props["subtitles"]) == 1
        assert props["subtitles"][0]["text"] == "Hello world"


class TestConvertIntro:
    def test_defaults(self) -> None:
        result = _convert_intro({})
        assert result["durationInSeconds"] == 3.0
        assert result["fontSize"] == 60
        assert result["fontColor"] == "#FFFFFF"
        assert result["backgroundColor"] == "#1a1a1a"

    def test_custom(self) -> None:
        result = _convert_intro(
            {
                "duration": 5.0,
                "text": "Welcome",
                "subtitle": "Sub",
                "font_size": 80,
                "font_color": "#FF0000",
                "background_color": "#000000",
            }
        )
        assert result["durationInSeconds"] == 5.0
        assert result["text"] == "Welcome"
        assert result["subtitle"] == "Sub"
        assert result["fontSize"] == 80


class TestConvertOutro:
    def test_defaults(self) -> None:
        result = _convert_outro({})
        assert result["durationInSeconds"] == 4.0

    def test_with_cta(self) -> None:
        result = _convert_outro({"cta": "Click here"})
        assert result["cta"] == "Click here"


class TestConvertWatermark:
    def test_defaults(self) -> None:
        result = _convert_watermark({})
        assert result["position"] == "bottom_right"
        assert result["opacity"] == 0.7
        assert result["size"] == 100


class TestConvertEffects:
    def test_empty(self) -> None:
        assert convert_effects([]) == []

    def test_simple_effect(self) -> None:
        result = convert_effects(
            [{"type": "ken_burns", "scale": 1.2, "direction": "right"}]
        )
        assert len(result) == 1
        assert result[0]["type"] == "ken_burns"
        assert result[0]["scale"] == 1.2
        assert result[0]["direction"] == "right"

    def test_snake_to_camel(self) -> None:
        result = convert_effects(
            [{"type": "zoom_to", "target_x": 0.3, "target_y": 0.7}]
        )
        assert result[0]["targetX"] == 0.3
        assert result[0]["targetY"] == 0.7
        assert "target_x" not in result[0]
        assert "target_y" not in result[0]

    def test_none_values_excluded(self) -> None:
        result = convert_effects(
            [{"type": "vignette", "intensity": 0.5, "color": None}]
        )
        assert "color" not in result[0]

    def test_multiple_effects(self) -> None:
        result = convert_effects(
            [
                {"type": "vignette", "intensity": 0.5},
                {"type": "letterbox", "ratio": 2.35},
            ]
        )
        assert len(result) == 2
        assert result[0]["type"] == "vignette"
        assert result[1]["type"] == "letterbox"


class TestCheckRemotionAvailable:
    @patch("shutil.which", return_value=None)
    def test_no_node(self, _mock: MagicMock) -> None:
        assert check_remotion_available() is False

    @patch("shutil.which", side_effect=lambda cmd: "/usr/bin/node" if cmd == "node" else None)
    def test_no_npx(self, _mock: MagicMock) -> None:
        assert check_remotion_available() is False

    @patch("shutil.which", return_value="/usr/bin/cmd")
    def test_no_package_json(self, _mock: MagicMock, tmp_path: Path) -> None:
        with patch("demodsl.providers.remotion_bridge._REMOTION_DIR", tmp_path):
            assert check_remotion_available() is False

    @patch("shutil.which", return_value="/usr/bin/cmd")
    def test_no_node_modules(self, _mock: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        with patch("demodsl.providers.remotion_bridge._REMOTION_DIR", tmp_path):
            assert check_remotion_available() is False

    @patch("shutil.which", return_value="/usr/bin/cmd")
    def test_all_present(self, _mock: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "node_modules").mkdir()
        with patch("demodsl.providers.remotion_bridge._REMOTION_DIR", tmp_path):
            assert check_remotion_available() is True


class TestRenderViaRemotion:
    @patch("demodsl.providers.remotion_bridge.check_remotion_available", return_value=False)
    def test_raises_when_not_available(self, _mock: MagicMock, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="not available"):
            render_via_remotion({"fps": 30}, tmp_path / "out.mp4")

    @patch("subprocess.run")
    @patch("demodsl.providers.remotion_bridge.check_remotion_available", return_value=True)
    def test_successful_render(
        self, _avail: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        output = tmp_path / "out.mp4"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Rendered OK"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        # Create the output file to simulate Remotion producing it
        output.write_bytes(b"\x00" * 100)
        result = render_via_remotion({"fps": 30}, output)
        assert result == output
        mock_run.assert_called_once()

    @patch("subprocess.run")
    @patch("demodsl.providers.remotion_bridge.check_remotion_available", return_value=True)
    def test_failed_render(
        self, _avail: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error in rendering"
        mock_run.return_value = mock_result
        with pytest.raises(RuntimeError, match="render failed"):
            render_via_remotion({"fps": 30}, tmp_path / "out.mp4")

    @patch("subprocess.run")
    @patch("demodsl.providers.remotion_bridge.check_remotion_available", return_value=True)
    def test_no_output_file(
        self, _avail: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        with pytest.raises(RuntimeError, match="produced no output"):
            render_via_remotion({"fps": 30}, tmp_path / "out.mp4")


class TestGetVideoDuration:
    @patch("subprocess.run")
    def test_returns_duration(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "12.345\n"
        mock_run.return_value = mock_result
        assert get_video_duration(Path("test.mp4")) == pytest.approx(12.345)

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=10))
    def test_fallback_on_timeout(self, _mock: MagicMock) -> None:
        assert get_video_duration(Path("test.mp4")) == 10.0

    @patch("subprocess.run")
    def test_fallback_on_bad_output(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "not_a_number\n"
        mock_run.return_value = mock_result
        assert get_video_duration(Path("test.mp4")) == 10.0
