# DemoDSL YAML Examples

Annotated examples from simple to complex.

---

## 1. Minimal — Navigate & Scroll

The simplest useful demo: navigate to a URL, scroll, and record.

```yaml
metadata:
  title: "Navigate & Scroll Demo"
  version: "2.0.0"

voice:
  engine: "gtts"          # Free TTS, no API key
  voice_id: "en"

scenarios:
  - name: "Navigate and Scroll"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Navigate to the target URL."
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 400
        narration: "Scroll down to reveal the Quick Start section."
        wait: 1.5

      - action: "scroll"
        direction: "up"
        pixels: 300
        narration: "Scroll back up to review content."
        wait: 1.5

pipeline:
  - generate_narration: {}
  - edit_video: {}

output:
  filename: "demo_navigate_scroll.mp4"
  directory: "output/"
```

**Key points:**
- First step is always `navigate` with the URL
- `wait` adds a pause after each step
- Minimal pipeline: `generate_narration` + `edit_video`

---

## 2. With Effects — Browser Visual Effects

Adds spotlight, highlight, glow effects during capture.

```yaml
metadata:
  title: "Browser Effects Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"

scenarios:
  - name: "Effects Showcase"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Visual effects are injected in real-time via JavaScript."
        wait: 2.0
        effects:
          - type: "spotlight"
            duration: 2.0
            intensity: 0.8

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "The highlight effect adds a glowing box-shadow."
        wait: 1.5
        effects:
          - type: "highlight"
            duration: 2.0
            color: "#FFD700"

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "Neon glow adds a vivid colored border."
        wait: 1.5
        effects:
          - type: "neon_glow"
            duration: 2.0
            color: "#FF00FF"

pipeline:
  - generate_narration: {}
  - edit_video: {}
```

**Key points:**
- `effects` is a list — multiple effects per step allowed
- Each effect has `type` + optional params (`duration`, `intensity`, `color`)

---

## 3. Multi-Scenario — Separate Browser Sessions

Two independent scenarios captured sequentially then concatenated.

```yaml
metadata:
  title: "Multi-Scenario Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"

scenarios:
  - name: "Landing Page Overview"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Scenario one captures the landing page."
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 800
        narration: "Scroll through the features section."
        wait: 2.0

      - action: "screenshot"
        filename: "landing_overview.png"
        narration: "Capture a screenshot."
        wait: 1.5

  - name: "Docs Deep Dive"
    url: "https://fran-cois.github.io/demodsl/docs"
    browser: "webkit"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/docs"
        narration: "Scenario two opens the documentation."
        wait: 2.0

      - action: "click"
        locator:
          type: "css"
          value: "a[href='#cli']"
        narration: "Navigate to the CLI reference."
        wait: 2.0

pipeline:
  - generate_narration: {}
  - edit_video: {}

output:
  filename: "demo_multi_scenario.mp4"
  directory: "output/"
```

**Key points:**
- Each scenario gets its own browser instance
- `click` uses a `locator` with `type` + `value`
- `screenshot` takes a capture saved to the workspace

---

## 4. Avatar + Popup Cards — Rich Overlays

Full-featured demo with animated avatar and info cards.

```yaml
metadata:
  title: "Rich Demo with Avatar & Cards"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"
  speed: 1.0

scenarios:
  - name: "Feature Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 1280
      height: 720

    avatar:
      enabled: true
      provider: "animated"
      position: "bottom-right"
      size: 100
      style: "bounce"
      shape: "circle"

    popup_card:
      enabled: true
      theme: "glass"
      animation: "slide"
      accent_color: "#818cf8"
      show_progress: true

    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Welcome to DemoDSL!"
        card:
          title: "DemoDSL"
          body: "Automated product demo generator."
          icon: "🎬"
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Six integrated phases for complete demos."
        card:
          title: "Six Phases"
          icon: "⚡"
          items:
            - "Browser Automation"
            - "Voice Narration"
            - "Visual Effects"
            - "Video Composition"
            - "Audio Mixing"
            - "Multi-format Export"

      - action: "scroll"
        direction: "down"
        pixels: 700
        narration: "Everything configured through YAML."
        card:
          title: "Zero Code Required"
          body: "Define your demo in a single YAML file."
          icon: "📄"
        wait: 3.0

pipeline:
  - generate_narration: {}
  - composite_avatar: {}     # Avatar overlay BEFORE edit_video
  - edit_video: {}

output:
  filename: "demo_rich.mp4"
  directory: "output/"
```

**Key points:**
- `avatar` and `popup_card` are configured at the scenario level
- `card` on each step shows contextual info/lists
- `composite_avatar` must be in the pipeline before `edit_video`
- `items` in a card are revealed progressively synced to narration

---

## 5. Voice Narration with Long Text

Using multi-line narration strings with YAML block scalars.

```yaml
steps:
  - action: "navigate"
    url: "https://example.com"
    narration: >
      Welcome to our product. This narration text is automatically
      converted to speech using the configured TTS engine. The audio
      duration determines how long each step is shown in the video.
    wait: 3.0
```

**Key point:** Use `>` for folded block scalars (wraps into one paragraph) or `|` for literal blocks (preserves newlines).
