"""Voice providers — ElevenLabs, Google Cloud TTS, Azure, AWS Polly + Dummy."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from demodsl.providers.base import (
    VoiceProvider,
    VoiceProviderFactory,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


class ElevenLabsVoiceProvider(VoiceProvider):
    """TTS via the ElevenLabs REST API."""

    API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not self._api_key:
            raise OSError("ELEVENLABS_API_KEY not set. Use DummyVoiceProvider or set the env var.")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def _ensure_cloned_voice(self, reference_audio: Path) -> str:
        """Clone a voice from a reference audio file via ElevenLabs Instant Voice Cloning.

        Returns the cloned voice_id. Caches the result to avoid re-uploading.
        """
        import httpx

        if hasattr(self, "_cloned_voice_id") and self._cloned_voice_id:
            return self._cloned_voice_id

        headers = {"xi-api-key": self._api_key}
        files = {"files": (reference_audio.name, reference_audio.read_bytes(), "audio/mpeg")}
        data = {"name": f"demodsl_clone_{reference_audio.stem}"}

        resp = httpx.post(
            "https://api.elevenlabs.io/v1/voices/add",
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )
        resp.raise_for_status()
        self._cloned_voice_id: str = resp.json()["voice_id"]
        logger.info("Cloned voice from %s → voice_id=%s", reference_audio, self._cloned_voice_id)
        return self._cloned_voice_id

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        import httpx

        # If reference_audio is provided, clone the voice and override voice_id
        effective_voice_id = voice_id
        if reference_audio and reference_audio.is_file():
            effective_voice_id = self._ensure_cloned_voice(reference_audio)

        url = f"{self.API_BASE}/{effective_voice_id}"
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

    def cache_extra(self) -> dict[str, str]:
        return {"model_id": "eleven_monolingual_v1"}

    def close(self) -> None:
        pass


class GoogleTTSVoiceProvider(VoiceProvider):
    """TTS via Google Cloud Text-to-Speech API."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not self._credentials:
            raise OSError(
                "GOOGLE_APPLICATION_CREDENTIALS not set. "
                "Point it to your service account JSON file."
            )
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning(
                "Google Cloud TTS does not support voice cloning — reference_audio ignored."
            )
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_id.split("-")[0] + "-" + voice_id.split("-")[1]
            if "-" in voice_id
            else "en-US",
            name=voice_id if "-" in voice_id else "en-US-Wavenet-D",
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
        logger.info(
            "Generated narration (Google TTS): %s (%d bytes)",
            out_path,
            len(response.audio_content),
        )
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
            raise OSError("AZURE_SPEECH_KEY not set. Set it along with AZURE_SPEECH_REGION.")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning("Azure TTS does not support voice cloning — reference_audio ignored.")
        import httpx

        url = self.API_BASE.format(region=self._region)
        voice_name = voice_id if "Neural" in voice_id else "en-US-JennyNeural"
        rate = f"{int((speed - 1) * 100):+d}%"
        pitch_str = f"{pitch:+d}Hz"

        ssml = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'<voice name="{voice_name}">'
            f'<prosody rate="{rate}" pitch="{pitch_str}">'
            f"{xml_escape(text)}"
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
        logger.info(
            "Generated narration (Azure TTS): %s (%d bytes)",
            out_path,
            len(resp.content),
        )
        return out_path

    def cache_extra(self) -> dict[str, str]:
        return {"region": self._region}

    def close(self) -> None:
        pass


class AWSPollyVoiceProvider(VoiceProvider):
    """TTS via Amazon Polly."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self._secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self._region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        if not self._access_key or not self._secret_key:
            raise OSError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set for Polly.")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning("AWS Polly does not support voice cloning — reference_audio ignored.")
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
        ssml_text = f'<speak><prosody rate="{rate}">{xml_escape(text)}</prosody></speak>'

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

    def cache_extra(self) -> dict[str, str]:
        return {"region": self._region}

    def close(self) -> None:
        pass


class OpenAITTSVoiceProvider(VoiceProvider):
    """TTS via OpenAI Audio API (tts-1 / tts-1-hd)."""

    API_BASE = "https://api.openai.com/v1/audio/speech"

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            raise OSError("OPENAI_API_KEY not set.")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning("OpenAI TTS does not support voice cloning — reference_audio ignored.")
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
        logger.info(
            "Generated narration (OpenAI TTS): %s (%d bytes)",
            out_path,
            len(resp.content),
        )
        return out_path

    def close(self) -> None:
        pass


class DummyVoiceProvider(VoiceProvider):
    """Generates silent MP3 files for development without an API key."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
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


