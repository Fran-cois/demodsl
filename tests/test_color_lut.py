"""Tests for the .cube 3D LUT parser/validator (demodsl.color_lut)."""

from __future__ import annotations

from pathlib import Path

import pytest

from demodsl.color_lut import (
    CubeLutError,
    escape_ffmpeg_filter_path,
    load_cube_lut,
    parse_cube_lut,
)

_VALID_2 = """TITLE "Test LUT"
LUT_3D_SIZE 2
0.0 0.0 0.0
1.0 0.0 0.0
0.0 1.0 0.0
1.0 1.0 0.0
0.0 0.0 1.0
1.0 0.0 1.0
0.0 1.0 1.0
1.0 1.0 1.0
"""


class TestParseCubeLut:
    def test_valid_lut(self) -> None:
        lut = parse_cube_lut(_VALID_2)
        assert lut.size == 2
        assert lut.title == "Test LUT"
        assert len(lut.entries) == 8
        assert lut.domain_min == (0.0, 0.0, 0.0)
        assert lut.domain_max == (1.0, 1.0, 1.0)

    def test_comments_and_blank_lines_ignored(self) -> None:
        text = "# a comment\n\n" + _VALID_2 + "\n# trailing comment\n"
        lut = parse_cube_lut(text)
        assert lut.size == 2

    def test_custom_domain(self) -> None:
        text = "LUT_3D_SIZE 2\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 2.0 2.0 2.0\n" + "\n".join(
            "0.0 0.0 0.0" for _ in range(8)
        )
        lut = parse_cube_lut(text)
        assert lut.domain_max == (2.0, 2.0, 2.0)

    def test_missing_size_header(self) -> None:
        with pytest.raises(CubeLutError, match="Missing LUT_3D_SIZE"):
            parse_cube_lut("0.0 0.0 0.0\n")

    def test_1d_lut_rejected(self) -> None:
        with pytest.raises(CubeLutError, match="1D LUTs"):
            parse_cube_lut("LUT_1D_SIZE 16\n")

    def test_size_out_of_range(self) -> None:
        with pytest.raises(CubeLutError, match="between 2 and 256"):
            parse_cube_lut("LUT_3D_SIZE 1\n")

    def test_wrong_row_count(self) -> None:
        with pytest.raises(CubeLutError, match="Expected 8 data rows"):
            parse_cube_lut("LUT_3D_SIZE 2\n0.0 0.0 0.0\n")

    def test_malformed_data_row(self) -> None:
        with pytest.raises(CubeLutError, match="Malformed data row"):
            parse_cube_lut("LUT_3D_SIZE 2\n0.0 0.0\n")

    def test_non_numeric_data_row(self) -> None:
        with pytest.raises(CubeLutError, match="Non-numeric data row"):
            parse_cube_lut("LUT_3D_SIZE 2\nred green blue\n")

    def test_malformed_size_line(self) -> None:
        with pytest.raises(CubeLutError, match="Malformed LUT_3D_SIZE"):
            parse_cube_lut("LUT_3D_SIZE not_a_number\n")


class TestLoadCubeLut:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(CubeLutError, match="not found"):
            load_cube_lut(tmp_path / "missing.cube")

    def test_loads_real_file(self, tmp_path: Path) -> None:
        p = tmp_path / "look.cube"
        p.write_text(_VALID_2)
        lut = load_cube_lut(p)
        assert lut.size == 2


class TestEscapeFfmpegFilterPath:
    def test_escapes_colon(self) -> None:
        assert escape_ffmpeg_filter_path("C:/luts/x.cube") == "C\\:/luts/x.cube"

    def test_escapes_backslash_and_quote(self) -> None:
        assert escape_ffmpeg_filter_path("a\\b'c") == "a\\\\b\\'c"

    def test_plain_path_unchanged(self) -> None:
        assert escape_ffmpeg_filter_path("/tmp/look.cube") == "/tmp/look.cube"
