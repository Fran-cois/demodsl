"""CLI for DemoDSL — Typer-based interface."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import typer

app = typer.Typer(
    name="demodsl",
    help="DSL-driven automated product demo video generator. Supports YAML and JSON configs.",
)


@app.command()
def run(
    config: Path = typer.Argument(..., help="Path to the YAML or JSON config file."),
    output_dir: Path = typer.Option("output", "--output-dir", "-o", help="Output directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and log without executing."),
    skip_voice: bool = typer.Option(False, "--skip-voice", help="Skip TTS generation."),
    skip_deploy: bool = typer.Option(False, "--skip-deploy", help="Skip cloud deployment."),
    no_tts_cache: bool = typer.Option(False, "--no-tts-cache", help="Disable TTS audio caching."),
    no_run_cache: bool = typer.Option(
        False,
        "--no-run-cache",
        "--force",
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
        "remotion", "--renderer", help="Render engine. Since v3.0, only 'remotion' is supported."
    ),
    separate_audio: bool = typer.Option(
        False,
        "--separate-audio",
        help="Output separate video.mp4, narration.mp3, and timing.json files.",
    ),
    thumbnails: int = typer.Option(
        0,
        "--thumbnails",
        help="Generate N candidate thumbnail images from the video (0 = disabled).",
        min=0,
        max=20,
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
    turbo: bool = typer.Option(
        False,
        "--turbo",
        help="Turbo mode: minimal waits, skip heavy post-processing "
        "(avatars, 3D, subtitles, speed re-encode). Ideal for quick previews.",
    ),
) -> None:
    """Parse and execute a DemoDSL config (YAML or JSON)."""
    _setup_logging(verbose)

    if renderer != "remotion":
        typer.echo(
            f"error: unsupported renderer {renderer!r}. Since v3.0, only "
            "'remotion' is supported (MoviePy was removed).",
            err=True,
        )
        raise typer.Exit(code=2)

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
        separate_audio=separate_audio,
        thumbnails=thumbnails,
        turbo=turbo,
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

    # Heuristic narration collision check: estimate spoken duration from
    # the configured words-per-minute rate (override with the env var
    # ``DEMODSL_VALIDATE_WPM`` for non-English locales).
    try:
        _WPM = max(60, int(os.environ.get("DEMODSL_VALIDATE_WPM", "150")))
    except ValueError:
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


@app.command("setup-login")
def setup_login(
    user_data_dir: Path = typer.Option(
        Path.home() / ".demodsl-chrome-profile",
        "--user-data-dir",
        "-u",
        help="Chrome profile directory to create/reuse (keep outside the repo).",
    ),
    url: str = typer.Option(
        "https://accounts.google.com",
        "--url",
        help="Sign-in page to open (default: Google account).",
    ),
    channel: str = typer.Option(
        "chrome",
        "--channel",
        help="Browser channel ('chrome', 'chrome-beta', 'msedge', or '' for bundled Chromium).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sign into a social provider once, in a reusable Chrome profile (provider 'playwright-persistent').

    Opens real Chrome against a persistent profile directory so you can log
    into Google (or any IdP) by hand. The session is saved and reused by
    demos that set ``provider: playwright-persistent`` — exporting
    ``DEMODSL_USER_DATA_DIR`` to the same path.
    """
    _setup_logging(verbose)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        typer.echo(
            "Error: Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium",
            err=True,
        )
        raise typer.Exit(1)

    profile = user_data_dir.expanduser()
    profile.mkdir(parents=True, exist_ok=True)

    # Strip the automation signals Google uses to show "Couldn't sign you in /
    # this browser may not be secure": drop the --enable-automation switch
    # (removes the infobar) and disable the AutomationControlled blink feature
    # (hides navigator.webdriver). Without these, manual sign-in is blocked.
    launch_kwargs: dict = {
        "headless": False,
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    }
    if channel:
        launch_kwargs["channel"] = channel

    typer.echo(f"Opening Chrome with profile: {profile}")
    typer.echo(f"Sign into {url} in the window, then press Enter here to save & close.")
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(str(profile), **launch_kwargs)
        except Exception as exc:
            if channel:
                typer.echo(f"Channel {channel!r} unavailable ({exc}); using bundled Chromium.")
                launch_kwargs.pop("channel", None)
                ctx = pw.chromium.launch_persistent_context(str(profile), **launch_kwargs)
            else:
                typer.echo(f"Error launching Chrome: {exc}", err=True)
                raise typer.Exit(1)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(url)
        except Exception as exc:
            typer.echo(f"Warning: could not open {url}: {exc}", err=True)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        ctx.close()

    typer.echo("\nSession saved. Run an option-B demo with:")
    typer.echo(f'  DEMODSL_USER_DATA_DIR="{profile}" demodsl run examples/demo_social_login.yaml')
    typer.echo('(set provider: "playwright-persistent" in the scenario)')


