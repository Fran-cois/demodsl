"""Tests for --separate-audio and --thumbnails features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from pydantic import ValidationError

from demodsl.models import DemoConfig, LanguagesConfig

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_config_path(
    tmp_path: Path,
    *,
    languages: dict[str, Any] | None = None,
    narrations: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Create a YAML config file with optional languages and narrations."""
    narrations = narrations or ["Hello world", "Second step"]
    steps: list[dict[str, Any]] = []
    for i, text in enumerate(narrations):
        steps.append(
            {
                "action": "navigate",
                "url": f"https://example.com/{i}",
                "narration": text,
                "wait": 2.0,
            }
        )
    data: dict[str, Any] = {
        "metadata": {"title": "Test Separate Audio"},
        "scenarios": [{"name": "S1", "url": "https://example.com", "steps": steps}],
    }
    if languages:
        data["languages"] = languages
    if extra:
        data.update(extra)
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    return p


def _make_config_with_mixed_steps(tmp_path: Path) -> Path:
    """Config with interleaved narrated and non-narrated steps."""
    data: dict[str, Any] = {
        "metadata": {"title": "Mixed Steps"},
        "scenarios": [
            {
                "name": "S1",
                "url": "https://example.com",
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Opening the page",
                        "wait": 2.0,
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#btn"},
                        "wait": 1.0,
                    },
                    {
                        "action": "navigate",
                        "url": "https://example.com/2",
                        "narration": "Second page",
                        "wait": 2.0,
                    },
                    {
                        "action": "scroll",
                        "direction": "down",
                        "pixels": 300,
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#done"},
                        "narration": "Final click",
                        "wait": 1.0,
                    },
                ],
            }
        ],
    }
    p = tmp_path / "mixed.yaml"
    p.write_text(yaml.dump(data))
    return p


def _make_multi_scenario_config(tmp_path: Path) -> Path:
    """Config with multiple scenarios containing narrations."""
    data: dict[str, Any] = {
        "metadata": {"title": "Multi Scenario"},
        "scenarios": [
            {
                "name": "S1",
                "url": "https://example.com",
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Scenario one start",
                        "wait": 2.0,
                    },
                ],
            },
            {
                "name": "S2",
                "url": "https://example.com/s2",
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com/s2",
                        "narration": "Scenario two start",
                        "wait": 3.0,
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#x"},
                        "narration": "Scenario two click",
                        "wait": 1.0,
                    },
                ],
            },
        ],
    }
    p = tmp_path / "multi.yaml"
    p.write_text(yaml.dump(data))
    return p


# ══════════════════════════════════════════════════════════════════════════════
# LanguagesConfig model
# ══════════════════════════════════════════════════════════════════════════════


class TestLanguagesConfig:
    def test_defaults(self) -> None:
        lc = LanguagesConfig()
        assert lc.default == "fr"
        assert lc.targets == []

    def test_custom(self) -> None:
        lc = LanguagesConfig(default="en", targets=["fr", "de", "ja"])
        assert lc.default == "en"
        assert lc.targets == ["fr", "de", "ja"]

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LanguagesConfig(default="fr", unknown_field="x")  # type: ignore[call-arg]

    def test_default_too_short(self) -> None:
        with pytest.raises(ValidationError):
            LanguagesConfig(default="x")

    def test_default_accepts_locale_code(self) -> None:
        lc = LanguagesConfig(default="pt-BR")
        assert lc.default == "pt-BR"

    def test_empty_targets(self) -> None:
        lc = LanguagesConfig(default="en", targets=[])
        assert lc.targets == []

    def test_single_target(self) -> None:
        lc = LanguagesConfig(default="fr", targets=["en"])
        assert lc.targets == ["en"]


