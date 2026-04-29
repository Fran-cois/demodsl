"""Smart TTS cache — reuse previously generated audio clips."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".cache" / "demodsl" / "tts"


class TTSCache:
    """Content-addressable cache for TTS audio files.

    Cache key is a SHA-256 of (engine, text, voice_id, speed, pitch,
    reference_audio content hash).  Cached files live under
    ``~/.cache/demodsl/tts/<hash>.<ext>``.
    """

    def __init__(self, *, enabled: bool = True, cache_dir: Path | None = None) -> None:
        self._enabled = enabled
        self._dir = cache_dir or _CACHE_DIR
        if self._enabled:
            self._dir.mkdir(parents=True, exist_ok=True)

    # ── public API ────────────────────────────────────────────────────────

    def lookup(
        self,
        *,
        engine: str,
        text: str,
        voice_id: str,
        speed: float,
        pitch: int,
        reference_audio: Path | None,
        extra: dict[str, str] | None = None,
        dest_path: Path,
    ) -> Path | None:
        """Return *dest_path* if a cached clip exists, else ``None``.

        On hit the cached file is copied into *dest_path* so downstream
        code sees it exactly where it expects a freshly-generated clip.
        """
        if not self._enabled:
            return None

        key = self._cache_key(engine, text, voice_id, speed, pitch, reference_audio, extra)
        cached = self._find_cached(key)
        if cached is None:
            return None

        dest_path = dest_path.with_suffix(cached.suffix)
        shutil.copy2(cached, dest_path)
        logger.info("TTS cache hit: %s → %s", key[:12], dest_path.name)
        return dest_path

    def store(
        self,
        *,
        engine: str,
        text: str,
        voice_id: str,
        speed: float,
        pitch: int,
        reference_audio: Path | None,
        extra: dict[str, str] | None = None,
        generated_path: Path,
    ) -> None:
        """Copy a freshly-generated clip into the cache."""
        if not self._enabled:
            return
        if not generated_path.exists():
            return

        key = self._cache_key(engine, text, voice_id, speed, pitch, reference_audio, extra)
        ext = generated_path.suffix  # .mp3 or .wav
        cache_file = self._dir / f"{key}{ext}"
        if not cache_file.exists():
            shutil.copy2(generated_path, cache_file)
            logger.info("TTS cache store: %s → %s", generated_path.name, key[:12])

    def clear(self) -> int:
        """Remove all cached TTS files. Returns number of files removed."""
        if not self._dir.exists():
            return 0
        count = 0
        for f in self._dir.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        return count

    @property
    def cache_dir(self) -> Path:
        return self._dir

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(
        engine: str,
        text: str,
        voice_id: str,
        speed: float,
        pitch: int,
        reference_audio: Path | None,
        extra: dict[str, str] | None = None,
    ) -> str:
        """Compute a deterministic SHA-256 cache key."""
        parts: dict[str, str] = {
            "engine": engine,
            "text": text,
            "voice_id": voice_id,
            "speed": f"{speed:.4f}",
            "pitch": str(pitch),
        }
        if reference_audio and reference_audio.is_file():
            parts["ref_audio_hash"] = hashlib.sha256(reference_audio.read_bytes()).hexdigest()
        if extra:
            for k, v in sorted(extra.items()):
                parts[f"x_{k}"] = v

        blob = json.dumps(parts, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()

    def _find_cached(self, key: str) -> Path | None:
        """Find a cached file by key (any extension)."""
        for ext in (".mp3", ".wav"):
            candidate = self._dir / f"{key}{ext}"
            if candidate.exists():
                return candidate
        return None
