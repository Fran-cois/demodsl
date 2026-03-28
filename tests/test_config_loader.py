"""Tests for demodsl.config_loader — YAML bomb protection."""

from __future__ import annotations

from pathlib import Path

import pytest

from demodsl.config_loader import (
    MAX_DEPTH,
    MAX_FILE_SIZE,
    MAX_NODES,
    ConfigTooLargeError,
    load_config,
)


@pytest.fixture()
def tmp_yaml(tmp_path: Path):
    """Helper: write content to a temp .yaml file and return its path."""

    def _write(content: str, name: str = "test.yaml") -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    return _write


class TestLoadConfigBasic:
    def test_valid_yaml(self, tmp_yaml) -> None:
        result = load_config(tmp_yaml("metadata:\n  title: hello"))
        assert result == {"metadata": {"title": "hello"}}

    def test_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.json"
        p.write_text('{"metadata": {"title": "hello"}}')
        result = load_config(p)
        assert result == {"metadata": {"title": "hello"}}

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/file.yaml"))


class TestYAMLBombProtection:
    def test_rejects_oversized_file(self, tmp_path: Path) -> None:
        p = tmp_path / "big.yaml"
        p.write_text("a" * (MAX_FILE_SIZE + 1))
        with pytest.raises(ConfigTooLargeError, match="too large"):
            load_config(p)

    def test_rejects_deep_nesting(self, tmp_yaml) -> None:
        # Build a YAML with nesting deeper than MAX_DEPTH
        lines = []
        for i in range(MAX_DEPTH + 5):
            lines.append("  " * i + f"k{i}:")
        lines.append("  " * (MAX_DEPTH + 5) + "val")
        content = "\n".join(lines)
        with pytest.raises(ConfigTooLargeError, match="nesting depth"):
            load_config(tmp_yaml(content))

    def test_accepts_normal_depth(self, tmp_yaml) -> None:
        # 10 levels is fine
        lines = []
        for i in range(10):
            lines.append("  " * i + f"k{i}:")
        lines.append("  " * 10 + "val")
        result = load_config(tmp_yaml("\n".join(lines)))
        assert isinstance(result, dict)

    def test_rejects_excessive_nodes(self, tmp_yaml) -> None:
        # Create a flat mapping with more keys than MAX_NODES
        # Use a list of scalars for efficiency
        items = "\n".join(f"- item{i}" for i in range(MAX_NODES + 10))
        content = f"data:\n{items}"
        with pytest.raises(ConfigTooLargeError, match="node count"):
            load_config(tmp_yaml(content))
