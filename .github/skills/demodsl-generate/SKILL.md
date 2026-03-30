---
name: demodsl-generate
description: "Generate and run DemoDSL demo configurations. Use when: creating a YAML demo config, building a product demo scenario, generating browser automation with narration and effects, running demodsl, scaffolding a new demo file."
argument-hint: "Describe the demo you want (URL, actions, effects, narration style)"
---

# DemoDSL Config Generator & Runner

Generate valid DemoDSL YAML configurations from a natural language description, then validate and execute them.

## When to Use

- User wants to create a product demo video from a URL
- User asks to generate a YAML/JSON config for demodsl
- User wants to add scenarios, effects, narration, or avatars to a demo
- User asks to run or execute a demo configuration

## Procedure

### Step 1 — Understand the request

Extract from the user's description:
- **Target URL(s)** to demo
- **Actions** to perform (navigate, click, type, scroll, screenshot)
- **Effects** desired (spotlight, confetti, glow, camera movements, etc.)
- **Narration** style and content
- **Features** to enable (avatar, subtitles, popup cards, cursor, glow select)
- **Output** preferences (format, resolution, filename)

If the user doesn't specify details, use sensible defaults:
- Browser: `webkit`, Viewport: `1280x720`
- Voice: `gtts` engine (free, no API key)
- Pipeline: `generate_narration` → `edit_video`

### Step 2 — Generate the YAML config

Build the config following these rules:

#### Required sections
```yaml
metadata:
  title: "..."        # Always required
  version: "2.0.0"    # Always "2.0.0"

scenarios:
  - name: "..."       # At least one scenario
    url: "..."        # Target URL
    steps: [...]      # At least one step

pipeline:
  - generate_narration: {}   # If narration is used
  - edit_video: {}           # Always needed for video output
```

#### Structure rules
1. Every step needs an `action` field: `navigate`, `click`, `type`, `scroll`, `wait_for`, or `screenshot`
2. The first step of a scenario should be `action: "navigate"` with the scenario URL
3. `click` and `type` steps need a `locator` with `type` (css/id/xpath/text) and `value`
4. `scroll` steps need `direction` (up/down/left/right) and `pixels`
5. `narration` is a free-text string on each step — it becomes TTS audio
6. `wait` on a step sets a pause in seconds after execution
7. `effects` is a list on each step — each has a `type` and optional params
8. `pre_steps` is an optional list on a scenario — steps executed before recording starts (useful for page loading, waiting for assets, login flows, etc.)

#### Pre-steps (warmup without recording)
Use `pre_steps` to run actions before recording begins. This is useful for initial page loads, waiting for heavy assets, or any setup that should not appear in the final video:
```yaml
scenarios:
  - name: "My demo"
    url: "https://example.com"
    pre_steps:
      - action: "navigate"
        url: "https://example.com"
      - action: "wait_for"
        locator: { type: "css", value: "#app-loaded" }
        timeout: 10
        wait: 2
    steps:
      - action: "click"
        locator: { type: "css", value: "#start-btn" }
        narration: "Click here to begin"
```

#### Pipeline ordering
The pipeline stages must be ordered logically:
1. `restore_audio` — denoise/normalize/EQ/compression/de-essing/reverb/silence-removal (optional)
2. `restore_video` — stabilize/sharpen (optional)
3. `color_correction` — brightness/contrast/saturation/gamma/white balance (optional)
4. `apply_effects` — post-processing effects (optional)
5. `generate_narration` — TTS audio generation (if narration used)
6. `render_device_mockup` — 3D device frame (optional)
7. `composite_avatar` — avatar overlay (if avatar enabled)
8. `edit_video` — intro/outro/transitions/watermark composition
9. `burn_subtitles` — subtitle burning (if subtitles enabled)
10. `mix_audio` — voice + background music (if background music used)
11. `speed` — global speed adjustment (optional)
12. `frame_rate` — frame rate conversion (optional)
13. `pip` — picture-in-picture overlay (optional)
14. `chapters` — chapter markers (optional)
15. `thumbnail` — thumbnail extraction (optional)
16. `optimize` — format/codec/quality conversion (optional)

#### Voice engines
- `gtts` — Free, no API key, use for testing/dev
- `elevenlabs` — High quality, needs `ELEVENLABS_API_KEY`
- `openai` — Good quality, needs `OPENAI_API_KEY`
- `espeak` — Offline, robotic voice, no API key
- Others: `google`, `azure`, `aws_polly`, `cosyvoice`, `coqui`, `piper`, `local_openai`, `custom`

Default to `gtts` unless the user requests a specific engine.

### Step 3 — Write the file

Save the generated YAML to the workspace. Default filename: `demo.yaml` in the project root, or use the name the user provides.

