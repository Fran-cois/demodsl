"""Voice providers — ElevenLabs + Dummy for dev without API key."""

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
VoiceProviderFactory.register("dummy", DummyVoiceProvider)
