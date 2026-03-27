"""Tests for demodsl.models — Pydantic validation of every model."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from demodsl.models import (
    Analytics,
    AudioConfig,
    AudioEffects,
    BackgroundMusic,
    Compression,
    CursorConfig,
    DemoConfig,
    DeviceRendering,
    Effect,
    GlowSelectConfig,
    Intro,
    Locator,
    Metadata,
    OutputConfig,
    Outro,
    PipelineStage,
    Scenario,
    SocialExport,
    Step,
    Thumbnail,
    Transitions,
    Viewport,
    VideoConfig,
    VideoOptimization,
    VoiceConfig,
    VoiceProcessing,
    Watermark,
)


# ── Metadata ──────────────────────────────────────────────────────────────────


class TestMetadata:
    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            Metadata()  # type: ignore[call-arg]

    def test_minimal(self) -> None:
        m = Metadata(title="Test")
        assert m.title == "Test"
        assert m.description is None
        assert m.author is None
        assert m.version is None

    def test_all_fields(self) -> None:
        m = Metadata(title="T", description="D", author="A", version="1.0")
        assert m.description == "D"
        assert m.author == "A"
        assert m.version == "1.0"


# ── VoiceConfig ───────────────────────────────────────────────────────────────


class TestVoiceConfig:
    def test_defaults(self) -> None:
        v = VoiceConfig()
        assert v.engine == "elevenlabs"
        assert v.voice_id == "josh"
        assert v.speed == 1.0
        assert v.pitch == 0

    @pytest.mark.parametrize(
        "engine",
        [
            "elevenlabs", "google", "azure", "aws_polly", "openai",
            "cosyvoice", "coqui", "piper", "local_openai",
            "espeak", "gtts",
        ],
    )
    def test_valid_engines(self, engine: str) -> None:
        v = VoiceConfig(engine=engine)
        assert v.engine == engine

    def test_invalid_engine(self) -> None:
        with pytest.raises(ValidationError):
            VoiceConfig(engine="invalid_engine")  # type: ignore[arg-type]

    def test_custom_values(self) -> None:
        v = VoiceConfig(engine="gtts", voice_id="fr", speed=0.5, pitch=-3)
        assert v.voice_id == "fr"
        assert v.speed == 0.5
        assert v.pitch == -3


# ── BackgroundMusic ───────────────────────────────────────────────────────────


class TestBackgroundMusic:
    def test_file_required(self) -> None:
        with pytest.raises(ValidationError):
            BackgroundMusic()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        bg = BackgroundMusic(file="music.mp3")
        assert bg.volume == 0.3
        assert bg.ducking_mode == "moderate"
        assert bg.loop is True

    @pytest.mark.parametrize("mode", ["none", "light", "moderate", "heavy"])
    def test_valid_ducking_modes(self, mode: str) -> None:
        bg = BackgroundMusic(file="x.mp3", ducking_mode=mode)
        assert bg.ducking_mode == mode

    def test_invalid_ducking_mode(self) -> None:
        with pytest.raises(ValidationError):
            BackgroundMusic(file="x.mp3", ducking_mode="extreme")  # type: ignore[arg-type]


# ── VoiceProcessing ───────────────────────────────────────────────────────────


class TestVoiceProcessing:
    def test_defaults(self) -> None:
        vp = VoiceProcessing()
        assert vp.normalize is True
        assert vp.target_dbfs == -20
        assert vp.remove_silence is True
        assert vp.silence_threshold == -40
        assert vp.enhance_clarity is False
        assert vp.enhance_warmth is False
        assert vp.noise_reduction is False


# ── Compression ───────────────────────────────────────────────────────────────


class TestCompression:
    def test_defaults(self) -> None:
        c = Compression()
        assert c.threshold == -20
        assert c.ratio == 3.0
        assert c.attack == 5
        assert c.release == 50


# ── AudioEffects ──────────────────────────────────────────────────────────────


class TestAudioEffects:
    def test_defaults(self) -> None:
        ae = AudioEffects()
        assert ae.eq_preset is None
        assert ae.reverb_preset is None
        assert ae.compression is None

    def test_with_compression(self) -> None:
        ae = AudioEffects(compression={"threshold": -10, "ratio": 2.0, "attack": 1, "release": 30})
        assert ae.compression is not None
        assert ae.compression.threshold == -10


# ── AudioConfig ───────────────────────────────────────────────────────────────


class TestAudioConfig:
    def test_all_none(self) -> None:
        ac = AudioConfig()
        assert ac.background_music is None
        assert ac.voice_processing is None
        assert ac.effects is None

    def test_nested(self) -> None:
        ac = AudioConfig(
            background_music={"file": "a.mp3"},
            voice_processing={},
            effects={"eq_preset": "podcast"},
        )
        assert ac.background_music is not None
        assert ac.background_music.file == "a.mp3"
        assert ac.voice_processing is not None
        assert ac.effects is not None
        assert ac.effects.eq_preset == "podcast"


# ── DeviceRendering ───────────────────────────────────────────────────────────


class TestDeviceRendering:
    def test_defaults(self) -> None:
        dr = DeviceRendering()
        assert dr.device == "iphone_15_pro"
        assert dr.orientation == "portrait"
        assert dr.quality == "high"
        assert dr.render_engine == "eevee"

    @pytest.mark.parametrize("orient", ["portrait", "landscape"])
    def test_valid_orientation(self, orient: str) -> None:
        dr = DeviceRendering(orientation=orient)
        assert dr.orientation == orient

    def test_invalid_quality(self) -> None:
        with pytest.raises(ValidationError):
            DeviceRendering(quality="ultra")  # type: ignore[arg-type]


# ── Intro / Outro / Transitions / Watermark ───────────────────────────────────


class TestIntro:
    def test_defaults(self) -> None:
        i = Intro()
        assert i.duration == 3.0
        assert i.type == "fade_in"
        assert i.text is None
        assert i.font_size == 60
        assert i.font_color == "#FFFFFF"
        assert i.background_color == "#1a1a1a"


class TestOutro:
    def test_defaults(self) -> None:
        o = Outro()
        assert o.duration == 4.0
        assert o.type == "fade_out"
        assert o.cta is None


class TestTransitions:
    def test_defaults(self) -> None:
        t = Transitions()
        assert t.type == "crossfade"
        assert t.duration == 0.5

    @pytest.mark.parametrize("t_type", ["crossfade", "slide", "zoom", "dissolve"])
    def test_valid_types(self, t_type: str) -> None:
        t = Transitions(type=t_type)
        assert t.type == t_type

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            Transitions(type="wipe")  # type: ignore[arg-type]


class TestWatermark:
    def test_image_required(self) -> None:
        with pytest.raises(ValidationError):
            Watermark()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        w = Watermark(image="logo.png")
        assert w.position == "bottom_right"
        assert w.opacity == 0.7
        assert w.size == 100

    @pytest.mark.parametrize(
        "pos", ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
    )
    def test_valid_positions(self, pos: str) -> None:
        w = Watermark(image="logo.png", position=pos)
        assert w.position == pos


# ── VideoOptimization / VideoConfig ───────────────────────────────────────────


class TestVideoOptimization:
    def test_defaults(self) -> None:
        vo = VideoOptimization()
        assert vo.target_size_mb is None
        assert vo.web_optimized is True
        assert vo.compression_level == "balanced"

    @pytest.mark.parametrize("level", ["low", "balanced", "high"])
    def test_valid_compression(self, level: str) -> None:
        vo = VideoOptimization(compression_level=level)
        assert vo.compression_level == level


class TestVideoConfig:
    def test_all_none(self) -> None:
        vc = VideoConfig()
        assert vc.intro is None
        assert vc.transitions is None
        assert vc.watermark is None
        assert vc.outro is None
        assert vc.optimization is None


# ── Viewport / Locator ────────────────────────────────────────────────────────


class TestViewport:
    def test_defaults(self) -> None:
        v = Viewport()
        assert v.width == 1920
        assert v.height == 1080

    def test_custom(self) -> None:
        v = Viewport(width=800, height=600)
        assert v.width == 800


class TestLocator:
    def test_value_required(self) -> None:
        with pytest.raises(ValidationError):
            Locator()  # type: ignore[call-arg]

    def test_default_type(self) -> None:
        loc = Locator(value=".btn")
        assert loc.type == "css"

    @pytest.mark.parametrize("loc_type", ["css", "id", "xpath", "text"])
    def test_valid_types(self, loc_type: str) -> None:
        loc = Locator(type=loc_type, value="x")
        assert loc.type == loc_type

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            Locator(type="name", value="x")  # type: ignore[arg-type]


# ── Effect ────────────────────────────────────────────────────────────────────


class TestEffect:
    def test_type_required(self) -> None:
        with pytest.raises(ValidationError):
            Effect()  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "effect_type",
        [
            "spotlight", "highlight", "confetti", "typewriter", "glow",
            "shockwave", "sparkle", "parallax", "cursor_trail", "zoom_pulse",
            "ripple", "fade_in", "fade_out", "glitch", "neon_glow",
            "slide_in", "success_checkmark", "vignette",
        ],
    )
    def test_valid_effect_types(self, effect_type: str) -> None:
        e = Effect(type=effect_type)
        assert e.type == effect_type

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            Effect(type="explosion")  # type: ignore[arg-type]

    def test_optional_params(self) -> None:
        e = Effect(type="spotlight", duration=1.0, intensity=0.8, color="#FF0000")
        assert e.duration == 1.0
        assert e.intensity == 0.8
        assert e.color == "#FF0000"
        assert e.speed is None


# ── Step ──────────────────────────────────────────────────────────────────────


class TestStep:
    def test_action_required(self) -> None:
        with pytest.raises(ValidationError):
            Step()  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "action", ["navigate", "click", "type", "scroll", "wait_for", "screenshot"]
    )
    def test_valid_actions(self, action: str) -> None:
        s = Step(action=action)
        assert s.action == action

    def test_invalid_action(self) -> None:
        with pytest.raises(ValidationError):
            Step(action="hover")  # type: ignore[arg-type]

    def test_navigate_step(self) -> None:
        s = Step(action="navigate", url="https://example.com", narration="Go", wait=2.0)
        assert s.url == "https://example.com"
        assert s.narration == "Go"
        assert s.wait == 2.0

    def test_click_step_with_effects(self) -> None:
        s = Step(
            action="click",
            locator={"type": "css", "value": "#btn"},
            effects=[{"type": "spotlight"}],
        )
        assert s.locator is not None
        assert s.locator.value == "#btn"
        assert len(s.effects) == 1

    def test_defaults_none(self) -> None:
        s = Step(action="navigate")
        assert s.url is None
        assert s.locator is None
        assert s.value is None
        assert s.effects is None


# ── Scenario ──────────────────────────────────────────────────────────────────


class TestScenario:
    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Scenario()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        sc = Scenario(name="Test", url="https://test.com")
        assert sc.browser == "chrome"
        assert sc.viewport.width == 1920
        assert sc.steps == []

    @pytest.mark.parametrize("browser", ["chrome", "firefox", "webkit"])
    def test_valid_browsers(self, browser: str) -> None:
        sc = Scenario(name="T", url="u", browser=browser)
        assert sc.browser == browser

    def test_invalid_browser(self) -> None:
        with pytest.raises(ValidationError):
            Scenario(name="T", url="u", browser="opera")  # type: ignore[arg-type]

    def test_cursor_none_by_default(self) -> None:
        sc = Scenario(name="T", url="u")
        assert sc.cursor is None

    def test_cursor_config_defaults(self) -> None:
        sc = Scenario(name="T", url="u", cursor={})
        assert sc.cursor is not None
        assert sc.cursor.visible is True
        assert sc.cursor.style == "dot"
        assert sc.cursor.color == "#ef4444"
        assert sc.cursor.size == 20
        assert sc.cursor.click_effect == "ripple"
        assert sc.cursor.smooth == 0.4

    def test_cursor_config_custom(self) -> None:
        sc = Scenario(
            name="T", url="u",
            cursor={"style": "pointer", "color": "#00ff00", "size": 32,
                    "click_effect": "pulse", "smooth": 0.6},
        )
        assert sc.cursor is not None
        assert sc.cursor.style == "pointer"
        assert sc.cursor.color == "#00ff00"
        assert sc.cursor.size == 32
        assert sc.cursor.click_effect == "pulse"
        assert sc.cursor.smooth == 0.6

    def test_cursor_invalid_style(self) -> None:
        with pytest.raises(ValidationError):
            Scenario(name="T", url="u", cursor={"style": "arrow"})

    def test_cursor_invalid_click_effect(self) -> None:
        with pytest.raises(ValidationError):
            Scenario(name="T", url="u", cursor={"click_effect": "explode"})

    def test_glow_select_none_by_default(self) -> None:
        sc = Scenario(name="T", url="u")
        assert sc.glow_select is None

    def test_glow_select_defaults(self) -> None:
        sc = Scenario(name="T", url="u", glow_select={})
        assert sc.glow_select is not None
        assert sc.glow_select.enabled is True
        assert sc.glow_select.colors == ["#a855f7", "#6366f1", "#ec4899", "#a855f7"]
        assert sc.glow_select.duration == 0.8
        assert sc.glow_select.padding == 8
        assert sc.glow_select.border_radius == 12
        assert sc.glow_select.intensity == 0.9

    def test_glow_select_custom(self) -> None:
        sc = Scenario(
            name="T", url="u",
            glow_select={"colors": ["#ff0000", "#00ff00"], "duration": 1.2,
                         "padding": 16, "border_radius": 8, "intensity": 0.7},
        )
        assert sc.glow_select is not None
        assert sc.glow_select.colors == ["#ff0000", "#00ff00"]
        assert sc.glow_select.duration == 1.2
        assert sc.glow_select.padding == 16

    def test_cursor_and_glow_select_together(self) -> None:
        sc = Scenario(name="T", url="u", cursor={}, glow_select={})
        assert sc.cursor is not None
        assert sc.glow_select is not None


# ── CursorConfig ──────────────────────────────────────────────────────────────


class TestCursorConfig:
    def test_defaults(self) -> None:
        c = CursorConfig()
        assert c.visible is True
        assert c.style == "dot"
        assert c.color == "#ef4444"
        assert c.size == 20
        assert c.click_effect == "ripple"
        assert c.smooth == 0.4

    @pytest.mark.parametrize("style", ["dot", "pointer"])
    def test_valid_styles(self, style: str) -> None:
        c = CursorConfig(style=style)
        assert c.style == style

    @pytest.mark.parametrize("effect", ["ripple", "pulse", "none"])
    def test_valid_click_effects(self, effect: str) -> None:
        c = CursorConfig(click_effect=effect)
        assert c.click_effect == effect

    def test_invisible(self) -> None:
        c = CursorConfig(visible=False)
        assert c.visible is False


# ── GlowSelectConfig ──────────────────────────────────────────────────────────


class TestGlowSelectConfig:
    def test_defaults(self) -> None:
        g = GlowSelectConfig()
        assert g.enabled is True
        assert len(g.colors) == 4
        assert g.duration == 0.8
        assert g.padding == 8
        assert g.border_radius == 12
        assert g.intensity == 0.9

    def test_custom_colors(self) -> None:
        g = GlowSelectConfig(colors=["#ff0000"])
        assert g.colors == ["#ff0000"]

    def test_disabled(self) -> None:
        g = GlowSelectConfig(enabled=False)
        assert g.enabled is False


# ── PipelineStage ─────────────────────────────────────────────────────────────


class TestPipelineStage:
    def test_explicit_stage_type(self) -> None:
        ps = PipelineStage(stage_type="optimize", params={"quality": "high"})
        assert ps.stage_type == "optimize"
        assert ps.params == {"quality": "high"}

    def test_shorthand_dict(self) -> None:
        """Accept {"restore_audio": {"denoise": true}} shorthand."""
        ps = PipelineStage.model_validate({"restore_audio": {"denoise": True}})
        assert ps.stage_type == "restore_audio"
        assert ps.params == {"denoise": True}

    def test_shorthand_empty(self) -> None:
        ps = PipelineStage.model_validate({"edit_video": {}})
        assert ps.stage_type == "edit_video"
        assert ps.params == {}

    def test_shorthand_non_dict_value(self) -> None:
        ps = PipelineStage.model_validate({"mix_audio": True})
        assert ps.stage_type == "mix_audio"
        assert ps.params == {}

    def test_shorthand_rejects_multiple_keys(self) -> None:
        with pytest.raises(ValidationError):
            PipelineStage.model_validate({"a": {}, "b": {}})

    def test_params_default_empty(self) -> None:
        ps = PipelineStage(stage_type="x")
        assert ps.params == {}


# ── OutputConfig / Thumbnail / SocialExport ───────────────────────────────────


class TestOutputConfig:
    def test_defaults(self) -> None:
        oc = OutputConfig()
        assert oc.filename == "output.mp4"
        assert oc.directory == "output/"
        assert oc.formats == ["mp4"]
        assert oc.thumbnails is None
        assert oc.social is None


class TestThumbnail:
    def test_required(self) -> None:
        with pytest.raises(ValidationError):
            Thumbnail()  # type: ignore[call-arg]

    def test_value(self) -> None:
        t = Thumbnail(timestamp=5.0)
        assert t.timestamp == 5.0


class TestSocialExport:
    def test_platform_required(self) -> None:
        with pytest.raises(ValidationError):
            SocialExport()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        se = SocialExport(platform="youtube")
        assert se.resolution is None
        assert se.max_size_mb is None


# ── Analytics ─────────────────────────────────────────────────────────────────


class TestAnalytics:
    def test_defaults(self) -> None:
        a = Analytics()
        assert a.track_engagement is False
        assert a.heatmap is False
        assert a.click_tracking is False

    def test_all_true(self) -> None:
        a = Analytics(track_engagement=True, heatmap=True, click_tracking=True)
        assert a.track_engagement is True


# ── DemoConfig (root) ─────────────────────────────────────────────────────────


class TestDemoConfig:
    def test_minimal(self, minimal_config_dict: dict[str, Any]) -> None:
        cfg = DemoConfig(**minimal_config_dict)
        assert cfg.metadata.title == "Test Demo"
        assert cfg.voice is None
        assert cfg.scenarios == []
        assert cfg.pipeline == []

    def test_full(self, full_config_dict: dict[str, Any]) -> None:
        cfg = DemoConfig(**full_config_dict)
        assert cfg.metadata.title == "Full Demo"
        assert cfg.voice is not None
        assert cfg.voice.engine == "elevenlabs"
        assert len(cfg.scenarios) == 1
        assert len(cfg.scenarios[0].steps) == 6
        assert len(cfg.pipeline) == 8
        assert cfg.output is not None
        assert cfg.output.filename == "demo.mp4"
        assert cfg.analytics is not None
        assert cfg.analytics.track_engagement is True

    def test_missing_metadata(self) -> None:
        with pytest.raises(ValidationError):
            DemoConfig()  # type: ignore[call-arg]

    def test_empty_scenarios(self) -> None:
        cfg = DemoConfig(metadata={"title": "T"}, scenarios=[])
        assert cfg.scenarios == []

    def test_pipeline_shorthand_in_list(self) -> None:
        cfg = DemoConfig(
            metadata={"title": "T"},
            pipeline=[
                {"restore_audio": {"denoise": True}},
                {"optimize": {"format": "mp4"}},
            ],
        )
        assert len(cfg.pipeline) == 2
        assert cfg.pipeline[0].stage_type == "restore_audio"
        assert cfg.pipeline[1].params == {"format": "mp4"}

    def test_null_optional_sections(self) -> None:
        cfg = DemoConfig(
            metadata={"title": "T"},
            voice=None,
            audio=None,
            device_rendering=None,
            video=None,
        )
        assert cfg.voice is None
        assert cfg.audio is None

    def test_from_yaml_string(self) -> None:
        import yaml
        raw = yaml.safe_load('metadata:\n  title: "YAML Test"')
        cfg = DemoConfig(**raw)
        assert cfg.metadata.title == "YAML Test"

    def test_from_json_string(self) -> None:
        import json
        raw = json.loads('{"metadata": {"title": "JSON Test"}}')
        cfg = DemoConfig(**raw)
        assert cfg.metadata.title == "JSON Test"
