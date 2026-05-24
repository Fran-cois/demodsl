"""Tests for the effect library system (models, registry, resolver)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from demodsl.effects.library_registry import EffectLibrary, LibraryLoadError
from demodsl.effects.library_resolver import (
    LibraryResolveError,
    _interpolate,
    _safe_eval,
    resolve_library_refs,
)
from demodsl.models.library import LibraryEffect, LibraryParam

# ── Model tests ──────────────────────────────────────────────────────────────


class TestLibraryParam:
    def test_required_param(self):
        p = LibraryParam(type="string")
        assert p.required is True

    def test_optional_param(self):
        p = LibraryParam(type="number", default=42)
        assert p.required is False


class TestLibraryEffect:
    def test_minimal(self):
        e = LibraryEffect(name="test/simple", layers=[{"id": "x", "type": "text"}])
        assert e.name == "test/simple"
        assert e.tags == []
        assert e.extends is None

    def test_with_params(self):
        e = LibraryEffect(
            name="my-effect",
            parameters={"color": LibraryParam(type="color", default="#FFF")},
            effects=[{"type": "glow", "color": "{{ color }}"}],
        )
        assert "color" in e.parameters
        assert e.parameters["color"].default == "#FFF"

    def test_invalid_name(self):
        with pytest.raises(Exception):
            LibraryEffect(name="has spaces!", layers=[])

    def test_valid_names(self):
        for name in ["simple", "lower_thirds/tech", "my-effect", "cam/dolly_orbit"]:
            e = LibraryEffect(name=name, layers=[])
            assert e.name == name


# ── Registry tests ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_library(tmp_path: Path) -> Path:
    """Create a temp library directory with test effect files."""
    d = tmp_path / "library" / "test"
    d.mkdir(parents=True)

    # Valid effect
    (d / "glow_fade.effect.yaml").write_text(
        yaml.dump(
            {
                "name": "test/glow_fade",
                "description": "Glow + fade combo",
                "tags": ["glow", "fade"],
                "parameters": {
                    "color": {"type": "color", "default": "#FF0000"},
                    "duration": {"type": "number", "default": 2.0},
                },
                "effects": [
                    {"type": "glow", "color": "{{ color }}"},
                    {"type": "fade_in", "duration": "{{ duration }}"},
                ],
            }
        )
    )

    # Effect with layers
    (d / "title_card.effect.yaml").write_text(
        yaml.dump(
            {
                "name": "test/title_card",
                "tags": ["text"],
                "parameters": {
                    "title": {"type": "string"},
                    "start": {"type": "number", "default": 0},
                },
                "layers": [
                    {
                        "id": "title",
                        "type": "text",
                        "content": "{{ title }}",
                        "start": "{{ start }}",
                        "duration": 3.0,
                    }
                ],
            }
        )
    )

    # Effect with extends
    (d / "parent.effect.yaml").write_text(
        yaml.dump(
            {
                "name": "test/parent",
                "tags": ["base"],
                "parameters": {
                    "color": {"type": "color", "default": "#FFF"},
                    "size": {"type": "number", "default": 42},
                },
                "layers": [
                    {"id": "bg", "type": "shape", "fill": "{{ color }}", "width": "{{ size }}"}
                ],
            }
        )
    )

    (d / "child.effect.yaml").write_text(
        yaml.dump(
            {
                "name": "test/child",
                "extends": "test/parent",
                "tags": ["derived"],
                "parameters": {
                    "color": {"type": "color", "default": "#000"},
                },
            }
        )
    )

    # Invalid file
    (d / "broken.effect.yaml").write_text("not: valid: yaml: [")

    return tmp_path / "library"


class TestEffectLibrary:
    def test_load_directory(self, tmp_library: Path):
        lib = EffectLibrary()
        count = lib.load_directory(tmp_library)
        # broken file skipped, 4 valid loaded
        assert count == 4
        assert "test/glow_fade" in lib
        assert "test/title_card" in lib
        assert "test/parent" in lib
        assert "test/child" in lib

    def test_get(self, tmp_library: Path):
        lib = EffectLibrary()
        lib.load_directory(tmp_library)
        e = lib.get("test/glow_fade")
        assert e is not None
        assert e.description == "Glow + fade combo"

    def test_get_missing(self, tmp_library: Path):
        lib = EffectLibrary()
        lib.load_directory(tmp_library)
        assert lib.get("nonexistent") is None

    def test_list_by_tag(self, tmp_library: Path):
        lib = EffectLibrary()
        lib.load_directory(tmp_library)
        glow = lib.list_by_tag("glow")
        assert len(glow) == 1
        assert glow[0].name == "test/glow_fade"

    def test_search(self, tmp_library: Path):
        lib = EffectLibrary()
        lib.load_directory(tmp_library)
        results = lib.search("title")
        assert any(e.name == "test/title_card" for e in results)

    def test_resolve_extends(self, tmp_library: Path):
        lib = EffectLibrary()
        lib.load_directory(tmp_library)
        child = lib.get("test/child")
        resolved = lib.resolve_extends(child)
        # Inherits size from parent, overrides color default
        assert "size" in resolved.parameters
        assert "color" in resolved.parameters
        assert resolved.parameters["color"].default == "#000"
        # Inherits layers from parent
        assert len(resolved.layers) == 1
        assert resolved.tags == ["base", "derived"]

    def test_circular_extends(self, tmp_path: Path):
        d = tmp_path / "lib"
        d.mkdir()
        (d / "a.effect.yaml").write_text(yaml.dump({"name": "a", "extends": "b", "effects": []}))
        (d / "b.effect.yaml").write_text(yaml.dump({"name": "b", "extends": "a", "effects": []}))
        lib = EffectLibrary()
        lib.load_directory(d)
        a = lib.get("a")
        with pytest.raises(LibraryLoadError, match="Circular"):
            lib.resolve_extends(a)

    def test_names(self, tmp_library: Path):
        lib = EffectLibrary()
        lib.load_directory(tmp_library)
        assert lib.names == sorted(lib.names)
        assert len(lib) == 4


# ── Resolver tests ───────────────────────────────────────────────────────────


class TestInterpolation:
    def test_simple_string(self):
        result = _interpolate("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_numeric_expression(self):
        result = _interpolate("{{ x + 1 }}", {"x": 5})
        assert result == 6

    def test_nested_dict(self):
        obj = {"color": "{{ c }}", "items": [1, "{{ n }}"]}
        result = _interpolate(obj, {"c": "#F00", "n": 42})
        assert result == {"color": "#F00", "items": [1, 42]}

    def test_passthrough_non_template(self):
        assert _interpolate(42, {}) == 42
        assert _interpolate([1, 2], {}) == [1, 2]
        assert _interpolate(None, {}) is None


class TestSafeEval:
    def test_arithmetic(self):
        assert _safe_eval("x + y", {"x": 3, "y": 4}) == 7
        assert _safe_eval("x * 2 - 1", {"x": 5}) == 9

    def test_builtins(self):
        assert _safe_eval("max(a, b)", {"a": 3, "b": 7}) == 7
        assert _safe_eval("round(x, 1)", {"x": 3.14159}) == 3.1
        assert _safe_eval("abs(n)", {"n": -5}) == 5

    def test_division(self):
        assert _safe_eval("960 / 1920", {}) == 0.5

    def test_string_concat(self):
        assert _safe_eval("prefix + '_text'", {"prefix": "hello"}) == "hello_text"

    def test_forbidden_import(self):
        with pytest.raises(LibraryResolveError):
            _safe_eval("__import__('os')", {})

    def test_unknown_name(self):
        with pytest.raises(LibraryResolveError):
            _safe_eval("undefined_var", {})


class TestResolveLibraryRefs:
    def _make_lib(self) -> EffectLibrary:
        lib = EffectLibrary()
        # Manually register effects for testing
        lib._effects["my/glow"] = LibraryEffect(
            name="my/glow",
            parameters={"color": LibraryParam(type="color", default="#FFF")},
            effects=[{"type": "glow", "color": "{{ color }}"}],
        )
        lib._effects["my/title"] = LibraryEffect(
            name="my/title",
            parameters={
                "text": LibraryParam(type="string"),
                "start": LibraryParam(type="number", default=0),
            },
            layers=[
                {
                    "id": "title",
                    "type": "text",
                    "content": "{{ text }}",
                    "start": "{{ start }}",
                }
            ],
        )
        return lib

    def test_resolve_step_effects(self):
        lib = self._make_lib()
        config: dict[str, Any] = {
            "steps": [
                {
                    "action": "navigate",
                    "effects": [
                        {"$use": "my/glow", "$params": {"color": "#00FF00"}},
                        {"type": "confetti"},
                    ],
                }
            ]
        }
        resolve_library_refs(config, lib)
        effects = config["steps"][0]["effects"]
        assert len(effects) == 2
        assert effects[0] == {"type": "glow", "color": "#00FF00"}
        assert effects[1] == {"type": "confetti"}

    def test_resolve_timeline_layers(self):
        lib = self._make_lib()
        config: dict[str, Any] = {
            "timeline": {
                "layers": [
                    {"$use": "my/title", "$params": {"text": "Hello", "start": 2.5}},
                ]
            }
        }
        resolve_library_refs(config, lib)
        layers = config["timeline"]["layers"]
        assert len(layers) == 1
        assert layers[0]["content"] == "Hello"
        assert layers[0]["start"] == 2.5

    def test_default_params(self):
        lib = self._make_lib()
        config: dict[str, Any] = {"steps": [{"action": "click", "effects": [{"$use": "my/glow"}]}]}
        resolve_library_refs(config, lib)
        assert config["steps"][0]["effects"][0]["color"] == "#FFF"

    def test_missing_required_param(self):
        lib = self._make_lib()
        config: dict[str, Any] = {
            "timeline": {"layers": [{"$use": "my/title"}]}  # missing 'text'
        }
        with pytest.raises(LibraryResolveError, match="Missing required"):
            resolve_library_refs(config, lib)

    def test_unknown_library_effect(self):
        lib = self._make_lib()
        config: dict[str, Any] = {"steps": [{"action": "x", "effects": [{"$use": "nonexistent"}]}]}
        with pytest.raises(LibraryResolveError, match="Unknown"):
            resolve_library_refs(config, lib)

    def test_context_mismatch_layers_in_effects(self):
        lib = self._make_lib()
        config: dict[str, Any] = {
            "steps": [{"action": "x", "effects": [{"$use": "my/title", "$params": {"text": "X"}}]}]
        }
        with pytest.raises(LibraryResolveError, match="timeline layers"):
            resolve_library_refs(config, lib)

    def test_inline_overrides(self):
        lib = self._make_lib()
        config: dict[str, Any] = {
            "timeline": {
                "layers": [
                    {
                        "$use": "my/title",
                        "$params": {"text": "Override"},
                        "duration": 5.0,
                    }
                ]
            }
        }
        resolve_library_refs(config, lib)
        layer = config["timeline"]["layers"][0]
        assert layer["content"] == "Override"
        assert layer["duration"] == 5.0

    def test_no_use_refs_passthrough(self):
        lib = self._make_lib()
        config: dict[str, Any] = {"steps": [{"action": "click", "effects": [{"type": "confetti"}]}]}
        resolve_library_refs(config, lib)
        assert config["steps"][0]["effects"] == [{"type": "confetti"}]

    def test_multi_scenario(self):
        lib = self._make_lib()
        config: dict[str, Any] = {
            "scenarios": [
                {
                    "steps": [
                        {"action": "x", "effects": [{"$use": "my/glow"}]},
                    ]
                }
            ]
        }
        resolve_library_refs(config, lib)
        assert config["scenarios"][0]["steps"][0]["effects"][0]["type"] == "glow"


# ── Integration: load_config_with_library ────────────────────────────────────


class TestLoadConfigWithLibrary:
    def test_full_flow(self, tmp_path: Path):
        from demodsl.config_loader import load_config_with_library

        # Create library
        lib_dir = tmp_path / "library" / "test"
        lib_dir.mkdir(parents=True)
        (lib_dir / "fade.effect.yaml").write_text(
            yaml.dump(
                {
                    "name": "test/fade",
                    "parameters": {"dur": {"type": "number", "default": 1.5}},
                    "effects": [{"type": "fade_in", "duration": "{{ dur }}"}],
                }
            )
        )

        # Create config that uses library
        config_file = tmp_path / "demo.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "url": "https://example.com",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "effects": [{"$use": "test/fade", "$params": {"dur": 3.0}}],
                        }
                    ],
                }
            )
        )

        raw = load_config_with_library(config_file)
        # $use should be resolved
        effects = raw["steps"][0]["effects"]
        assert effects[0] == {"type": "fade_in", "duration": 3.0}

    def test_no_library_refs(self, tmp_path: Path):
        from demodsl.config_loader import load_config_with_library

        config_file = tmp_path / "simple.yaml"
        config_file.write_text(yaml.dump({"url": "https://x.com", "steps": []}))

        raw = load_config_with_library(config_file)
        assert raw["url"] == "https://x.com"
