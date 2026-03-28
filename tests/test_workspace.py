"""Tests for demodsl.pipeline.workspace — Workspace context manager."""

from __future__ import annotations

from pathlib import Path

from demodsl.pipeline.workspace import Workspace


class TestWorkspace:
    def test_creates_subdirs_in_tmp(self) -> None:
        with Workspace() as ws:
            for name in Workspace.SUBDIRS:
                assert (ws.root / name).is_dir()
            assert ws._tmp is True

    def test_creates_subdirs_with_custom_base(self, tmp_path: Path) -> None:
        base = tmp_path / "custom_ws"
        with Workspace(base_dir=base) as ws:
            assert ws.root == base
            assert ws._tmp is False
            for name in Workspace.SUBDIRS:
                assert (ws.root / name).is_dir()

    def test_subdirs_constant(self) -> None:
        assert Workspace.SUBDIRS == ("raw_video", "audio_clips", "frames", "rendered", "output")

    def test_property_raw_video(self) -> None:
        with Workspace() as ws:
            assert ws.raw_video == ws.root / "raw_video"

    def test_property_audio_clips(self) -> None:
        with Workspace() as ws:
            assert ws.audio_clips == ws.root / "audio_clips"

    def test_property_frames(self) -> None:
        with Workspace() as ws:
            assert ws.frames == ws.root / "frames"

    def test_property_rendered(self) -> None:
        with Workspace() as ws:
            assert ws.rendered == ws.root / "rendered"

    def test_property_output(self) -> None:
        with Workspace() as ws:
            assert ws.output == ws.root / "output"

    def test_cleanup_removes_tmp(self) -> None:
        ws = Workspace()
        root = ws.root
        assert root.exists()
        ws.cleanup()
        assert not root.exists()

    def test_cleanup_preserves_custom(self, tmp_path: Path) -> None:
        base = tmp_path / "persistent"
        ws = Workspace(base_dir=base)
        ws.cleanup()
        assert base.exists()

    def test_context_manager_cleans_tmp(self) -> None:
        with Workspace() as ws:
            root = ws.root
            assert root.exists()
        assert not root.exists()

    def test_context_manager_preserves_custom(self, tmp_path: Path) -> None:
        base = tmp_path / "keep"
        with Workspace(base_dir=base):
            pass
        assert base.exists()

    def test_enter_returns_self(self) -> None:
        ws = Workspace()
        try:
            entered = ws.__enter__()
            assert entered is ws
        finally:
            ws.cleanup()
