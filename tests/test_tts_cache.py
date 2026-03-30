"""Tests for demodsl.providers.tts_cache — TTSCache."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.providers.tts_cache import TTSCache


class TestTTSCacheKey:
    """Cache key computation is deterministic and sensitive to inputs."""

    def test_same_inputs_same_key(self) -> None:
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        assert k1 == k2

    def test_different_text_different_key(self) -> None:
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("elevenlabs", "Goodbye", "josh", 1.0, 0, None)
        assert k1 != k2

    def test_different_engine_different_key(self) -> None:
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("openai", "Hello", "josh", 1.0, 0, None)
        assert k1 != k2

    def test_different_voice_id_different_key(self) -> None:
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("elevenlabs", "Hello", "rachel", 1.0, 0, None)
        assert k1 != k2

    def test_different_speed_different_key(self) -> None:
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.5, 0, None)
        assert k1 != k2

    def test_different_pitch_different_key(self) -> None:
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 5, None)
        assert k1 != k2

    def test_reference_audio_changes_key(self, tmp_path: Path) -> None:
        ref = tmp_path / "sample.wav"
        ref.write_bytes(b"\x00" * 100)
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, ref)
        assert k1 != k2

    def test_different_reference_audio_different_key(self, tmp_path: Path) -> None:
        ref1 = tmp_path / "a.wav"
        ref1.write_bytes(b"\x00" * 100)
        ref2 = tmp_path / "b.wav"
        ref2.write_bytes(b"\xff" * 100)
        k1 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, ref1)
        k2 = TTSCache._cache_key("elevenlabs", "Hello", "josh", 1.0, 0, ref2)
        assert k1 != k2

    def test_extra_params_change_key(self) -> None:
        k1 = TTSCache._cache_key("local_openai", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key(
            "local_openai",
            "Hello",
            "josh",
            1.0,
            0,
            None,
            extra={"api_url": "http://localhost:8000", "model": "tts-1"},
        )
        assert k1 != k2

    def test_different_extra_model_different_key(self) -> None:
        k1 = TTSCache._cache_key(
            "piper",
            "Hello",
            "josh",
            1.0,
            0,
            None,
            extra={"model": "/models/en-us.onnx"},
        )
        k2 = TTSCache._cache_key(
            "piper",
            "Hello",
            "josh",
            1.0,
            0,
            None,
            extra={"model": "/models/fr-fr.onnx"},
        )
        assert k1 != k2

    def test_same_extra_same_key(self) -> None:
        extra = {"api_url": "http://localhost:50000"}
        k1 = TTSCache._cache_key(
            "cosyvoice", "Hello", "josh", 1.0, 0, None, extra=extra
        )
        k2 = TTSCache._cache_key(
            "cosyvoice", "Hello", "josh", 1.0, 0, None, extra=extra
        )
        assert k1 == k2

    def test_empty_extra_same_as_none(self) -> None:
        k1 = TTSCache._cache_key("dummy", "Hello", "josh", 1.0, 0, None, extra=None)
        k2 = TTSCache._cache_key("dummy", "Hello", "josh", 1.0, 0, None, extra={})
        assert k1 == k2


class TestTTSCacheDisabled:
    """When disabled, cache is a no-op."""

    def test_lookup_returns_none(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=False, cache_dir=tmp_path / "cache")
        result = cache.lookup(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=tmp_path / "out.mp3",
        )
        assert result is None

    def test_store_does_nothing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache = TTSCache(enabled=False, cache_dir=cache_dir)
        gen = tmp_path / "generated.mp3"
        gen.write_bytes(b"\x00" * 50)
        cache.store(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen,
        )
        assert not cache_dir.exists()


class TestTTSCacheLookupAndStore:
    """End-to-end cache store → lookup cycle."""

    def test_miss_then_hit(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")
        dest = tmp_path / "workspace" / "narration_001.mp3"
        dest.parent.mkdir(parents=True)

        # Miss
        result = cache.lookup(
            engine="dummy",
            text="Hello world",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest,
        )
        assert result is None

        # Store
        gen = tmp_path / "generated.mp3"
        gen.write_bytes(b"fake-audio-data-12345")
        cache.store(
            engine="dummy",
            text="Hello world",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen,
        )

        # Hit
        result = cache.lookup(
            engine="dummy",
            text="Hello world",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest,
        )
        assert result is not None
        assert result.exists()
        assert result.read_bytes() == b"fake-audio-data-12345"

    def test_wav_extension_preserved(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "narration.wav"
        gen.write_bytes(b"wav-data")
        cache.store(
            engine="coqui",
            text="Test",
            voice_id="default",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen,
        )

        dest = tmp_path / "out.mp3"  # initial extension is mp3
        result = cache.lookup(
            engine="coqui",
            text="Test",
            voice_id="default",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest,
        )
        assert result is not None
        assert result.suffix == ".wav"
        assert result.read_bytes() == b"wav-data"

    def test_different_text_is_a_miss(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "gen.mp3"
        gen.write_bytes(b"audio")
        cache.store(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen,
        )

        dest = tmp_path / "out.mp3"
        result = cache.lookup(
            engine="dummy",
            text="Goodbye",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest,
        )
        assert result is None


class TestTTSCacheClear:
    def test_clear_removes_files(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "gen.mp3"
        gen.write_bytes(b"audio")
        cache.store(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen,
        )
        assert len(list(cache.cache_dir.iterdir())) == 1

        removed = cache.clear()
        assert removed == 1
        assert len(list(cache.cache_dir.iterdir())) == 0

    def test_clear_on_empty_dir(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")
        assert cache.clear() == 0

    def test_clear_on_nonexistent_dir(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=False, cache_dir=tmp_path / "nonexist")
        assert cache.clear() == 0


class TestTTSCacheWithExtra:
    """Cache correctly discriminates on provider-specific params."""

    def test_different_model_is_a_miss(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "gen.wav"
        gen.write_bytes(b"audio-model-a")
        cache.store(
            engine="piper",
            text="Hello",
            voice_id="default",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={"model": "/models/en-us.onnx"},
            generated_path=gen,
        )

        # Same text, different model → miss
        dest = tmp_path / "out.wav"
        result = cache.lookup(
            engine="piper",
            text="Hello",
            voice_id="default",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={"model": "/models/fr-fr.onnx"},
            dest_path=dest,
        )
        assert result is None

    def test_same_model_is_a_hit(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "gen.wav"
        gen.write_bytes(b"audio-model-a")
        cache.store(
            engine="piper",
            text="Hello",
            voice_id="default",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={"model": "/models/en-us.onnx"},
            generated_path=gen,
        )

        dest = tmp_path / "out.wav"
        result = cache.lookup(
            engine="piper",
            text="Hello",
            voice_id="default",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={"model": "/models/en-us.onnx"},
            dest_path=dest,
        )
        assert result is not None
        assert result.read_bytes() == b"audio-model-a"

    def test_different_api_url_is_a_miss(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "gen.mp3"
        gen.write_bytes(b"audio-server-a")
        cache.store(
            engine="local_openai",
            text="Hello",
            voice_id="alloy",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={"api_url": "http://server-a:8000", "model": "tts-1"},
            generated_path=gen,
        )

        dest = tmp_path / "out.mp3"
        result = cache.lookup(
            engine="local_openai",
            text="Hello",
            voice_id="alloy",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={"api_url": "http://server-b:8000", "model": "tts-1"},
            dest_path=dest,
        )
        assert result is None


class TestProviderCacheExtra:
    """Each provider returns the right cache_extra() keys."""

    def test_dummy_returns_empty(self) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        p = DummyVoiceProvider()
        assert p.cache_extra() == {}

    def test_piper_includes_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIPER_MODEL", "/my/model.onnx")
        from demodsl.providers.voice import PiperVoiceProvider

        p = PiperVoiceProvider()
        extra = p.cache_extra()
        assert extra["model"] == "/my/model.onnx"

    def test_local_openai_includes_url_and_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOCAL_TTS_URL", "http://my-server:9000")
        monkeypatch.setenv("LOCAL_TTS_MODEL", "custom-tts")
        from demodsl.providers.voice import LocalOpenAIVoiceProvider

        p = LocalOpenAIVoiceProvider()
        extra = p.cache_extra()
        assert extra["api_url"] == "http://my-server:9000"
        assert extra["model"] == "custom-tts"

    def test_cosyvoice_includes_api_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COSYVOICE_API_URL", "http://cosyvoice:7000")
        from demodsl.providers.voice import CosyVoiceProvider

        p = CosyVoiceProvider()
        extra = p.cache_extra()
        assert extra["api_url"] == "http://cosyvoice:7000"

    def test_custom_includes_url_and_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://my-tts/generate")
        from demodsl.providers.voice import CustomVoiceProvider

        p = CustomVoiceProvider()
        extra = p.cache_extra()
        assert extra["api_url"] == "http://my-tts/generate"
        assert "format" in extra

    def test_espeak_includes_bin(self) -> None:
        from demodsl.providers.voice import ESpeakVoiceProvider

        p = ESpeakVoiceProvider()
        assert "espeak_bin" in p.cache_extra()

    def test_coqui_includes_model_and_language(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from demodsl.providers.voice import CoquiXTTSVoiceProvider

        monkeypatch.setenv("COQUI_MODEL", "my-model")
        monkeypatch.setenv("COQUI_LANGUAGE", "fr")
        p = CoquiXTTSVoiceProvider()
        extra = p.cache_extra()
        assert extra["model"] == "my-model"
        assert extra["language"] == "fr"

    def test_elevenlabs_includes_model_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        from demodsl.providers.voice import ElevenLabsVoiceProvider

        p = ElevenLabsVoiceProvider()
        assert p.cache_extra()["model_id"] == "eleven_monolingual_v1"

    def test_azure_includes_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
        from demodsl.providers.voice import AzureTTSVoiceProvider

        p = AzureTTSVoiceProvider()
        assert p.cache_extra()["region"] == "westeurope"

    def test_aws_polly_includes_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        from demodsl.providers.voice import AWSPollyVoiceProvider

        p = AWSPollyVoiceProvider()
        assert p.cache_extra()["region"] == "eu-west-1"


# ── Cache key format tests ───────────────────────────────────────────────────


class TestCacheKeyFormat:
    """Cache key is a valid SHA-256 hex digest."""

    def test_key_is_64_hex_chars(self) -> None:
        key = TTSCache._cache_key("dummy", "Hello", "josh", 1.0, 0, None)
        assert re.fullmatch(r"[0-9a-f]{64}", key)

    def test_key_deterministic_across_calls(self) -> None:
        keys = {
            TTSCache._cache_key("dummy", "Test", "josh", 1.0, 0, None)
            for _ in range(10)
        }
        assert len(keys) == 1

    def test_key_with_unicode_text(self) -> None:
        k1 = TTSCache._cache_key("dummy", "Bonjour le monde 🌍", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("dummy", "Bonjour le monde 🌍", "josh", 1.0, 0, None)
        assert k1 == k2
        assert re.fullmatch(r"[0-9a-f]{64}", k1)

    def test_key_with_empty_text(self) -> None:
        key = TTSCache._cache_key("dummy", "", "josh", 1.0, 0, None)
        assert re.fullmatch(r"[0-9a-f]{64}", key)

    def test_key_with_very_long_text(self) -> None:
        text = "word " * 10000
        key = TTSCache._cache_key("dummy", text, "josh", 1.0, 0, None)
        assert re.fullmatch(r"[0-9a-f]{64}", key)


# ── Cache edge cases ─────────────────────────────────────────────────────────


class TestTTSCacheEdgeCases:
    """Edge cases and robustness tests."""

    def test_store_nonexistent_file_is_noop(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")
        cache.store(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=tmp_path / "does_not_exist.mp3",
        )
        assert len(list((tmp_path / "cache").iterdir())) == 0

    def test_store_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen1 = tmp_path / "gen1.mp3"
        gen1.write_bytes(b"first-audio")
        cache.store(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen1,
        )

        gen2 = tmp_path / "gen2.mp3"
        gen2.write_bytes(b"second-audio-different")
        cache.store(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen2,
        )

        dest = tmp_path / "out.mp3"
        result = cache.lookup(
            engine="dummy",
            text="Hello",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest,
        )
        assert result is not None
        assert result.read_bytes() == b"first-audio"

    def test_lookup_copies_file_not_moves(self, tmp_path: Path) -> None:
        """Lookup copies from cache, doesn't remove the original."""
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        gen = tmp_path / "gen.mp3"
        gen.write_bytes(b"audio-bytes")
        cache.store(
            engine="dummy",
            text="Copy test",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            generated_path=gen,
        )

        dest1 = tmp_path / "out1.mp3"
        result1 = cache.lookup(
            engine="dummy",
            text="Copy test",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest1,
        )

        dest2 = tmp_path / "out2.mp3"
        result2 = cache.lookup(
            engine="dummy",
            text="Copy test",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            dest_path=dest2,
        )

        assert result1 is not None and result2 is not None
        assert result1.read_bytes() == b"audio-bytes"
        assert result2.read_bytes() == b"audio-bytes"
        # Cache file still exists
        cached_files = list((tmp_path / "cache").iterdir())
        assert len(cached_files) == 1

    def test_cache_dir_created_on_init(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        assert not cache_dir.exists()
        TTSCache(enabled=True, cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_cache_dir_not_created_when_disabled(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "no_create"
        TTSCache(enabled=False, cache_dir=cache_dir)
        assert not cache_dir.exists()

    def test_reference_audio_nonexistent_treated_as_none(self, tmp_path: Path) -> None:
        ref = tmp_path / "ghost.wav"  # doesn't exist
        k1 = TTSCache._cache_key("dummy", "Hello", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("dummy", "Hello", "josh", 1.0, 0, ref)
        assert k1 == k2

    def test_speed_precision_matters(self) -> None:
        """1.0 and 1.0001 should produce the same key (4 decimal places)."""
        k1 = TTSCache._cache_key("dummy", "Test", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("dummy", "Test", "josh", 1.00001, 0, None)
        assert k1 == k2

    def test_speed_different_at_4th_decimal(self) -> None:
        k1 = TTSCache._cache_key("dummy", "Test", "josh", 1.0, 0, None)
        k2 = TTSCache._cache_key("dummy", "Test", "josh", 1.0001, 0, None)
        assert k1 != k2

    def test_multiple_entries_independent(self, tmp_path: Path) -> None:
        """Storing multiple different texts creates separate cache entries."""
        cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        for i, text in enumerate(["Alpha", "Beta", "Gamma"]):
            gen = tmp_path / f"gen_{i}.mp3"
            gen.write_bytes(f"audio-{text}".encode())
            cache.store(
                engine="dummy",
                text=text,
                voice_id="josh",
                speed=1.0,
                pitch=0,
                reference_audio=None,
                generated_path=gen,
            )

        assert len(list((tmp_path / "cache").iterdir())) == 3

        for text in ["Alpha", "Beta", "Gamma"]:
            dest = tmp_path / f"out_{text}.mp3"
            result = cache.lookup(
                engine="dummy",
                text=text,
                voice_id="josh",
                speed=1.0,
                pitch=0,
                reference_audio=None,
                dest_path=dest,
            )
            assert result is not None
            assert result.read_bytes() == f"audio-{text}".encode()


# ── Orchestrator integration tests ───────────────────────────────────────────


class TestNarrationOrchestratorCacheIntegration:
    """Tests that NarrationOrchestrator correctly uses the TTS cache."""

    @staticmethod
    def _make_config(narrations: list[str | None]):
        from demodsl.models import DemoConfig

        steps = []
        for narration in narrations:
            step: dict = {"action": "navigate", "url": "https://example.com"}
            if narration:
                step["narration"] = narration
            steps.append(step)
        return DemoConfig(
            **{
                "metadata": {"title": "Cache Test"},
                "scenarios": [
                    {"name": "S1", "url": "https://example.com", "steps": steps}
                ],
            }
        )

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_cache_prevents_duplicate_api_calls(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """When the same text appears twice, only one API call is made."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        config = self._make_config(["Hello world", "Hello world"])
        orch = NarrationOrchestrator(config, tts_cache=True)
        orch._tts_cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        mock_voice = MagicMock()
        call_count = [0]

        def fake_generate(**kwargs):
            call_count[0] += 1
            p = tmp_path / f"narration_{call_count[0]:03d}.mp3"
            p.write_bytes(b"audio-data")
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_voice.cache_extra.return_value = {}
        mock_factory.create.return_value = mock_voice

        with Workspace() as ws:
            result = orch.generate_narrations(ws)

            assert len(result) == 2
            # Only 1 API call, second should be a cache hit
            assert mock_voice.generate.call_count == 1
            # Both paths should exist and have the same content
            for path in result.values():
                assert path.exists()
                assert path.read_bytes() == b"audio-data"

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_cache_disabled_calls_api_every_time(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """When cache is disabled, every narration triggers an API call."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        config = self._make_config(["Hello world", "Hello world"])
        orch = NarrationOrchestrator(config, tts_cache=False)

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = tmp_path / f"narration_{counter[0]:03d}.mp3"
            p.write_bytes(b"audio-data")
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_voice.cache_extra.return_value = {}
        mock_factory.create.return_value = mock_voice

        with Workspace() as ws:
            result = orch.generate_narrations(ws)

        assert len(result) == 2
        assert mock_voice.generate.call_count == 2

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_different_texts_all_generate(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """Different narration texts each trigger an API call."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        config = self._make_config(["First", "Second", "Third"])
        orch = NarrationOrchestrator(config, tts_cache=True)
        orch._tts_cache = TTSCache(enabled=True, cache_dir=tmp_path / "cache")

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = tmp_path / f"narration_{counter[0]:03d}.mp3"
            p.write_bytes(f"audio-{counter[0]}".encode())
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_voice.cache_extra.return_value = {}
        mock_factory.create.return_value = mock_voice

        with Workspace() as ws:
            result = orch.generate_narrations(ws)

        assert len(result) == 3
        assert mock_voice.generate.call_count == 3

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_second_run_uses_cache(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """Simulating two runs: second run should fully use cache."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        config = self._make_config(["Hello", "World"])
        cache_dir = tmp_path / "shared_cache"

        # First run
        orch1 = NarrationOrchestrator(config, tts_cache=True)
        orch1._tts_cache = TTSCache(enabled=True, cache_dir=cache_dir)

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = tmp_path / f"run1_narration_{counter[0]:03d}.mp3"
            p.write_bytes(f"audio-{counter[0]}".encode())
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_voice.cache_extra.return_value = {}
        mock_factory.create.return_value = mock_voice

        with Workspace() as ws:
            orch1.generate_narrations(ws)
            assert mock_voice.generate.call_count == 2

        # Second run with same config and shared cache
        mock_voice.generate.reset_mock()
        orch2 = NarrationOrchestrator(config, tts_cache=True)
        orch2._tts_cache = TTSCache(enabled=True, cache_dir=cache_dir)

        with Workspace() as ws:
            result2 = orch2.generate_narrations(ws)

            assert len(result2) == 2
            # No new API calls
            assert mock_voice.generate.call_count == 0
            # Files should exist and have the right content
            for path in result2.values():
                assert path.exists()

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_cache_extra_passed_to_cache(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """Provider-specific extra params are passed to the cache."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        config = self._make_config(["Hello"])
        cache_dir = tmp_path / "cache"

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = tmp_path / f"narration_{counter[0]:03d}.mp3"
            p.write_bytes(b"audio-local")
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_voice.cache_extra.return_value = {
            "api_url": "http://my-server:8000",
            "model": "custom-tts",
        }
        mock_factory.create.return_value = mock_voice

        orch = NarrationOrchestrator(config, tts_cache=True)
        orch._tts_cache = TTSCache(enabled=True, cache_dir=cache_dir)

        with Workspace() as ws:
            orch.generate_narrations(ws)

        # Verify cache_extra was called
        mock_voice.cache_extra.assert_called_once()

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_provider_change_invalidates_cache(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """Changing provider extra params (e.g. model) causes cache miss."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        config = self._make_config(["Hello"])
        cache_dir = tmp_path / "cache"

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = tmp_path / f"narration_{counter[0]:03d}.mp3"
            p.write_bytes(f"audio-{counter[0]}".encode())
            return p

        mock_voice.generate.side_effect = fake_generate

        # Run 1: model A
        mock_voice.cache_extra.return_value = {"model": "model-a"}
        mock_factory.create.return_value = mock_voice

        orch1 = NarrationOrchestrator(config, tts_cache=True)
        orch1._tts_cache = TTSCache(enabled=True, cache_dir=cache_dir)

        with Workspace() as ws:
            orch1.generate_narrations(ws)
        assert mock_voice.generate.call_count == 1

        # Run 2: model B → should NOT use cache
        mock_voice.generate.reset_mock()
        mock_voice.cache_extra.return_value = {"model": "model-b"}
        counter[0] = 10

        orch2 = NarrationOrchestrator(config, tts_cache=True)
        orch2._tts_cache = TTSCache(enabled=True, cache_dir=cache_dir)

        with Workspace() as ws:
            orch2.generate_narrations(ws)
        assert mock_voice.generate.call_count == 1  # fresh call, not cached

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_mixed_cached_and_fresh(
        self, mock_factory: MagicMock, mock_time: MagicMock, tmp_path: Path
    ) -> None:
        """Some clips cached, some fresh — only fresh ones call API."""
        from demodsl.orchestrators.narration import NarrationOrchestrator
        from demodsl.pipeline.workspace import Workspace

        cache_dir = tmp_path / "cache"

        # Pre-populate cache with "Cached text"
        cache = TTSCache(enabled=True, cache_dir=cache_dir)
        pre = tmp_path / "pre.mp3"
        pre.write_bytes(b"pre-cached-audio")
        cache.store(
            engine="dummy",
            text="Cached text",
            voice_id="josh",
            speed=1.0,
            pitch=0,
            reference_audio=None,
            extra={},
            generated_path=pre,
        )

        config = self._make_config(["Cached text", "Fresh text"])
        orch = NarrationOrchestrator(config, tts_cache=True)
        orch._tts_cache = TTSCache(enabled=True, cache_dir=cache_dir)

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = tmp_path / f"narration_{counter[0]:03d}.mp3"
            p.write_bytes(b"fresh-audio")
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_voice.cache_extra.return_value = {}
        mock_factory.create.return_value = mock_voice

        with Workspace() as ws:
            result = orch.generate_narrations(ws)

            assert len(result) == 2
            assert mock_voice.generate.call_count == 1  # only "Fresh text"
            # Cached clip has pre-cached content
            assert result[0].read_bytes() == b"pre-cached-audio"
            # Fresh clip has new content
            assert result[1].read_bytes() == b"fresh-audio"


# ── Engine wiring tests ─────────────────────────────────────────────────────


class TestEngineTTSCacheWiring:
    """DemoEngine passes tts_cache to NarrationOrchestrator."""

    def test_cache_enabled_by_default(self, full_yaml_path: "Path") -> None:
        from demodsl.engine import DemoEngine

        engine = DemoEngine(config_path=full_yaml_path, dry_run=True)
        assert engine._narration._tts_cache._enabled is True

    def test_cache_disabled_flag(self, full_yaml_path: "Path") -> None:
        from demodsl.engine import DemoEngine

        engine = DemoEngine(config_path=full_yaml_path, dry_run=True, tts_cache=False)
        assert engine._narration._tts_cache._enabled is False


# ── CLI flag tests ───────────────────────────────────────────────────────────


class TestCLINoTTSCache:
    """CLI --no-tts-cache flag is properly wired."""

    def test_no_tts_cache_flag_accepted(self, full_yaml_path: "Path") -> None:
        from typer.testing import CliRunner as _CliRunner

        from demodsl.cli import app

        runner = _CliRunner()
        result = runner.invoke(
            app,
            ["run", str(full_yaml_path), "--dry-run", "--no-tts-cache"],
        )
        assert result.exit_code == 0

    def test_help_mentions_tts_cache(self) -> None:
        from typer.testing import CliRunner as _CliRunner

        from demodsl.cli import app

        runner = _CliRunner()
        result = runner.invoke(app, ["run", "--help"])
        assert "--no-tts-cache" in result.output

    @patch("demodsl.engine.DemoEngine")
    def test_no_tts_cache_passed_to_engine(
        self, mock_engine_cls: MagicMock, full_yaml_path: "Path"
    ) -> None:
        from typer.testing import CliRunner as _CliRunner

        from demodsl.cli import app

        mock_engine_cls.return_value.run.return_value = None
        runner = _CliRunner()
        runner.invoke(
            app,
            ["run", str(full_yaml_path), "--no-tts-cache"],
        )
        _, kwargs = mock_engine_cls.call_args
        assert kwargs["tts_cache"] is False

    @patch("demodsl.engine.DemoEngine")
    def test_default_tts_cache_enabled(
        self, mock_engine_cls: MagicMock, full_yaml_path: "Path"
    ) -> None:
        from typer.testing import CliRunner as _CliRunner

        from demodsl.cli import app

        mock_engine_cls.return_value.run.return_value = None
        runner = _CliRunner()
        runner.invoke(
            app,
            ["run", str(full_yaml_path)],
        )
        _, kwargs = mock_engine_cls.call_args
        assert kwargs["tts_cache"] is True
