# DemoDSL

[![Tests](https://github.com/Fran-cois/demodsl/actions/workflows/test.yml/badge.svg)](https://github.com/Fran-cois/demodsl/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-81%25-brightgreen)](https://github.com/Fran-cois/demodsl/actions/workflows/test.yml)
[![Perf](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Fran-cois/demodsl/main/docs/public/perf/badge.json)](docs/public/perf/PERF_RESULTS.md)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20|%203.12-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**DSL-driven automated product demo video generator.**

Define your product demos in YAML or JSON — DemoDSL handles browser automation, voice narration, visual effects, video editing, and final export.

## Demo

> This video was generated automatically by DemoDSL — running `demodsl run demo_site.yaml` against its own documentation site.

<div align="center">
  <a href="https://github.com/Fran-cois/demodsl/blob/main/docs/public/videos/demodsl_site_demo.mp4">
    <img src="https://raw.githubusercontent.com/Fran-cois/demodsl/main/docs/public/videos/demodsl_site_demo_thumbnail.jpg" alt="DemoDSL Demo Video" width="720" />
  </a>
  <br />
  <sub>▶ Click the image to watch the full demo video</sub>
</div>

<details>
<summary>YAML config used</summary>

```yaml
metadata:
  title: "DemoDSL Documentation Site Tour"

voice:
  engine: "gtts"
  voice_id: "en"

subtitle:
  enabled: true
  style: "classic"

scenarios:
  - name: "Landing Page Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport: { width: 1280, height: 720 }
    avatar:
      enabled: true
      provider: "animated"
      style: "clippy"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Welcome to DemoDSL..."
      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Discover the Quick Start section..."

pipeline:
  - generate_narration: {}
  - edit_video: {}
  - mix_audio: {}
  - burn_subtitles: {}
  - composite_avatar: {}
  - optimize: { format: "mp4" }
```

</details>

## Features

- **YAML & JSON DSL** — Declarative scenario definitions with steps, effects, and narration
- **Browser Automation** — Playwright-powered capture (Chrome, Firefox, WebKit)
- **12 Voice Providers** — ElevenLabs, OpenAI, Azure, Google, AWS Polly, CosyVoice, Coqui, Piper, eSpeak, gTTS, local OpenAI-compatible, custom
- **63 Visual Effects** — 33 browser JS effects + 30 post-processing effects (camera, cinematic, retro, transitions, overlays)
- **Animated Avatars** — 61 built-in styles with 4 providers (animated, D-ID, HeyGen, SadTalker)
- **Subtitles** — 6 styles (classic, TikTok, color, word-by-word, typewriter, karaoke) with Word-level timing
- **Cursor Overlay** — Smooth animated cursor with click effects (ripple, pulse)
- **Popup Cards** — Glass/dark/light/gradient cards with progressive item reveal
- **Video Composition** — Intro/outro, transitions, watermarks via Remotion (React/Node)
- **Audio Mixing** — Background music with smart ducking during narration
- **11 Pipeline Stages** — Chain of Responsibility with critical/optional error handling
- **MoviePy Renderer** — Legacy Python renderer (deprecated, will be removed in a future release)
- **Cloud Deploy** — S3, GCS, Azure Blob, Cloudflare R2, custom S3-compatible
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
- `--turbo` — Fast preview: minimal waits, skip heavy post-processing (avatars, 3D, subtitles)
- `--verbose, -v` — Debug logging

## Effect Library & Anchors

demodsl ships with 27+ reusable presets (callouts, intros, CTAs, dataviz, social
proof, transitions…) in `library/`. Use them with `$use` + `$params`:

```yaml
timeline:
  layers:
    - $use: callouts/circle_highlight
      $params:
        x: 880
        y: 530
        radius: 90
```

### Selector-driven layout with `anchors:`

Instead of hard-coding pixel coordinates, declare **anchors** at the top of your
config and let demodsl probe the live page (via Playwright) to extract bounding
boxes once. Anchors expose `x, y, w, h, cx, cy, left, top, right, bottom`:

```yaml
anchors:
  signup_btn:
    selector: "#signup"      # ← probed at load time
  hero:
    x: 100                   # ← or supply coords manually
    y: 200
    w: 400
    h: 80

scenarios:
  - name: demo
    url: https://app.example.com
    timeline:
      layers:
        # Style 1 — explicit template expressions
        - $use: callouts/circle_highlight
          $params:
            x: "{{ anchors.signup_btn.cx }}"
            y: "{{ anchors.signup_btn.cy }}"
            radius: "{{ anchors.signup_btn.w / 2 + 20 }}"

        # Style 2 — the `anchor:` shortcut auto-fills declared x/y/w/h
        - $use: callouts/tooltip
          $params:
            anchor: signup_btn
            number: "1"
            text: "Click here to start"
```

If a selector can't be resolved (network error, missing element, no Playwright),
demodsl logs a warning and falls back to viewport center so the demo still
renders.

See [`examples/demo_anchors_selectors.yaml`](examples/demo_anchors_selectors.yaml)
for a complete demo.

## Architecture

DemoDSL uses a modular architecture with 5 design patterns:

| Component | Pattern | Purpose |
|-----------|---------|---------|
| Providers | Abstract Factory | Voice, Browser, Render provider instantiation |
| Browser Actions | Command | Navigate, Click, Type, Scroll, WaitFor, Screenshot |
| Pipeline | Chain of Responsibility | 11 stages with critical/optional error handling |
| Visual Effects | Registry + Strategy | 63 effects in 2 registries (browser JS + post-processing) |
| Video Composition | Builder | Progressive intro → segments → watermark → outro assembly |

## Pipeline Stages

| Stage | Critical | Description |
|-------|----------|-------------|
| `restore_audio` | Optional | Denoise (afftdn) + normalize (loudnorm) audio via ffmpeg |
| `restore_video` | Optional | Stabilize (vidstab) + sharpen (unsharp) video via ffmpeg |
| `apply_effects` | Optional | Post-processing visual effects (ordering stage) |
| `generate_narration` | **Critical** | TTS generation + video sync (ordering stage) |
| `render_device_mockup` | Optional | Device frame overlay via ffmpeg composite |
| `edit_video` | **Critical** | Intro, outro, transitions, watermark (ordering stage) |
| `mix_audio` | **Critical** | Voice + background music ducking |
| `optimize` | **Critical** | Final encoding with CRF or target bitrate |
| `composite_avatar` | Optional | Avatar overlay compositing (ordering stage) |
| `burn_subtitles` | Optional | Subtitle rendering (ordering stage) |
| `deploy` | Optional | Cloud deployment (ordering stage) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ELEVENLABS_API_KEY` | ElevenLabs TTS API key |
| `OPENAI_API_KEY` | OpenAI API key (tts-1-hd) |
| `ANTHROPIC_API_KEY` | Anthropic API key (discovery harness `--policy llm --llm anthropic`) |
| `OPENROUTER_API_KEY` | OpenRouter API key (discovery harness `--policy llm --llm openrouter`) |
| `OPENROUTER_BASE_URL` | OpenRouter base URL (default: `https://openrouter.ai/api/v1`) |
| `OPENROUTER_SITE_URL` | Optional `HTTP-Referer` sent to OpenRouter for app ranking |
| `OPENROUTER_APP_NAME` | Optional `X-Title` sent to OpenRouter (default: `demodsl`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google Cloud service account JSON |
| `AZURE_SPEECH_KEY` | Azure Cognitive Services Speech key |
| `AZURE_SPEECH_REGION` | Azure region (default: `eastus`) |
| `AWS_ACCESS_KEY_ID` | AWS access key for Polly |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for Polly |
| `AWS_DEFAULT_REGION` | AWS region (default: `us-east-1`) |
| `COSYVOICE_API_URL` | CosyVoice API server URL (default: `http://localhost:50000`) |
| `COQUI_MODEL` | Coqui TTS model name (default: `xtts_v2`) |
| `COQUI_LANGUAGE` | Language code for Coqui TTS (default: `en`) |
| `PIPER_BIN` | Path to piper binary (default: `piper`) |
| `PIPER_MODEL` | Path to Piper `.onnx` voice model (required for `piper` engine) |
| `LOCAL_TTS_URL` | OpenAI-compatible local TTS server URL (default: `http://localhost:8000`) |
| `LOCAL_TTS_API_KEY` | API key for local TTS server (default: `not-needed`) |
| `LOCAL_TTS_MODEL` | Model name for local TTS server (default: `tts-1`) |
| `ESPEAK_BIN` | Path to eSpeak-NG binary (default: `espeak-ng`) |

Without the required credentials, DemoDSL falls back to a silent dummy provider for development.

> **Vintage / debug providers**: `espeak` and `gtts` need no API key — ideal pour le prototypage rapide. `espeak` donne un son robotique rétro, `gtts` utilise Google Translate (nécessite internet + `pip install gtts`).

## Plugins

DemoDSL supports external plugins discovered via Python entry-points. Plugins can provide new pipeline stages, hook callbacks, and providers.

| Plugin | Description | Install |
|--------|-------------|---------|
| [demodsl-blender](https://github.com/Fran-cois/demodsl-blender) | 3D device rendering via Blender (phone/tablet/laptop mockups) | `pip install demodsl-blender` |
| demodsl_webinar | Live webinar simulation overlay (crowd, Q&A, reactions) | Included in `plugins/` |

### Writing a plugin

A plugin registers itself via `pyproject.toml` entry-points:

```toml
[project.entry-points."demodsl.stages"]
render_device_3d = "my_plugin.stage:RenderDevice3DStage"

[project.entry-points."demodsl.providers.blender"]
headless = "my_plugin.provider:HeadlessBlenderProvider"

[project.entry-points."demodsl.hooks"]
my_hook = "my_plugin.hooks:MyHookPlugin"
```

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.
🇫🇷 [Version française](CONTRIBUTING.fr.md)
