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
  <video src="https://raw.githubusercontent.com/Fran-cois/demodsl/main/docs/public/videos/demodsl_site_demo.mp4" width="720" controls></video>
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
- **Video Composition** — Intro/outro, transitions, watermarks via MoviePy
- **Audio Mixing** — Background music with smart ducking during narration
- **11 Pipeline Stages** — Chain of Responsibility with critical/optional error handling
- **Remotion Renderer** — React-based video composition alternative
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
- `--verbose, -v` — Debug logging

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

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.
