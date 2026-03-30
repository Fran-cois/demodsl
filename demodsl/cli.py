"""CLI for DemoDSL — Typer-based interface."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

app = typer.Typer(
    name="demodsl",
    help="DSL-driven automated product demo video generator. Supports YAML and JSON configs.",
)


@app.command()
def run(
    config: Path = typer.Argument(..., help="Path to the YAML or JSON config file."),
    output_dir: Path = typer.Option(
        "output", "--output-dir", "-o", help="Output directory."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate and log without executing."
    ),
    skip_voice: bool = typer.Option(False, "--skip-voice", help="Skip TTS generation."),
    skip_deploy: bool = typer.Option(
        False, "--skip-deploy", help="Skip cloud deployment."
    ),
    no_tts_cache: bool = typer.Option(
        False, "--no-tts-cache", help="Disable TTS audio caching."
    ),
    no_run_cache: bool = typer.Option(
        False,
        "--no-run-cache",
        help="Disable run-level caching (re-record everything).",
    ),
    cache_dir: Path | None = typer.Option(
        None, "--cache-dir", help="Override default run-cache directory."
    ),
    force_record: bool = typer.Option(
        False,
        "--force-record",
        help="Force browser re-recording even if cache is valid.",
    ),
    renderer: str = typer.Option(
        "moviepy", "--renderer", help="Render engine: moviepy or remotion."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging."
    ),
) -> None:
    """Parse and execute a DemoDSL config (YAML or JSON)."""
    _setup_logging(verbose)

    from demodsl.engine import DemoEngine
    from demodsl.models import DemoStoppedError

    engine = DemoEngine(
        config_path=config,
        dry_run=dry_run,
        skip_voice=skip_voice,
        skip_deploy=skip_deploy,
        tts_cache=not no_tts_cache,
        run_cache=not no_run_cache,
        cache_dir=cache_dir,
        force_record=force_record,
        output_dir=output_dir,
        renderer=renderer,
    )
    try:
        result = engine.run()
    except DemoStoppedError as exc:
        typer.echo(f"Demo stopped: {exc}", err=True)
        raise typer.Exit(code=1)
    if result:
        typer.echo(f"Done → {result}")
    else:
        typer.echo("Done (no output file produced).")


@app.command()
def validate(
    config: Path = typer.Argument(..., help="Path to the YAML or JSON config file."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Validate a config (YAML or JSON) without executing."""
    _setup_logging(verbose)

    from demodsl.engine import DemoEngine

    engine = DemoEngine(config_path=config, dry_run=True)
    cfg = engine.validate()
    typer.echo(f"Valid ✓  —  {cfg.metadata.title} (v{cfg.metadata.version})")
    typer.echo(f"  Scenarios: {len(cfg.scenarios)}")
    total_steps = sum(len(s.steps) for s in cfg.scenarios)
    typer.echo(f"  Steps:     {total_steps}")
    typer.echo(f"  Pipeline:  {len(cfg.pipeline)} stages")

    # Heuristic narration collision check (~150 words per minute)
    _WPM = 150
    gap = cfg.voice.narration_gap if cfg.voice else 0.3
    step_idx = 0
    narrated: list[tuple[int, float, float]] = []  # (index, estimated_dur, wait)
    for scenario in cfg.scenarios:
        for step in scenario.steps:
            if step.narration:
                words = len(step.narration.split())
                est_dur = max(1.0, words / _WPM * 60)
                wait = step.wait or 0.0
                narrated.append((step_idx, est_dur, wait))
            step_idx += 1

    warnings = 0
    for pos in range(len(narrated) - 1):
        idx_a, dur_a, wait_a = narrated[pos]
        idx_b, _dur_b, _wait_b = narrated[pos + 1]
        effective = max(wait_a, dur_a + gap)
        if dur_a > effective:
            typer.echo(
                f"  ⚠ Potential collision: step {idx_a} narration "
                f"(~{dur_a:.1f}s) may overlap step {idx_b} "
                f"(wait={wait_a:.1f}s)",
                err=True,
            )
            warnings += 1
    if warnings:
        typer.echo(f"  {warnings} potential narration collision(s) detected.", err=True)
    else:
        typer.echo("  Narration: no collision risk detected ✓")


