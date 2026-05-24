"""Safe YAML/JSON config loader with depth and node-count limits."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DEPTH = 50
MAX_NODES = 100_000


class ConfigTooLargeError(yaml.YAMLError):
    """Raised when the YAML document exceeds safe parsing limits."""


class _SafeCountingLoader(yaml.SafeLoader):
    """SafeLoader subclass that counts depth and total nodes."""

    _max_depth: int = MAX_DEPTH
    _max_nodes: int = MAX_NODES

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self._node_count = 0
        self._depth = 0

    def _check_limits(self, depth: int) -> None:
        self._node_count += 1
        if self._node_count > self._max_nodes:
            raise ConfigTooLargeError(
                f"YAML document exceeds maximum node count ({self._max_nodes})"
            )
        if depth > self._max_depth:
            raise ConfigTooLargeError(
                f"YAML document exceeds maximum nesting depth ({self._max_depth})"
            )

    def compose_node(self, parent: yaml.Node | None, index: object) -> yaml.Node | None:
        self._depth += 1
        self._check_limits(self._depth)
        node = super().compose_node(parent, index)
        self._depth -= 1
        return node


def _check_json_depth(obj: object, depth: int = 0) -> None:
    """Walk a JSON-decoded structure to enforce :data:`MAX_DEPTH`."""
    if depth > MAX_DEPTH:
        raise ConfigTooLargeError(f"JSON document exceeds maximum nesting depth ({MAX_DEPTH})")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_json_depth(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _check_json_depth(v, depth + 1)


def load_config(path: Path) -> dict:
    """Load and parse a YAML or JSON config file with safety limits.

    Raises:
        ConfigTooLargeError: If file size, depth, or node count exceeds limits.
        yaml.YAMLError: On malformed YAML.
        json.JSONDecodeError: On malformed JSON.
        FileNotFoundError: If the file does not exist.
    """
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ConfigTooLargeError(f"Config file too large: {size} bytes (max {MAX_FILE_SIZE})")

    text = path.read_text()

    if path.suffix.lower() == ".json":
        data = json.loads(text)
        _check_json_depth(data)
        return data

    return yaml.load(text, Loader=_SafeCountingLoader)  # noqa: S506


def load_config_with_library(path: Path) -> dict[str, Any]:
    """Load config and resolve any ``$use`` library references.

    This is the high-level entry point that combines YAML loading with
    effect library expansion. Use this instead of :func:`load_config` when
    you need library support.
    """
    from demodsl.effects.library_registry import EffectLibrary
    from demodsl.effects.library_resolver import resolve_library_refs

    raw = load_config(path)

    # Build library from project-local and user-level dirs
    library = EffectLibrary()
    project_root = _find_project_root(path.parent)
    library.load_defaults(project_root)

    # Resolve $use references
    if _has_use_refs(raw):
        resolve_library_refs(raw, library)

    return raw


def _find_project_root(start: Path) -> Path:
    """Walk up from *start* to find a directory containing pyproject.toml or library/."""
    current = start.resolve()
    for _ in range(10):
        if (current / "pyproject.toml").exists() or (current / "library").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return start


def _has_use_refs(obj: object) -> bool:
    """Quick check: does the config contain any $use keys?"""
    if isinstance(obj, dict):
        if "$use" in obj:
            return True
        return any(_has_use_refs(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_use_refs(v) for v in obj)
    return False
