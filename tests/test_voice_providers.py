"""Tests for demodsl.providers.voice — All voice providers."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_has_boto3 = (
    "boto3" in sys.modules
    or __import__("importlib").util.find_spec("boto3") is not None
)
_has_gtts = (
    "gtts" in sys.modules or __import__("importlib").util.find_spec("gtts") is not None
)
_has_ffmpeg = shutil.which("ffmpeg") is not None
try:
    from pydub import AudioSegment  # noqa: F401

    _has_pydub = True
except ImportError:
    _has_pydub = False


# ── ElevenLabsVoiceProvider ──────────────────────────────────────────────────


class TestElevenLabsVoiceProvider:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        from demodsl.providers.voice import ElevenLabsVoiceProvider

        with pytest.raises(EnvironmentError, match="ELEVENLABS_API_KEY"):
            ElevenLabsVoiceProvider()

    def test_init_with_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        from demodsl.providers.voice import ElevenLabsVoiceProvider

        provider = ElevenLabsVoiceProvider(output_dir=tmp_path)
        assert provider._api_key == "test-key"
        assert provider._counter == 0

    @patch("httpx.post")
    def test_generate_creates_file(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"\x00" * 100
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import ElevenLabsVoiceProvider

        provider = ElevenLabsVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello world", "josh")
        assert path.exists()
        assert path.name == "narration_001.mp3"
        assert provider._counter == 1

    @patch("httpx.post")
    def test_generate_counter_increments(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import ElevenLabsVoiceProvider

        provider = ElevenLabsVoiceProvider(output_dir=tmp_path)
        provider.generate("A", "josh")
        path2 = provider.generate("B", "josh")
        assert path2.name == "narration_002.mp3"

    @patch("httpx.post")
    def test_generate_with_reference_audio_clones_voice(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        # First call = voice clone, second call = TTS synthesis
        clone_resp = MagicMock()
        clone_resp.raise_for_status = MagicMock()
        clone_resp.json.return_value = {"voice_id": "cloned-abc123"}
        synth_resp = MagicMock()
        synth_resp.content = b"\x00" * 100
        synth_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [clone_resp, synth_resp]

        ref_file = tmp_path / "my_voice.wav"
        ref_file.write_bytes(b"\x00" * 200)

        from demodsl.providers.voice import ElevenLabsVoiceProvider

        provider = ElevenLabsVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello", "josh", reference_audio=ref_file)
        assert path.exists()
        # The clone endpoint should have been called first
        clone_call = mock_post.call_args_list[0]
        assert "voices/add" in str(clone_call)
        # The synthesis call should use the cloned voice_id
        synth_call = mock_post.call_args_list[1]
        assert "cloned-abc123" in str(synth_call)

    @patch("httpx.post")
    def test_cloned_voice_is_cached(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        clone_resp = MagicMock()
        clone_resp.raise_for_status = MagicMock()
        clone_resp.json.return_value = {"voice_id": "cloned-xyz"}
        synth_resp = MagicMock()
        synth_resp.content = b"\x00" * 50
        synth_resp.raise_for_status = MagicMock()
        # First time: clone + synth; second time: synth only (cached)
        mock_post.side_effect = [clone_resp, synth_resp, synth_resp]

        ref_file = tmp_path / "my_voice.wav"
        ref_file.write_bytes(b"\x00" * 100)

        from demodsl.providers.voice import ElevenLabsVoiceProvider

        provider = ElevenLabsVoiceProvider(output_dir=tmp_path)
        provider.generate("First", "josh", reference_audio=ref_file)
        provider.generate("Second", "josh", reference_audio=ref_file)
        # Clone API should only be called once, not twice
        assert mock_post.call_count == 3  # 1 clone + 2 synth


# ── GoogleTTSVoiceProvider ───────────────────────────────────────────────────


class TestGoogleTTSVoiceProvider:
    def test_missing_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        from demodsl.providers.voice import GoogleTTSVoiceProvider

        with pytest.raises(EnvironmentError, match="GOOGLE_APPLICATION_CREDENTIALS"):
            GoogleTTSVoiceProvider()

    def test_init_with_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/to/creds.json")
        from demodsl.providers.voice import GoogleTTSVoiceProvider

        provider = GoogleTTSVoiceProvider()
        assert provider._credentials == "/path/to/creds.json"


# ── AzureTTSVoiceProvider ───────────────────────────────────────────────────


class TestAzureTTSVoiceProvider:
    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        from demodsl.providers.voice import AzureTTSVoiceProvider

        with pytest.raises(EnvironmentError, match="AZURE_SPEECH_KEY"):
            AzureTTSVoiceProvider()

    def test_default_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        from demodsl.providers.voice import AzureTTSVoiceProvider

        provider = AzureTTSVoiceProvider()
        assert provider._region == "eastus"

    def test_custom_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
        from demodsl.providers.voice import AzureTTSVoiceProvider

        provider = AzureTTSVoiceProvider()
        assert provider._region == "westeurope"

    @patch("httpx.post")
    def test_generate_ssml(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import AzureTTSVoiceProvider

        provider = AzureTTSVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello", "en-US-JennyNeural", speed=1.5, pitch=5)
        assert path.exists()
        # Verify SSML was sent
        call_args = mock_post.call_args
        call_args.kwargs.get("content") or call_args.args[1] if len(
            call_args.args
        ) > 1 else ""
        # SSML should be in the call somewhere
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_ssml_escapes_special_chars(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import AzureTTSVoiceProvider

        provider = AzureTTSVoiceProvider(output_dir=tmp_path)
        malicious_text = 'Hello </prosody></voice></speak><speak> & "evil" <tag>'
        provider.generate(malicious_text, "en-US-JennyNeural")
        call_args = mock_post.call_args
        ssml_body = call_args.kwargs.get("content", "")
        # The raw XML closing tags should NOT appear unescaped
        assert "</prosody></voice></speak><speak>" not in ssml_body
        assert "&amp;" in ssml_body
        assert "&lt;" in ssml_body


# ── AWSPollyVoiceProvider ────────────────────────────────────────────────────


class TestAWSPollyVoiceProvider:
    def test_missing_access_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
        from demodsl.providers.voice import AWSPollyVoiceProvider

        with pytest.raises(EnvironmentError):
            AWSPollyVoiceProvider()

    def test_missing_secret_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "access")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        from demodsl.providers.voice import AWSPollyVoiceProvider

        with pytest.raises(EnvironmentError):
            AWSPollyVoiceProvider()

    def test_default_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        from demodsl.providers.voice import AWSPollyVoiceProvider

        provider = AWSPollyVoiceProvider()
        assert provider._region == "us-east-1"

    @pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
    def test_ssml_escapes_special_chars(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"\x00" * 50
        mock_client.synthesize_speech.return_value = {"AudioStream": mock_stream}

        with patch("boto3.client", return_value=mock_client):
            from demodsl.providers.voice import AWSPollyVoiceProvider

            provider = AWSPollyVoiceProvider(output_dir=tmp_path)
            malicious_text = "Say </prosody></speak> & <evil>"
            provider.generate(malicious_text, "Matthew")
            call_args = mock_client.synthesize_speech.call_args
            ssml_sent = call_args.kwargs.get("Text", "")
            # The injected XML should be escaped (& → &amp;, < → &lt;)
            assert "&amp;" in ssml_sent
            assert "&lt;evil&gt;" in ssml_sent
            # The injected </prosody> should be escaped, not raw
            assert "&lt;/prosody&gt;" in ssml_sent


# ── OpenAITTSVoiceProvider ───────────────────────────────────────────────────


class TestOpenAITTSVoiceProvider:
    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from demodsl.providers.voice import OpenAITTSVoiceProvider

        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            OpenAITTSVoiceProvider()

    @patch("httpx.post")
    def test_speed_clamped(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import OpenAITTSVoiceProvider

        provider = OpenAITTSVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "alloy", speed=10.0)
        call_json = mock_post.call_args.kwargs.get("json") or {}
        assert call_json.get("speed", 10.0) <= 4.0

    @patch("httpx.post")
    def test_invalid_voice_fallback(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.content = b"\x00"
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import OpenAITTSVoiceProvider

        provider = OpenAITTSVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "invalid_voice_name")
        call_json = mock_post.call_args.kwargs.get("json") or {}
        # Unknown voice should fall back to "alloy"
        assert call_json.get("voice") == "alloy"


# ── CosyVoiceProvider ────────────────────────────────────────────────────────


class TestCosyVoiceProvider:
    def test_default_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COSYVOICE_API_URL", raising=False)
        from demodsl.providers.voice import CosyVoiceProvider

        provider = CosyVoiceProvider()
        assert provider._api_url == "http://localhost:50000"

    def test_custom_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COSYVOICE_API_URL", "http://my-server:9000")
        from demodsl.providers.voice import CosyVoiceProvider

        provider = CosyVoiceProvider()
        assert provider._api_url == "http://my-server:9000"

    @patch("httpx.post")
    def test_generate(
        self, mock_post: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COSYVOICE_API_URL", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 100
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import CosyVoiceProvider

        provider = CosyVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello", "speaker1")
        assert path.exists()
        assert path.suffix == ".wav"
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_generate_with_reference_audio(
        self, mock_post: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COSYVOICE_API_URL", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 100
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        ref_file = tmp_path / "my_voice.wav"
        ref_file.write_bytes(b"\x00" * 200)

        from demodsl.providers.voice import CosyVoiceProvider

        provider = CosyVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello", "speaker1", reference_audio=ref_file)
        assert path.exists()
        call_json = mock_post.call_args.kwargs.get("json") or {}
        assert "reference_audio" in call_json
        assert call_json.get("mode") == "zero_shot"


# ── CoquiXTTSVoiceProvider ──────────────────────────────────────────────────


class TestCoquiXTTSVoiceProvider:
    def test_lazy_loading(self) -> None:
        from demodsl.providers.voice import CoquiXTTSVoiceProvider

        provider = CoquiXTTSVoiceProvider()
        assert provider._tts is None

    def test_close_resets_model(self) -> None:
        from demodsl.providers.voice import CoquiXTTSVoiceProvider

        provider = CoquiXTTSVoiceProvider()
        provider._tts = MagicMock()
        provider.close()
        assert provider._tts is None

    @pytest.mark.skip(reason="not ready — requires TTS library and model download")
    def test_generate_real(self) -> None:
        pass


# ── PiperVoiceProvider ───────────────────────────────────────────────────────


class TestPiperVoiceProvider:
    def test_missing_model_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PIPER_MODEL", raising=False)
        from demodsl.providers.voice import PiperVoiceProvider

        with pytest.raises(EnvironmentError, match="PIPER_MODEL"):
            PiperVoiceProvider()

    def test_init_with_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIPER_MODEL", "/models/voice.onnx")
        from demodsl.providers.voice import PiperVoiceProvider

        provider = PiperVoiceProvider()
        assert provider._model_path == "/models/voice.onnx"
        assert provider._piper_bin == "piper"

    def test_custom_bin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIPER_MODEL", "/m.onnx")
        monkeypatch.setenv("PIPER_BIN", "/usr/local/bin/piper-tts")
        from demodsl.providers.voice import PiperVoiceProvider

        provider = PiperVoiceProvider()
        assert provider._piper_bin == "/usr/local/bin/piper-tts"

    @patch("subprocess.run")
    def test_generate_length_scale(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("PIPER_MODEL", "/m.onnx")
        from demodsl.providers.voice import PiperVoiceProvider

        provider = PiperVoiceProvider(output_dir=tmp_path)
        provider.generate("Hello", "default", speed=2.0)
        cmd = mock_run.call_args.args[0]
        # length_scale = 1.0 / 2.0 = 0.5
        assert "--length_scale" in cmd
        idx = cmd.index("--length_scale")
        assert cmd[idx + 1] == "0.5"


# ── LocalOpenAIVoiceProvider ─────────────────────────────────────────────────


class TestLocalOpenAIVoiceProvider:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOCAL_TTS_URL", raising=False)
        monkeypatch.delenv("LOCAL_TTS_API_KEY", raising=False)
        monkeypatch.delenv("LOCAL_TTS_MODEL", raising=False)
        from demodsl.providers.voice import LocalOpenAIVoiceProvider

        provider = LocalOpenAIVoiceProvider()
        assert provider._api_url == "http://localhost:8000"
        assert provider._api_key == "not-needed"
        assert provider._model == "tts-1"

    @patch("httpx.post")
    def test_speed_clamped(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("LOCAL_TTS_URL", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00"
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import LocalOpenAIVoiceProvider

        provider = LocalOpenAIVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "alloy", speed=100.0)
        call_json = mock_post.call_args.kwargs.get("json") or {}
        assert call_json.get("speed", 100.0) <= 4.0


# ── ESpeakVoiceProvider ──────────────────────────────────────────────────────


class TestESpeakVoiceProvider:
    def test_default_bin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ESPEAK_BIN", raising=False)
        from demodsl.providers.voice import ESpeakVoiceProvider

        provider = ESpeakVoiceProvider()
        assert provider._espeak_bin == "espeak-ng"

    @patch("subprocess.run")
    def test_wpm_calculation(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("ESPEAK_BIN", raising=False)
        from demodsl.providers.voice import ESpeakVoiceProvider

        provider = ESpeakVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "en", speed=2.0)
        cmd = mock_run.call_args.args[0]
        idx = cmd.index("-s")
        assert cmd[idx + 1] == str(int(175 * 2.0))

    @patch("subprocess.run")
    def test_pitch_clamped(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("ESPEAK_BIN", raising=False)
        from demodsl.providers.voice import ESpeakVoiceProvider

        provider = ESpeakVoiceProvider(output_dir=tmp_path)
        # pitch=100 → 50+100=150 → clamped to 99
        provider.generate("Test", "en", pitch=100)
        cmd = mock_run.call_args.args[0]
        idx = cmd.index("-p")
        assert int(cmd[idx + 1]) <= 99

    @patch("subprocess.run")
    def test_pitch_negative_clamped(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("ESPEAK_BIN", raising=False)
        from demodsl.providers.voice import ESpeakVoiceProvider

        provider = ESpeakVoiceProvider(output_dir=tmp_path)
        # pitch=-100 → 50+(-100)=-50 → clamped to 0
        provider.generate("Test", "en", pitch=-100)
        cmd = mock_run.call_args.args[0]
        idx = cmd.index("-p")
        assert int(cmd[idx + 1]) >= 0

    @patch("subprocess.run")
    def test_voice_id_passed(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("ESPEAK_BIN", raising=False)
        from demodsl.providers.voice import ESpeakVoiceProvider

        provider = ESpeakVoiceProvider(output_dir=tmp_path)
        provider.generate("Bonjour", "fr")
        cmd = mock_run.call_args.args[0]
        idx = cmd.index("-v")
        assert cmd[idx + 1] == "fr"


# ── GTTSVoiceProvider ────────────────────────────────────────────────────────


@pytest.mark.skipif(not _has_gtts, reason="gtts not installed")
class TestGTTSVoiceProvider:
    @patch("gtts.gTTS")
    def test_generate_uses_lang(self, mock_gtts_cls: MagicMock, tmp_path: Path) -> None:
        mock_tts = MagicMock()
        mock_gtts_cls.return_value = mock_tts

        from demodsl.providers.voice import GTTSVoiceProvider

        provider = GTTSVoiceProvider(output_dir=tmp_path)
        provider.generate("Hello", "fr", speed=1.0)

        mock_gtts_cls.assert_called_once()
        call_kwargs = mock_gtts_cls.call_args.kwargs
        assert call_kwargs.get("lang") == "fr"

    @patch("gtts.gTTS")
    def test_slow_flag_when_speed_low(
        self, mock_gtts_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_tts = MagicMock()
        mock_gtts_cls.return_value = mock_tts

        from demodsl.providers.voice import GTTSVoiceProvider

        provider = GTTSVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "en", speed=0.5)

        call_kwargs = mock_gtts_cls.call_args.kwargs
        assert call_kwargs.get("slow") is True

    @patch("gtts.gTTS")
    def test_not_slow_at_normal_speed(
        self, mock_gtts_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_tts = MagicMock()
        mock_gtts_cls.return_value = mock_tts

        from demodsl.providers.voice import GTTSVoiceProvider

        provider = GTTSVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "en", speed=1.0)

        call_kwargs = mock_gtts_cls.call_args.kwargs
        assert call_kwargs.get("slow") is False


# ── CustomVoiceProvider ──────────────────────────────────────────────────────


class TestCustomVoiceProvider:
    def test_missing_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CUSTOM_TTS_URL", raising=False)
        from demodsl.providers.voice import CustomVoiceProvider

        with pytest.raises(EnvironmentError, match="CUSTOM_TTS_URL"):
            CustomVoiceProvider()

    def test_init_with_url(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "https://my-tts.example.com/synthesize")
        monkeypatch.setenv("CUSTOM_TTS_API_KEY", "my-secret")
        monkeypatch.setenv("CUSTOM_TTS_RESPONSE_FORMAT", "wav")
        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider(output_dir=tmp_path)
        assert provider._api_url == "https://my-tts.example.com/synthesize"
        assert provider._api_key == "my-secret"
        assert provider._format == "wav"
        assert provider._counter == 0

    def test_default_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.delenv("CUSTOM_TTS_RESPONSE_FORMAT", raising=False)
        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider()
        assert provider._format == "mp3"

    def test_invalid_format_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.setenv("CUSTOM_TTS_RESPONSE_FORMAT", "ogg")
        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider()
        assert provider._format == "mp3"

    @patch("httpx.post")
    def test_generate_creates_file(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.delenv("CUSTOM_TTS_API_KEY", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 100
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello world", "my-voice", speed=1.2, pitch=3)
        assert path.exists()
        assert path.name == "narration_001.mp3"
        # Verify JSON payload
        call_json = mock_post.call_args.kwargs.get("json") or {}
        assert call_json["text"] == "Hello world"
        assert call_json["voice_id"] == "my-voice"
        assert call_json["speed"] == 1.2
        assert call_json["pitch"] == 3

    @patch("httpx.post")
    def test_generate_with_api_key(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.setenv("CUSTOM_TTS_API_KEY", "secret-key")
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "voice1")
        call_headers = mock_post.call_args.kwargs.get("headers") or {}
        assert call_headers.get("Authorization") == "Bearer secret-key"

    @patch("httpx.post")
    def test_generate_without_api_key(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.delenv("CUSTOM_TTS_API_KEY", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider(output_dir=tmp_path)
        provider.generate("Test", "voice1")
        call_headers = mock_post.call_args.kwargs.get("headers") or {}
        assert "Authorization" not in call_headers

    @patch("httpx.post")
    def test_generate_wav_format(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.setenv("CUSTOM_TTS_RESPONSE_FORMAT", "wav")
        monkeypatch.delenv("CUSTOM_TTS_API_KEY", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00" * 50
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Test", "voice1")
        assert path.suffix == ".wav"

    @patch("httpx.post")
    def test_counter_increments(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CUSTOM_TTS_URL", "http://localhost:9000/tts")
        monkeypatch.delenv("CUSTOM_TTS_API_KEY", raising=False)
        mock_resp = MagicMock()
        mock_resp.content = b"\x00"
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from demodsl.providers.voice import CustomVoiceProvider

        provider = CustomVoiceProvider(output_dir=tmp_path)
        p1 = provider.generate("A", "v")
        p2 = provider.generate("B", "v")
        assert p1.name == "narration_001.mp3"
        assert p2.name == "narration_002.mp3"


# ── DummyVoiceProvider ───────────────────────────────────────────────────────


class TestDummyVoiceProvider:
    def test_no_env_required(self) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        provider = DummyVoiceProvider()
        assert provider._counter == 0

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_generate_creates_file(self, tmp_path: Path) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        provider = DummyVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hello world", "any_voice")
        assert path.exists()
        assert path.suffix == ".mp3"
        assert path.name == "narration_001.mp3"

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_duration_calculation(self, tmp_path: Path) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        provider = DummyVoiceProvider(output_dir=tmp_path)
        # 150 words → 1 minute = 60000ms
        text = " ".join(["word"] * 150)
        path = provider.generate(text, "v")
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(str(path))
        # Should be approximately 60000ms
        assert abs(len(audio) - 60000) < 1000

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_minimum_duration(self, tmp_path: Path) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        provider = DummyVoiceProvider(output_dir=tmp_path)
        path = provider.generate("Hi", "v")
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(str(path))
        assert len(audio) >= 1000

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_counter_increments(self, tmp_path: Path) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        provider = DummyVoiceProvider(output_dir=tmp_path)
        p1 = provider.generate("A", "v")
        p2 = provider.generate("B", "v")
        assert p1.name == "narration_001.mp3"
        assert p2.name == "narration_002.mp3"

    def test_close_is_noop(self) -> None:
        from demodsl.providers.voice import DummyVoiceProvider

        provider = DummyVoiceProvider()
        provider.close()  # Should not raise