class TestDemoConfigWithLanguages:
    def test_languages_absent(self) -> None:
        cfg = DemoConfig(metadata={"title": "T"})  # type: ignore[arg-type]
        assert cfg.languages is None

    def test_languages_present(self) -> None:
        cfg = DemoConfig(
            metadata={"title": "T"},  # type: ignore[arg-type]
            languages={"default": "en", "targets": ["fr"]},  # type: ignore[arg-type]
        )
        assert cfg.languages is not None
        assert cfg.languages.default == "en"
        assert cfg.languages.targets == ["fr"]

    def test_languages_default_only(self) -> None:
        cfg = DemoConfig(
            metadata={"title": "T"},  # type: ignore[arg-type]
            languages={"default": "es"},  # type: ignore[arg-type]
        )
        assert cfg.languages.default == "es"
        assert cfg.languages.targets == []

    def test_languages_with_scenarios(self) -> None:
        cfg = DemoConfig(
            metadata={"title": "T"},  # type: ignore[arg-type]
            languages={"default": "ja", "targets": ["en", "fr"]},  # type: ignore[arg-type]
            scenarios=[
                {
                    "name": "S",
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "narration": "こんにちは",
                        }
                    ],
                }
            ],  # type: ignore[arg-type]
        )
        assert cfg.languages.default == "ja"
        assert len(cfg.scenarios) == 1

    def test_yaml_roundtrip(self, tmp_path: Path) -> None:
        data = {
            "metadata": {"title": "Multi-lang"},
            "languages": {"default": "fr", "targets": ["en", "es"]},
            "scenarios": [
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "narration": "Bienvenue",
                        }
                    ],
                }
            ],
        }
        p = tmp_path / "lang.yaml"
        p.write_text(yaml.dump(data))
        from demodsl.config_loader import load_config

        raw = load_config(p)
        cfg = DemoConfig(**raw)
        assert cfg.languages.default == "fr"
        assert cfg.languages.targets == ["en", "es"]

    def test_json_roundtrip(self, tmp_path: Path) -> None:
        data = {
            "metadata": {"title": "Multi-lang"},
            "languages": {"default": "de", "targets": ["en"]},
        }
        p = tmp_path / "lang.json"
        p.write_text(json.dumps(data))
        from demodsl.config_loader import load_config

        raw = load_config(p)
        cfg = DemoConfig(**raw)
        assert cfg.languages.default == "de"


# ══════════════════════════════════════════════════════════════════════════════
# Engine: separate_audio flag
# ══════════════════════════════════════════════════════════════════════════════


