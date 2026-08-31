"""Tests for demodsl.transcribe (speech-to-text auto-captioning)."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demodsl.transcribe import (
    Cue,
    MissingTranscriptionDependencyError,
    Word,
    cues_to_srt,
    cues_to_vtt,
    is_available,
    transcribe,
)


class TestIsAvailable:
    def test_true_when_find_spec_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("demodsl.transcribe.importlib.util.find_spec", lambda name: object())
        assert is_available() is True

    def test_false_when_find_spec_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("demodsl.transcribe.importlib.util.find_spec", lambda name: None)
        assert is_available() is False


class TestTranscribe:
    def test_raises_when_dependency_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("demodsl.transcribe.is_available", lambda: False)
        with pytest.raises(MissingTranscriptionDependencyError, match="demodsl\\[captions\\]"):
            transcribe(tmp_path / "audio.mp3")

    def test_raises_when_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("demodsl.transcribe.is_available", lambda: True)
        with pytest.raises(FileNotFoundError):
            transcribe(tmp_path / "nope.mp3")

    def test_builds_cues_from_segments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        monkeypatch.setattr("demodsl.transcribe.is_available", lambda: True)

        word1 = types.SimpleNamespace(word=" Hello", start=0.0, end=0.4)
        word2 = types.SimpleNamespace(word=" world", start=0.4, end=0.9)
        segment = types.SimpleNamespace(
            text=" Hello world", start=0.0, end=0.9, words=[word1, word2]
        )
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (
            [segment],
            types.SimpleNamespace(language="en"),
        )
        fake_module = types.SimpleNamespace(WhisperModel=MagicMock(return_value=fake_model))
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

        cues = transcribe(audio, model_size="tiny", language="en")
        assert len(cues) == 1
        assert cues[0].text == "Hello world"
        assert cues[0].start == 0.0
        assert cues[0].end == 0.9
        assert [w.text for w in cues[0].words] == ["Hello", "world"]

    def test_multiple_segments_with_no_words(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        monkeypatch.setattr("demodsl.transcribe.is_available", lambda: True)

        seg1 = types.SimpleNamespace(text=" First", start=0.0, end=1.0, words=None)
        seg2 = types.SimpleNamespace(text=" Second", start=1.0, end=2.0, words=None)
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([seg1, seg2], types.SimpleNamespace(language="en"))
        fake_module = types.SimpleNamespace(WhisperModel=MagicMock(return_value=fake_model))
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

        cues = transcribe(audio)
        assert [c.text for c in cues] == ["First", "Second"]
        assert cues[0].words == []


class TestCuesToSrt:
    def test_format(self) -> None:
        cues = [Cue(text="Hello world", start=0.0, end=1.5)]
        srt = cues_to_srt(cues)
        assert "1\n00:00:00,000 --> 00:00:01,500\nHello world" in srt

    def test_multiple_cues_numbered(self) -> None:
        cues = [
            Cue(text="One", start=0.0, end=1.0),
            Cue(text="Two", start=1.0, end=2.0),
        ]
        srt = cues_to_srt(cues)
        assert srt.count("\n\n") == 2 or "2\n00:00:01,000" in srt


class TestCuesToVtt:
    def test_format(self) -> None:
        cues = [Cue(text="Hello world", start=0.0, end=1.5)]
        vtt = cues_to_vtt(cues)
        assert vtt.startswith("WEBVTT\n")
        assert "00:00:00.000 --> 00:00:01.500\nHello world" in vtt


class TestWordDataclass:
    def test_fields(self) -> None:
        w = Word(text="hi", start=0.1, end=0.3)
        assert (w.text, w.start, w.end) == ("hi", 0.1, 0.3)


class TestTranscribeCli:
    def test_missing_file_exits_nonzero(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        result = CliRunner().invoke(app, ["transcribe", str(tmp_path / "nope.mp3")])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_missing_dependency_exits_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        media = tmp_path / "audio.mp3"
        media.write_bytes(b"fake")
        monkeypatch.setattr("demodsl.transcribe.is_available", lambda: False)
        result = CliRunner().invoke(app, ["transcribe", str(media)])
        assert result.exit_code == 1
        assert "captions" in result.output

    def test_writes_srt_vtt_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        media = tmp_path / "audio.mp3"
        media.write_bytes(b"fake")
        monkeypatch.setattr("demodsl.transcribe.is_available", lambda: True)

        word = types.SimpleNamespace(word=" Hi", start=0.0, end=0.3)
        segment = types.SimpleNamespace(text=" Hi", start=0.0, end=0.3, words=[word])
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([segment], types.SimpleNamespace(language="en"))
        fake_module = types.SimpleNamespace(WhisperModel=MagicMock(return_value=fake_model))
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

        srt_path = tmp_path / "out.srt"
        vtt_path = tmp_path / "out.vtt"
        json_path = tmp_path / "out.json"
        result = CliRunner().invoke(
            app,
            [
                "transcribe",
                str(media),
                "--srt",
                str(srt_path),
                "--vtt",
                str(vtt_path),
                "--json",
                str(json_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert srt_path.exists()
        assert vtt_path.exists()
        assert json_path.exists()
        assert "Hi" in srt_path.read_text()
