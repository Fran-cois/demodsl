"""Voice providers — ElevenLabs, Google Cloud TTS, Azure, AWS Polly + Dummy."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from demodsl.providers.base import VoiceProvider, VoiceProviderFactory

logger = logging.getLogger(__name__)


class ElevenLabsVoiceProvider(VoiceProvider):
    """TTS via the ElevenLabs REST API."""

    API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not self._api_key:
            raise EnvironmentError(
                "ELEVENLABS_API_KEY not set. Use DummyVoiceProvider or set the env var."
            )
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        import httpx

        url = f"{self.API_BASE}/{voice_id}"
        headers = {"xi-api-key": self._api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = httpx.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        out_path.write_bytes(resp.content)
        logger.info("Generated narration: %s (%d bytes)", out_path, len(resp.content))
        return out_path

    def close(self) -> None:
        pass


class GoogleTTSVoiceProvider(VoiceProvider):
    """TTS via Google Cloud Text-to-Speech API."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not self._credentials:
            raise EnvironmentError(
                "GOOGLE_APPLICATION_CREDENTIALS not set. "
                "Point it to your service account JSON file."
            )
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_id.split("-")[0] + "-" + voice_id.split("-")[1]
            if "-" in voice_id
            else "en-US",
            name=voice_id if "-" in voice_id else f"en-US-Wavenet-D",
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
            pitch=float(pitch),
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        out_path.write_bytes(response.audio_content)
        logger.info("Generated narration (Google TTS): %s (%d bytes)", out_path, len(response.audio_content))
        return out_path

    def close(self) -> None:
        pass


class AzureTTSVoiceProvider(VoiceProvider):
    """TTS via Azure Cognitive Services Speech."""

    API_BASE = "https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_key = os.environ.get("AZURE_SPEECH_KEY", "")
        self._region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
        if not self._api_key:
            raise EnvironmentError(
                "AZURE_SPEECH_KEY not set. Set it along with AZURE_SPEECH_REGION."
            )
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        import httpx

        url = self.API_BASE.format(region=self._region)
        voice_name = voice_id if "Neural" in voice_id else f"en-US-JennyNeural"
        rate = f"{int((speed - 1) * 100):+d}%"
        pitch_str = f"{pitch:+d}Hz"

        ssml = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'<voice name="{voice_name}">'
            f'<prosody rate="{rate}" pitch="{pitch_str}">'
            f"{text}"
            "</prosody></voice></speak>"
        )

        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        }
        resp = httpx.post(url, content=ssml, headers=headers, timeout=60)
        resp.raise_for_status()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        out_path.write_bytes(resp.content)
        logger.info("Generated narration (Azure TTS): %s (%d bytes)", out_path, len(resp.content))
        return out_path

    def close(self) -> None:
        pass


class AWSPollyVoiceProvider(VoiceProvider):
    """TTS via Amazon Polly."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self._secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self._region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        if not self._access_key or not self._secret_key:
            raise EnvironmentError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set for Polly."
            )
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        import boto3

        client = boto3.client(
            "polly",
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
        )

        polly_voice = voice_id if voice_id[0].isupper() else "Matthew"
        engine = "neural"

        # Wrap in SSML for speed control
        rate = f"{int(speed * 100)}%"
        ssml_text = f'<speak><prosody rate="{rate}">{text}</prosody></speak>'

        response = client.synthesize_speech(
            Text=ssml_text,
            TextType="ssml",
            OutputFormat="mp3",
            VoiceId=polly_voice,
            Engine=engine,
        )

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        with open(out_path, "wb") as f:
            f.write(response["AudioStream"].read())

        logger.info("Generated narration (AWS Polly): %s", out_path)
        return out_path

    def close(self) -> None:
        pass


class OpenAITTSVoiceProvider(VoiceProvider):
    """TTS via OpenAI Audio API (tts-1 / tts-1-hd)."""

    API_BASE = "https://api.openai.com/v1/audio/speech"

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            raise EnvironmentError("OPENAI_API_KEY not set.")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        import httpx

        valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
        voice = voice_id if voice_id in valid_voices else "alloy"

        payload = {
            "model": "tts-1-hd",
            "input": text,
            "voice": voice,
            "speed": max(0.25, min(4.0, speed)),
            "response_format": "mp3",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = httpx.post(self.API_BASE, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        out_path.write_bytes(resp.content)
        logger.info("Generated narration (OpenAI TTS): %s (%d bytes)", out_path, len(resp.content))
        return out_path

    def close(self) -> None:
        pass


class DummyVoiceProvider(VoiceProvider):
    """Generates silent MP3 files for development without an API key."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(self, text: str, voice_id: str, speed: float = 1.0, pitch: int = 0) -> Path:
        from pydub import AudioSegment

        # Estimate duration: ~150 words per minute
        word_count = len(text.split())
        duration_ms = max(1000, int(word_count / 150 * 60 * 1000))

        silence = AudioSegment.silent(duration=duration_ms)
        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        silence.export(str(out_path), format="mp3")
        logger.info("Generated silent narration: %s (%dms)", out_path, duration_ms)
        return out_path

    def close(self) -> None:
        pass


# Register with factory
VoiceProviderFactory.register("elevenlabs", ElevenLabsVoiceProvider)
VoiceProviderFactory.register("google", GoogleTTSVoiceProvider)
VoiceProviderFactory.register("azure", AzureTTSVoiceProvider)
VoiceProviderFactory.register("aws_polly", AWSPollyVoiceProvider)
VoiceProviderFactory.register("openai", OpenAITTSVoiceProvider)
VoiceProviderFactory.register("dummy", DummyVoiceProvider)
