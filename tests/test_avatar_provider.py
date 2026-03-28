"""Tests for demodsl.providers.avatar — Avatar providers."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_has_ffmpeg = shutil.which("ffmpeg") is not None
try:
    from pydub import AudioSegment  # noqa: F401

    _has_pydub = True
except ImportError:
    _has_pydub = False
requires_ffmpeg = pytest.mark.skipif(
    not _has_ffmpeg or not _has_pydub, reason="ffmpeg or pydub not available"
)


# ── AnimatedAvatarProvider ───────────────────────────────────────────────────


class TestAnimatedAvatarProvider:
    def test_init_creates_output_dir(self, tmp_path: Path) -> None:
        from demodsl.providers.avatar import AnimatedAvatarProvider

        out = tmp_path / "avatars"
        provider = AnimatedAvatarProvider(output_dir=out)
        assert out.exists()
        assert provider._counter == 0

    @pytest.mark.skipif(not _has_pydub, reason="pydub not importable")
    def test_extract_amplitudes_normalization(self) -> None:
        from pydub import AudioSegment

        from demodsl.providers.avatar import AnimatedAvatarProvider

        # Create a short silent audio segment
        audio = AudioSegment.silent(duration=1000)  # 1 second
        amps = AnimatedAvatarProvider._extract_amplitudes(audio, 30)
        assert len(amps) == 30
        # Silent audio should have all-zero amplitudes
        assert all(a == 0.0 for a in amps)

    def test_load_avatar_default(self) -> None:
        from demodsl.providers.avatar import AnimatedAvatarProvider

        img = AnimatedAvatarProvider._load_avatar(None, 64)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"

    def test_load_avatar_preset_robot(self) -> None:
        from demodsl.providers.avatar import AnimatedAvatarProvider

        img = AnimatedAvatarProvider._load_avatar("robot", 80)
        assert img.size == (80, 80)

    def test_load_avatar_from_file(self, tmp_path: Path) -> None:
        from PIL import Image

        from demodsl.providers.avatar import AnimatedAvatarProvider

        # Create a test image
        test_img = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
        img_path = tmp_path / "test_avatar.png"
        test_img.save(img_path)

        img = AnimatedAvatarProvider._load_avatar(str(img_path), 100)
        assert img.size == (100, 100)

    def test_load_avatar_from_url(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        from io import BytesIO
        from unittest.mock import MagicMock

        from PIL import Image

        from demodsl.providers.avatar import AnimatedAvatarProvider

        # Create a fake image served via URL
        fake_img = Image.new("RGBA", (200, 200), (0, 128, 255, 255))
        buf = BytesIO()
        fake_img.save(buf, "PNG")
        fake_bytes = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *a, **kw: mock_resp,
        )
        # Use a temp dir as cache to avoid polluting real cache
        monkeypatch.setattr(
            "pathlib.Path.home",
            lambda: tmp_path,
        )

        img = AnimatedAvatarProvider._load_avatar(
            "https://avatars.githubusercontent.com/u/22380190?v=4",
            100,
        )
        assert img.size == (100, 100)
        assert img.mode == "RGBA"

        # Second call should use cache
        mock_resp.read.reset_mock()
        img2 = AnimatedAvatarProvider._load_avatar(
            "https://avatars.githubusercontent.com/u/22380190?v=4",
            100,
        )
        assert img2.size == (100, 100)
        mock_resp.read.assert_not_called()

    def test_apply_shape_circle(self) -> None:
        from PIL import Image

        from demodsl.providers.avatar import AnimatedAvatarProvider

        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        result = AnimatedAvatarProvider._apply_shape(img, "circle", 64)
        assert result.mode == "RGBA"
        # Corner pixel should be transparent (outside circle)
        assert result.getpixel((0, 0))[3] == 0

    def test_apply_shape_square_unchanged(self) -> None:
        from PIL import Image

        from demodsl.providers.avatar import AnimatedAvatarProvider

        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        result = AnimatedAvatarProvider._apply_shape(img, "square", 64)
        # Square should keep all pixels opaque
        assert result.getpixel((0, 0))[3] == 255

    def test_apply_shape_rounded(self) -> None:
        from PIL import Image

        from demodsl.providers.avatar import AnimatedAvatarProvider

        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        result = AnimatedAvatarProvider._apply_shape(img, "rounded", 64)
        assert result.mode == "RGBA"

    @requires_ffmpeg
    @patch("subprocess.run")
    def test_generate_calls_ffmpeg(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        from pydub import AudioSegment

        from demodsl.providers.avatar import AnimatedAvatarProvider

        # Create a test audio file
        audio = AudioSegment.silent(duration=500)  # 0.5 seconds
        audio_path = tmp_path / "test_narration.mp3"
        audio.export(str(audio_path), format="mp3")

        # Mock ffmpeg success
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        provider = AnimatedAvatarProvider(output_dir=tmp_path)
        provider.generate(
            audio_path,
            image=None,
            size=64,
            style="bounce",
            shape="circle",
        )

        # ffmpeg should have been called
        assert mock_run.called
        # Frames dir should be cleaned up
        assert not list(tmp_path.glob("avatar_frames_*"))

    @requires_ffmpeg
    def test_generate_all_styles(self, tmp_path: Path) -> None:
        """Verify frame generation works for all animation styles."""
        from pydub import AudioSegment

        from demodsl.providers.avatar import AnimatedAvatarProvider

        audio = AudioSegment.silent(duration=200)
        audio_path = tmp_path / "short.mp3"
        audio.export(str(audio_path), format="mp3")

        provider = AnimatedAvatarProvider(output_dir=tmp_path)

        for style in ("bounce", "waveform", "pulse"):
            # We patch subprocess to avoid needing ffmpeg
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                provider.generate(
                    audio_path,
                    size=48,
                    style=style,
                    shape="circle",
                )

    def test_close_is_noop(self, tmp_path: Path) -> None:
        from demodsl.providers.avatar import AnimatedAvatarProvider

        provider = AnimatedAvatarProvider(output_dir=tmp_path)
        provider.close()  # should not raise


# ── DIDProvider ──────────────────────────────────────────────────────────────


class TestDIDProvider:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("D_ID_API_KEY", raising=False)
        from demodsl.providers.avatar import DIDProvider

        with pytest.raises(EnvironmentError, match="D_ID_API_KEY"):
            DIDProvider()

    def test_init_with_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("D_ID_API_KEY", "test-key")
        from demodsl.providers.avatar import DIDProvider

        provider = DIDProvider(output_dir=tmp_path)
        assert provider._api_key == "test-key"

    def test_env_var_syntax(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("MY_DID_KEY", "resolved-key")
        from demodsl.providers.avatar import DIDProvider

        provider = DIDProvider(output_dir=tmp_path, api_key="${MY_DID_KEY}")
        assert provider._api_key == "resolved-key"


# ── HeyGenProvider ───────────────────────────────────────────────────────────


class TestHeyGenProvider:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HEYGEN_API_KEY", raising=False)
        from demodsl.providers.avatar import HeyGenProvider

        with pytest.raises(EnvironmentError, match="HEYGEN_API_KEY"):
            HeyGenProvider()

    def test_init_with_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("HEYGEN_API_KEY", "hg-key")
        from demodsl.providers.avatar import HeyGenProvider

        provider = HeyGenProvider(output_dir=tmp_path)
        assert provider._api_key == "hg-key"


# ── SadTalkerProvider ────────────────────────────────────────────────────────


class TestSadTalkerProvider:
    def test_init_defaults(self, tmp_path: Path) -> None:
        from demodsl.providers.avatar import SadTalkerProvider

        provider = SadTalkerProvider(output_dir=tmp_path)
        assert provider._sadtalker_path == "sadtalker"

    @requires_ffmpeg
    def test_no_image_falls_back_to_animated(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        from demodsl.providers.avatar import SadTalkerProvider

        audio = AudioSegment.silent(duration=200)
        audio_path = tmp_path / "test.mp3"
        audio.export(str(audio_path), format="mp3")

        provider = SadTalkerProvider(output_dir=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Should fall back to AnimatedAvatarProvider since no image
            provider.generate(audio_path, image=None, size=64)
            # AnimatedAvatarProvider calls subprocess for ffmpeg
            assert mock_run.called


# ── Factory registration ─────────────────────────────────────────────────────


class TestAvatarProviderFactory:
    def test_animated_registered(self) -> None:
        from demodsl.providers.base import AvatarProviderFactory

        import demodsl.providers.avatar  # noqa: F401

        assert "animated" in AvatarProviderFactory._registry

    def test_did_registered(self) -> None:
        from demodsl.providers.base import AvatarProviderFactory

        import demodsl.providers.avatar  # noqa: F401

        assert "d-id" in AvatarProviderFactory._registry

    def test_heygen_registered(self) -> None:
        from demodsl.providers.base import AvatarProviderFactory

        import demodsl.providers.avatar  # noqa: F401

        assert "heygen" in AvatarProviderFactory._registry

    def test_sadtalker_registered(self) -> None:
        from demodsl.providers.base import AvatarProviderFactory

        import demodsl.providers.avatar  # noqa: F401

        assert "sadtalker" in AvatarProviderFactory._registry

    def test_create_animated(self, tmp_path: Path) -> None:
        from demodsl.providers.base import AvatarProviderFactory

        import demodsl.providers.avatar  # noqa: F401

        provider = AvatarProviderFactory.create("animated", output_dir=tmp_path)
        assert provider is not None

    def test_unknown_provider_raises(self) -> None:
        from demodsl.providers.base import AvatarProviderFactory

        with pytest.raises(ValueError, match="Unknown avatar provider"):
            AvatarProviderFactory.create("nonexistent")


# ── AvatarConfig model ───────────────────────────────────────────────────────


class TestAvatarConfigModel:
    def test_default_values(self) -> None:
        from demodsl.models import AvatarConfig

        cfg = AvatarConfig()
        assert cfg.enabled is True
        assert cfg.provider == "animated"
        assert cfg.position == "bottom-right"
        assert cfg.size == 120
        assert cfg.style == "bounce"
        assert cfg.shape == "circle"

    def test_custom_values(self) -> None:
        from demodsl.models import AvatarConfig

        cfg = AvatarConfig(
            provider="d-id",
            position="top-left",
            size=200,
            style="pulse",
            shape="rounded",
            api_key="${D_ID_API_KEY}",
        )
        assert cfg.provider == "d-id"
        assert cfg.size == 200
        assert cfg.api_key == "${D_ID_API_KEY}"

    def test_scenario_with_avatar(self) -> None:
        from demodsl.models import DemoConfig

        config_dict = {
            "metadata": {"title": "Avatar Test"},
            "scenarios": [
                {
                    "name": "test",
                    "url": "https://example.com",
                    "avatar": {
                        "enabled": True,
                        "provider": "animated",
                        "position": "bottom-left",
                        "size": 80,
                    },
                    "steps": [],
                }
            ],
        }
        config = DemoConfig(**config_dict)
        assert config.scenarios[0].avatar is not None
        assert config.scenarios[0].avatar.provider == "animated"
        assert config.scenarios[0].avatar.size == 80


# ── Avatar overlay ───────────────────────────────────────────────────────────


class TestAvatarOverlay:
    def test_calc_position_bottom_right(self) -> None:
        from demodsl.effects.avatar_overlay import _calc_position

        x, y = _calc_position("bottom-right", 1920, 1080, 120)
        canvas = int(120 * 1.4)
        assert x == 1920 - canvas - 20
        assert y == 1080 - canvas - 20

    def test_calc_position_top_left(self) -> None:
        from demodsl.effects.avatar_overlay import _calc_position

        x, y = _calc_position("top-left", 1920, 1080, 120)
        assert x == 20
        assert y == 20

    def test_composite_no_clips_returns_original(self, tmp_path: Path) -> None:
        from demodsl.effects.avatar_overlay import composite_avatar

        video = tmp_path / "test.mp4"
        video.touch()
        result = composite_avatar(
            video,
            {},
            [],
            {},
            tmp_path / "out.mp4",
        )
        assert result == video

    def test_calc_text_position_bottom_right(self) -> None:
        from demodsl.effects.avatar_overlay import _calc_text_position

        tx, ty, tw = _calc_text_position("bottom-right", 1920, 1080, 120, 18)
        canvas = int(120 * 1.4)
        expected_w = canvas + 40
        assert tw == expected_w
        assert int(tx) == 1920 - expected_w - 20 + 10
        assert int(ty) == 1080 - 20 - 4

    def test_calc_text_position_top_left(self) -> None:
        from demodsl.effects.avatar_overlay import _calc_text_position

        tx, ty, tw = _calc_text_position("top-left", 1920, 1080, 120, 18)
        canvas = int(120 * 1.4)
        assert int(tx) == 20 - 10
        assert int(ty) == 20 + canvas + 8

    def test_escape_drawtext(self) -> None:
        from demodsl.effects.avatar_overlay import _escape_drawtext

        assert _escape_drawtext("hello world") == "hello world"
        assert "\\:" in _escape_drawtext("key:value")
        assert "%%" in _escape_drawtext("100%")
        assert "\n" not in _escape_drawtext("line1\nline2")

    def test_parse_box_color_rgba(self) -> None:
        from demodsl.effects.avatar_overlay import _parse_box_color

        result = _parse_box_color("rgba(0,0,0,0.7)")
        assert result == "#000000@0.7"

    def test_parse_box_color_plain(self) -> None:
        from demodsl.effects.avatar_overlay import _parse_box_color

        assert _parse_box_color("black") == "black"

    @patch("subprocess.run")
    @patch(
        "demodsl.effects.avatar_overlay._get_video_dimensions",
        return_value=(1920, 1080),
    )
    def test_composite_with_show_subtitle(
        self,
        mock_dims: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        from demodsl.effects.avatar_overlay import composite_avatar

        video = tmp_path / "test.mp4"
        video.touch()
        clip = tmp_path / "clip0.mp4"
        clip.touch()

        mock_run.return_value = MagicMock(returncode=0)

        output = tmp_path / "out.mp4"
        output.touch()  # simulate ffmpeg creating the file

        composite_avatar(
            video,
            {0: clip},
            [0.0],
            {0: 3.0},
            output,
            show_subtitle=True,
            narration_texts={0: "Hello world"},
        )

        # ffmpeg should have been called with drawtext in filter_complex
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args.kwargs.get("args", [])
        filter_str = ""
        for i, arg in enumerate(cmd):
            if arg == "-filter_complex" and i + 1 < len(cmd):
                filter_str = cmd[i + 1]
                break
        assert "drawtext" in filter_str
        assert "Hello world" in filter_str

    @patch("subprocess.run")
    @patch(
        "demodsl.effects.avatar_overlay._get_video_dimensions",
        return_value=(1920, 1080),
    )
    def test_composite_without_show_subtitle_no_drawtext(
        self,
        mock_dims: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        from demodsl.effects.avatar_overlay import composite_avatar

        video = tmp_path / "test.mp4"
        video.touch()
        clip = tmp_path / "clip0.mp4"
        clip.touch()

        mock_run.return_value = MagicMock(returncode=0)

        output = tmp_path / "out.mp4"
        output.touch()

        composite_avatar(
            video,
            {0: clip},
            [0.0],
            {0: 3.0},
            output,
            show_subtitle=False,
            narration_texts={0: "Hello world"},
        )

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args.kwargs.get("args", [])
        filter_str = ""
        for i, arg in enumerate(cmd):
            if arg == "-filter_complex" and i + 1 < len(cmd):
                filter_str = cmd[i + 1]
                break
        assert "drawtext" not in filter_str
