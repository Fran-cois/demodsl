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

    engine = DemoEngine(
        config_path=config,
        dry_run=dry_run,
        skip_voice=skip_voice,
        skip_deploy=skip_deploy,
        output_dir=output_dir,
        renderer=renderer,
    )
    result = engine.run()
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


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    app()