class TestEngineSeparateAudioInit:
    def test_separate_audio_flag_stored(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)
        assert engine._separate_audio is True

    def test_separate_audio_default_false(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True)
        assert engine._separate_audio is False

    def test_language_passed_to_narration(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, languages={"default": "es", "targets": ["en"]})
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)
        assert engine._narration._language == "es"

    def test_language_not_passed_without_separate_audio(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, languages={"default": "de", "targets": ["en"]})
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=False)
        assert engine._narration._language is None

    def test_separate_audio_without_languages_block(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)
        # No languages block → language is None (system default)
        assert engine._narration._language is None

    def test_separate_audio_with_custom_output_dir(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        custom = tmp_path / "custom_output"
        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(
            config_path=cfg_path,
            dry_run=True,
            separate_audio=True,
            output_dir=custom,
        )
        assert engine._output_dir == custom
        assert engine._separate_audio is True


# ══════════════════════════════════════════════════════════════════════════════
# Engine: _build_timing_json
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildTimingJson:
    def test_basic_timing(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Bienvenue", "Cliquez ici"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        step_timestamps = [0.0, 5.0]
        narration_durations = {0: 3.2, 1: 2.5}
        narration_map = {0: Path("clip_0.mp3"), 1: Path("clip_1.mp3")}

        timing = engine._build_timing_json(step_timestamps, narration_durations, narration_map)

        assert len(timing) == 2
        assert timing[0]["step"] == 0
        assert timing[0]["text"] == "Bienvenue"
        assert timing[0]["start"] == 0.0
        assert timing[0]["end"] == 3.2
        assert timing[1]["step"] == 1
        assert timing[1]["text"] == "Cliquez ici"
        assert timing[1]["start"] == 5.0
        assert timing[1]["end"] == 7.5

    def test_skips_non_narrated_steps(self, tmp_path: Path) -> None:
        """Steps without narration should NOT appear in timing.json."""
        from demodsl.engine import DemoEngine

        p = _make_config_with_mixed_steps(tmp_path)
        engine = DemoEngine(config_path=p, dry_run=True, separate_audio=True)

        # Steps 0, 2, 4 have narration; steps 1, 3 do not
        timing = engine._build_timing_json(
            step_timestamps=[0.0, 3.0, 4.0, 7.0, 8.0],
            narration_durations={0: 2.5, 2: 2.0, 4: 1.5},
            narration_map={
                0: Path("c0.mp3"),
                2: Path("c2.mp3"),
                4: Path("c4.mp3"),
            },
        )

        assert len(timing) == 3
        assert [t["step"] for t in timing] == [0, 2, 4]
        assert timing[0]["text"] == "Opening the page"
        assert timing[1]["text"] == "Second page"
        assert timing[2]["text"] == "Final click"

    def test_empty_narration_map(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[0.0, 5.0],
            narration_durations={},
            narration_map={},
        )

        assert timing == []

    def test_timestamps_have_decimal_precision(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Test"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[1.23456],
            narration_durations={0: 2.78901},
            narration_map={0: Path("clip.mp3")},
        )

        assert timing[0]["start"] == 1.2
        assert timing[0]["end"] == 4.0

    def test_multi_scenario_timing(self, tmp_path: Path) -> None:
        """timing.json should span across multiple scenarios."""
        from demodsl.engine import DemoEngine

        p = _make_multi_scenario_config(tmp_path)
        engine = DemoEngine(config_path=p, dry_run=True, separate_audio=True)

        # Scenario 1: step 0 narrated. Scenario 2: step 1, step 2 narrated
        timing = engine._build_timing_json(
            step_timestamps=[0.0, 5.0, 8.0],
            narration_durations={0: 2.0, 1: 3.0, 2: 1.5},
            narration_map={
                0: Path("c0.mp3"),
                1: Path("c1.mp3"),
                2: Path("c2.mp3"),
            },
        )

        assert len(timing) == 3
        assert timing[0]["text"] == "Scenario one start"
        assert timing[1]["text"] == "Scenario two start"
        assert timing[2]["text"] == "Scenario two click"

    def test_timing_order_follows_yaml(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["First", "Second", "Third"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[0.0, 3.0, 6.0],
            narration_durations={0: 2.0, 1: 2.0, 2: 2.0},
            narration_map={
                0: Path("c0.mp3"),
                1: Path("c1.mp3"),
                2: Path("c2.mp3"),
            },
        )

        steps = [t["step"] for t in timing]
        assert steps == sorted(steps)

    def test_single_narration(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Only one"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[2.5],
            narration_durations={0: 4.0},
            narration_map={0: Path("c0.mp3")},
        )

        assert len(timing) == 1
        assert timing[0]["step"] == 0
        assert timing[0]["start"] == 2.5
        assert timing[0]["end"] == 6.5

    def test_zero_duration_narration(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Silence"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[1.0],
            narration_durations={0: 0.0},
            narration_map={0: Path("c0.mp3")},
        )

        assert timing[0]["start"] == 1.0
        assert timing[0]["end"] == 1.0

    def test_timing_json_is_valid_json(self, tmp_path: Path) -> None:
        """Verify the output can be serialized to valid JSON."""
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Héllo «world»", "Ünïcödé"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[0.0, 5.0],
            narration_durations={0: 3.0, 1: 2.0},
            narration_map={0: Path("c0.mp3"), 1: Path("c1.mp3")},
        )

        serialized = json.dumps(timing, indent=2, ensure_ascii=False)
        reloaded = json.loads(serialized)
        assert reloaded == timing
        assert "Héllo «world»" in serialized

    def test_timing_fields_types(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Test"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[0.0],
            narration_durations={0: 2.5},
            narration_map={0: Path("c.mp3")},
        )

        entry = timing[0]
        assert isinstance(entry["step"], int)
        assert isinstance(entry["text"], str)
        assert isinstance(entry["start"], float)
        assert isinstance(entry["end"], float)

    def test_step_index_beyond_timestamps(self, tmp_path: Path) -> None:
        """If step_idx >= len(step_timestamps), start should default to 0.0."""
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, narrations=["Overflow"])
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=True)

        timing = engine._build_timing_json(
            step_timestamps=[],  # empty!
            narration_durations={0: 1.5},
            narration_map={0: Path("c.mp3")},
        )

        assert timing[0]["start"] == 0.0
        assert timing[0]["end"] == 1.5


# ══════════════════════════════════════════════════════════════════════════════
# Engine: _generate_thumbnails
# ══════════════════════════════════════════════════════════════════════════════


