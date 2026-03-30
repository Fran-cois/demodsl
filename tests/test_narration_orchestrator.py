"""Tests for demodsl.orchestrators.narration — NarrationOrchestrator."""

from __future__ import annotations

import logging
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


# ── Forced collision integration tests ────────────────────────────────────────


def _make_tone(tmp_path: Path, name: str, duration_ms: int, freq: float) -> Path:
    """Create an MP3 with a sine tone so we can detect overlap via amplitude."""
    from pydub import AudioSegment
    from pydub.generators import Sine

    tone = Sine(freq).to_audio_segment(duration=duration_ms).apply_gain(-10)
    path = tmp_path / f"{name}.mp3"
    tone.export(str(path), format="mp3")
    return path


@pytest.mark.skipif(
    not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
)
class TestForcedCollisionWarnStrategy:
    """Warn strategy: clips overlap, both are mixed together at original positions."""

    def test_warn_keeps_both_clips_at_original_offsets(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        # clip_a = 3s at t=0, clip_b = 2s at t=1 → 2s overlap
        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 2000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "collision_strategy": "warn"},
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0]
        )
        assert result is not None

        combined = AudioSegment.from_file(str(result))
        # In the overlap zone (1.0s–3.0s) both tones are mixed, so the RMS
        # should be higher than in the solo zones.
        solo_zone = combined[0:900]   # 0–0.9s: only clip_a
        overlap_zone = combined[1100:2900]  # 1.1–2.9s: both clips
        assert overlap_zone.rms > solo_zone.rms * 0.8  # overlapping zone is louder

    def test_warn_logs_collision(self, tmp_path: Path, caplog) -> None:
        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 1000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "collision_strategy": "warn"},
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        with caplog.at_level(logging.WARNING):
            orch.build_narration_track({0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0])
        assert any("collision" in r.message.lower() for r in caplog.records)


@pytest.mark.skipif(
    not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
)
class TestForcedCollisionShiftStrategy:
    """Shift strategy: the second clip is delayed so it starts after the first ends."""

    def test_shift_eliminates_overlap(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        # clip_a = 3s at t=0, clip_b = 2s at t=1 → would overlap 2s
        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 2000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={
                "engine": "gtts",
                "narration_gap": 0.5,
                "collision_strategy": "shift",
            },
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0]
        )
        assert result is not None

        combined = AudioSegment.from_file(str(result))
        # clip_a is 3s → with 0.5s gap, clip_b should start at 3.5s
        # Check that the gap zone (3.0–3.4s) is silent
        gap_zone = combined[3000:3400]
        assert gap_zone.rms < 50  # essentially silent

        # clip_b should be audible at 3.5–5.5s
        shifted_zone = combined[3600:5400]
        assert shifted_zone.rms > 100  # has audio

    def test_shift_logs_shift_amount(self, tmp_path: Path, caplog) -> None:
        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 1000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={
                "engine": "gtts",
                "narration_gap": 0.3,
                "collision_strategy": "shift",
            },
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        with caplog.at_level(logging.WARNING):
            orch.build_narration_track({0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0])
        assert any("shifting" in r.message.lower() for r in caplog.records)

    def test_shift_no_change_when_no_collision(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        # clip_a = 1s at t=0, clip_b = 1s at t=5 → no collision
        path_a = _make_tone(tmp_path, "a", 1000, 440.0)
        path_b = _make_tone(tmp_path, "b", 1000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={
                "engine": "gtts",
                "narration_gap": 0.3,
                "collision_strategy": "shift",
            },
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 5.0, 10.0]
        )
        assert result is not None

        combined = AudioSegment.from_file(str(result))
        # clip_b should still start at t=5s (not shifted)
        before_b = combined[4800:4950]
        assert before_b.rms < 50  # silence just before t=5
        at_b = combined[5100:5800]
        assert at_b.rms > 100  # clip_b is there