@app.command()
def init(
    output: Path = typer.Option(
        "demo.yaml", "--output", "-o", help="Output file path (.yaml or .json)."
    ),
) -> None:
    """Generate a minimal config template (YAML or JSON)."""
    if output.suffix.lower() == ".json":
        import json

        template_data = {
            "metadata": {
                "title": "My Product Demo",
                "description": "A quick demo",
                "version": "1.0.0",
            },
            "voice": {"engine": "elevenlabs", "voice_id": "josh"},
            "scenarios": [
                {
                    "name": "Main Demo",
                    "url": "https://example.com",
                    "browser": "chrome",
                    "viewport": {"width": 1920, "height": 1080},
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "https://example.com",
                            "narration": "Welcome to the demo!",
                            "wait": 2.0,
                        }
                    ],
                }
            ],
            "pipeline": [
                {"generate_narration": {}},
                {"edit_video": {}},
                {"mix_audio": {}},
                {"optimize": {"format": "mp4", "codec": "h264", "quality": "high"}},
            ],
            "output": {
                "filename": "demo.mp4",
                "directory": "output/",
                "formats": ["mp4"],
            },
        }
        output.write_text(json.dumps(template_data, indent=2) + "\n")
    else:
        template = """\
metadata:
  title: "My Product Demo"
  description: "A quick demo"
  version: "1.0.0"

voice:
  engine: "elevenlabs"
  voice_id: "josh"

scenarios:
  - name: "Main Demo"
    url: "https://example.com"
    browser: "chrome"
    viewport:
      width: 1920
      height: 1080
    steps:
      - action: "navigate"
        url: "https://example.com"
        narration: "Welcome to the demo!"
        wait: 2.0

pipeline:
  - generate_narration: {}
  - edit_video: {}
  - mix_audio: {}
  - optimize:
      format: "mp4"
      codec: "h264"
      quality: "high"

output:
  filename: "demo.mp4"
  directory: "output/"
  formats:
    - "mp4"
"""
        output.write_text(template)
    typer.echo(f"Template created → {output}")


