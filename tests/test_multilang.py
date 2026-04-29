"""Tests for multi-language (multi-track audio + subtitles) support."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import DemoConfig, LanguagesConfig
from demodsl.orchestrators.export import ExportOrchestrator
from demodsl.orchestrators.narration import NarrationOrchestrator
from demodsl.orchestrators.post_processing import PostProcessingOrchestrator
from demodsl.effects.registry import EffectRegistry
from demodsl.pipeline.workspace import Workspace


def _ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path / "ws")


_has_ffmpeg = shutil.which("ffmpeg") is not None
try:
    from pydub import AudioSegment  # noqa: F401

    _has_pydub = True
except ImportError:
    _has_pydub = False


def _make_config(
    *,
    languages: dict | None = None,
    voice: dict | None = None,
    subtitle: dict | None = None,
    steps: list | None = None,
) -> DemoConfig:
    data: dict = {"metadata": {"title": "Multilang"}}
    if languages is not None:
        data["languages"] = languages
    if voice is not None:
        data["voice"] = voice
    if subtitle is not None:
        data["subtitle"] = subtitle
    data["scenarios"] = [
        {
            "name": "S1",
            "url": "https://example.com",
            "steps": steps
            or [
                {
                    "action": "navigate",
                    "url": "https://example.com",
                    "narration": "Bonjour",
                    "narrations": {"en": "Hello", "de": "Hallo"},
                },
                {
                    "action": "pause",
                    "wait": 1.0,
                    "narration": "Encore",
                    "narrations": {"en": "Again"},  # missing 'de'
                },
            ],
        }
    ]
    return DemoConfig(**data)


# ── Models ──────────────────────────────────────────────────────────────


class TestLanguagesConfigModel:
    def test_defaults(self) -> None:
        cfg = LanguagesConfig()
        assert cfg.default == "fr"
        assert cfg.targets == []
        assert cfg.voices is None
        assert cfg.embed is True
        assert cfg.burn_default is False
        assert cfg.audio_only == []
        assert cfg.subtitle_only == []

    def test_full(self) -> None:
        cfg = LanguagesConfig(
            default="en",
            targets=["fr", "de"],
            voices={"fr": {"engine": "gtts", "voice_id": "fr"}},
            embed=False,
            burn_default=True,
            audio_only=["es"],
            subtitle_only=["it"],
        )
        assert cfg.default == "en"
        assert cfg.targets == ["fr", "de"]
        assert cfg.voices is not None and cfg.voices["fr"].voice_id == "fr"
        assert cfg.embed is False
        assert cfg.burn_default is True
        assert cfg.audio_only == ["es"]
        assert cfg.subtitle_only == ["it"]

    def test_locale_codes_accepted(self) -> None:
        # BCP-47 forms
        for code in ("en", "fr", "en-US", "pt-BR", "zh_TW", "yue"):
            LanguagesConfig(default=code)

    def test_invalid_code_rejected(self) -> None:
        with pytest.raises(Exception):
            LanguagesConfig(default="123")
        with pytest.raises(Exception):
            LanguagesConfig(default="x")  # too short


class TestStepNarrationsField:
    def test_step_accepts_narrations_dict(self) -> None:
        cfg = _make_config(languages={"default": "fr", "targets": ["en"]})
        step0 = cfg.scenarios[0].steps[0]
        assert step0.narrations == {"en": "Hello", "de": "Hallo"}

    def test_step_without_narrations_is_ok(self) -> None:
        cfg = _make_config(
            steps=[
                {
                    "action": "navigate",
                    "url": "https://example.com",
                    "narration": "Hi",
                }
            ]
        )
        assert cfg.scenarios[0].steps[0].narrations is None


# ── Narration orchestrator (text/voice resolution) ──────────────────────


class TestBuildNarrationTextsForLang:
    def test_default_uses_base_narration(self) -> None:
        cfg = _make_config(languages={"default": "fr", "targets": ["en"]})
        orch = NarrationOrchestrator(cfg, skip_voice=True)
        texts = orch.build_narration_texts_for_lang("fr", "fr")
        assert texts == {0: "Bonjour", 1: "Encore"}

    def test_target_uses_translation(self) -> None:
        cfg = _make_config(languages={"default": "fr", "targets": ["en"]})
        orch = NarrationOrchestrator(cfg, skip_voice=True)
        texts = orch.build_narration_texts_for_lang("en", "fr")
        assert texts == {0: "Hello", 1: "Again"}

    def test_target_falls_back_to_default_when_missing(self) -> None:
        cfg = _make_config(languages={"default": "fr", "targets": ["de"]})
        orch = NarrationOrchestrator(cfg, skip_voice=True)
        texts = orch.build_narration_texts_for_lang("de", "fr")
        # Step 0 has 'de'; step 1 is missing 'de', falls back to FR text.
        assert texts == {0: "Hallo", 1: "Encore"}

    def test_voice_config_for_lang_uses_override(self) -> None:
        cfg = _make_config(
            voice={"engine": "gtts", "voice_id": "fr"},
            languages={
                "default": "fr",
                "targets": ["en"],
                "voices": {"en": {"engine": "gtts", "voice_id": "en"}},
            },
        )
        orch = NarrationOrchestrator(cfg, skip_voice=True)
        # Default voice fallback when no override
        assert orch._voice_config_for_lang("fr", "fr").voice_id == "fr"
        # Override per-lang
        assert orch._voice_config_for_lang("en", "fr").voice_id == "en"
        # Unknown target falls back to root voice
        assert orch._voice_config_for_lang("zz", "fr").voice_id == "fr"


class TestGenerateNarrationsForLang:
    def test_skip_voice_returns_dry_paths(self, tmp_path: Path) -> None:
        cfg = _make_config(languages={"default": "fr", "targets": ["en"]})
        orch = NarrationOrchestrator(cfg, skip_voice=True)
        ws = _ws(tmp_path)
        result = orch.generate_narrations_for_lang(ws, "en", "fr")
        assert set(result) == {0, 1}
        for p in result.values():
            assert "_en_" in p.name or p.name.startswith("_dry_en_")

    def test_lang_tagged_in_cache_extra(self, tmp_path: Path) -> None:
        """Cache extra should contain the language so the same source text
        generated for different languages is cached separately."""
        cfg = _make_config(
            voice={"engine": "gtts", "voice_id": "fr"},
            languages={"default": "fr", "targets": ["en"]},
        )
        orch = NarrationOrchestrator(cfg, skip_voice=False)
        ws = _ws(tmp_path)

        captured_extras: list[dict] = []

        class _FakeProvider:
            def cache_extra(self):
                return {"engine_specific": "x"}

            def generate(self, text, voice_id, speed, pitch, reference_audio=None):
                out = ws.audio_clips / f"clip_{len(captured_extras)}.mp3"
                out.write_bytes(b"\x00")
                return out

            def close(self):
                pass

        with patch(
            "demodsl.providers.base.VoiceProviderFactory.create",
            return_value=_FakeProvider(),
        ):
            orig_store = orch._tts_cache.store

            def _spy_lookup(*args, **kwargs):
                captured_extras.append(dict(kwargs.get("extra") or {}))
                return None

            def _spy_store(*args, **kwargs):
                return orig_store(*args, **kwargs)

            with patch.object(orch._tts_cache, "lookup", side_effect=_spy_lookup):
                with patch.object(orch._tts_cache, "store", side_effect=_spy_store):
                    orch.generate_narrations_for_lang(ws, "en", "fr")

        assert captured_extras, "lookup should have been called"
        assert all(e.get("_lang") == "en" for e in captured_extras)


# ── Subtitle file generation ────────────────────────────────────────────


class TestGenerateSubtitleFile:
    def test_writes_lang_specific_ass(self, tmp_path: Path) -> None:
        cfg = _make_config(
            subtitle={"enabled": True, "style": "classic"},
            languages={"default": "fr", "targets": ["en"]},
        )
        post = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = _ws(tmp_path)

        narration_texts = {0: "Hello", 1: "Again"}
        durations = {0: 1.0, 1: 1.5}
        timestamps = [0.0, 2.0]

        ass = post.generate_subtitle_file(
            ws, narration_texts, durations, timestamps, "en"
        )
        assert ass is not None
        assert ass.name == "subtitles_en.ass"
        assert ass.exists()
        content = ass.read_text(encoding="utf-8")
        assert "Hello" in content
        assert "Again" in content

    def test_returns_none_when_no_text(self, tmp_path: Path) -> None:
        cfg = _make_config(
            subtitle={"enabled": True},
            languages={"default": "fr", "targets": ["en"]},
        )
        post = PostProcessingOrchestrator(cfg, EffectRegistry())
        ws = _ws(tmp_path)

        assert post.generate_subtitle_file(ws, {}, {}, [], "en") is None


# ── Multilang export (ffmpeg mux) ───────────────────────────────────────


class TestExportMultilangVideo:
    def test_falls_back_when_no_audio_tracks(self, tmp_path: Path) -> None:
        cfg = _make_config()
        orch = ExportOrchestrator(cfg)
        src = tmp_path / "in.mp4"
        dst = tmp_path / "out.mp4"
        src.write_bytes(b"\x00")

        with patch.object(orch, "export_video") as mock_export:
            orch.export_multilang_video(src, dst, audio_tracks=[])
        mock_export.assert_called_once_with(src, dst, audio=None)

    @patch("subprocess.run")
    def test_builds_correct_ffmpeg_command(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        cfg = _make_config()
        orch = ExportOrchestrator(cfg)

        src = tmp_path / "in.mp4"
        dst = tmp_path / "out.mp4"
        src.write_bytes(b"\x00")
        a_fr = tmp_path / "fr.mp3"
        a_fr.write_bytes(b"\x00")
        a_en = tmp_path / "en.mp3"
        a_en.write_bytes(b"\x00")
        s_fr = tmp_path / "fr.ass"
        s_fr.write_text("")
        s_en = tmp_path / "en.ass"
        s_en.write_text("")

        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        mock_run.return_value = result

        with patch.object(orch, "verify_video"):
            orch.export_multilang_video(
                src,
                dst,
                audio_tracks=[("fr", a_fr), ("en", a_en)],
                subtitle_tracks=[("fr", s_fr), ("en", s_en)],
            )

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        # Inputs: video + 2 audio + 2 sub
        assert cmd.count("-i") == 5
        # Stream maps
        assert "0:v:0" in cmd
        assert "1:a:0" in cmd
        assert "2:a:0" in cmd
        assert "3:s:0" in cmd
        assert "4:s:0" in cmd
        # Language metadata
        joined = " ".join(cmd)
        assert "language=fr" in joined
        assert "language=en" in joined
        # Subtitle codec for MP4 container
        assert "mov_text" in cmd
        # First audio is default
        assert "-disposition:a:0" in cmd

    @patch("subprocess.run")
    def test_falls_back_on_ffmpeg_failure(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        cfg = _make_config()
        orch = ExportOrchestrator(cfg)
        src = tmp_path / "in.mp4"
        dst = tmp_path / "out.mp4"
        src.write_bytes(b"\x00")
        a_fr = tmp_path / "fr.mp3"
        a_fr.write_bytes(b"\x00")

        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        mock_run.return_value = result

        with patch.object(orch, "export_video") as mock_export:
            orch.export_multilang_video(src, dst, audio_tracks=[("fr", a_fr)])
        mock_export.assert_called_once_with(src, dst, audio=a_fr)


# ── Engine multilang plumbing ────────────────────────────────────────────


class TestEngineMultilangHelper:
    """Smoke-test the engine helper without running the full pipeline."""

    def test_helper_skipped_without_languages(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        # Minimal config without languages
        yaml_text = """
metadata:
  title: NoLang
voice:
  engine: gtts
  voice_id: fr
scenarios:
  - name: s
    url: https://example.com
    steps:
      - action: navigate
        url: https://example.com
        narration: hi
"""
        cfg_path = tmp_path / "demo.yaml"
        cfg_path.write_text(yaml_text)

        engine = DemoEngine(config_path=cfg_path, dry_run=True)
        # Default LanguagesConfig is None → multilang inactive.
        assert engine.config.languages is None

    def test_targets_make_languages_active(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        yaml_text = """
metadata:
  title: ML
voice:
  engine: gtts
  voice_id: fr
languages:
  default: fr
  targets: [en, de]
scenarios:
  - name: s
    url: https://example.com
    steps:
      - action: navigate
        url: https://example.com
        narration: bonjour
        narrations:
          en: hello
          de: hallo
"""
        cfg_path = tmp_path / "demo.yaml"
        cfg_path.write_text(yaml_text)
        engine = DemoEngine(config_path=cfg_path, dry_run=True)
        assert engine.config.languages is not None
        assert engine.config.languages.targets == ["en", "de"]
        # Step retains per-lang dict
        step = engine.config.scenarios[0].steps[0]
        assert step.narrations == {"en": "hello", "de": "hallo"}
