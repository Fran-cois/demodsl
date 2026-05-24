"""Tests for selector-based anchor templating."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from demodsl.config_loader import load_config_with_library
from demodsl.effects.anchor_resolver import (
    AnchorResolveError,
    apply_anchor_templates,
    extract_anchors_spec,
    resolve_anchors,
)


class TestExtractAnchorsSpec:
    def test_returns_none_when_absent(self):
        raw = {"metadata": {"name": "x"}}
        assert extract_anchors_spec(raw) is None
        assert "anchors" not in raw

    def test_pops_anchors_block(self):
        raw = {"anchors": {"btn": {"x": 10, "y": 20}}, "metadata": {"name": "x"}}
        spec = extract_anchors_spec(raw)
        assert spec == {"btn": {"x": 10, "y": 20}}
        assert "anchors" not in raw  # mutated

    def test_rejects_non_mapping(self):
        with pytest.raises(AnchorResolveError):
            extract_anchors_spec({"anchors": ["bad"]})


class TestManualAnchors:
    def test_x_y_only(self):
        out = resolve_anchors({"btn": {"x": 100, "y": 200}}, scenarios=None)
        c = out["btn"]
        assert c["x"] == 100 and c["y"] == 200
        assert c["w"] == 0 and c["h"] == 0
        assert c["cx"] == 100 and c["cy"] == 200

    def test_x_y_w_h(self):
        out = resolve_anchors({"btn": {"x": 100, "y": 200, "w": 50, "h": 30}}, scenarios=None)
        c = out["btn"]
        assert c["cx"] == 125 and c["cy"] == 215
        assert c["right"] == 150 and c["bottom"] == 230

    def test_missing_coords_raises(self):
        with pytest.raises(AnchorResolveError):
            resolve_anchors({"btn": {"y": 10}}, scenarios=None)


class TestApplyAnchorTemplates:
    def test_replaces_whole_string_with_native_value(self):
        anchors = {
            "btn": {
                "x": 100,
                "y": 200,
                "w": 40,
                "h": 20,
                "cx": 120,
                "cy": 210,
                "left": 100,
                "top": 200,
                "right": 140,
                "bottom": 220,
            }
        }
        cfg = {"layers": [{"position": ["{{ anchors.btn.cx }}", "{{ anchors.btn.cy }}"]}]}
        out = apply_anchor_templates(cfg, anchors)
        assert out["layers"][0]["position"] == [120, 210]

    def test_supports_arithmetic(self):
        anchors = {
            "btn": {
                "x": 0,
                "y": 0,
                "w": 0,
                "h": 0,
                "cx": 100,
                "cy": 50,
                "left": 0,
                "top": 0,
                "right": 0,
                "bottom": 0,
            }
        }
        cfg = {"v": "{{ anchors.btn.cx + 20 }}"}
        out = apply_anchor_templates(cfg, anchors)
        assert out["v"] == 120

    def test_leaves_non_anchor_templates(self):
        cfg = {"v": "{{ x + 1 }}"}
        out = apply_anchor_templates(cfg, {})
        assert out["v"] == "{{ x + 1 }}"

    def test_unknown_anchor_raises(self):
        cfg = {"v": "{{ anchors.missing.cx }}"}
        with pytest.raises(AnchorResolveError):
            apply_anchor_templates(cfg, {})


class TestIntegrationWithLibrary:
    """End-to-end: anchors + $use expansion via load_config_with_library."""

    def test_manual_anchor_drives_callout_position(self, tmp_path: Path):
        # Place tmp YAML inside the repo so _find_project_root locates library/.
        repo_root = Path(__file__).resolve().parent.parent
        scratch = repo_root / "tests" / ".tmp_anchor_demo"
        scratch.mkdir(exist_ok=True)
        try:
            cfg = textwrap.dedent("""
            metadata:
              name: anchor-demo
              duration: 5
            anchors:
              hero_btn:
                x: 800
                y: 400
                w: 200
                h: 60
            scenarios:
              - name: s
                url: https://example.com
                steps:
                  - action: navigate
                    wait: 1
            timeline:
              layers:
                - $use: callouts/circle_highlight
                  $params:
                    x: "{{ anchors.hero_btn.cx }}"
                    y: "{{ anchors.hero_btn.cy }}"
                    radius: 90
        """).strip()
            p = scratch / "demo.yaml"
            p.write_text(cfg)
            raw = load_config_with_library(p)

            # The circle_highlight preset expands into shape layers — check the
            # first layer's transform position has the anchor center (900, 430).
            layers = raw["timeline"]["layers"]
            assert layers, "library expansion produced no layers"
            first = layers[0]
            pos = first["transform"]["position"]
            assert pos == [900, 430]
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)

    def test_anchor_shortcut_autofills_x_y(self):
        """`anchor: name` in $params auto-fills declared x/y from the anchor."""
        repo_root = Path(__file__).resolve().parent.parent
        scratch = repo_root / "tests" / ".tmp_anchor_shortcut"
        scratch.mkdir(exist_ok=True)
        try:
            cfg = textwrap.dedent("""
                metadata:
                  name: anchor-shortcut
                  duration: 5
                anchors:
                  cta_btn:
                    x: 700
                    y: 300
                    w: 200
                    h: 80
                scenarios:
                  - name: s
                    url: https://example.com
                    steps:
                      - action: navigate
                        wait: 1
                timeline:
                  layers:
                    - $use: callouts/circle_highlight
                      $params:
                        anchor: cta_btn
                        radius: 100
            """).strip()
            p = scratch / "demo.yaml"
            p.write_text(cfg)
            raw = load_config_with_library(p)

            layers = raw["timeline"]["layers"]
            assert layers, "no layers expanded"
            # Anchor cta_btn: cx=800, cy=340 → first layer position must match.
            pos = layers[0]["transform"]["position"]
            assert pos == [800, 340]
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)

    def test_anchor_shortcut_unknown_name_raises(self):
        repo_root = Path(__file__).resolve().parent.parent
        scratch = repo_root / "tests" / ".tmp_anchor_shortcut_bad"
        scratch.mkdir(exist_ok=True)
        try:
            cfg = textwrap.dedent("""
                metadata:
                  name: bad
                anchors:
                  btn: { x: 0, y: 0 }
                scenarios:
                  - name: s
                    url: https://example.com
                timeline:
                  layers:
                    - $use: callouts/circle_highlight
                      $params:
                        anchor: typo
            """).strip()
            p = scratch / "demo.yaml"
            p.write_text(cfg)
            with pytest.raises(Exception, match="unknown anchor"):
                load_config_with_library(p)
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)