# ── Discovery harness CLI ─────────────────────────────────────────────────────


@app.command()
def discover(
    query: str = typer.Argument(..., help="What feature to show/test, in plain language."),
    url: str = typer.Option(..., "--url", help="Start URL of the site to explore."),
    output_dir: Path = typer.Option(
        "output", "--output-dir", "-o", help="Where to write the config/video."
    ),
    policy: str = typer.Option(
        "llm", "--policy", help="Agent policy: 'llm' (cloud model) or 'heuristic' (offline)."
    ),
    llm_backend: str = typer.Option(
        "openai",
        "--llm",
        help="LLM backend: 'openai', 'openrouter', 'anthropic', or 'simulated' "
        "(offline, no API key).",
    ),
    model: str = typer.Option("gpt-4o", "--model", help="Model name for the chosen backend."),
    tree_search: bool = typer.Option(
        False,
        "--tree-search",
        help="Best-of-N tree search with self-evaluation (higher quality, higher cost).",
    ),
    rollouts: int = typer.Option(3, "--rollouts", help="Rollouts for tree search.", min=1, max=8),
    max_steps: int = typer.Option(
        8, "--max-steps", help="Max actions during discovery.", min=1, max=30
    ),
    token_budget: int = typer.Option(8000, "--token-budget", help="Hard token budget for the run."),
    observation_budget: int = typer.Option(
        1024, "--obs-budget", help="Per-step page-representation token budget."
    ),
    max_jumps: int | None = typer.Option(
        None,
        "--max-jumps",
        help="Max number of href jumps (cross-page navigations) allowed. Unlimited if unset.",
    ),
    allow_external: bool = typer.Option(
        False,
        "--allow-external",
        help="Allow following links to external domains (off the start site). "
        "By default navigation is restricted to the start domain.",
    ),
    explore_first: bool = typer.Option(
        False,
        "--explore-first",
        help="Two-phase mode: crawl the site deterministically (no LLM) into an "
        "exploration graph, then let the LLM pick the demo from that graph.",
    ),
    max_pages: int = typer.Option(
        8, "--max-pages", help="Explore-first: max pages to crawl.", min=1, max=100
    ),
    max_depth: int = typer.Option(
        2, "--max-depth", help="Explore-first: max link depth from the start page.", min=1, max=6
    ),
    live_pricing: bool = typer.Option(
        False,
        "--live-pricing",
        help="Fetch live model prices from the OpenRouter /models API for the cost "
        "estimate (falls back to the built-in table offline).",
    ),
    # Persona simulation (reproduce a user's reflexes/effort, not the best path)
    persona: str | None = typer.Option(
        None,
        "--persona",
        help="Simulate a user persona, e.g. 'jeune maman pressée, cadre infirmière' "
        "or a preset (hurried_parent|power_user|cautious_senior|curious_explorer|impatient_skimmer).",
    ),
    persona_lang: str | None = typer.Option(
        None, "--persona-lang", help="Persona reflection language (fr|en); auto-detected otherwise."
    ),
    persona_patience: float | None = typer.Option(
        None, "--persona-patience", help="Override patience trait [0..1].", min=0.0, max=1.0
    ),
    persona_tech: float | None = typer.Option(
        None, "--persona-tech", help="Override tech-savviness trait [0..1].", min=0.0, max=1.0
    ),
    persona_thoroughness: float | None = typer.Option(
        None, "--persona-thoroughness", help="Override thoroughness trait [0..1].", min=0.0, max=1.0
    ),
    persona_confidence: float | None = typer.Option(
        None, "--persona-confidence", help="Override confidence trait [0..1].", min=0.0, max=1.0
    ),
    # Authenticated discovery (latest-version providers) ----------------------
    provider: str = typer.Option(
        "playwright",
        "--provider",
        help="Browser provider: playwright | playwright-cdp | playwright-persistent.",
    ),
    user_data_dir: Path | None = typer.Option(
        None, "--user-data-dir", "-u", help="Chrome profile dir (provider playwright-persistent)."
    ),
    cdp_url: str | None = typer.Option(
        None, "--cdp-url", help="DevTools endpoint to attach to (provider playwright-cdp)."
    ),
    channel: str | None = typer.Option(
        None, "--channel", help="Browser channel (chrome|msedge|...)."
    ),
    headless: bool = typer.Option(False, "--headless", help="Run the auth browser headless."),
    isolate: bool = typer.Option(False, "--isolate", help="Clone the profile before launch."),
    oauth_provider: str | None = typer.Option(
        None, "--oauth", help="Prepend an oauth_login step (google|microsoft|github|generic)."
    ),
    render: bool = typer.Option(False, "--render", help="Also render a proof video (turbo)."),
    graph: bool = typer.Option(
        False,
        "--graph",
        help="Also export a navigation graph of the explored path(s) "
        "(Mermaid + DOT + JSON + HTML) next to the config.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Discover the best DemoDSL config for a feature, then emit a validated YAML.

    Examples:
        demodsl discover "open the pricing page" --url https://acme.com
        demodsl discover "the signed-in dashboard" --url https://app.acme.com \\
            --provider playwright-persistent -u ~/.demodsl-chrome-profile --render
    """
    _setup_logging(verbose)

    from demodsl.discover import DiscoveryHarness
    from demodsl.models import BrowserAuthConfig

    auth: BrowserAuthConfig | None = None
    if user_data_dir or cdp_url or channel or headless or isolate:
        auth = BrowserAuthConfig(
            user_data_dir=str(user_data_dir.expanduser()) if user_data_dir else None,
            cdp_url=cdp_url,
            channel=channel,
            headless=headless or None,
            isolate=isolate,
        )
    login = {"provider": oauth_provider} if oauth_provider else None

    persona_obj = None
    if persona:
        from dataclasses import replace as _replace

        from demodsl.discover.persona import PERSONA_PRESETS, Persona

        overrides = {
            "language": persona_lang,
            "patience": persona_patience,
            "tech_savviness": persona_tech,
            "thoroughness": persona_thoroughness,
            "confidence": persona_confidence,
        }
        overrides = {k: v for k, v in overrides.items() if v is not None}
        if persona in PERSONA_PRESETS:
            base_persona = PERSONA_PRESETS[persona]
            persona_obj = _replace(base_persona, **overrides) if overrides else base_persona
        else:
            persona_obj = Persona.from_description(persona, **overrides)

    harness = DiscoveryHarness.build(
        policy=policy,
        llm_backend=llm_backend,
        model=model,
        tree_search=tree_search,
        n_rollouts=rollouts,
        max_steps=max_steps,
        token_budget=token_budget,
        observation_budget=observation_budget,
        persona=persona_obj,
        max_jumps=max_jumps,
        allow_external=allow_external,
        explore_first=explore_first,
        max_pages=max_pages,
        max_depth=max_depth,
        live_pricing=live_pricing,
    )
    try:
        result = harness.discover(
            url=url,
            query=query,
            provider=provider,
            auth=auth,
            login=login,
            verify=render,
            output_dir=output_dir,
            verify_turbo=True,
        )
    except Exception as exc:  # surface a friendly message, full trace with -v
        typer.echo(f"error: discovery failed: {exc}", err=True)
        if verbose:
            raise
        raise typer.Exit(code=1)

    typer.echo(result.summary())
    if not result.trajectory.feature_reached:
        typer.echo(
            f"⚠️  The requested feature was not found on {url}. "
            "The generated demo only opens the site (no feature walkthrough).",
            err=True,
        )
    if result.persona_report is not None:
        typer.echo("")
        typer.echo(result.persona_report.to_markdown())
    if result.config_path:
        typer.echo(f"Config → {result.config_path}")
    if result.video_path:
        typer.echo(f"Video  → {result.video_path}")

    if graph:
        from demodsl.discover.graph import build_path_graph, write_path_graph

        paths = [("best", result.trajectory)]
        for i, cand in enumerate(result.candidates, start=1):
            if cand is result.trajectory:
                continue
            paths.append((f"candidate {i}", cand))
        pg = build_path_graph(query=query, start_url=url, paths=paths)
        written = write_path_graph(pg, output_dir)
        typer.echo(
            f"Graph  → {pg.n_nodes} pages · {pg.n_edges} transitions ({len(pg.paths)} path(s))"
        )
        for fmt, path in written.items():
            typer.echo(f"  {fmt:<7}→ {path}")


@app.command()
def review(
    query: str = typer.Argument(..., help="What feature to show/test, in plain language."),
    url: str = typer.Option(..., "--url", help="Start URL of the site to review."),
    panel: int = typer.Option(
        3, "--panel", "-n", help="Number of varied personas in the panel.", min=1, max=10
    ),
    base: str | None = typer.Option(
        None,
        "--base",
        help="Optional audience/domain seed, e.g. 'voyageur en train soucieux du climat'. "
        "Keeps the panel on-domain while still spanning attitudes/behaviours.",
    ),
    lang: str | None = typer.Option(
        None, "--lang", help="Force persona language (fr|en); inferred otherwise."
    ),
    output_dir: Path = typer.Option(
        "output/review", "--output-dir", "-o", help="Where to write the panel + report."
    ),
    policy: str = typer.Option(
        "heuristic", "--policy", help="Agent policy: 'heuristic' (offline) or 'llm' (cloud model)."
    ),
    llm_backend: str = typer.Option(
        "openai",
        "--llm",
        help="LLM backend: 'openai', 'openrouter', 'anthropic', or 'simulated' "
        "(offline, no API key).",
    ),
    model: str = typer.Option("gpt-4o", "--model", help="Model name for the chosen backend."),
    max_steps: int = typer.Option(
        8, "--max-steps", help="Max actions per persona during discovery.", min=1, max=30
    ),
    render: bool = typer.Option(
        False, "--render", help="Also render a turbo proof video for each persona."
    ),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="Skip PDF rendering (HTML report only)."),
    no_hero: bool = typer.Option(
        False, "--no-hero", help="Skip the best-effort hero screenshot of the site."
    ),
    graph: bool = typer.Option(
        False,
        "--graph",
        help="Also export a navigation graph unioning every persona's path "
        "(Mermaid + DOT + JSON + HTML) and link it from the report.",
    ),
    # Authenticated discovery (same wiring as `discover`) ---------------------
    provider: str = typer.Option(
        "playwright",
        "--provider",
        help="Browser provider: playwright | playwright-cdp | playwright-persistent.",
    ),
    user_data_dir: Path | None = typer.Option(
        None, "--user-data-dir", "-u", help="Chrome profile dir (provider playwright-persistent)."
    ),
    cdp_url: str | None = typer.Option(
        None, "--cdp-url", help="DevTools endpoint to attach to (provider playwright-cdp)."
    ),
    channel: str | None = typer.Option(
        None, "--channel", help="Browser channel (chrome|msedge|...)."
    ),
    headless: bool = typer.Option(False, "--headless", help="Run the auth browser headless."),
    isolate: bool = typer.Option(False, "--isolate", help="Clone the profile before launch."),
    oauth_provider: str | None = typer.Option(
        None, "--oauth", help="Prepend an oauth_login step (google|microsoft|github|generic)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a panel of varied personas past a feature and emit a PDF review report.

    Generates up to N diverse personas (a clear spread of attitudes and
    behaviours), drives the discovery harness once per persona to build (and
    optionally render) a demo, then aggregates every outcome — emotion, effort,
    think-aloud and designer findings — into ``review.pdf`` (+ ``review.html`` /
    ``review.json``).

    Examples:
        demodsl review "find a low-carbon train trip and see the offers" \\
            --url https://www.hourrail.voyage/fr --panel 3 \\
            --provider playwright-persistent -u ~/.demodsl-google-profile --channel chrome
    """
    _setup_logging(verbose)

    from demodsl.discover.panel import build_panel
    from demodsl.discover.review import run_review
    from demodsl.models import BrowserAuthConfig

    auth: BrowserAuthConfig | None = None
    if user_data_dir or cdp_url or channel or headless or isolate:
        auth = BrowserAuthConfig(
            user_data_dir=str(user_data_dir.expanduser()) if user_data_dir else None,
            cdp_url=cdp_url,
            channel=channel,
            headless=headless or None,
            isolate=isolate,
        )
    login = {"provider": oauth_provider} if oauth_provider else None

    personas = build_panel(panel, base=base, lang=lang)
    typer.echo(f"Panel of {len(personas)} personas:")
    for p in personas:
        typer.echo(f"  · {p.label} — {p.traits_line()}")

    def _progress(i: int, total: int, persona) -> None:
        typer.echo(f"\n[{i + 1}/{total}] {persona.label} …")

    try:
        report = run_review(
            url=url,
            query=query,
            personas=personas,
            output_dir=output_dir,
            provider=provider,
            auth=auth,
            login=login,
            policy=policy,
            llm_backend=llm_backend,
            model=model,
            max_steps=max_steps,
            render=render,
            pdf=not no_pdf,
            hero=not no_hero,
            graph=graph,
            progress=_progress,
        )
    except Exception as exc:  # surface a friendly message, full trace with -v
        typer.echo(f"error: review failed: {exc}", err=True)
        if verbose:
            raise
        raise typer.Exit(code=1)

    typer.echo("")
    typer.echo(
        f"Panel done: {report.reached_count}/{report.n} reached · "
        f"{report.gave_up_count}/{report.n} gave up · sentiment {report.overall_sentiment()}"
    )
    for text, cnt in report.recurring_findings():
        if cnt >= 2:
            typer.echo(f"  ⚠ ({cnt}) {text}")
    if report.json_path:
        typer.echo(f"JSON   → {report.json_path}")
    if report.html_path:
        typer.echo(f"HTML   → {report.html_path}")
    if report.pdf_path:
        typer.echo(f"PDF    → {report.pdf_path}")
    elif report.notes:
        typer.echo(f"note: {report.notes[-1]}", err=True)
    if report.graph_paths:
        for fmt, path in report.graph_paths.items():
            typer.echo(f"Graph  → {path} ({fmt})")


@app.command()
def benchmark(
    output_dir: Path = typer.Option(
        "output/benchmark", "--output-dir", "-o", help="Where to write the report."
    ),
    max_steps: int = typer.Option(6, "--max-steps", min=1, max=20),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the offline page-representation ablation benchmark and print the table.

    Compares the adaptive representation against full-DOM and viewport/SoM
    baselines on a deterministic simulated environment (no network/API key).
    """
    _setup_logging(verbose)

    from demodsl.discover.benchmark import run_benchmark

    report = run_benchmark(max_steps=max_steps)
    md = report.to_markdown()
    typer.echo(md)

    out = output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark_report.md").write_text(md, encoding="utf-8")
    (out / "benchmark_report.json").write_text(report.to_json(), encoding="utf-8")
    typer.echo(f"\nReport → {out / 'benchmark_report.md'}")


@app.command()
def mind2web(
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Real Mind2Web JSON file/dir (official schema). Falls back to the "
        "reproducible offline sample when omitted (or set MIND2WEB_PATH).",
    ),
    output_dir: Path = typer.Option(
        "output/mind2web", "--output-dir", "-o", help="Where to write the report."
    ),
    max_steps: int | None = typer.Option(None, "--max-steps", min=1),
    token_budget: int = typer.Option(52, "--token-budget", min=16),
    max_elements: int = typer.Option(18, "--max-elements", min=1),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the Mind2Web element-grounding ablation and print the table.

    Isolates each grounding component (lexical baseline → +attribute-aware/fuzzy
    → +recall floor) on identical candidate snapshots. Uses the real dataset
    when --path/MIND2WEB_PATH is given, else a faithful offline sample (no
    network/API key).
    """
    _setup_logging(verbose)

    from demodsl.discover.mind2web import run_mind2web_eval

    report = run_mind2web_eval(
        path=path,
        max_steps=max_steps,
        token_budget=token_budget,
        max_elements=max_elements,
        out_dir=output_dir,
    )
    typer.echo(report.to_markdown())
    typer.echo(f"\nReport → {output_dir / 'mind2web_report.md'}")


# ── Effect library CLI ────────────────────────────────────────────────────────

library_app = typer.Typer(help="Browse and manage the effect preset library.")
app.add_typer(library_app, name="library")


def _load_library() -> EffectLibrary:  # noqa: F821
    from demodsl.effects.library_registry import EffectLibrary

    lib = EffectLibrary()
    lib.load_defaults(project_root=Path.cwd())
    return lib


@library_app.command("list")
def library_list(
    tag: str | None = typer.Option(None, "--tag", "-t", help="Filter by tag."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """List all available library presets."""
    _setup_logging(verbose)
    lib = _load_library()

    effects = lib.list_by_tag(tag) if tag else lib.list_all()
    if not effects:
        typer.echo("No presets found." + (f" (tag={tag})" if tag else ""))
        raise typer.Exit(0)

    typer.echo(f"  {len(effects)} preset(s):\n")
    for e in sorted(effects, key=lambda x: x.name):
        tags = " ".join(f"[{t}]" for t in e.tags[:3])
        typer.echo(f"  {e.name:<30} {e.description[:50]}")
        if verbose:
            typer.echo(f"    Tags: {tags}")
            params = ", ".join(e.parameters.keys()) if e.parameters else "none"
            typer.echo(f"    Params: {params}")


@library_app.command("search")
def library_search(
    query: str = typer.Argument(..., help="Search term (matches name, description, tags)."),
) -> None:
    """Search presets by keyword."""
    lib = _load_library()
    results = lib.search(query)
    if not results:
        typer.echo(f"No presets matching '{query}'.")
        raise typer.Exit(0)

    typer.echo(f"  {len(results)} result(s) for '{query}':\n")
    for e in results:
        typer.echo(f"  {e.name:<30} {e.description[:50]}")


@library_app.command("info")
def library_info(
    name: str = typer.Argument(..., help="Preset name (e.g. 'lower_thirds/tech')."),
) -> None:
    """Show detailed info about a preset (parameters, layers, inheritance)."""
    lib = _load_library()
    effect = lib.get(name)
    if effect is None:
        typer.echo(f"Preset '{name}' not found.", err=True)
        typer.echo(f"  Available: {', '.join(lib.names)}")
        raise typer.Exit(1)

    typer.echo(f"\n  {effect.name}")
    typer.echo(f"  {effect.description}")
    typer.echo(f"  Tags: {', '.join(effect.tags)}")
    if effect.extends:
        typer.echo(f"  Extends: {effect.extends}")

    if effect.parameters:
        typer.echo("\n  Parameters:")
        for pname, param in effect.parameters.items():
            req = " (required)" if param.required else f" = {param.default}"
            typer.echo(f"    {pname}: {param.type}{req}")
            if param.description:
                typer.echo(f"      {param.description}")

    if effect.layers:
        typer.echo(f"\n  Layers: {len(effect.layers)}")
        for i, layer in enumerate(effect.layers):
            lid = layer.get("id", f"#{i}")
            ltype = layer.get("type", "?")
            typer.echo(f"    [{i}] {lid} ({ltype})")

    if effect.effects:
        typer.echo(f"\n  Effects: {len(effect.effects)}")
        for eff in effect.effects:
            typer.echo(f"    - {eff.get('type', '?')}")

    # Usage snippet
    typer.echo("\n  Usage:")
    typer.echo(f'    - $use: "{effect.name}"')
    if effect.parameters:
        typer.echo("      $params:")
        for pname, param in effect.parameters.items():
            val = param.default if param.default is not None else "<value>"
            typer.echo(f"        {pname}: {val}")
    typer.echo()


@library_app.command("scaffold")
def library_scaffold(
    name: str = typer.Argument(..., help="Preset name (e.g. 'my_category/my_effect')."),
    output_dir: Path = typer.Option("library", "--dir", "-d", help="Library directory."),
) -> None:
    """Create a new preset skeleton file."""
    parts = name.split("/")
    if len(parts) != 2:
        typer.echo("Name must be 'category/effect_name' (e.g. 'intros/fade_in').", err=True)
        raise typer.Exit(1)

    category, effect_name = parts
    target = output_dir / category / f"{effect_name}{'.effect.yaml'}"

    if target.exists():
        typer.echo(f"File already exists: {target}", err=True)
        raise typer.Exit(1)

    template = f"""\
name: {name}
description: TODO — describe what this preset does.
tags: [{category}, TODO]
parameters:
  color:
    type: color
    default: "#FFFFFF"
    description: Primary color
  start:
    type: number
    default: 0
    description: Start time in seconds
  duration:
    type: number
    default: 3.0
    description: Total duration
layers:
  - id: main_layer
    type: text
    content: "TODO"
    font_size: 36
    color: "{{{{ color }}}}"
    start: "{{{{ start }}}}"
    duration: "{{{{ duration }}}}"
    transform:
      position: [60, 900]
    animators:
      - property: opacity
        keyframes:
          - {{ t: 0, v: 0 }}
          - {{ t: 0.3, v: 1, ease: ease-out }}
          - {{ t: "{{{{ duration - 0.4 }}}}", v: 1 }}
          - {{ t: "{{{{ duration }}}}", v: 0 }}
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template)
    typer.echo(f"Created → {target}")
    typer.echo(f"  Edit the file, then test with: demodsl library info {name}")


# ── Cache management ──────────────────────────────────────────────────────────

cache_app = typer.Typer(help="Manage the run cache.")
app.add_typer(cache_app, name="cache")

stats_app = typer.Typer(help="Track and export demo usage statistics.")
app.add_typer(stats_app, name="stats")


@cache_app.command("stats")
def cache_stats(
    config: Path | None = typer.Argument(None, help="Show stats for a specific config file."),
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


@stats_app.command("show")
def stats_show() -> None:
    """Show local usage stats (demos created, runs, renderer split)."""
    from demodsl.stats import StatsStore

    summary = StatsStore().summary()
    typer.echo(f"  File:           {summary['path']}")
    typer.echo(f"  Demos created:  {summary['demos_created']}")
    typer.echo(f"  Total runs:     {summary['runs']}")
    typer.echo(f"  Dry runs:       {summary['dry_runs']}")
    typer.echo(f"  Projects:       {summary['unique_projects']}")
    typer.echo("  Renderers:")
    renderers = summary.get("renderers", {})
    if not renderers:
        typer.echo("    - none")
    else:
        for name, count in sorted(renderers.items()):
            typer.echo(f"    - {name}: {count}")
    if summary.get("last_run"):
        typer.echo(f"  Last run:       {summary['last_run']}")


@stats_app.command("export")
def stats_export(
    output: Path = typer.Option(
        "output/demodsl_stats_export.json",
        "--output",
        "-o",
        help="Export path for raw stats JSON.",
    ),
) -> None:
    """Export raw stats JSON to a file (useful for dashboards / promotion)."""
    from demodsl.stats import StatsStore

    store = StatsStore()
    data = store.load()
    output.parent.mkdir(parents=True, exist_ok=True)
    import json

    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    typer.echo(f"Stats exported -> {output}")


@stats_app.command("promo")
def stats_promo(
    lang: str = typer.Option(
        "fr",
        "--lang",
        "-l",
        help="Language for promo text: fr, en, es, de.",
    ),
    all_langs: bool = typer.Option(
        False,
        "--all",
        help="Print promo text in all supported languages.",
    ),
) -> None:
    """Print promotion-friendly one-liners from local stats."""
    from demodsl.stats import StatsStore

    store = StatsStore()

    if all_langs:
        for code, text in store.promo_texts().items():
            typer.echo(f"[{code}] {text}")
        return

    if lang not in StatsStore.SUPPORTED_PROMO_LANGS:
        supported = ", ".join(StatsStore.SUPPORTED_PROMO_LANGS)
        typer.echo(
            f"Unsupported language '{lang}'. Supported values: {supported}",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(store.promo_text(lang=lang))


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
    narration_durations: dict[str, float] = cache.get_artifact("narration_durations") or {}

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
                        f"{step.locator.type}={step.locator.value}" if step.locator else None
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
            typer.echo(f"    after step {p['after_step']}: {p['duration']}s ({p['type']})")

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
                pause_dur = float(tokens[2])
                ptype = tokens[3] if len(tokens) > 3 else "audio"
                if pause_dur <= 0:
                    typer.echo("  Duration must be > 0. Use 'remove' to delete.")
                    continue
                # Remove existing pause for this step if any
                existing_pauses = [p for p in existing_pauses if p["after_step"] != step_i]
                existing_pauses.append({"after_step": step_i, "duration": pause_dur, "type": ptype})
                typer.echo(f"  ✓ Pause {pause_dur}s ({ptype}) after step {step_i}")
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
                            typer.echo(f"  ✓ Audio offset {offset:+.1f}s on step {step_i}")
                            changes_made = True
                        idx += 1
            except (ValueError, IndexError):
                typer.echo("  Usage: offset <step_index> <seconds>")

        elif cmd == "remove" and len(tokens) >= 2:
            try:
                step_i = int(tokens[1])
                before = len(existing_pauses)
                existing_pauses = [p for p in existing_pauses if p["after_step"] != step_i]
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


# ── Mobile diagnostic commands ───────────────────────────────────────────────


@app.command("test-connection")
def test_connection(
    config: Path = typer.Argument(..., help="Path to the YAML or JSON config file."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Test Appium connection to a mobile device/simulator."""
    _setup_logging(verbose)

    from demodsl.config_loader import load_config
    from demodsl.models import DemoConfig
    from demodsl.providers.mobile import AppiumMobileProvider

    raw = load_config(config)
    cfg = DemoConfig(**raw)

    # Find first mobile scenario
    mobile_cfg = None
    for scenario in cfg.scenarios:
        if scenario.mobile:
            mobile_cfg = scenario.mobile
            break

    if mobile_cfg is None:
        typer.echo("No mobile scenario found in config.", err=True)
        raise typer.Exit(1)

    typer.echo(f"  Platform:    {mobile_cfg.platform}")
    typer.echo(f"  Device:      {mobile_cfg.device_name}")
    typer.echo(f"  Appium:      {mobile_cfg.appium_server}")

    provider = AppiumMobileProvider()
    try:
        typer.echo("  Connecting...")
        provider.launch_without_recording(mobile_cfg)
        size = provider.get_window_size()
        typer.echo(f"  Screen:      {size['width']}×{size['height']}")

        # Take a diagnostic screenshot
        screenshot_path = Path("output") / "test_connection_screenshot.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        provider.screenshot(screenshot_path)
        typer.echo(f"  Screenshot:  {screenshot_path}")

        typer.echo("  Connection OK ✓")
    except Exception as exc:
        typer.echo(f"  Connection FAILED ✗  — {exc}", err=True)
        raise typer.Exit(1)
    finally:
        try:
            provider.close()
        except Exception:
            pass


@app.command()
def inspect(
    config: Path = typer.Argument(..., help="Path to the YAML or JSON config file."),
    raw_xml: bool = typer.Option(False, "--raw", help="Output raw XML instead of formatted tree."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Dump the accessibility tree of a mobile app screen."""
    _setup_logging(verbose)

    from demodsl.config_loader import load_config
    from demodsl.models import DemoConfig
    from demodsl.providers.mobile import AppiumMobileProvider

    raw_config = load_config(config)
    cfg = DemoConfig(**raw_config)

    mobile_cfg = None
    for scenario in cfg.scenarios:
        if scenario.mobile:
            mobile_cfg = scenario.mobile
            break

    if mobile_cfg is None:
        typer.echo("No mobile scenario found in config.", err=True)
        raise typer.Exit(1)

    provider = AppiumMobileProvider()
    try:
        provider.launch_without_recording(mobile_cfg)
        source = provider.page_source()

        if raw_xml:
            typer.echo(source)
        else:
            _print_accessibility_tree(source)

        # Take screenshot alongside the tree
        screenshot_path = Path("output") / "inspect_screenshot.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        provider.screenshot(screenshot_path)
        typer.echo(f"\n  Screenshot: {screenshot_path}")
    except Exception as exc:
        typer.echo(f"  Inspect failed: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        try:
            provider.close()
        except Exception:
            pass


def _print_accessibility_tree(xml_source: str) -> None:
    """Parse XML page source and print a human-readable tree."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_source)
    except ET.ParseError:
        typer.echo(xml_source)
        return

    _USEFUL_ATTRS = {
        "name",
        "label",
        "text",
        "content-desc",
        "accessibility-id",
        "resource-id",
        "class",
        "type",
        "visible",
        "enabled",
        "accessible",
        "value",
    }

    def _walk(el: ET.Element, depth: int = 0) -> None:
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        attrs = {k: v for k, v in el.attrib.items() if k in _USEFUL_ATTRS and v}
        indent = "  " * depth
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        line = f"{indent}<{tag}"
        if attr_str:
            line += f" {attr_str}"
        line += ">"
        typer.echo(line)
        for child in el:
            _walk(child, depth + 1)

    _walk(root)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


if __name__ == "__main__":
    app()
