"""Tests for demodsl.stats."""

from __future__ import annotations

from pathlib import Path

from demodsl.stats import StatsStore


class TestStatsStore:
    def test_load_default_when_missing(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        data = store.load()
        assert data["totals"]["demos_created"] == 0
        assert data["totals"]["runs"] == 0
        assert data["totals"]["execution_minutes"] == 0.0

    def test_record_real_run_increments_demo_counter(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        store.record_run(
            project_title="Demo A",
            config_path=tmp_path / "demo.yaml",
            renderer="moviepy",
            output=tmp_path / "out.mp4",
            dry_run=False,
            duration_minutes=1.5,
        )
        summary = store.summary()
        assert summary["demos_created"] == 1
        assert summary["runs"] == 1
        assert summary["dry_runs"] == 0
        assert summary["execution_minutes"] == 1.5
        assert summary["renderers"]["moviepy"] == 1

    def test_record_dry_run(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        store.record_run(
            project_title="Demo Dry",
            config_path=tmp_path / "demo.yaml",
            renderer="remotion",
            output=None,
            dry_run=True,
            duration_minutes=0.3,
        )
        summary = store.summary()
        assert summary["demos_created"] == 0
        assert summary["runs"] == 1
        assert summary["dry_runs"] == 1
        assert summary["execution_minutes"] == 0.3
        assert summary["renderers"]["remotion"] == 1

    def test_promo_text_contains_key_numbers(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        store.record_run(
            project_title="Demo A",
            config_path=tmp_path / "a.yaml",
            renderer="moviepy",
            output=tmp_path / "a.mp4",
            dry_run=False,
            duration_minutes=2.5,
        )
        text = store.promo_text()
        assert "1 demos" in text
        assert "1 projet" in text
        assert "2.5 min" in text

    def test_promo_text_english(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        store.record_run(
            project_title="Demo A",
            config_path=tmp_path / "a.yaml",
            renderer="moviepy",
            output=tmp_path / "a.mp4",
            dry_run=False,
            duration_minutes=1.0,
        )
        text = store.promo_text("en")
        assert "I have created 1 product demos" in text
        assert "1.0 min" in text

    def test_promo_text_fallback_to_en(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        text = store.promo_text("xx")
        assert "I have created" in text

    def test_promo_texts_all_languages(self, tmp_path: Path) -> None:
        store = StatsStore(tmp_path / "stats.json")
        texts = store.promo_texts()
        assert set(texts) == set(StatsStore.SUPPORTED_PROMO_LANGS)