@pytest.mark.skipif(
    not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
)
class TestForcedCollisionTruncateStrategy:
    """Truncate strategy: the first clip is cut short with a fade-out."""

    def test_truncate_shortens_first_clip(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        # clip_a = 3s at t=0, clip_b = 2s at t=1 → clip_a should be truncated to 1s
        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 2000, 880.0)

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

        combined = AudioSegment.from_file(str(result))
        # After truncation clip_a ends at 1.0s, clip_b starts at 1.0s
        # The zone 1.5–2.5s should only contain clip_b (no summed amplitudes)
        after_truncate = combined[1500:2500]
        before_truncate = combined[0:800]
        # Both should have audio, but the after zone shouldn't be louder than
        # roughly the amplitude of a single tone (no double-mixing)
        assert after_truncate.rms < before_truncate.rms * 2.5

    def test_truncate_logs_truncation(self, tmp_path: Path, caplog) -> None:
        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 1000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "collision_strategy": "truncate"},
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        with caplog.at_level(logging.WARNING):
            orch.build_narration_track({0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0])
        assert any("truncated" in r.message.lower() for r in caplog.records)

    def test_truncate_preserves_second_clip_position(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        path_a = _make_tone(tmp_path, "a", 3000, 440.0)
        path_b = _make_tone(tmp_path, "b", 2000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={"engine": "gtts", "collision_strategy": "truncate"},
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 1.0, 10.0]
        )
        combined = AudioSegment.from_file(str(result))
        # clip_b starts at 1.0s and is 2s long → audible at 1.1–2.9s
        clip_b_zone = combined[1100:2900]
        assert clip_b_zone.rms > 100


@pytest.mark.skipif(
    not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
)
class TestForcedCollisionChainedOverlaps:
    """Multiple consecutive collisions — verify all are handled."""

    def test_triple_collision_shift(self, tmp_path: Path) -> None:
        from pydub import AudioSegment

        # 3 clips of 2s each, spaced 0.5s apart → chain of collisions
        path_a = _make_tone(tmp_path, "a", 2000, 330.0)
        path_b = _make_tone(tmp_path, "b", 2000, 550.0)
        path_c = _make_tone(tmp_path, "c", 2000, 770.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={
                "engine": "gtts",
                "narration_gap": 0.2,
                "collision_strategy": "shift",
            },
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / "combined.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b, 2: path_c},
            out,
            [0.0, 0.5, 1.0, 15.0],
        )
        assert result is not None

        combined = AudioSegment.from_file(str(result))
        # After shifting:
        # clip_a: 0–2s
        # clip_b: 2.2s–4.2s (shifted from 0.5)
        # clip_c: should start after clip_b ends + gap

        # Verify detect_collisions on the OUTPUT offsets would find no overlaps
        durations_out = {0: 2.0, 1: 2.0, 2: 2.0}
        # clip_a at 0, clip_b shifted to 2.2, clip_c at least 4.4
        # The silence zone between clip_a and clip_b (2.0–2.15s)
        gap_ab = combined[2000:2150]
        assert gap_ab.rms < 50  # gap between a and b

    def test_triple_collision_warn_detects_all(self, tmp_path: Path) -> None:
        path_a = _make_tone(tmp_path, "a", 2000, 330.0)
        path_b = _make_tone(tmp_path, "b", 2000, 550.0)
        path_c = _make_tone(tmp_path, "c", 2000, 770.0)

        # All 3 overlap: detect_collisions should find 2 collision pairs
        timestamps = [0.0, 0.5, 1.0, 15.0]
        durations = {0: 2.0, 1: 2.0, 2: 2.0}
        collisions = NarrationOrchestrator.detect_collisions(timestamps, durations)
        assert len(collisions) == 2
        assert collisions[0] == (0, 1, pytest.approx(1.5, abs=0.01))
        assert collisions[1] == (1, 2, pytest.approx(1.5, abs=0.01))


@pytest.mark.skipif(
    not (_has_ffmpeg and _has_pydub), reason="ffmpeg or pydub not available"
)
class TestCollisionWithVaryingGaps:
    """Verify narration_gap is respected with different values."""

    @pytest.mark.parametrize("gap", [0.0, 0.3, 1.0, 2.0])
    def test_shift_respects_gap_value(self, tmp_path: Path, gap: float) -> None:
        from pydub import AudioSegment

        path_a = _make_tone(tmp_path, "a", 2000, 440.0)
        path_b = _make_tone(tmp_path, "b", 1000, 880.0)

        config = DemoConfig(
            metadata={"title": "Test"},
            voice={
                "engine": "gtts",
                "narration_gap": gap,
                "collision_strategy": "shift",
            },
        )
        orch = NarrationOrchestrator(config)
        out = tmp_path / f"combined_gap{gap}.mp3"
        result = orch.build_narration_track(
            {0: path_a, 1: path_b}, out, [0.0, 0.5, 15.0]
        )
        assert result is not None

        combined = AudioSegment.from_file(str(result))
        # clip_a is 2s, gap is `gap` → clip_b should start at 2.0 + gap
        expected_start_ms = int((2.0 + gap) * 1000)
        # Check silence just before clip_b starts
        if expected_start_ms > 2100:
            pre_b = combined[2100 : expected_start_ms - 50]
            assert pre_b.rms < 50  # silent in the gap
        # Check clip_b is audible after expected start
        post_start = combined[expected_start_ms + 100 : expected_start_ms + 800]
        assert post_start.rms > 80
