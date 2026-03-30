"""RunCache — persistent cache for pipeline artefacts across runs.

Allows skipping expensive steps (browser recording, pipeline stages)
when only the voice or edit config has changed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "demodsl" / "runs"


class RunCache:
    """Content-addressable cache for full pipeline run artefacts.

    Each config file gets its own cache directory keyed by its absolute path.
    A JSON manifest tracks fingerprints + artefact paths so that subsequent
    runs can skip unchanged stages.
    """

    def __init__(
        self,
        config_path: Path,
        *,
        enabled: bool = True,
        cache_dir: Path | None = None,
    ) -> None:
        self._enabled = enabled
        self._config_path = config_path.resolve()

        # Stable directory name derived from the config file path
        config_key = hashlib.sha256(str(self._config_path).encode()).hexdigest()[:16]
        root = cache_dir or _DEFAULT_CACHE_ROOT
        self._dir = root / config_key

        self._manifest: dict[str, Any] = {}

        if self._enabled:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._load_manifest()

    # ── Fingerprinting ────────────────────────────────────────────────────

    @staticmethod
    def fingerprint(data: Any) -> str:
        """Compute a deterministic SHA-256 of arbitrary JSON-serialisable *data*."""
        blob = json.dumps(data, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    @staticmethod
    def fingerprint_config_sections(config: Any) -> dict[str, str]:
        """Return per-section fingerprints for a ``DemoConfig`` instance.

        Sections tracked:
        - scenarios — steps, URLs, selectors, effects, viewport
        - voice — TTS engine / voice_id / speed / pitch / reference_audio
        - pipeline — ordered list of stage definitions
        - subtitle — subtitle config
        - audio — background music, audio effects
        - edit — pause/edit config
        """
        fps: dict[str, str] = {}
        model = config.model_dump(exclude_none=True)

        # Scenarios: everything that affects the browser recording
        scenarios_data = model.get("scenarios", [])
        fps["scenarios"] = RunCache.fingerprint(scenarios_data)

        # Voice config (affects TTS generation)
        fps["voice"] = RunCache.fingerprint(model.get("voice"))

        # Pipeline stages config
        fps["pipeline"] = RunCache.fingerprint(model.get("pipeline", []))

        # Subtitle config
        fps["subtitle"] = RunCache.fingerprint(model.get("subtitle"))

        # Audio config (background music, processing)
        fps["audio"] = RunCache.fingerprint(model.get("audio"))

        # Edit config (pauses, offsets)
        fps["edit"] = RunCache.fingerprint(model.get("edit"))

        return fps

    # ── Manifest I/O ──────────────────────────────────────────────────────

    @property
    def manifest_path(self) -> Path:
        return self._dir / "manifest.json"

    @property
    def cache_dir(self) -> Path:
        return self._dir

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def manifest(self) -> dict[str, Any]:
        return self._manifest

    def _load_manifest(self) -> None:
        if self.manifest_path.exists():
            try:
                self._manifest = json.loads(self.manifest_path.read_text("utf-8"))
                logger.debug("Loaded run-cache manifest: %s", self.manifest_path)
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt manifest, starting fresh")
                self._manifest = {}

    def save_manifest(self) -> None:
        if not self._enabled:
            return
        self.manifest_path.write_text(
            json.dumps(self._manifest, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        logger.debug("Saved run-cache manifest")

    def update_manifest(
        self,
        fingerprints: dict[str, str],
        artifacts: dict[str, Any],
    ) -> None:
        """Merge new fingerprints and artefact info, then persist."""
        self._manifest["config_path"] = str(self._config_path)
        self._manifest["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._manifest.setdefault("fingerprints", {}).update(fingerprints)
        self._manifest.setdefault("artifacts", {}).update(artifacts)
        self.save_manifest()

    # ── Cache queries ─────────────────────────────────────────────────────

    def section_unchanged(self, section: str, current_fp: str) -> bool:
        """Return ``True`` if *section* fingerprint matches the cached value."""
        if not self._enabled:
            return False
        cached = self._manifest.get("fingerprints", {}).get(section)
        return cached == current_fp

    def get_artifact(self, key: str) -> Any | None:
        """Return a cached artefact value (path, list, dict, etc.)."""
        if not self._enabled:
            return None
        return self._manifest.get("artifacts", {}).get(key)

    def has_cached_files(self, *rel_paths: str) -> bool:
        """Check whether all listed paths exist under the cache directory."""
        return all((self._dir / p).exists() for p in rel_paths)

    # ── Artefact storage ──────────────────────────────────────────────────

    def store_file(self, src: Path, rel_dest: str) -> Path:
        """Copy *src* into the cache at *rel_dest*.  Returns the cache path."""
        dest = self._dir / rel_dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        logger.debug("Cache store: %s → %s", src.name, rel_dest)
        return dest

    def restore_file(self, rel_src: str, dest: Path) -> Path | None:
        """Copy a cached file to *dest*.  Returns *dest* or ``None``."""
        src = self._dir / rel_src
        if not src.exists():
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        logger.debug("Cache restore: %s → %s", rel_src, dest)
        return dest

    # ── Maintenance ───────────────────────────────────────────────────────

    def clear(self) -> int:
        """Remove all cached artefacts for this config.  Returns files removed."""
        if not self._dir.exists():
            return 0
        count = sum(1 for f in self._dir.rglob("*") if f.is_file())
        shutil.rmtree(self._dir)
        self._manifest = {}
        return count

    @staticmethod
    def clear_all(cache_dir: Path | None = None) -> int:
        """Remove the entire run-cache tree.  Returns files removed."""
        root = cache_dir or _DEFAULT_CACHE_ROOT
        if not root.exists():
            return 0
        count = sum(1 for f in root.rglob("*") if f.is_file())
        shutil.rmtree(root)
        return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics for this config."""
        if not self._dir.exists():
            return {"exists": False, "files": 0, "size_bytes": 0}
        files = list(self._dir.rglob("*"))
        total = sum(f.stat().st_size for f in files if f.is_file())
        return {
            "exists": True,
            "files": sum(1 for f in files if f.is_file()),
            "size_bytes": total,
            "size_mb": round(total / (1024 * 1024), 1),
            "path": str(self._dir),
        }

    @staticmethod
    def global_stats(cache_dir: Path | None = None) -> dict[str, Any]:
        """Return aggregate stats across all cached configs."""
        root = cache_dir or _DEFAULT_CACHE_ROOT
        if not root.exists():
            return {"configs": 0, "files": 0, "size_bytes": 0}
        configs = [d for d in root.iterdir() if d.is_dir()]
        all_files = list(root.rglob("*"))
        total = sum(f.stat().st_size for f in all_files if f.is_file())
        return {
            "configs": len(configs),
            "files": sum(1 for f in all_files if f.is_file()),
            "size_bytes": total,
            "size_mb": round(total / (1024 * 1024), 1),
            "path": str(root),
        }
