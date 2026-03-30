"""Tests for demodsl.pipeline.run_cache — RunCache."""

from __future__ import annotations

from pathlib import Path

import pytest

from demodsl.pipeline.run_cache import RunCache


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    f = tmp_path / "demo.yaml"
    f.write_text("metadata:\n  title: Test\n")
    return f


@pytest.fixture()
def cache(config_file: Path, cache_dir: Path) -> RunCache:
    return RunCache(config_file, cache_dir=cache_dir)


# ── Fingerprinting ────────────────────────────────────────────────────────────


class TestFingerprinting:
    def test_same_data_same_fingerprint(self) -> None:
        fp1 = RunCache.fingerprint({"engine": "elevenlabs", "voice_id": "josh"})
        fp2 = RunCache.fingerprint({"engine": "elevenlabs", "voice_id": "josh"})
        assert fp1 == fp2

    def test_different_data_different_fingerprint(self) -> None:
        fp1 = RunCache.fingerprint({"engine": "elevenlabs"})
        fp2 = RunCache.fingerprint({"engine": "openai"})
        assert fp1 != fp2

    def test_order_independent(self) -> None:
        fp1 = RunCache.fingerprint({"b": 2, "a": 1})
        fp2 = RunCache.fingerprint({"a": 1, "b": 2})
        assert fp1 == fp2

    def test_none_data(self) -> None:
        fp = RunCache.fingerprint(None)
        assert isinstance(fp, str) and len(fp) == 64

    def test_fingerprint_config_sections(self) -> None:
        from demodsl.models import DemoConfig

        cfg = DemoConfig(metadata={"title": "T"})  # type: ignore[arg-type]
        fps = RunCache.fingerprint_config_sections(cfg)
        assert "scenarios" in fps
        assert "voice" in fps
        assert "pipeline" in fps
        assert "subtitle" in fps
        assert "audio" in fps
        assert "edit" in fps


# ── Manifest ──────────────────────────────────────────────────────────────────


class TestManifest:
    def test_save_and_load(self, cache: RunCache) -> None:
        cache.update_manifest(
            {"voice": "abc123"},
            {"narration_map": {"0": "clips/n1.mp3"}},
        )
        # Reload
        loaded = RunCache(cache._config_path, cache_dir=cache._dir.parent)
        assert loaded.manifest["fingerprints"]["voice"] == "abc123"
        assert loaded.manifest["artifacts"]["narration_map"]["0"] == "clips/n1.mp3"

    def test_section_unchanged(self, cache: RunCache) -> None:
        cache.update_manifest({"voice": "aaa"}, {})
        assert cache.section_unchanged("voice", "aaa")
        assert not cache.section_unchanged("voice", "bbb")
        assert not cache.section_unchanged("scenarios", "xxx")

    def test_disabled_cache_always_returns_false(
        self, config_file: Path, cache_dir: Path
    ) -> None:
        c = RunCache(config_file, enabled=False, cache_dir=cache_dir)
        c._manifest = {"fingerprints": {"voice": "hello"}}
        assert not c.section_unchanged("voice", "hello")

    def test_get_artifact_missing(self, cache: RunCache) -> None:
        assert cache.get_artifact("non_existent") is None

    def test_update_merges(self, cache: RunCache) -> None:
        cache.update_manifest({"voice": "a"}, {"x": 1})
        cache.update_manifest({"scenarios": "b"}, {"y": 2})
        assert cache.manifest["fingerprints"]["voice"] == "a"
        assert cache.manifest["fingerprints"]["scenarios"] == "b"
        assert cache.manifest["artifacts"]["x"] == 1
        assert cache.manifest["artifacts"]["y"] == 2


# ── File storage ──────────────────────────────────────────────────────────────


class TestFileStorage:
    def test_store_and_restore(self, cache: RunCache, tmp_path: Path) -> None:
        src = tmp_path / "input.mp3"
        src.write_bytes(b"fake audio data")

        cache.store_file(src, "audio_clips/narration_001.mp3")

        dest = tmp_path / "restored.mp3"
        result = cache.restore_file("audio_clips/narration_001.mp3", dest)
        assert result == dest
        assert dest.read_bytes() == b"fake audio data"

    def test_restore_missing_returns_none(
        self, cache: RunCache, tmp_path: Path
    ) -> None:
        dest = tmp_path / "nothing.mp3"
        assert cache.restore_file("no/such/file.mp3", dest) is None

    def test_has_cached_files(self, cache: RunCache, tmp_path: Path) -> None:
        src = tmp_path / "vid.mp4"
        src.write_bytes(b"video data")
        cache.store_file(src, "raw_video/vid.mp4")
        assert cache.has_cached_files("raw_video/vid.mp4")
        assert not cache.has_cached_files("raw_video/other.mp4")


# ── Maintenance ───────────────────────────────────────────────────────────────


class TestMaintenance:
    def test_clear(self, cache: RunCache, tmp_path: Path) -> None:
        src = tmp_path / "f.mp3"
        src.write_bytes(b"data")
        cache.store_file(src, "clip.mp3")
        cache.update_manifest({"voice": "x"}, {})

        removed = cache.clear()
        assert removed >= 2  # manifest.json + clip.mp3
        assert cache.manifest == {}

    def test_clear_all(self, cache_dir: Path, config_file: Path) -> None:
        c1 = RunCache(config_file, cache_dir=cache_dir)
        c1.update_manifest({"v": "1"}, {})

        removed = RunCache.clear_all(cache_dir)
        assert removed >= 1
        assert not cache_dir.exists()

    def test_stats(self, cache: RunCache, tmp_path: Path) -> None:
        src = tmp_path / "data.bin"
        src.write_bytes(b"x" * 1024)
        cache.store_file(src, "data.bin")
        cache.update_manifest({}, {})

        info = cache.stats()
        assert info["exists"]
        assert info["files"] >= 2
        assert info["size_bytes"] >= 1024

    def test_global_stats_empty(self, tmp_path: Path) -> None:
        info = RunCache.global_stats(tmp_path / "empty")
        assert info["configs"] == 0

    def test_stats_nonexistent(self, config_file: Path, tmp_path: Path) -> None:
        c = RunCache(config_file, enabled=False, cache_dir=tmp_path / "nope")
        info = c.stats()
        assert not info["exists"]