class TestGenerateThumbnails:
    def test_no_ffmpeg_returns_empty(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        with patch("shutil.which", return_value=None):
            result = DemoEngine._generate_thumbnails(tmp_path / "video.mp4", tmp_path, 3)
        assert result == []

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_generates_correct_count(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)

        # First call: ffprobe duration. Subsequent calls: ffmpeg extract
        def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            cmd = args[0] if args else kwargs.get("args", [])
            m = MagicMock()
            m.returncode = 0
            if "ffprobe" in cmd[0]:
                m.stdout = "30.0\n"
            else:
                # Create the output file
                for c in cmd:
                    if str(c).endswith(".png"):
                        Path(c).write_bytes(b"\x89PNG fake")
            return m

        mock_run.side_effect = side_effect
        out_dir = tmp_path / "thumbs"

        result = DemoEngine._generate_thumbnails(video, out_dir, 3)
        assert len(result) == 3
        assert all(p.name.startswith("thumbnail_") for p in result)

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_timestamp_distribution(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Thumbnails should be at evenly-spaced timestamps."""
        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)
        timestamps_used: list[str] = []

        def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            cmd = args[0] if args else kwargs.get("args", [])
            m = MagicMock()
            m.returncode = 0
            if "ffprobe" in cmd[0]:
                m.stdout = "40.0\n"
            else:
                # Capture the -ss timestamp
                if "-ss" in cmd:
                    idx = cmd.index("-ss")
                    timestamps_used.append(cmd[idx + 1])
                for c in cmd:
                    if str(c).endswith(".png"):
                        Path(c).write_bytes(b"\x89PNG")
            return m

        mock_run.side_effect = side_effect

        DemoEngine._generate_thumbnails(video, tmp_path / "out", 4)

        # For 40s video and 4 thumbnails: 8s, 16s, 24s, 32s
        assert len(timestamps_used) == 4
        expected = [8.0, 16.0, 24.0, 32.0]
        actual = [float(t) for t in timestamps_used]
        assert actual == expected

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_single_thumbnail(self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)

        def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            cmd = args[0] if args else kwargs.get("args", [])
            m = MagicMock()
            m.returncode = 0
            if "ffprobe" in cmd[0]:
                m.stdout = "10.0\n"
            else:
                for c in cmd:
                    if str(c).endswith(".png"):
                        Path(c).write_bytes(b"\x89PNG")
            return m

        mock_run.side_effect = side_effect
        result = DemoEngine._generate_thumbnails(video, tmp_path, 1)
        assert len(result) == 1
        assert result[0].name == "thumbnail_00.png"

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_ffmpeg_failure_skips(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """If ffmpeg fails for one thumbnail, others should still be generated."""
        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)
        call_num = 0

        def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_num
            cmd = args[0] if args else kwargs.get("args", [])
            m = MagicMock()
            if "ffprobe" in cmd[0]:
                m.returncode = 0
                m.stdout = "20.0\n"
            else:
                call_num += 1
                if call_num == 2:  # Fail the second thumbnail
                    m.returncode = 1
                    m.stderr = "error"
                else:
                    m.returncode = 0
                    for c in cmd:
                        if str(c).endswith(".png"):
                            Path(c).write_bytes(b"\x89PNG")
            return m

        mock_run.side_effect = side_effect
        result = DemoEngine._generate_thumbnails(video, tmp_path, 3)
        assert len(result) == 2  # 1 failed, 2 succeeded

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_probe_failure_returns_empty(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        import subprocess as sp

        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)

        mock_run.side_effect = sp.SubprocessError("ffprobe died")
        result = DemoEngine._generate_thumbnails(video, tmp_path, 3)
        assert result == []

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_zero_duration_returns_empty(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)

        probe = MagicMock()
        probe.returncode = 0
        probe.stdout = "0.0\n"
        mock_run.return_value = probe

        result = DemoEngine._generate_thumbnails(video, tmp_path, 3)
        assert result == []

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_creates_output_dir(
        self, _which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from demodsl.engine import DemoEngine

        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00" * 100)
        out_dir = tmp_path / "sub" / "dir"

        def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            cmd = args[0] if args else kwargs.get("args", [])
            m = MagicMock()
            m.returncode = 0
            if "ffprobe" in cmd[0]:
                m.stdout = "10.0\n"
            else:
                for c in cmd:
                    if str(c).endswith(".png"):
                        Path(c).write_bytes(b"\x89PNG")
            return m

        mock_run.side_effect = side_effect
        DemoEngine._generate_thumbnails(video, out_dir, 1)
        assert out_dir.exists()


# ══════════════════════════════════════════════════════════════════════════════
# Engine: thumbnails flag init
# ══════════════════════════════════════════════════════════════════════════════


class TestEngineThumbnailsInit:
    def test_thumbnails_default_zero(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True)
        assert engine._thumbnails == 0

    def test_thumbnails_stored(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True, thumbnails=5)
        assert engine._thumbnails == 5

    def test_thumbnails_combined_with_separate_audio(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(
            config_path=cfg_path,
            dry_run=True,
            separate_audio=True,
            thumbnails=3,
        )
        assert engine._separate_audio is True
        assert engine._thumbnails == 3


# ══════════════════════════════════════════════════════════════════════════════
# CLI: --separate-audio and --thumbnails flags
# ══════════════════════════════════════════════════════════════════════════════


class TestCLISeparateAudioFlag:
    def test_help_mentions_separate_audio(self) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["run", "--help"])
        assert "--separate-audio" in result.output

    def test_help_mentions_thumbnails(self) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["run", "--help"])
        assert "--thumbnails" in result.output

    def test_help_thumbnails_description(self) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["run", "--help"])
        assert "thumbnail" in result.output.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Retrocompat: languages ignored without --separate-audio
# ══════════════════════════════════════════════════════════════════════════════


class TestRetrocompat:
    def test_languages_ignored_without_flag(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path, languages={"default": "ja", "targets": ["en"]})
        engine = DemoEngine(config_path=cfg_path, dry_run=True, separate_audio=False)
        # Languages block is parsed but language is not forwarded
        assert engine.config.languages is not None
        assert engine.config.languages.default == "ja"
        assert engine._narration._language is None

    def test_config_without_languages_valid(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(config_path=cfg_path, dry_run=True)
        assert engine.config.languages is None

    def test_dry_run_no_output_produced(self, tmp_path: Path) -> None:
        from demodsl.engine import DemoEngine

        cfg_path = _make_config_path(tmp_path)
        engine = DemoEngine(
            config_path=cfg_path,
            dry_run=True,
            separate_audio=True,
            output_dir=tmp_path / "out",
        )
        result = engine.run()
        assert result is None

    def test_existing_yaml_still_valid(self, tmp_path: Path) -> None:
        """A YAML without languages should still parse fine."""
        data = {
            "metadata": {"title": "Legacy"},
            "voice": {"engine": "gtts", "voice_id": "fr"},
            "scenarios": [
                {
                    "name": "S1",
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "narration": "Bonjour",
                        }
                    ],
                }
            ],
            "pipeline": [{"generate_narration": {}}, {"edit_video": {}}],
        }
        p = tmp_path / "legacy.yaml"
        p.write_text(yaml.dump(data))
        from demodsl.engine import DemoEngine

        engine = DemoEngine(config_path=p, dry_run=True)
        assert engine.config.languages is None
        assert engine.config.voice.engine == "gtts"


# ══════════════════════════════════════════════════════════════════════════════
# NarrationOrchestrator: language parameter
# ══════════════════════════════════════════════════════════════════════════════


class TestNarrationOrchestratorLanguage:
    def test_language_stored(self) -> None:
        from demodsl.orchestrators.narration import NarrationOrchestrator

        cfg = DemoConfig(metadata={"title": "T"})  # type: ignore[arg-type]
        orch = NarrationOrchestrator(cfg, language="es")
        assert orch._language == "es"

    def test_language_default_none(self) -> None:
        from demodsl.orchestrators.narration import NarrationOrchestrator

        cfg = DemoConfig(metadata={"title": "T"})  # type: ignore[arg-type]
        orch = NarrationOrchestrator(cfg)
        assert orch._language is None

    def test_language_various_codes(self) -> None:
        from demodsl.orchestrators.narration import NarrationOrchestrator

        for code in ["fr", "en", "de", "ja", "zh", "pt-BR"]:
            cfg = DemoConfig(metadata={"title": "T"})  # type: ignore[arg-type]
            orch = NarrationOrchestrator(cfg, language=code)
            assert orch._language == code
