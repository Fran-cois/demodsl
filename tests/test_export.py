"""Tests for demodsl.orchestrators.export — _human_size utility."""

from __future__ import annotations

import pytest

from demodsl.orchestrators.export import _human_size


class TestHumanSize:
    @pytest.mark.parametrize(
        "nbytes,expected",
        [
            (0, "0B"),
            (512, "512B"),
            (1024, "1KB"),
            (1536, "2KB"),
            (1_048_576, "1MB"),
            (10_485_760, "10MB"),
            (1_073_741_824, "1GB"),
            (1_099_511_627_776, "1.0TB"),
        ],
    )
    def test_human_size(self, nbytes: int, expected: str) -> None:
        assert _human_size(nbytes) == expected
