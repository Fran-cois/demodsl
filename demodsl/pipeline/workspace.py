"""Temporary workspace for intermediate assets."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import TracebackType


class Workspace:
    """Manages a temporary directory tree for pipeline artefacts.

    Sub-directories created automatically:
        raw_video/   – raw browser recordings
        audio_clips/ – individual TTS narration clips
        frames/      – extracted video frames
        rendered/    – intermediate rendered segments
        output/      – final output files
    """

    SUBDIRS = ("raw_video", "audio_clips", "frames", "rendered", "output")

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is not None:
            self.root = base_dir
            self.root.mkdir(parents=True, exist_ok=True)
            self._tmp = False
        else:
            self.root = Path(tempfile.mkdtemp(prefix="demodsl_"))
            self._tmp = True

        for name in self.SUBDIRS:
            (self.root / name).mkdir(exist_ok=True)

    # convenient accessors
    @property
    def raw_video(self) -> Path:
        return self.root / "raw_video"

    @property
    def audio_clips(self) -> Path:
        return self.root / "audio_clips"

    @property
    def frames(self) -> Path:
        return self.root / "frames"

    @property
    def rendered(self) -> Path:
        return self.root / "rendered"

    @property
    def output(self) -> Path:
        return self.root / "output"

    def cleanup(self) -> None:
        if self._tmp and self.root.exists():
            shutil.rmtree(self.root)

    # context-manager
    def __enter__(self) -> Workspace:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.cleanup()