# ── Local providers ──────────────────────────────────────────────────────────


class CosyVoiceProvider(VoiceProvider):
    """TTS via CosyVoice (Alibaba/Qwen ecosystem) served locally or remotely.

    Expects a CosyVoice-compatible HTTP API (e.g. CosyVoice WebUI or a
    FastAPI wrapper). Set COSYVOICE_API_URL to the endpoint base URL.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_url = os.environ.get("COSYVOICE_API_URL", "http://localhost:50000")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def cache_extra(self) -> dict[str, str]:
        return {"api_url": self._api_url}

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        import httpx

        payload: dict = {
            "text": text,
            "speaker": voice_id,
            "speed": speed,
        }

        # CosyVoice supports zero-shot voice cloning with a reference audio
        if reference_audio and reference_audio.is_file():
            import base64

            audio_bytes = reference_audio.read_bytes()
            payload["reference_audio"] = base64.b64encode(audio_bytes).decode()
            payload["mode"] = "zero_shot"
            logger.info(
                "CosyVoice: using reference audio %s for zero-shot cloning",
                reference_audio,
            )

        resp = httpx.post(
            f"{self._api_url}/api/tts",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.wav"
        out_path.write_bytes(resp.content)
        logger.info(
            "Generated narration (CosyVoice): %s (%d bytes)",
            out_path,
            len(resp.content),
        )
        return out_path

    def close(self) -> None:
        pass


class CoquiXTTSVoiceProvider(VoiceProvider):
    """TTS via Coqui XTTS v2, running locally via the TTS Python library."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0
        self._tts = None

    def _ensure_model(self) -> None:
        if self._tts is not None:
            return
        from TTS.api import TTS

        model_name = os.environ.get("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
        self._tts = TTS(model_name)
        logger.info("Loaded Coqui model: %s", model_name)

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        self._ensure_model()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.wav"

        # reference_audio takes priority for voice cloning,
        # otherwise voice_id is used as speaker wav path or speaker name
        speaker_wav: str | None = None
        speaker: str | None = None
        if reference_audio and reference_audio.is_file():
            speaker_wav = str(reference_audio)
            logger.info("Coqui XTTS: cloning voice from %s", reference_audio)
        elif Path(voice_id).is_file():
            speaker_wav = voice_id
        else:
            speaker = voice_id

        language = os.environ.get("COQUI_LANGUAGE", "en")

        kwargs: dict = {"text": text, "file_path": str(out_path), "language": language}
        if speaker_wav:
            kwargs["speaker_wav"] = speaker_wav
        elif speaker:
            kwargs["speaker"] = speaker

        self._tts.tts_to_file(**kwargs)  # type: ignore[union-attr]
        logger.info("Generated narration (Coqui XTTS): %s", out_path)
        return out_path

    def cache_extra(self) -> dict[str, str]:
        model = os.environ.get("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
        language = os.environ.get("COQUI_LANGUAGE", "en")
        return {"model": model, "language": language}

    def close(self) -> None:
        self._tts = None


class PiperVoiceProvider(VoiceProvider):
    """TTS via Piper — fast, lightweight local TTS via subprocess."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0
        self._piper_bin = os.environ.get("PIPER_BIN", "piper")
        self._model_path = os.environ.get("PIPER_MODEL", "")
        if not self._model_path:
            raise OSError("PIPER_MODEL must be set to the path of the .onnx voice model.")

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning("Piper does not support voice cloning — reference_audio ignored.")
        import subprocess

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.wav"

        # voice_id can override model path if it's a file
        model = voice_id if Path(voice_id).suffix == ".onnx" else self._model_path
        length_scale = 1.0 / speed if speed > 0 else 1.0

        cmd = [
            self._piper_bin,
            "--model",
            model,
            "--output_file",
            str(out_path),
            "--length_scale",
            str(length_scale),
        ]
        subprocess.run(
            cmd,
            input=text.encode(),
            check=True,
            capture_output=True,
        )
        logger.info("Generated narration (Piper): %s", out_path)
        return out_path

    def cache_extra(self) -> dict[str, str]:
        return {"model": self._model_path}

    def close(self) -> None:
        pass


class LocalOpenAIVoiceProvider(VoiceProvider):
    """TTS via an OpenAI-compatible local API (vLLM, LocalAI, AllTalk, etc.).

    Uses the same /v1/audio/speech endpoint format as OpenAI but against
    a local server. Set LOCAL_TTS_URL to point to your server.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_url = os.environ.get("LOCAL_TTS_URL", "http://localhost:8000")
        self._api_key = os.environ.get("LOCAL_TTS_API_KEY", "not-needed")
        self._model = os.environ.get("LOCAL_TTS_MODEL", "tts-1")
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def cache_extra(self) -> dict[str, str]:
        return {"api_url": self._api_url, "model": self._model}

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning(
                "LocalOpenAI provider does not support voice cloning — reference_audio ignored."
            )
        import httpx

        payload = {
            "model": self._model,
            "input": text,
            "voice": voice_id,
            "speed": max(0.25, min(4.0, speed)),
            "response_format": "mp3",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = httpx.post(
            f"{self._api_url}/v1/audio/speech",
            json=payload,
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"
        out_path.write_bytes(resp.content)
        logger.info(
            "Generated narration (Local OpenAI-compat): %s (%d bytes)",
            out_path,
            len(resp.content),
        )
        return out_path

    def close(self) -> None:
        pass


# ── Vintage / debug providers ────────────────────────────────────────────────


class ESpeakVoiceProvider(VoiceProvider):
    """TTS via eSpeak-NG — robotic vintage voice, zero dependencies beyond espeak.

    Great for debug runs and retro aesthetics. Supports pitch and speed.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0
        self._espeak_bin = os.environ.get("ESPEAK_BIN", "espeak-ng")

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning("eSpeak does not support voice cloning — reference_audio ignored.")
        import subprocess

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.wav"

        wpm = int(175 * speed)
        pitch_val = max(0, min(99, 50 + pitch))

        cmd = [
            self._espeak_bin,
            "-v",
            voice_id,
            "-s",
            str(wpm),
            "-p",
            str(pitch_val),
            "-w",
            str(out_path),
            "--",
            text,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Generated narration (eSpeak): %s", out_path)
        return out_path

    def cache_extra(self) -> dict[str, str]:
        return {"espeak_bin": self._espeak_bin}

    def close(self) -> None:
        pass


class GTTSVoiceProvider(VoiceProvider):
    """TTS via Google Translate TTS (gTTS) — free, no API key needed.

    Produces natural-ish speech with a slight robotic quality.
    Useful for quick prototyping and debug without any credentials.
    voice_id is used as the language code (e.g. "en", "fr", "de").
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        if reference_audio:
            logger.warning("gTTS does not support voice cloning — reference_audio ignored.")
        from gtts import gTTS

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.mp3"

        tts = gTTS(text=text, lang=voice_id, slow=(speed < 0.7))
        tts.save(str(out_path))

        # Apply speed adjustment via pydub if not default
        if speed != 1.0 and speed >= 0.7:
            from pydub import AudioSegment

            audio = AudioSegment.from_mp3(str(out_path))
            # speed_change via frame_rate manipulation
            adjusted = audio._spawn(
                audio.raw_data,
                overrides={"frame_rate": int(audio.frame_rate * speed)},
            ).set_frame_rate(audio.frame_rate)
            adjusted.export(str(out_path), format="mp3")

        logger.info("Generated narration (gTTS): %s", out_path)
        return out_path

    def close(self) -> None:
        pass


class CustomVoiceProvider(VoiceProvider):
    """TTS via a user-defined HTTP endpoint.

    Configure with environment variables:
    - CUSTOM_TTS_URL: Full endpoint URL (required).
    - CUSTOM_TTS_API_KEY: Bearer token sent in Authorization header (optional).
    - CUSTOM_TTS_RESPONSE_FORMAT: Expected audio format, "mp3" or "wav" (default: "mp3").

    The provider POSTs a JSON body with keys: text, voice_id, speed, pitch.
    The response body must be raw audio bytes in the configured format.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._api_url = os.environ.get("CUSTOM_TTS_URL", "")
        if not self._api_url:
            raise OSError("CUSTOM_TTS_URL must be set to the TTS endpoint URL.")
        self._api_key = os.environ.get("CUSTOM_TTS_API_KEY", "")
        self._format = os.environ.get("CUSTOM_TTS_RESPONSE_FORMAT", "mp3")
        if self._format not in ("mp3", "wav"):
            self._format = "mp3"
        self._output_dir = output_dir or Path(".")
        self._counter = 0

    def cache_extra(self) -> dict[str, str]:
        return {"api_url": self._api_url, "format": self._format}

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        import httpx

        payload: dict = {
            "text": text,
            "voice_id": voice_id,
            "speed": speed,
            "pitch": pitch,
        }

        # Pass reference audio to the custom endpoint if provided
        if reference_audio and reference_audio.is_file():
            import base64

            payload["reference_audio"] = base64.b64encode(reference_audio.read_bytes()).decode()
            logger.info(
                "Custom TTS: sending reference_audio %s for voice cloning",
                reference_audio,
            )

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        resp = httpx.post(self._api_url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()

        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.{self._format}"
        out_path.write_bytes(resp.content)
        logger.info(
            "Generated narration (Custom TTS): %s (%d bytes)",
            out_path,
            len(resp.content),
        )
        return out_path

    def close(self) -> None:
        pass


class VoxtralVoiceProvider(VoiceProvider):
    """TTS via Mistral Voxtral (mlx-audio local model).

    voice_id maps to speaker preset (e.g. "casual_male", "formal_female").
    Runs locally on Apple Silicon via MLX.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._counter = 0
        self._model = None

    def _load_model(self):
        if self._model is None:
            from mlx_audio.tts.utils import load_model

            self._model = load_model("mlx-community/Voxtral-4B-TTS-2603-mlx-4bit")
        return self._model

    def generate(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        reference_audio: Path | None = None,
    ) -> Path:
        import soundfile as sf

        model = self._load_model()
        self._counter += 1
        out_path = self._output_dir / f"narration_{self._counter:03d}.wav"

        result = None
        for chunk in model.generate(text=text, speaker=voice_id, speed=speed):
            result = chunk

        if result is not None:
            sf.write(str(out_path), result.audio, result.sample_rate)

        logger.info("Generated narration (voxtral): %s", out_path)
        return out_path

    def cache_extra(self) -> dict:
        return {"engine": "voxtral"}

    def close(self) -> None:
        self._model = None


# Register with factory
VoiceProviderFactory.register("elevenlabs", ElevenLabsVoiceProvider)
VoiceProviderFactory.register("google", GoogleTTSVoiceProvider)
VoiceProviderFactory.register("azure", AzureTTSVoiceProvider)
VoiceProviderFactory.register("aws_polly", AWSPollyVoiceProvider)
VoiceProviderFactory.register("openai", OpenAITTSVoiceProvider)
VoiceProviderFactory.register("cosyvoice", CosyVoiceProvider)
VoiceProviderFactory.register("coqui", CoquiXTTSVoiceProvider)
VoiceProviderFactory.register("piper", PiperVoiceProvider)
VoiceProviderFactory.register("local_openai", LocalOpenAIVoiceProvider)
VoiceProviderFactory.register("espeak", ESpeakVoiceProvider)
VoiceProviderFactory.register("gtts", GTTSVoiceProvider)
VoiceProviderFactory.register("voxtral", VoxtralVoiceProvider)
VoiceProviderFactory.register("custom", CustomVoiceProvider)
VoiceProviderFactory.register("dummy", DummyVoiceProvider)
