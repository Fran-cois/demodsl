# DemoDSL YAML Examples

Auto-generated from `examples/` directory.

---

## Minimal — Navigate & Scroll

Source: `examples/demo_navigate_scroll.yaml`

```yaml
# Feature demo: Navigate & Scroll
# Shows basic page navigation and scrolling actions
metadata:
  title: "Navigate & Scroll Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"

scenarios:
  - name: "Navigate and Scroll"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Navigate to the target URL. The page loads and waits for network idle."
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 400
        narration: "Scroll down 400 pixels to reveal the Quick Start section."
        wait: 1.5

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Continue scrolling to the Features grid."
        wait: 1.5

      - action: "scroll"
        direction: "up"
        pixels: 300
        narration: "Scroll back up to review content we passed."
        wait: 1.5

pipeline:
  - generate_narration: {}
  - edit_video: {}

output:
  filename: "demo_navigate_scroll.mp4"
  directory: "output/"
```

---

## Browser Effects

Source: `examples/demo_browser_effects.yaml`

```yaml
# Feature demo: Browser visual effects
# Showcases spotlight, highlight, glow, neon_glow, success_checkmark
# Note: confetti/sparkle/shockwave use heavy canvas JS, tested separately
metadata:
  title: "Browser Effects Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"

scenarios:
  - name: "Effects Showcase"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Visual effects are injected in real-time via JavaScript during browser capture."
        wait: 2.0
        effects:
          - type: "spotlight"
            duration: 2.0
            intensity: 0.8

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "The highlight effect adds a glowing box-shadow on hovered elements."
        wait: 1.5
        effects:
          - type: "highlight"
            duration: 2.0
            color: "#FFD700"

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "The glow effect creates an inner glow around the viewport."
        wait: 1.5
        effects:
          - type: "glow"
            duration: 2.0
            color: "#6366f1"

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "Neon glow adds a vivid colored border around the entire page."
        wait: 1.5
        effects:
          - type: "neon_glow"
            duration: 2.0
            color: "#FF00FF"

      - action: "screenshot"
        filename: "effects_final.png"
        narration: "The success checkmark shows an animated green check overlay."
        wait: 1.5
        effects:
          - type: "success_checkmark"
            duration: 2.0

pipeline:
  - generate_narration: {}
  - edit_video: {}

output:
  filename: "demo_browser_effects.mp4"
  directory: "output/"
```

---

## Multi-Scenario

Source: `examples/demo_multi_scenario.yaml`

```yaml
# Feature demo: Multiple scenarios in one config
# Shows how to define two separate browser sessions
metadata:
  title: "Multi-Scenario Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"

scenarios:
  - name: "Landing Page Overview"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Scenario one captures the landing page. Each scenario gets its own browser session."
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 800
        narration: "Scroll through the features section in the first scenario."
        wait: 2.0

      - action: "screenshot"
        filename: "landing_overview.png"
        narration: "Capture a screenshot at the end of scenario one."
        wait: 1.5

  - name: "Docs Deep Dive"
    url: "https://fran-cois.github.io/demodsl/docs"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/docs"
        narration: "Scenario two opens the documentation page in a new browser."
        wait: 2.0

      - action: "click"
        locator:
          type: "css"
          value: "a[href='#cli']"
        narration: "Navigate to the CLI reference via the sidebar."
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 400
        narration: "Multiple scenarios are executed sequentially and concatenated in the final output."
        wait: 1.5

pipeline:
  - generate_narration: {}
  - edit_video: {}

output:
  filename: "demo_multi_scenario.mp4"
  directory: "output/"
```

---

## Voice Narration

Source: `examples/demo_voice_narration.yaml`

