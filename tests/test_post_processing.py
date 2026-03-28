"""Tests for demodsl.orchestrators.post_processing — PostProcessingOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig
from demodsl.orchestrators.post_processing import PostProcessingOrchestrator


def _minimal_config(**overrides) -> DemoConfig:
    base = {
        "metadata": {"title": "t", "version": "1"},
        "scenarios": [
            {
                "name": "s1",
                "url": "https://example.com",
                "steps": [{"action": "navigate", "url": "https://example.com"}],
            }
        ],
    }
    base.update(overrides)
    return DemoConfig(**base)


class TestInit:
    def test_defaults(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        assert orch.renderer == "moviepy"

    def test_custom_renderer(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry(), renderer="remotion")
        assert orch.renderer == "remotion"


class TestGetAvatarConfig:
    def test_no_avatar_returns_disabled(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        assert orch.get_avatar_config() == {"enabled": False}

    def test_with_avatar_enabled(self) -> None:
        cfg = _minimal_config(
            scenarios=[
                {
                    "name": "s1",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://x.com"}],
                    "avatar": {"enabled": True, "provider": "animated"},
                }
            ]
        )
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        result = orch.get_avatar_config()
        assert result["enabled"] is True
        assert result["provider"] == "animated"


class TestGetSubtitleConfig:
    def test_no_subtitle_returns_disabled(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        assert orch.get_subtitle_config() == {"enabled": False}

    def test_top_level_subtitle(self) -> None:
        cfg = _minimal_config(subtitle={"enabled": True, "font_size": 40})
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        result = orch.get_subtitle_config()
        assert result["enabled"] is True

    def test_scenario_level_subtitle_fallback(self) -> None:
        cfg = _minimal_config(
            scenarios=[
                {
                    "name": "s1",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://x.com"}],
                    "subtitle": {"enabled": True, "speed": "fast"},
                }
            ]
        )
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        result = orch.get_subtitle_config()
        assert result["enabled"] is True


class TestGetRenderProvider:
    def test_moviepy_renderer(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        provider = orch._get_render_provider()
        assert provider is not None

    def test_remotion_renderer(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry(), renderer="remotion")
        provider = orch._get_render_provider()
        assert provider is not None


class TestApplyPostEffects:
    def test_no_effects_returns_original(self, tmp_path: Path) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        video = tmp_path / "video.mp4"
        video.touch()
        output = tmp_path / "output.mp4"
        result = orch.apply_post_effects_to_video(
            video, output, [0.0, 5.0], [[], []]
        )
        assert result == video

    @patch("moviepy.VideoFileClip")
    @patch("moviepy.concatenate_videoclips")
    def test_with_effects_applies_them(
        self, mock_concat: MagicMock, mock_vfc: MagicMock, tmp_path: Path
    ) -> None:
        clip = MagicMock()
        clip.duration = 10.0
        clip.subclipped.return_value = clip
        mock_vfc.return_value = clip

        result_clip = MagicMock()
        mock_concat.return_value = result_clip

        effects = EffectRegistry()
        handler = MagicMock()
        handler.apply.return_value = clip
        effects._post["test_effect"] = handler

        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, effects)

        video = tmp_path / "video.mp4"
        video.touch()
        output = tmp_path / "output.mp4"

        result = orch.apply_post_effects_to_video(
            video,
            output,
            [0.0, 5.0],
            [[("test_effect", {"intensity": 0.5})], []],
        )
        assert result == output
        handler.apply.assert_called_once()

    @patch("moviepy.VideoFileClip")
    @patch("moviepy.concatenate_videoclips")
    def test_effect_failure_skips(
        self, mock_concat: MagicMock, mock_vfc: MagicMock, tmp_path: Path
    ) -> None:
        clip = MagicMock()
        clip.duration = 10.0
        clip.subclipped.return_value = clip
        mock_vfc.return_value = clip

        result_clip = MagicMock()
        mock_concat.return_value = result_clip

        effects = EffectRegistry()
        handler = MagicMock()
        handler.apply.side_effect = RuntimeError("boom")
        effects._post["bad_effect"] = handler

        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, effects)

        video = tmp_path / "video.mp4"
        video.touch()
        output = tmp_path / "output.mp4"

        result = orch.apply_post_effects_to_video(
            video, output, [0.0], [[("bad_effect", {})]]
        )
        assert result == output

    @patch("moviepy.VideoFileClip")
    @patch("moviepy.concatenate_videoclips")
    def test_empty_segments_returns_original(
        self, mock_concat: MagicMock, mock_vfc: MagicMock, tmp_path: Path
    ) -> None:
        clip = MagicMock()
        clip.duration = 5.0
        # subclipped is never called because end <= start for all steps
        mock_vfc.return_value = clip
        cfg = _minimal_config()
        effects = EffectRegistry()
        effects._post["fx"] = MagicMock()  # register so it counts as having effects
        orch = PostProcessingOrchestrator(cfg, effects)
        video = tmp_path / "video.mp4"
        video.touch()
        output = tmp_path / "output.mp4"
        # timestamps: step0 starts at 10.0, step1 starts at 5.0 → end <= start for step0
        # step1 end is total_duration (5.0), which equals start (5.0), so also skipped
        result = orch.apply_post_effects_to_video(
            video, output, [10.0, 5.0], [[("fx", {})], []]
        )
        assert result == video
        clip.close.assert_called()


class TestGenerateAvatarClips:
    def test_dry_run_returns_empty(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        result = orch.generate_avatar_clips(ws, {0: Path("a.mp3")}, dry_run=True)
        assert result == {}

    def test_no_narration_map_returns_empty(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        result = orch.generate_avatar_clips(ws, {})
        assert result == {}

    def test_avatar_disabled_returns_empty(self) -> None:
        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        result = orch.generate_avatar_clips(ws, {0: Path("a.mp3")})
        assert result == {}

    @patch("demodsl.providers.base.AvatarProviderFactory.create")
    def test_provider_creation_failure_returns_empty(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.side_effect = EnvironmentError("no provider")
        cfg = _minimal_config(
            scenarios=[
                {
                    "name": "s1",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://x.com"}],
                    "avatar": {"enabled": True, "provider": "animated"},
                }
            ]
        )
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        ws.root = Path("/tmp/ws")
        result = orch.generate_avatar_clips(ws, {0: Path("a.mp3")})
        assert result == {}

    @patch("demodsl.providers.base.AvatarProviderFactory.create")
    def test_successful_avatar_generation(self, mock_create: MagicMock, tmp_path: Path) -> None:
        avatar_provider = MagicMock()
        avatar_provider.generate.return_value = tmp_path / "clip_0.mp4"
        mock_create.return_value = avatar_provider

        cfg = _minimal_config(
            scenarios=[
                {
                    "name": "s1",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://x.com"}],
                    "avatar": {"enabled": True, "provider": "animated"},
                }
            ]
        )
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        ws.root = tmp_path

        audio = tmp_path / "narration_0.mp3"
        audio.touch()

        result = orch.generate_avatar_clips(ws, {0: audio})
        assert 0 in result
        avatar_provider.generate.assert_called_once()
        avatar_provider.close.assert_called_once()

    @patch("demodsl.providers.base.AvatarProviderFactory.create")
    def test_avatar_generation_failure_skips_step(self, mock_create: MagicMock, tmp_path: Path) -> None:
        avatar_provider = MagicMock()
        avatar_provider.generate.side_effect = RuntimeError("generation failed")
        mock_create.return_value = avatar_provider

        cfg = _minimal_config(
            scenarios=[
                {
                    "name": "s1",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://x.com"}],
                    "avatar": {"enabled": True, "provider": "animated"},
                }
            ]
        )
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        ws.root = tmp_path

        audio = tmp_path / "narration_0.mp3"
        audio.touch()

        result = orch.generate_avatar_clips(ws, {0: audio})
        assert result == {}
        avatar_provider.close.assert_called_once()


class TestBurnSubtitles:
    @patch("demodsl.orchestrators.post_processing.burn_subtitles")
    @patch("demodsl.orchestrators.post_processing.generate_ass_subtitle")
    @patch("demodsl.orchestrators.post_processing.build_subtitle_entries")
    def test_burn_with_entries(
        self,
        mock_build: MagicMock,
        mock_gen_ass: MagicMock,
        mock_burn: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = [{"text": "Hello", "start": 0, "end": 2}]
        mock_burn.return_value = tmp_path / "subtitled.mp4"

        cfg = _minimal_config(subtitle={"enabled": True})
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        ws.root = tmp_path

        orch.burn_subtitles(
            tmp_path / "video.mp4",
            ws,
            {0: "Hello"},
            {0: 2.0},
            [0.0],
        )
        mock_build.assert_called_once()
        mock_gen_ass.assert_called_once()
        mock_burn.assert_called_once()

    @patch("demodsl.orchestrators.post_processing.build_subtitle_entries")
    def test_no_entries_skips(self, mock_build: MagicMock, tmp_path: Path) -> None:
        mock_build.return_value = []

        cfg = _minimal_config(subtitle={"enabled": True})
        orch = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = MagicMock()
        ws.root = tmp_path

        video = tmp_path / "video.mp4"
        result = orch.burn_subtitles(video, ws, {}, {}, [])
        assert result == video


class TestRemotionFullCompose:
    @patch("demodsl.providers.remotion_bridge.get_video_duration")
    @patch("demodsl.providers.base.RenderProviderFactory.create")
    def test_basic_compose(
        self, mock_render_create: MagicMock, mock_dur: MagicMock, tmp_path: Path
    ) -> None:
        mock_dur.return_value = 10.0
        render_provider = MagicMock()
        render_provider.compose_full.return_value = tmp_path / "composed.mp4"
        mock_render_create.return_value = render_provider

        cfg = _minimal_config()
        orch = PostProcessingOrchestrator(cfg, EffectRegistry(), renderer="remotion")
        ws = MagicMock()
        ws.root = tmp_path

        orch.remotion_full_compose(
            tmp_path / "video.mp4",
            ws,
            narration_durations={},
            step_timestamps=[0.0, 5.0],
            step_post_effects=[[], []],
        )
        render_provider.compose_full.assert_called_once()

    @patch("demodsl.providers.remotion_bridge.get_video_duration")
    @patch("demodsl.providers.base.RenderProviderFactory.create")
    def test_with_subtitles_and_effects(
        self, mock_render_create: MagicMock, mock_dur: MagicMock, tmp_path: Path
    ) -> None:
        mock_dur.return_value = 10.0
        render_provider = MagicMock()
        render_provider.compose_full.return_value = tmp_path / "composed.mp4"
        mock_render_create.return_value = render_provider

        cfg = _minimal_config(subtitle={"enabled": True})
        orch = PostProcessingOrchestrator(cfg, EffectRegistry(), renderer="remotion")
        ws = MagicMock()
        ws.root = tmp_path

        orch.remotion_full_compose(
            tmp_path / "video.mp4",
            ws,
            narration_durations={0: 3.0},
            step_timestamps=[0.0, 5.0],
            step_post_effects=[[("blur", {"radius": 5})], []],
            narration_texts={0: "Hello world"},
        )
        render_provider.compose_full.assert_called_once()
        call_kwargs = render_provider.compose_full.call_args.kwargs
        assert call_kwargs["subtitle_entries"] is not None
        assert len(call_kwargs["subtitle_entries"]) == 1
        assert call_kwargs["step_effects"] != []
