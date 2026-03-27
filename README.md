# DemoDSL

**DSL-driven automated product demo video generator.**

Define your product demos in YAML or JSON — DemoDSL handles browser automation, voice narration, visual effects, video editing, and final export.

## Features

- **YAML & JSON DSL** — Declarative scenario definitions with steps, effects, and narration
- **Browser Automation** — Playwright-powered capture (Chrome, Firefox, WebKit)
- **Voice Narration** — ElevenLabs TTS with automatic sync to video
- **18 Visual Effects** — Spotlight, confetti, glitch, neon glow, and more
- **Video Composition** — Intro/outro, transitions, watermarks via MoviePy
- **Audio Mixing** — Background music with smart ducking during narration
- **Multi-format Export** — MP4, WebM, GIF + social media presets (YouTube, Instagram, Twitter)

## Installation

```bash
pip install demodsl
```

Then install Playwright browsers:

```bash
playwright install chromium
```

## Quick Start

**1. Generate a template:**

```bash
demodsl init
```

**2. Edit `demo.yaml`:**

```yaml
metadata:
  title: "My Product Demo"

scenarios:
  - name: "Main Demo"
    url: "https://myapp.com"
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "Welcome to our product!"
        effects:
          - type: "spotlight"
            duration: 2.0

pipeline:
  - generate_narration: {}
  - edit_video: {}
  - mix_audio: {}
  - optimize:
      format: "mp4"
```

**3. Run:**

```bash
demodsl run demo.yaml
```

**4. Validate without executing:**

```bash
demodsl validate demo.yaml
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `demodsl run <config>` | Execute the full pipeline |
| `demodsl validate <config>` | Validate config without executing |
| `demodsl init` | Generate a minimal template |
| `demodsl init -o demo.json` | Generate a JSON template |

### Options

- `--output-dir, -o` — Output directory (default: `output/`)
- `--dry-run` — Log all steps without executing
- `--skip-voice` — Skip TTS generation (dev mode)
- `--verbose, -v` — Debug logging

## Architecture

DemoDSL uses a modular architecture with 5 design patterns:

| Component | Pattern | Purpose |
|-----------|---------|---------|
| Providers | Abstract Factory | Voice, Browser, Render provider instantiation |
| Browser Actions | Command | Navigate, Click, Type, Scroll, WaitFor, Screenshot |
| Pipeline | Chain of Responsibility | 8 stages with critical/optional error handling |
| Visual Effects | Registry + Strategy | 18 effects in 2 registries (browser JS + post-processing) |
| Video Composition | Builder | Progressive intro → segments → watermark → outro assembly |

## Pipeline Stages

| Stage | Critical | Description |
|-------|----------|-------------|
| `restore_audio` | Optional | Denoise + normalize audio |
| `restore_video` | Optional | Stabilize + sharpen video |
| `apply_effects` | Optional | Post-processing visual effects |
| `generate_narration` | **Critical** | TTS generation + video sync |
| `render_device_mockup` | Optional | Device frame overlay |
| `edit_video` | **Critical** | Intro, outro, transitions, watermark |
| `mix_audio` | **Critical** | Voice + background music ducking |
| `optimize` | **Critical** | Final encoding + compression |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ELEVENLABS_API_KEY` | ElevenLabs TTS API key |

Without an API key, DemoDSL falls back to a silent dummy provider for development.

## License

MIT