```yaml
# Feature demo: Voice narration with gTTS
# Showcases TTS narration synced to browser actions
metadata:
  title: "Voice Narration Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"
  speed: 1.0

scenarios:
  - name: "Narrated Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: >
          Welcome to DemoDSL. Every step in your configuration can include
          a narration field. The text is automatically converted to speech
          using your chosen TTS engine. Here we use gTTS, which is free
          and requires no API key.
        wait: 3.0

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: >
          DemoDSL supports twelve voice engines, from cloud providers like
          ElevenLabs and OpenAI, to local options like Piper and eSpeak.
          The generated audio clips are synced to the video timeline.
        wait: 3.0

      - action: "scroll"
        direction: "down"
        pixels: 700
        narration: >
          If no API key is found for the selected engine, DemoDSL falls
          back to a silent dummy provider. This lets you develop and test
          your demo configurations without any credentials.
        wait: 3.0

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: >
          Voice narration brings your product demos to life. Combine it
          with visual effects and browser automation for a polished,
          professional result.
        wait: 2.0

pipeline:
  - generate_narration: {}
  - edit_video: {}

output:
  filename: "demo_voice_narration.mp4"
  directory: "output/"
```

---

## Avatar

Source: `examples/demo_avatar.yaml`

```yaml
# Feature demo: Avatar overlay synced to narration
# Showcases animated avatar (free) with bounce style
metadata:
  title: "Avatar Narration Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"
  speed: 1.0

scenarios:
  - name: "Avatar Narrated Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 1280
      height: 720

    # Avatar configuration — appears during narration
    avatar:
      enabled: true
      provider: "animated"        # free, no API key needed
      # image: "path/to/avatar.png"  # optional custom image
      position: "bottom-right"
      size: 100
      style: "bounce"             # bounce | waveform | pulse
      shape: "circle"             # circle | rounded | square
      background: "rgba(0,0,0,0.5)"

    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: >
          Welcome to DemoDSL! I'm your animated avatar narrator.
          I appear in the corner and bounce along with the narration audio.
        wait: 3.0

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: >
          DemoDSL supports two avatar modes. The free animated mode uses
          Pillow to generate a bouncing avatar synced to audio amplitude.
          No API key or GPU required.
        wait: 3.0

      - action: "scroll"
        direction: "down"
        pixels: 700
        narration: >
          For a realistic talking head, you can switch to paid providers
          like D-ID or HeyGen. Just set your API key and a source photo,
          and the avatar will lip-sync naturally to your narration.
        wait: 3.0

pipeline:
  - generate_narration: {}
  - composite_avatar: {}
  - edit_video: {}

output:
  filename: "demo_avatar.mp4"
  directory: "output/"
```

---

## Popup Cards

Source: `examples/demo_popup_card.yaml`

```yaml
# Demo: Popup Cards — synced text overlays with progressive item reveal
metadata:
  title: "Popup Card Feature Demo"
  description: "Shows popup cards synced with narration, including progressive list reveals"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"
  speed: 1.0

scenarios:
  - name: "Card Overlay Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    popup_card:
      enabled: true
      position: "bottom-right"
      theme: "glass"
      animation: "slide"
      accent_color: "#818cf8"
      show_progress: true

    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Welcome to DemoDSL. Let me walk you through the key features."
        card:
          title: "DemoDSL"
          body: "A DSL-driven automated product demo video generator."
          icon: "🎬"
        wait: 2.0

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "DemoDSL includes six integrated phases: browser automation, voice narration, visual effects, video composition, audio mixing, and multi-format export."
        card:
          title: "Six Integrated Phases"
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
        narration: "The architecture uses five proven design patterns for maximum flexibility."
        card:
          title: "Design Patterns"
          icon: "🏗️"
          items:
            - "Abstract Factory"
            - "Command Pattern"
            - "Chain of Responsibility"
            - "Registry Strategy"
            - "Builder"

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Everything is configured through simple YAML files. No code needed."
        card:
          title: "Zero Code Required"
          body: "Define your entire demo in a single YAML or JSON file."
          icon: "📄"
        wait: 3.0

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "Multiple output formats are supported for every platform."
        card:
          title: "Output Formats"
          icon: "📦"
          items:
            - "MP4 (H.264)"
            - "WebM (VP8/VP9)"
            - "GIF (animated)"
            - "Social Media Optimized"
        wait: 2.0

output:
  filename: "demo_popup_card.mp4"
  directory: "output/"

pipeline:
  - generate_narration: {}
  - edit_video: {}
```

---

## Cursor Trails

