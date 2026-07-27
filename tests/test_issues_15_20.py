"""Regression tests for GitHub issues #15-#20 (agent-authoring toolchain).

Everything here is browser-free: the modules are designed so the parts that
matter (manifest derivation, diagnostics, pacing, locator collection,
suggestion ranking, frame warnings, beat expansion) are pure functions.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from demodsl.models import DemoConfig, Step


def _config(steps: list[dict], **scenario_extra) -> DemoConfig:
    return DemoConfig(
        **{
            "metadata": {"title": "T", "version": "1.0"},
            "scenarios": [
                {
                    "name": "S",
                    "url": "https://example.com",
                    "steps": steps,
                    **scenario_extra,
                }
            ],
        }
    )


# ── Issue #15 — machine-readable capability manifest ─────────────────────────


class TestIssue15Capabilities:
    def test_manifest_covers_every_action_and_effect(self):
        from demodsl.capabilities import build_manifest
        from demodsl.models.effects import EFFECT_VALID_PARAMS

        manifest = build_manifest()
        names = {a["name"] for a in manifest["actions"]}
        assert {"navigate", "hover", "click", "camera", "os_setting"} <= names

        effect_names = {e["name"] for e in manifest["effects"]}
        assert set(EFFECT_VALID_PARAMS) <= effect_names

    def test_required_fields_match_the_model(self):
        from demodsl.capabilities import build_manifest

        by_name = {a["name"]: a for a in build_manifest()["actions"]}
        assert by_name["hover"]["requires"] == ["locator"]
        assert by_name["navigate"]["requires"] == ["url"]
        assert set(by_name["type"]["requires"]) == {"locator", "value"}
        # A required field is never repeated in `optional`.
        for action in by_name.values():
            assert not set(action["requires"]) & set(action["optional"])

    def test_effect_params_carry_types_and_bounds(self):
        from demodsl.capabilities import build_manifest

        effects = {e["name"]: e for e in build_manifest()["effects"]}
        annotation = effects["animated_annotation"]
        assert annotation["auto_anchored"] is True
        assert annotation["params"]["color"]["type"] == "css_color"
        assert annotation["params"]["radius"]["exclusive_min"] == 0
        assert annotation["recommended_duration"] == [2.0, 10.0]
        # Non-pointing effects are not advertised as auto-anchored.
        assert effects["confetti"]["auto_anchored"] is False

    def test_manifest_is_json_serialisable_and_versioned(self):
        from demodsl import __version__
        from demodsl.capabilities import build_manifest

        manifest = build_manifest()
        assert manifest["version"] == __version__
        json.dumps(manifest)  # must not raise

    def test_json_schema_is_emitted(self):
        from demodsl.capabilities import json_schema

        schema = json_schema()
        assert "properties" in schema
        assert "scenarios" in schema["properties"]

    def test_diagnostic_codes_are_published(self):
        from demodsl.capabilities import build_manifest
        from demodsl.diagnostics import DIAGNOSTIC_CODES

        assert set(build_manifest()["diagnostic_codes"]) == set(DIAGNOSTIC_CODES)


# ── Issue #16 — `demodsl probe` ──────────────────────────────────────────────


class TestIssue16Probe:
    def test_collects_step_drag_and_camera_targets(self):
        from demodsl.probe import collect_targets

        config = _config(
            [
                {"action": "navigate", "url": "https://example.com"},
                {
                    "action": "hover",
                    "locator": {"type": "css", "value": "h1"},
                    "camera": {"zoom": 1.4, "target": {"type": "css", "value": ".hero"}},
                },
                {
                    "action": "drag",
                    "locator": {"type": "css", "value": ".a"},
                    "target_locator": {"type": "css", "value": ".b"},
                },
            ]
        )
        targets = collect_targets(config)
        kinds = [(t.index, t.kind, t.locator.value) for t in targets]
        assert (1, "locator", "h1") in kinds
        assert (1, "camera.target", ".hero") in kinds
        assert (2, "target_locator", ".b") in kinds

    def test_target_url_follows_navigation(self):
        from demodsl.probe import collect_targets

        config = _config(
            [
                {"action": "navigate", "url": "https://example.com"},
                {"action": "hover", "locator": {"type": "css", "value": "h1"}},
                {"action": "navigate", "url": "https://example.com/pricing"},
                {"action": "hover", "locator": {"type": "css", "value": ".plan"}},
            ]
        )
        by_value = {t.locator.value: t.url for t in collect_targets(config)}
        assert by_value["h1"] == "https://example.com"
        assert by_value[".plan"] == "https://example.com/pricing"

    def test_mobile_scenarios_are_not_probed(self):
        from demodsl.probe import collect_targets

        config = DemoConfig(
            **{
                "metadata": {"title": "T", "version": "1.0"},
                "scenarios": [
                    {
                        "name": "S",
                        "mobile": {
                            "platform": "ios",
                            "device_name": "iPhone 15",
                            "bundle_id": "com.example.app",
                        },
                        "steps": [{"action": "tap", "locator": {"type": "id", "value": "ok"}}],
                    }
                ],
            }
        )
        assert collect_targets(config) == []

    def test_suggest_ranks_near_matches(self):
        from demodsl.probe import suggest

        elements = [
            {"text": "Pricing", "locator": {"value": "nav a"}, "prominence": 0.7},
            {"text": "Careers", "locator": {"value": "footer a"}, "prominence": 0.1},
        ]
        out = suggest("Pricing — see plans", elements)
        assert out[0]["value"] == "Pricing"
        assert out[0]["similarity"] >= 0.5

    def test_suggest_falls_back_to_prominent_elements(self):
        from demodsl.probe import suggest

        elements = [
            {"text": "Zebra", "locator": {"value": "a.z"}, "is_link": True},
            {"text": "Quokka", "locator": {"value": "a.q"}, "is_link": True},
        ]
        out = suggest("completely unrelated label", elements)
        assert out, "an agent must always get something real to re-target"
        assert all(entry.get("fallback") for entry in out)


# ── Issue #17 — `demodsl storyboard` ─────────────────────────────────────────


class TestIssue17Storyboard:
    def test_offscreen_mark_is_flagged(self):
        from demodsl.storyboard import frame_warnings

        assert any(
            "outside the frame" in w for w in frame_warnings((1.4, 0.5), effects=["hand_mark"])
        )

    def test_mark_under_the_subtitle_band_is_flagged(self):
        from demodsl.storyboard import frame_warnings

        warnings_ = frame_warnings((0.5, 0.95), narration="A line of narration.")
        assert any("subtitle band" in w for w in warnings_)

    def test_two_beats_marking_the_same_region_is_flagged(self):
        from demodsl.storyboard import frame_warnings

        warnings_ = frame_warnings((0.50, 0.50), previous_anchor=(0.51, 0.49))
        assert any("same region" in w for w in warnings_)

    def test_pointing_effect_without_anchor_is_flagged(self):
        from demodsl.storyboard import frame_warnings

        assert frame_warnings(None, effects=["animated_annotation"]) == [
            "pointing effect without a resolved anchor"
        ]

    def test_clean_frame_has_no_warning(self):
        from demodsl.storyboard import frame_warnings

        assert frame_warnings((0.5, 0.4), narration="Short line.", wait=8.0) == []

    def test_contact_sheet_tiles_every_frame(self, tmp_path: Path):
        from PIL import Image

        from demodsl.storyboard import contact_sheet

        frames = []
        for i in range(5):
            path = tmp_path / f"step-{i:03d}.png"
            Image.new("RGB", (1920, 1080), (i * 20, 0, 0)).save(path)
            frames.append(path)
        sheet = contact_sheet(frames, tmp_path / "storyboard.png", columns=4, width=100)
        with Image.open(sheet) as img:
            assert img.width == 400  # 4 columns
            assert img.height == 2 * int(1080 * 100 / 1920)  # 2 rows


# ── Issue #18 — structured diagnostics ───────────────────────────────────────


class TestIssue18Diagnostics:
    def test_scroll_while_zoomed_yields_code_path_and_fix(self):
        from demodsl.diagnostics import diagnose

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            config = _config(
                [
                    {"action": "navigate", "url": "https://example.com"},
                    {
                        "action": "hover",
                        "locator": {"type": "css", "value": "h1"},
                        "camera": {"zoom": 1.55},
                    },
                    {"action": "scroll", "direction": "down", "pixels": 400},
                ]
            )
        found = [d for d in diagnose(config) if d.code == "camera.scroll_while_zoomed"]
        assert found, "the scroll-while-zoomed error must be reported"
        diag = found[0]
        assert diag.severity == "error"
        assert diag.path == "scenarios[0].steps[2]"
        assert diag.fix == {
            "op": "insert_before",
            "path": "scenarios[0].steps[2]",
            "value": {"action": "camera_reset", "camera": {"reset": True}},
        }

    def test_short_canvas_effect_is_warned_with_a_fix(self):
        from demodsl.diagnostics import diagnose

        config = _config(
            [
                {
                    "action": "pause",
                    "wait": 3.0,
                    "effects": [{"type": "confetti", "duration": 1.2}],
                }
            ]
        )
        diag = next(d for d in diagnose(config) if d.code == "effect.duration_below_threshold")
        assert diag.severity == "warn"
        assert diag.path == "scenarios[0].steps[0].effects[0]"
        assert diag.fix["op"] == "set"
        assert diag.fix["value"] == 2.0

    def test_narration_collision_suggests_a_wait(self):
        from demodsl.diagnostics import diagnose

        long_line = " ".join(["word"] * 40)
        config = _config(
            [
                {"action": "pause", "narration": long_line, "wait": 2.0},
                {"action": "pause", "narration": "Second.", "wait": 3.0},
            ]
        )
        diag = next(d for d in diagnose(config) if d.code == "narration.collision")
        assert diag.fix["path"] == "scenarios[0].steps[0].wait"
        assert diag.fix["value"] > 2.0

    def test_parse_errors_become_diagnostics_not_tracebacks(self):
        from demodsl.diagnostics import diagnose_raw

        diagnostics, config = diagnose_raw(
            {
                "metadata": {"title": "T", "version": "1.0"},
                "scenarios": [
                    {"name": "S", "steps": [{"action": "click"}]}  # missing locator
                ],
            }
        )
        assert config is None
        assert diagnostics
        assert all(d.code == "config.parse_error" for d in diagnostics)
        assert diagnostics[0].path.startswith("scenarios[0]")

    def test_every_emitted_code_is_declared(self):
        from demodsl.diagnostics import DIAGNOSTIC_CODES, diagnose

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            config = _config(
                [
                    {
                        "action": "hover",
                        "locator": {"type": "text", "value": "A very long label — with an em dash"},
                        "wait": 6.0,
                        "camera": {"zoom": 3.4},
                        "effects": [
                            {"type": "confetti", "duration": 0.5},
                            {"type": "sparkle", "duration": 3.0},
                            {"type": "glow", "color": "#fff"},
                            {"type": "ripple"},
                        ],
                    }
                ]
            )
        codes = {d.code for d in diagnose(config)}
        assert codes, "the deliberately bad step must produce diagnostics"
        assert codes <= DIAGNOSTIC_CODES

    def test_diagnostics_serialise_without_empty_keys(self):
        from demodsl.diagnostics import diagnose

        config = _config(
            [
                {
                    "action": "pause",
                    "wait": 3.0,
                    "effects": [{"type": "confetti", "duration": 1.0}],
                }
            ]
        )
        payload = [d.to_dict() for d in diagnose(config)]
        json.dumps(payload)
        for entry in payload:
            assert "meta" not in entry or entry["meta"]


# ── Issue #19 — `demodsl estimate` ───────────────────────────────────────────


class TestIssue19Estimate:
    def test_spoken_seconds_scales_with_words(self):
        from demodsl.estimate import spoken_seconds

        short = spoken_seconds("Three little words")
        long = spoken_seconds(" ".join(["word"] * 40))
        assert 0 < short < long
        assert spoken_seconds("") == 0.0

    def test_engine_changes_the_duration(self):
        from demodsl.estimate import spoken_seconds

        text = " ".join(["word"] * 30)
        assert spoken_seconds(text, engine="espeak") < spoken_seconds(text, engine="coqui")

    def test_speed_shortens_the_duration(self):
        from demodsl.estimate import spoken_seconds

        text = " ".join(["word"] * 30)
        assert spoken_seconds(text, speed=1.5) < spoken_seconds(text, speed=1.0)

    def test_report_flags_too_short_and_too_long_waits(self):
        from demodsl.estimate import estimate_config

        config = _config(
            [
                {"action": "pause", "narration": " ".join(["word"] * 30), "wait": 3.0},
                {"action": "pause", "narration": "Short line.", "wait": 20.0},
                {"action": "pause", "wait": 1.0},
            ]
        )
        report = estimate_config(config)
        assert report["mode"] == "modelled"
        assert [s["verdict"] for s in report["steps"]] == ["too_short", "too_long"]
        assert report["steps"][0]["suggested_wait"] > 3.0
        assert report["total_seconds"] > 0

    def test_apply_fix_rewrites_the_waits(self):
        from demodsl.estimate import apply_fix, estimate_config

        raw = {
            "metadata": {"title": "T", "version": "1.0"},
            "scenarios": [
                {
                    "name": "S",
                    "url": "https://example.com",
                    "steps": [
                        {"action": "pause", "narration": " ".join(["word"] * 30), "wait": 3.0},
                        {"action": "pause", "narration": "Short.", "wait": 1.1},
                    ],
                }
            ],
        }
        report = estimate_config(DemoConfig(**raw))
        changed = apply_fix(raw, report)
        assert changed == 1
        assert raw["scenarios"][0]["steps"][0]["wait"] > 3.0
        assert raw["scenarios"][0]["steps"][1]["wait"] == 1.1


# ── Issue #20 — semantic `beat:` step ────────────────────────────────────────


class TestIssue20Beat:
    def test_shorthand_role_expands_to_camera_effects_and_wait(self):
        step = Step(
            **{
                "beat": "cta",
                "locator": {"type": "text", "value": "Start free"},
                "narration": "One clear call to action seals the pitch.",
            }
        )
        assert step.action == "hover"
        assert step.camera is not None and step.camera.zoom > 1.0
        assert [e.type for e in step.effects or []] == ["callout_arrow", "zoom_pulse"]
        assert step.wait and step.wait > 0

    def test_sentiment_adds_the_reviewer_verdict_mark(self):
        step = Step(
            **{
                "beat": {"role": "proof", "sentiment": "good", "note": "4.9/5"},
                "locator": {"type": "css", "value": ".rating"},
                "narration": "Users love it.",
            }
        )
        types = [e.type for e in step.effects or []]
        assert "hand_mark" in types
        assert next(e for e in step.effects if e.type == "hand_mark").style == "check"
        assert next(e for e in step.effects if e.type == "animated_annotation").text == "4.9/5"

    def test_hero_role_frames_wider_than_an_argument(self):
        hero = Step(
            **{"beat": "hero", "locator": {"type": "css", "value": "h1"}, "narration": "Hi."}
        )
        argument = Step(
            **{"beat": "argument", "locator": {"type": "css", "value": "p"}, "narration": "Hi."}
        )
        assert hero.camera.zoom < argument.camera.zoom

    def test_explicit_fields_win_over_the_expansion(self):
        step = Step(
            **{
                "beat": "cta",
                "action": "click",
                "locator": {"type": "css", "value": "button"},
                "narration": "Click.",
                "wait": 9.5,
                "effects": [{"type": "ripple"}],
                "camera": {"zoom": 2.0},
            }
        )
        assert step.action == "click"
        assert step.wait == 9.5
        assert [e.type for e in step.effects] == ["ripple"]
        assert step.camera.zoom == 2.0

    def test_beat_without_locator_stays_a_pause(self):
        step = Step(**{"beat": "argument", "narration": "Just a line."})
        assert step.action == "pause"
        assert step.camera is None

    def test_beat_does_not_trigger_the_irrelevant_field_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            Step(
                **{
                    "beat": "hero",
                    "locator": {"type": "css", "value": "h1"},
                    "narration": "Hello.",
                }
            )

    def test_invalid_role_is_rejected(self):
        with pytest.raises(Exception):
            Step(**{"beat": "not-a-role", "narration": "x"})

    def test_beat_config_validates_end_to_end(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            config = _config(
                [
                    {"action": "navigate", "url": "https://example.com", "wait": 2.0},
                    {
                        "beat": "hero",
                        "locator": {"type": "css", "value": "h1"},
                        "narration": "The hero promises effortless invoicing.",
                    },
                    {"action": "camera_reset", "camera": {"reset": True}},
                ]
            )
        assert config.scenarios[0].steps[1].effects


# ── CLI surface for the browser-free commands ────────────────────────────────


def _write(tmp_path: Path, steps: list[dict]) -> Path:
    import yaml

    path = tmp_path / "demo.yaml"
    path.write_text(
        yaml.dump(
            {
                "metadata": {"title": "T", "version": "1.0"},
                "scenarios": [{"name": "S", "url": "https://example.com", "steps": steps}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


class TestNewCliCommands:
    def test_capabilities_emits_json(self):
        from typer.testing import CliRunner

        from demodsl.cli import app

        result = CliRunner().invoke(app, ["capabilities"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["actions"] and payload["effects"]

    def test_capabilities_schema_flag(self, tmp_path: Path):
        from typer.testing import CliRunner

        from demodsl.cli import app

        dest = tmp_path / "schema.json"
        result = CliRunner().invoke(app, ["capabilities", "--schema", "-o", str(dest)])
        assert result.exit_code == 0
        assert "scenarios" in json.loads(dest.read_text())["properties"]

    def test_validate_json_reports_diagnostics_and_exit_code(self, tmp_path: Path):
        from typer.testing import CliRunner

        from demodsl.cli import app

        config = _write(
            tmp_path,
            [
                {"action": "navigate", "url": "https://example.com", "wait": 2.0},
                {
                    "action": "hover",
                    "locator": {"type": "css", "value": "h1"},
                    "camera": {"zoom": 1.6},
                },
                {"action": "scroll", "direction": "down", "pixels": 400},
            ],
        )
        result = CliRunner().invoke(app, ["validate", str(config), "--json"])
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        codes = {d["code"] for d in payload["diagnostics"]}
        assert "camera.scroll_while_zoomed" in codes

    def test_estimate_json(self, tmp_path: Path):
        from typer.testing import CliRunner

        from demodsl.cli import app

        config = _write(
            tmp_path,
            [{"action": "pause", "narration": " ".join(["word"] * 30), "wait": 3.0}],
        )
        result = CliRunner().invoke(app, ["estimate", str(config), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["steps"][0]["verdict"] == "too_short"
