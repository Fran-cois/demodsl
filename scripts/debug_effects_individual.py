#!/usr/bin/env python3
"""Generate and run one YAML config per effect for individual debugging.

Usage:
    python scripts/debug_effects_individual.py                # run all
    python scripts/debug_effects_individual.py spotlight glow  # run only these
    python scripts/debug_effects_individual.py --list          # list effects
    python scripts/debug_effects_individual.py --gen-only      # generate YAMLs without running
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

URL = "https://fran-cois.github.io/demodsl/"
OUT_DIR = Path("output/debug_effects")
YAML_DIR = Path("examples/debug_effects")

# ── All 33 browser effects with their params ────────────────────────────
EFFECTS: list[dict] = [
    # Lighting
    {"type": "spotlight", "duration": 2.5, "intensity": 0.8},
    {"type": "highlight", "duration": 2.5, "color": "#FFD700"},
    {"type": "frosted_glass", "duration": 2.5, "intensity": 0.8},
    {"type": "glow", "duration": 2.5, "color": "#6366f1"},
    {"type": "neon_glow", "duration": 2.5, "color": "#FF00FF"},
    # Particles A
    {"type": "confetti", "duration": 3.0},
    {"type": "sparkle", "duration": 3.0},
    {"type": "bubbles", "duration": 3.0},
    {"type": "snow", "duration": 3.0},
    # Particles B
    {"type": "fireworks", "duration": 3.0},
    {"type": "party_popper", "duration": 3.0},
    {"type": "emoji_rain", "duration": 3.0},
    {"type": "star_burst", "duration": 2.0},
    # One-shot FX
    {"type": "shockwave"},
    {"type": "ripple"},
    # Cursor trails
    {"type": "cursor_trail", "simulate_mouse": True, "duration": 3.0},
    {"type": "cursor_trail_rainbow", "simulate_mouse": True, "duration": 3.0},
    {"type": "cursor_trail_comet", "simulate_mouse": True, "duration": 3.0},
    {"type": "cursor_trail_fire", "simulate_mouse": True, "duration": 3.0},
    {
        "type": "cursor_trail_glow",
        "color": "#00BFFF",
        "simulate_mouse": True,
        "duration": 3.0,
    },
    {"type": "cursor_trail_line", "simulate_mouse": True, "duration": 3.0},
    {"type": "cursor_trail_particles", "simulate_mouse": True, "duration": 3.0},
    # Text
    {"type": "typewriter"},
    {"type": "text_highlight", "color": "#FFD700"},
    {"type": "text_scramble", "speed": 50},
    # Interactive
    {"type": "magnetic_hover", "intensity": 0.3},
    {"type": "morphing_background", "colors": ["#667eea", "#764ba2", "#f093fb"]},
    {"type": "matrix_rain", "color": "#00FF41", "duration": 3.0},
    # Utility
    {"type": "progress_bar", "color": "#6366f1", "position": "top"},
    {
        "type": "countdown_timer",
        "duration": 3,
        "color": "#FFFFFF",
        "position": "top-right",
    },
    {"type": "tooltip_annotation", "text": "Click here"},
    {
        "type": "callout_arrow",
        "text": "Look here!",
        "color": "#ef4444",
        "target_x": 0.5,
        "target_y": 0.5,
    },
    {"type": "success_checkmark"},
]


def _effect_params_yaml(effect: dict) -> str:
    """Render effect as a YAML list item under effects: (already indented for dedent template)."""
    lines = []
    first = True
    for k, v in effect.items():
        # After dedent removes 4 spaces, we need 10 spaces for list item, 12 for continuation
        # So in the template we need 14 / 16 spaces (14 - 4 = 10, 16 - 4 = 12)
        prefix = "              - " if first else "                "
        first = False
        if isinstance(v, bool):
            lines.append(f"{prefix}{k}: {str(v).lower()}")
        elif isinstance(v, list):
            items = ", ".join(f'"{i}"' for i in v)
            lines.append(f"{prefix}{k}: [{items}]")
        elif isinstance(v, str):
            lines.append(f'{prefix}{k}: "{v}"')
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)


def generate_yaml(effect: dict) -> tuple[str, str]:
    """Return (filename, yaml_content) for a single-effect config."""
    name = effect["type"]
    wait = effect.get("duration", 2.5) + 1.0
    filename = f"debug_{name}.yaml"

    effect_block = _effect_params_yaml(effect)

    yaml = textwrap.dedent(f"""\
    # Auto-generated — single effect debug: {name}
    metadata:
      title: "Debug — {name}"
      version: "2.0.0"

    scenarios:
      - name: "{name}"
        url: "{URL}"
        browser: "chrome"
        viewport: {{ width: 1280, height: 720 }}
        pre_steps:
          - action: "navigate"
            url: "{URL}"
            wait: 2.0
        steps:
          - action: "scroll"
            direction: "down"
            pixels: 50
            narration: "Effect: {name}"
            wait: {wait}
            effects:
{effect_block}

    pipeline:
      - optimize:
          format: mp4
          codec: h264
          quality: high

    output:
      filename: "debug_{name}.mp4"
      directory: "{OUT_DIR}"
    """)
    return filename, yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug effects individually")
    parser.add_argument("effects", nargs="*", help="Effect names to run (default: all)")
    parser.add_argument("--list", action="store_true", help="List all effects and exit")
    parser.add_argument(
        "--gen-only", action="store_true", help="Generate YAMLs without running"
    )
    parser.add_argument(
        "--force", action="store_true", default=True, help="Force overwrite (default)"
    )
    args = parser.parse_args()

    if args.list:
        for i, e in enumerate(EFFECTS, 1):
            print(f"  {i:2d}. {e['type']}")
        return

    # Filter effects if names provided
    selected = EFFECTS
    if args.effects:
        names = set(args.effects)
        selected = [e for e in EFFECTS if e["type"] in names]
        unknown = names - {e["type"] for e in selected}
        if unknown:
            print(f"Unknown effects: {', '.join(sorted(unknown))}", file=sys.stderr)
            sys.exit(1)

    YAML_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate all YAML files
    configs: list[tuple[str, Path]] = []
    for effect in selected:
        fname, content = generate_yaml(effect)
        path = YAML_DIR / fname
        path.write_text(content)
        configs.append((effect["type"], path))

    print(f"Generated {len(configs)} YAML configs in {YAML_DIR}/")

    if args.gen_only:
        for name, path in configs:
            print(f"  {path}")
        return

    # Run each config
    results: list[tuple[str, bool]] = []
    for i, (name, path) in enumerate(configs, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(configs)}] Running: {name}")
        print(f"{'=' * 60}")
        ret = subprocess.run(
            ["demodsl", "run", str(path), "--force"],
            cwd=Path.cwd(),
        )
        ok = ret.returncode == 0
        results.append((name, ok))
        status = "OK" if ok else "FAIL"
        print(f"  → {status}: {OUT_DIR}/debug_{name}.mp4")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    for name, ok in results:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")
    print(f"\n  {passed} passed, {failed} failed out of {len(results)}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
