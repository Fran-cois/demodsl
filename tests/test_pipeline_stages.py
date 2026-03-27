"""Tests for demodsl.pipeline.stages — Chain of Responsibility pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.pipeline.stages import (
    ApplyEffectsStage,
    EditVideoStage,
    GenerateNarrationStage,
    MixAudioStage,
    OptimizeStage,
    PipelineContext,
    PipelineStageHandler,
    RenderDeviceMockupStage,
    RestoreAudioStage,
    RestoreVideoStage,
    _STAGE_MAP,
    build_chain,
)


class TestPipelineContext:
    def test_defaults(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        assert ctx.raw_video is None
        assert ctx.processed_video is None
        assert ctx.audio_clips == []
        assert ctx.narration_map == {}
        assert ctx.final_audio is None
        assert ctx.config == {}
        assert ctx.metadata == {}

    def test_mutable_fields_independent(self, tmp_path: Path) -> None:
        ctx1 = PipelineContext(workspace_root=tmp_path)
        ctx2 = PipelineContext(workspace_root=tmp_path)
        ctx1.audio_clips.append(Path("a.mp3"))
        assert ctx2.audio_clips == []


class TestStageMap:
    def test_has_8_stages(self) -> None:
        assert len(_STAGE_MAP) == 8

    @pytest.mark.parametrize("name", [
        "restore_audio", "restore_video", "apply_effects",
        "generate_narration", "render_device_mockup",
        "edit_video", "mix_audio", "optimize",
    ])
    def test_stage_registered(self, name: str) -> None:
        assert name in _STAGE_MAP

    def test_critical_stages(self) -> None:
        critical = {"generate_narration": True, "edit_video": True,
                     "mix_audio": True, "optimize": True}
        for name, expected in critical.items():
            cls = _STAGE_MAP[name]
            instance = cls({})
            assert instance.critical == expected, f"{name} critical={instance.critical}"

    def test_optional_stages(self) -> None:
        optional = {"restore_audio": False, "restore_video": False,
                     "apply_effects": False, "render_device_mockup": False}
        for name, expected in optional.items():
            cls = _STAGE_MAP[name]
            instance = cls({})
            assert instance.critical == expected, f"{name} critical={instance.critical}"


class TestSetNext:
    def test_set_next_returns_handler(self) -> None:
        a = RestoreAudioStage({})
        b = RestoreVideoStage({})
        result = a.set_next(b)
        assert result is b

    def test_chain_links(self) -> None:
        a = RestoreAudioStage({})
        b = RestoreVideoStage({})
        a.set_next(b)
        assert a._next is b


class TestHandleChain:
    def test_single_stage(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = RestoreAudioStage({"denoise": True})
        result = stage.handle(ctx)
        assert result is ctx

    def test_chain_passes_context(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        a = RestoreAudioStage({})
        b = RestoreVideoStage({})
        a.set_next(b)
        result = a.handle(ctx)
        assert result is ctx

    def test_optional_stage_skips_on_error(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)

        class FailingOptional(PipelineStageHandler):
            name = "failing"  # type: ignore[assignment]
            def __init__(self) -> None:
                super().__init__(critical=False)
            def process(self, ctx: PipelineContext) -> PipelineContext:
                raise RuntimeError("boom")

        stage = FailingOptional()
        next_stage = RestoreAudioStage({})
        stage.set_next(next_stage)
        result = stage.handle(ctx)
        assert result is ctx  # chain continues

    def test_critical_stage_raises(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)

        class FailingCritical(PipelineStageHandler):
            name = "failing_critical"  # type: ignore[assignment]
            def __init__(self) -> None:
                super().__init__(critical=True)
            def process(self, ctx: PipelineContext) -> PipelineContext:
                raise RuntimeError("critical failure")

        stage = FailingCritical()
        with pytest.raises(RuntimeError, match="critical failure"):
            stage.handle(ctx)


class TestMixAudioStage:
    def test_early_return_no_audio(self, tmp_path: Path) -> None:
        ctx = PipelineContext(workspace_root=tmp_path)
        stage = MixAudioStage({})
        result = stage.process(ctx)
        assert result is ctx


class TestBuildChain:
    def test_stage_type_format(self) -> None:
        stages = [
            {"stage_type": "restore_audio", "params": {"denoise": True}},
            {"stage_type": "edit_video", "params": {}},
        ]
        head = build_chain(stages)
        assert head is not None
        assert head.name == "restore_audio"
        assert head._next is not None
        assert head._next.name == "edit_video"

    def test_raw_dict_format(self) -> None:
        stages = [
            {"restore_audio": {"denoise": True}},
            {"optimize": {"format": "mp4"}},
        ]
        head = build_chain(stages)
        assert head is not None
        assert head.name == "restore_audio"

    def test_unknown_stage_skipped(self) -> None:
        stages = [
            {"stage_type": "nonexistent"},
            {"stage_type": "optimize", "params": {}},
        ]
        head = build_chain(stages)
        assert head is not None
        assert head.name == "optimize"

    def test_empty_list_returns_none(self) -> None:
        assert build_chain([]) is None

    def test_all_unknown_returns_none(self) -> None:
        stages = [{"stage_type": "fake1"}, {"stage_type": "fake2"}]
        assert build_chain(stages) is None

    def test_full_chain_length(self) -> None:
        stages = [{"stage_type": name, "params": {}} for name in _STAGE_MAP]
        head = build_chain(stages)
        assert head is not None
        count = 1
        node = head
        while node._next:
            node = node._next
            count += 1
        assert count == 8
