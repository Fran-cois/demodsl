"""Speech-to-text auto-captioning — CapCut's Auto Caption / speech recognition,
adapted for a real recorded audio or video track.

This is the reverse of demodsl's own narration pipeline: narration is
synthesized FROM known text via TTS, so its timing is already exact. A real
voice-over or a screen+mic recording has no such text, so this module runs
speech-to-text (via ``faster-whisper``, fully offline once the model is
cached — no cloud API or account) to produce timed caption cues.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

INSTALL_HINT = "pip install 'demodsl[captions]'"


class MissingTranscriptionDependencyError(RuntimeError):
    """Raised when faster-whisper isn't installed."""

    def __init__(self) -> None:
        super().__init__(
            "Speech-to-text requires faster-whisper, which isn't installed. "
            f"Install it with: {INSTALL_HINT}"
        )


def is_available() -> bool:
    """Whether faster-whisper can be imported, without actually importing it."""
    return importlib.util.find_spec("faster_whisper") is not None


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Cue:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)


def transcribe(
    audio: Path,
    *,
    model_size: str = "base",
    language: str | None = None,
) -> list[Cue]:
    """Transcribe *audio* (or a video file's audio track) into timed cues."""
    if not is_available():
        raise MissingTranscriptionDependencyError()
    if not audio.exists():
        raise FileNotFoundError(f"Audio/video file not found: {audio}")

    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio), word_timestamps=True, language=language)

    cues: list[Cue] = []
    for segment in segments:
        words = [Word(text=w.word.strip(), start=w.start, end=w.end) for w in (segment.words or [])]
        cues.append(
            Cue(text=segment.text.strip(), start=segment.start, end=segment.end, words=words)
        )
    return cues


def _srt_timestamp(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_timestamp(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def cues_to_srt(cues: list[Cue]) -> str:
    lines: list[str] = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(cue.start)} --> {_srt_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines)


def cues_to_vtt(cues: list[Cue]) -> str:
    lines: list[str] = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{_vtt_timestamp(cue.start)} --> {_vtt_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines)
