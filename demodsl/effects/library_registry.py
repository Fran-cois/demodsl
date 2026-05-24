"""Effect library — registry that discovers and loads .effect.yaml presets.

Usage::

    from demodsl.effects.library_registry import EffectLibrary

    lib = EffectLibrary()
    lib.load_directory(Path("library"))
    effect = lib.get("lower_thirds/tech")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import yaml

from demodsl.models.library import LibraryEffect

logger = logging.getLogger(__name__)

EFFECT_FILE_SUFFIX = ".effect.yaml"

# Standard search paths (relative to project root)
_DEFAULT_DIRS: list[str] = [
    "library",
]
# User-level library
_USER_DIR = Path.home() / ".demodsl" / "library"


class LibraryLoadError(Exception):
    """Raised when a library effect file cannot be parsed."""


class EffectLibrary:
    """Registry of reusable effect presets.

    Scans one or more directories for ``.effect.yaml`` files and validates
    them into :class:`~demodsl.models.library.LibraryEffect` instances.
    """

    def __init__(self) -> None:
        self._effects: dict[str, LibraryEffect] = {}

    # ── Loading ──────────────────────────────────────────────────────────

    def load_directory(self, directory: Path) -> int:
        """Load all .effect.yaml files from *directory* (recursively).

        Returns the count of effects loaded. Logs warnings for invalid files.
        """
        if not directory.is_dir():
            return 0

        count = 0
        for path in sorted(directory.rglob(f"*{EFFECT_FILE_SUFFIX}")):
            try:
                self._load_file(path)
                count += 1
            except (LibraryLoadError, Exception) as exc:  # noqa: BLE001
                logger.warning("Skipping invalid library effect %s: %s", path, exc)
        return count

    def load_defaults(self, project_root: Path | None = None) -> int:
        """Load from default directories (project-local + user-level).

        Returns total number of effects loaded.
        """
        total = 0
        if project_root:
            for rel in _DEFAULT_DIRS:
                total += self.load_directory(project_root / rel)
        if _USER_DIR.is_dir():
            total += self.load_directory(_USER_DIR)
        return total

    def _load_file(self, path: Path) -> None:
        """Load a single .effect.yaml file."""
        text = path.read_text()
        raw = yaml.safe_load(text)
        if not isinstance(raw, dict):
            msg = f"Expected a mapping, got {type(raw).__name__}"
            raise LibraryLoadError(msg)

        try:
            effect = LibraryEffect(**raw)
        except Exception as exc:
            raise LibraryLoadError(str(exc)) from exc

        if effect.name in self._effects:
            logger.warning(
                "Library effect %r from %s overrides existing definition",
                effect.name,
                path,
            )
        self._effects[effect.name] = effect

    # ── Lookup ───────────────────────────────────────────────────────────

    def get(self, name: str) -> LibraryEffect | None:
        """Retrieve a library effect by name. Returns None if not found."""
        return self._effects.get(name)

    def list_all(self) -> list[LibraryEffect]:
        """Return all loaded effects sorted by name."""
        return sorted(self._effects.values(), key=lambda e: e.name)

    def list_by_tag(self, tag: str) -> list[LibraryEffect]:
        """Return effects matching a given tag."""
        return [e for e in self._effects.values() if tag in e.tags]

    def search(self, query: str) -> list[LibraryEffect]:
        """Simple text search across name, description, and tags."""
        q = query.lower()
        return [
            e
            for e in self._effects.values()
            if q in e.name.lower()
            or q in e.description.lower()
            or any(q in t.lower() for t in e.tags)
        ]

    @property
    def names(self) -> list[str]:
        """Sorted list of all registered effect names."""
        return sorted(self._effects.keys())

    def __len__(self) -> int:
        return len(self._effects)

    def __contains__(self, name: str) -> bool:
        return name in self._effects

    # ── Inheritance resolution ───────────────────────────────────────────

    def resolve_extends(self, effect: LibraryEffect, _chain: Sequence[str] = ()) -> LibraryEffect:
        """Resolve ``extends`` inheritance (deep merge parent → child).

        Raises LibraryLoadError on circular references.
        """
        if not effect.extends:
            return effect

        if effect.name in _chain:
            msg = f"Circular extends chain: {' → '.join([*_chain, effect.name])}"
            raise LibraryLoadError(msg)

        parent = self.get(effect.extends)
        if parent is None:
            msg = f"Effect {effect.name!r} extends unknown {effect.extends!r}"
            raise LibraryLoadError(msg)

        # Resolve parent first (recursive)
        parent = self.resolve_extends(parent, (*_chain, effect.name))

        # Merge: child overrides parent
        merged_params = {**parent.parameters, **effect.parameters}
        merged_layers = effect.layers if effect.layers else parent.layers
        merged_effects = effect.effects if effect.effects else parent.effects
        merged_tags = list(dict.fromkeys([*parent.tags, *effect.tags]))

        return LibraryEffect(
            name=effect.name,
            description=effect.description or parent.description,
            tags=merged_tags,
            parameters=merged_params,
            layers=merged_layers,
            effects=merged_effects,
            extends=None,  # fully resolved
        )