@app.command()
def setup_remotion(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Install Remotion dependencies (requires Node.js ≥ 18)."""
    import shutil
    import subprocess

    _setup_logging(verbose)

    if not shutil.which("node"):
        typer.echo("Error: Node.js not found. Install Node.js ≥ 18 first.", err=True)
        raise typer.Exit(1)

    remotion_dir = Path(__file__).resolve().parent.parent / "remotion"
    if not (remotion_dir / "package.json").exists():
        typer.echo(f"Error: Remotion project not found at {remotion_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Installing Remotion dependencies in {remotion_dir}...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=str(remotion_dir),
        capture_output=not verbose,
        text=True,
    )
    if result.returncode != 0:
        typer.echo("npm install failed.", err=True)
        if result.stderr:
            typer.echo(result.stderr[-500:], err=True)
        raise typer.Exit(1)

    typer.echo("Remotion setup complete. Use --renderer remotion when running demos.")


# ── Cache management ──────────────────────────────────────────────────────────

cache_app = typer.Typer(help="Manage the run cache.")
app.add_typer(cache_app, name="cache")


@cache_app.command("stats")
def cache_stats(
    config: Path | None = typer.Argument(
        None, help="Show stats for a specific config file."
    ),
    cache_dir: Path | None = typer.Option(None, "--cache-dir"),
) -> None:
    """Show run-cache statistics."""
    from demodsl.pipeline.run_cache import RunCache

    if config:
        cache = RunCache(config, cache_dir=cache_dir)
        info = cache.stats()
    else:
        info = RunCache.global_stats(cache_dir)

    if not info.get("exists", info.get("configs", 0) > 0):
        typer.echo("No cache data found.")
        return

    typer.echo(f"  Path:    {info.get('path', 'N/A')}")
    if "configs" in info:
        typer.echo(f"  Configs: {info['configs']}")
    typer.echo(f"  Files:   {info['files']}")
    typer.echo(f"  Size:    {info.get('size_mb', 0)} MB")


@cache_app.command("clear")
def cache_clear(
    config: Path | None = typer.Argument(
        None, help="Clear cache for a specific config (or all if omitted)."
    ),
    cache_dir: Path | None = typer.Option(None, "--cache-dir"),
) -> None:
    """Clear cached run artefacts."""
    from demodsl.pipeline.run_cache import RunCache

    if config:
        cache = RunCache(config, cache_dir=cache_dir)
        removed = cache.clear()
        typer.echo(f"Cleared {removed} files for {config.name}")
    else:
        removed = RunCache.clear_all(cache_dir)
        typer.echo(f"Cleared {removed} cached files (all configs)")


# ── Interactive edit ──────────────────────────────────────────────────────────


@app.command()
def edit(
    config: Path = typer.Argument(..., help="Path to the YAML or JSON config file."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Save edited config to a different file."
    ),
    cache_dir: Path | None = typer.Option(None, "--cache-dir"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Interactively edit pauses and timing for a demo config."""
    _setup_logging(verbose)

    import yaml

    from demodsl.config_loader import load_config
    from demodsl.pipeline.run_cache import RunCache

    raw = load_config(config)
    from demodsl.models import DemoConfig

    cfg = DemoConfig(**raw)

    # Load cached timing if available
    cache = RunCache(config, cache_dir=cache_dir)
    step_timestamps: list[float] = cache.get_artifact("step_timestamps") or []
    narration_durations: dict[str, float] = (
        cache.get_artifact("narration_durations") or {}
    )

    # Build step listing
    step_idx = 0
    step_info: list[dict[str, object]] = []
    for scenario in cfg.scenarios:
        for step in scenario.steps:
            ts = step_timestamps[step_idx] if step_idx < len(step_timestamps) else None
            nar_dur = narration_durations.get(str(step_idx))
            step_info.append(
                {
                    "index": step_idx,
                    "action": step.action,
                    "url": getattr(step, "url", None),
                    "locator": (
                        f"{step.locator.type}={step.locator.value}"
                        if step.locator
                        else None
                    ),
                    "narration": step.narration,
                    "narration_dur": nar_dur,
                    "timestamp": ts,
                    "wait": step.wait,
                }
            )
            step_idx += 1

    # Display timeline
    typer.echo(f"\n  Timeline: {cfg.metadata.title}\n")
    for info in step_info:
        ts_str = f"{info['timestamp']:.1f}s" if info["timestamp"] is not None else "?"
        parts = [f"  Step {info['index']} [{ts_str}]: {info['action']}"]
        if info["url"]:
            parts.append(f"→ {info['url']}")
        elif info["locator"]:
            parts.append(f"→ {info['locator']}")
        if info["narration"]:
            dur = f" | {info['narration_dur']:.1f}s" if info["narration_dur"] else ""
            nar_preview = str(info["narration"])[:40]
            parts.append(f'("{nar_preview}"{dur})')
        typer.echo(" ".join(parts))

    # Show existing pauses
    existing_pauses: list[dict[str, object]] = []
    if cfg.edit and cfg.edit.pauses:
        existing_pauses = [p.model_dump() for p in cfg.edit.pauses]
        typer.echo(f"\n  Existing pauses: {len(existing_pauses)}")
        for p in existing_pauses:
            typer.echo(
                f"    after step {p['after_step']}: {p['duration']}s ({p['type']})"
            )

    typer.echo(
        "\n  Commands: pause <step> <duration> [freeze], "
        "offset <step> <seconds>, remove <step>, save, quit\n"
    )

    # Interactive loop
    changes_made = False
    while True:
        try:
            line = typer.prompt("edit", default="").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line or line == "quit":
            break

        tokens = line.split()
        cmd = tokens[0].lower()

        if cmd == "pause" and len(tokens) >= 3:
            try:
                step_i = int(tokens[1])
                dur = float(tokens[2])
                ptype = tokens[3] if len(tokens) > 3 else "audio"
                if dur <= 0:
                    typer.echo("  Duration must be > 0. Use 'remove' to delete.")
                    continue
                # Remove existing pause for this step if any
                existing_pauses = [
                    p for p in existing_pauses if p["after_step"] != step_i
                ]
                existing_pauses.append(
                    {"after_step": step_i, "duration": dur, "type": ptype}
                )
                typer.echo(f"  ✓ Pause {dur}s ({ptype}) after step {step_i}")
                changes_made = True
            except (ValueError, IndexError):
                typer.echo("  Usage: pause <step_index> <duration> [audio|freeze]")

        elif cmd == "offset" and len(tokens) >= 3:
            try:
                step_i = int(tokens[1])
                offset = float(tokens[2])
                # Update audio_offset in raw config
                raw.setdefault("scenarios", [])
                idx = 0
                for sc in raw["scenarios"]:
                    for st in sc.get("steps", []):
                        if idx == step_i:
                            st["audio_offset"] = offset
                            typer.echo(
                                f"  ✓ Audio offset {offset:+.1f}s on step {step_i}"
                            )
                            changes_made = True
                        idx += 1
            except (ValueError, IndexError):
                typer.echo("  Usage: offset <step_index> <seconds>")

        elif cmd == "remove" and len(tokens) >= 2:
            try:
                step_i = int(tokens[1])
                before = len(existing_pauses)
                existing_pauses = [
                    p for p in existing_pauses if p["after_step"] != step_i
                ]
                if len(existing_pauses) < before:
                    typer.echo(f"  ✓ Removed pause after step {step_i}")
                    changes_made = True
                else:
                    typer.echo(f"  No pause found after step {step_i}")
            except ValueError:
                typer.echo("  Usage: remove <step_index>")

        elif cmd == "save":
            if existing_pauses:
                raw["edit"] = {"pauses": existing_pauses}
            elif "edit" in raw:
                del raw["edit"]

            dest = output or config
            dest.write_text(
                yaml.dump(raw, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
            typer.echo(f"  ✓ Saved → {dest}")
            changes_made = False

        else:
            typer.echo("  Unknown command. Try: pause, offset, remove, save, quit")

    if changes_made:
        typer.echo("  Unsaved changes. Use 'save' before quitting next time.")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    app()