### Step 4 — Validate

Run validation:
```bash
cd /Users/famat/PycharmProjects/SIDE/demodsl && python -m demodsl validate <config_file>
```

If validation fails, fix the YAML and retry.

### Step 5 — Execute

Run the demo:
```bash
cd /Users/famat/PycharmProjects/SIDE/demodsl && python -m demodsl run <config_file> --output-dir output/
```

Add `--skip-voice` if the user wants a quick test without TTS.
Add `--dry-run` if the user just wants to verify the config.
Add `--verbose` for debug logging.

## Feature Configuration Quick Reference

### Avatar (animated narrator in corner)
```yaml
avatar:
  enabled: true
  provider: "animated"     # free | "d-id"/"heygen" need API keys
  position: "bottom-right"
  size: 100
  style: "bounce"          # 40+ styles available
  shape: "circle"
```
Add `composite_avatar: {}` to the pipeline BEFORE `edit_video`.

### Subtitles
```yaml
subtitle:
  enabled: true
  style: "classic"    # classic|tiktok|color|word_by_word|typewriter|karaoke|bounce|cinema|highlight_line|fade_word|emoji_react
  position: "bottom"
```
Add `burn_subtitles: {}` to the pipeline AFTER `edit_video`.

### Popup cards
```yaml
popup_card:
  enabled: true
  theme: "glass"      # glass|dark|light|gradient
  animation: "slide"
```
Then on steps, add a `card` field with `title`, `body`, `items`, `icon`.

### Cursor customization
```yaml
cursor:
  visible: true
  style: "dot"        # dot|pointer
  color: "#ef4444"
  click_effect: "ripple"   # ripple|pulse|none
```

### Glow select (element hover glow)
```yaml
glow_select:
  enabled: true
  colors: ["#a855f7", "#6366f1", "#ec4899"]
```

### Background music + audio
```yaml
audio:
  background_music:
    file: "audio/music.mp3"
    volume: 0.3
    ducking_mode: "moderate"
  voice_processing:
    enhance_clarity: true      # boost vocal presence (2-5kHz)
    enhance_warmth: false      # boost low-mids (150-300Hz)
    de_ess: true               # reduce sibilance (s/sh sounds)
    noise_reduction: true
    noise_reduction_strength: "moderate"  # light|moderate|heavy|auto
    remove_silence: true
    min_silence_duration: 0.5
  effects:
    eq_preset: "podcast"       # podcast|warm|bright|telephone|radio|deep|custom
    compression:
      preset: "voice"          # voice|podcast|broadcast|gentle|custom
    reverb_preset: "small_room"  # none|small_room|large_room|hall|cathedral|plate
```
Add `restore_audio: {}` (before narration) and `mix_audio: {}` to the pipeline.

### Color correction
```yaml
video:
  color_correction:
    brightness: 0.1            # -1.0 to 1.0
    contrast: 0.2              # -1.0 to 1.0
    saturation: 1.2            # 0.0 to 3.0
    gamma: 1.0                 # 0.1 to 3.0
    white_balance: "daylight"  # auto|daylight|tungsten|fluorescent|cloudy
    temperature: 5600          # 2000-10000 Kelvin (overrides white_balance)
```
Add `color_correction: {}` to the pipeline.

### Speed control
Per-step speed: add `speed: 0.5` (slow-mo) or `speed: 2.0` (fast) on any step.
Speed ramp: add `speed_ramp: {start_speed: 1.0, end_speed: 0.5, ease: "ease-in-out"}`.
Freeze frame: add `freeze_duration: 3.0` on a step.
Audio offset (J/L cuts): add `audio_offset: -0.5` (J-cut) or `audio_offset: 0.5` (L-cut).
Global speed: add `speed: {speed: 1.5}` to the pipeline.

### Picture-in-Picture
```yaml
video:
  pip:
    source: "webcam_recording.mp4"
    position: "bottom-right"
    size: 0.25                 # 25% of main video width
    shape: "rounded"           # rectangle|circle|rounded
    opacity: 0.95
```
Add `pip: {}` to the pipeline.

### Social export profiles
```yaml
output:
  social:
    - platform: "youtube"
    - platform: "instagram_reels"
      crop_mode: "center"      # center|smart|manual
    - platform: "tiktok"
    - platform: "twitter"
    - platform: "linkedin"
  thumbnails:
    - auto: true
      format: "png"
    - timestamp: 5.0
      format: "jpeg"
```
Add `thumbnail: {}` and `chapters: {}` to the pipeline if needed.

## References

- [Schema reference](./references/schema-reference.md) — all fields, types, defaults
- [Effects catalog](./references/effects-catalog.md) — 50+ effects with params
- [Examples](./references/examples.md) — annotated YAML examples
