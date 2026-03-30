"""Tests for demodsl.orchestrators.narration — NarrationOrchestrator."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import DemoConfig
from demodsl.orchestrators.narration import NarrationOrchestrator
from demodsl.pipeline.workspace import Workspace

_has_ffmpeg = shutil.which("ffmpeg") is not None
try:
    from pydub import AudioSegment  # noqa: F401

    _has_pydub = True
except ImportError:
    _has_pydub = False


def _make_config(scenarios: list | None = None) -> DemoConfig:
    """Create a DemoConfig with optional scenarios."""
    data: dict = {"metadata": {"title": "Test"}}
    if scenarios:
        data["scenarios"] = scenarios
    return DemoConfig(**data)


def _make_config_with_narration() -> DemoConfig:
    return _make_config(
        scenarios=[
            {
                "name": "S1",
                "url": "https://example.com",
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Hello world",
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#btn"},
                    },
                    {
                        "action": "navigate",
                        "url": "https://example.com/2",
                        "narration": "Second step",
                    },
                ],
            }
        ]
    )


class TestNarrationOrchestratorInit:
    def test_default(self) -> None:
        config = _make_config()
        orch = NarrationOrchestrator(config)
        assert orch.skip_voice is False

    def test_skip_voice(self) -> None:
        config = _make_config()
        orch = NarrationOrchestrator(config, skip_voice=True)
        assert orch.skip_voice is True


class TestBuildNarrationTexts:
    def test_empty_scenarios(self) -> None:
        config = _make_config()
        orch = NarrationOrchestrator(config)
        assert orch.build_narration_texts() == {}

    def test_with_narrations(self) -> None:
        config = _make_config_with_narration()
        orch = NarrationOrchestrator(config)
        texts = orch.build_narration_texts()
        assert texts == {0: "Hello world", 2: "Second step"}

    def test_no_narrations(self) -> None:
        config = _make_config(
            scenarios=[
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                        }
                    ],
                }
            ]
        )
        orch = NarrationOrchestrator(config)
        assert orch.build_narration_texts() == {}


class TestDryRunNarrations:
    def test_returns_empty(self) -> None:
        config = _make_config_with_narration()
        orch = NarrationOrchestrator(config)
        result = orch._dry_run_narrations()
        assert result == {}


class TestGenerateNarrations:
    def test_dry_run_returns_empty(self) -> None:
        config = _make_config_with_narration()
        orch = NarrationOrchestrator(config)
        with Workspace() as ws:
            result = orch.generate_narrations(ws, dry_run=True)
        assert result == {}

    def test_skip_voice_returns_empty(self) -> None:
        config = _make_config_with_narration()
        orch = NarrationOrchestrator(config, skip_voice=True)
        with Workspace() as ws:
            result = orch.generate_narrations(ws)
        assert result == {}

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_generates_narrations(
        self, mock_factory: MagicMock, mock_time: MagicMock
    ) -> None:
        config = _make_config_with_narration()
        orch = NarrationOrchestrator(config)

        mock_voice = MagicMock()
        counter = [0]

        def fake_generate(**kwargs):
            counter[0] += 1
            p = Path(f"/tmp/narration_{counter[0]:03d}.mp3")
            return p

        mock_voice.generate.side_effect = fake_generate
        mock_factory.create.return_value = mock_voice

        with Workspace() as ws:
            result = orch.generate_narrations(ws)

        assert len(result) == 2
        assert 0 in result
        assert 2 in result
        assert mock_voice.close.called

    @patch("demodsl.orchestrators.narration.time")
    @patch("demodsl.orchestrators.narration.VoiceProviderFactory")
    def test_fallback_to_dummy_on_error(
        self, mock_factory: MagicMock, mock_time: MagicMock
    ) -> None:
        config = _make_config_with_narration()
        orch = NarrationOrchestrator(config)

        mock_dummy = MagicMock()
        mock_dummy.generate.return_value = Path("/tmp/narration.mp3")

        def create_side_effect(engine, **kwargs):
            if engine != "dummy":
                raise EnvironmentError("No API key")
            return mock_dummy

        mock_factory.create.side_effect = create_side_effect

        with Workspace() as ws:
            orch.generate_narrations(ws)

        # Should have fallen back to dummy provider
        assert mock_dummy.generate.called


class TestMeasureNarrationDurations:
    def test_empty_map(self) -> None:
        result = NarrationOrchestrator.measure_narration_durations({})
        assert result == {}

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_measures_duration(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        clip = AudioSegment.silent(duration=2000)
        clip_path = tmp_path / "clip.mp3"
        clip.export(str(clip_path), format="mp3")

        result = NarrationOrchestrator.measure_narration_durations({0: clip_path})
        assert len(result) == 1
        assert abs(result[0] - 2.0) < 0.2

    def test_skips_missing_files(self) -> None:
        result = NarrationOrchestrator.measure_narration_durations(
            {0: Path("/nonexistent/clip.mp3")}
        )
        # Should not raise, but clip won't be measurable, entry skipped
        assert 0 not in result or result == {}


class TestBuildNarrationTrack:
    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_empty_narration_map(self, tmp_path: Path) -> None:
        config = _make_config()
        orch = NarrationOrchestrator(config)
        result = orch.build_narration_track({}, tmp_path / "out.mp3", [0.0, 1.0])
        assert result is None

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_empty_timestamps(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        clip = AudioSegment.silent(duration=500)
        clip_path = tmp_path / "clip.mp3"
        clip.export(str(clip_path), format="mp3")

        config = _make_config()
        orch = NarrationOrchestrator(config)
        result = orch.build_narration_track({0: clip_path}, tmp_path / "out.mp3", [])
        assert result is None

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_builds_combined_track(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        clip = AudioSegment.silent(duration=500)
        clip_path = tmp_path / "clip.mp3"
        clip.export(str(clip_path), format="mp3")

        config = _make_config()
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track({0: clip_path}, out, [0.0, 2.0])
        assert result is not None
        assert result.exists()

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_build_track_shift_strategy(self, tmp_path: Path) -> None:
        """Overlapping clips are shifted when collision_strategy='shift'."""
        from pydub import AudioSegment

        clip_a = AudioSegment.silent(duration=3000)  # 3s clip
        clip_b = AudioSegment.silent(duration=1000)  # 1s clip
        path_a = tmp_path / "a.mp3"
        path_b = tmp_path / "b.mp3"
        clip_a.export(str(path_a), format="mp3")
        clip_b.export(str(path_b), format="mp3")

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "narration_gap": 0.3, "collision_strategy": "shift"},
        )
        orch = NarrationOrchestrator(config)

        # step 0 at t=0 with 3s clip, step 1 at t=1 → collision
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0]
        )
        assert result is not None
        assert result.exists()

    @pytest.mark.skipif(
        not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
    )
    def test_build_track_truncate_strategy(self, tmp_path: Path) -> None:
        """Overlapping clips are truncated when collision_strategy='truncate'."""
        from pydub import AudioSegment

        clip_a = AudioSegment.silent(duration=3000)
        clip_b = AudioSegment.silent(duration=1000)
        path_a = tmp_path / "a.mp3"
        path_b = tmp_path / "b.mp3"
        clip_a.export(str(path_a), format="mp3")
        clip_b.export(str(path_b), format="mp3")

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "collision_strategy": "truncate"},
        )
        orch = NarrationOrchestrator(config)

        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0]
        )
        assert result is not None
        assert result.exists()


class TestDetectCollisions:
    def test_no_collisions(self) -> None:
        timestamps = [0.0, 3.0, 6.0]
        durations = {0: 2.0, 2: 2.0}
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert collisions == []

    def test_single_collision(self) -> None:
        timestamps = [0.0, 1.0, 5.0]
        durations = {0: 3.0, 1: 1.0}  # step 0 ends at 3.0, step 1 starts at 1.0
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert len(collisions) == 1
        assert collisions[0][0] == 0
        assert collisions[0][1] == 1
        assert abs(collisions[0][2] - 2.0) < 0.01  # 2s overlap

    def test_multiple_collisions(self) -> None:
        timestamps = [0.0, 1.0, 2.0]
        durations = {0: 3.0, 1: 3.0, 2: 1.0}
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert len(collisions) == 2

    def test_no_narrations(self) -> None:
        collisions = NarrationOrchestrator.detect_collisions([0.0, 1.0], {})
        assert collisions == []

    def test_single_narration_no_collision(self) -> None:
        collisions = NarrationOrchestrator.detect_collisions([0.0], {0: 5.0})
        assert collisions == []

    def test_gap_between_narrated_steps(self) -> None:
        """Non-narrated steps between narrated ones should not cause false positives."""
        timestamps = [0.0, 2.0, 5.0, 8.0]
        durations = {0: 1.5, 3: 1.5}  # steps 1 and 2 have no narration
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert collisions == []

    def test_exact_boundary(self) -> None:
        """Step A ends exactly when step B starts — no collision."""
        timestamps = [0.0, 2.0]
        durations = {0: 2.0, 1: 1.0}
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert collisions == []

    def test_tiny_overlap(self) -> None:
        timestamps = [0.0, 1.99]
        durations = {0: 2.0, 1: 1.0}
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert len(collisions) == 1
        assert collisions[0][2] == pytest.approx(0.01, abs=0.001)
