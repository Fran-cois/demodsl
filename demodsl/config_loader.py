"""Safe YAML/JSON config loader with depth and node-count limits."""

from __future__ import annotations

import json
import logging
from pathlib import Path

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

    def compose_node(self, parent: yaml.Node | None, index: object) -> yaml.Node | None:  # type: ignore[override]
        self._depth += 1
        self._check_limits(self._depth)
        node = super().compose_node(parent, index)
        self._depth -= 1
        return node


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
        raise ConfigTooLargeError(
            f"Config file too large: {size} bytes (max {MAX_FILE_SIZE})"
        )

    text = path.read_text()

    if path.suffix.lower() == ".json":
        return json.loads(text)

    return yaml.load(text, Loader=_SafeCountingLoader)  # noqa: S506