Source: `examples/demo_cursor_trails.yaml`

```yaml
metadata:
  title: "Cursor Trail Variants Demo"
  version: "1.0"

scenarios:
  - name: "Default dot trail"
    url: "https://example.com"
    viewport: {width: 1920, height: 1080}
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail
        wait: 3

  - name: "Rainbow trail"
    url: "https://example.com"
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail_rainbow
        wait: 3

  - name: "Comet trail"
    url: "https://example.com"
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail_comet
        wait: 3

  - name: "Glow trail"
    url: "https://example.com"
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail_glow
            color: "#00BFFF"
        wait: 3

  - name: "Line trail"
    url: "https://example.com"
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail_line
        wait: 3

  - name: "Particles trail"
    url: "https://example.com"
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail_particles
        wait: 3

  - name: "Fire trail"
    url: "https://example.com"
    steps:
      - action: navigate
        url: "https://example.com"
        effects:
          - type: cursor_trail_fire
        wait: 3
```

---

## Subtitles

Source: `examples/demo_subtitle.yaml`

```yaml
# Feature demo: Subtitle styles
# Showcases all subtitle display modes synced with narration
metadata:
  title: "Subtitle Styles Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"
  speed: 1.0

# Top-level subtitle config (applies to all scenarios)
# Style options: classic, tiktok, color, word_by_word, typewriter, karaoke
# Speed options: slow, normal, fast, tiktok
subtitle:
  enabled: true
  style: "tiktok"        # bold centered word-by-word highlights
  speed: "tiktok"        # fast display (6 words/sec)
  font_size: 64
  font_color: "#FFFFFF"
  highlight_color: "#FFD700"
  position: "center"

scenarios:
  - name: "TikTok Style"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 1080
      height: 1920
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: >
          DemoDSL lets you create stunning demo videos with just YAML.
          No editing software needed!
        wait: 4.0

      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: >
          Add subtitles in six different styles. TikTok style shows
          bold highlighted words one at a time.
        wait: 4.0

      - action: "scroll"
        direction: "down"
        pixels: 400
        narration: >
          Classic mode gives you traditional bottom-bar subtitles.
          Karaoke mode fills words with color progressively.
        wait: 4.0

pipeline:
  - restore_audio:
      normalize: true
  - edit_video: {}
  - burn_subtitles: {}
  - optimize:
      format: mp4
      codec: h264
      quality: high

output:
  filename: "demo_subtitle_tiktok.mp4"
  directory: "output/"
```

---

## Turbo Mode — Fast Preview

Source: `examples/demo_turbo.yaml`

Run with `--turbo` to skip heavy post-processing and clamp all waits to 50ms:
```bash
demodsl run examples/demo_turbo.yaml --turbo
```

```yaml
# Turbo mode — fast preview generation
# Turbo skips avatars, 3D rendering, subtitles, post-effects, speed re-encode.
# All browser waits are clamped to 50ms. Remove --turbo for the full render.

metadata:
  title: "Turbo Preview Demo"
  version: "2.0.0"

voice:
  engine: "gtts"
  voice_id: "en"

subtitle:
  enabled: true
  style: "tiktok"
  position: "bottom"

scenarios:
  - name: "Quick Site Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "chrome"
    viewport:
      width: 1280
      height: 720
    natural: true
    # Avatar is per-scenario — skipped in turbo mode
    avatar:
      enabled: true
      provider: "animated"
      position: "bottom-right"
      size: 100
      style: "bounce"
      shape: "circle"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Welcome to DemoDSL. This is a turbo preview."
        wait: 2.0
        effects:
          - type: "spotlight"
            duration: 1.5

      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "In turbo mode all waits are clamped to 50ms."
        wait: 1.5

      - action: "screenshot"
        filename: "turbo_preview.png"
        narration: "Remove --turbo for the final render with all features."
        wait: 1.0

pipeline:
  - generate_narration: {}
  - composite_avatar: {}   # skipped in turbo
  - edit_video: {}
  - burn_subtitles: {}     # skipped in turbo

output:
  filename: "demo_turbo_preview.mp4"
  directory: "output/"
```
