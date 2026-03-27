This is a sophisticated DSL that bridges several high-level domains:** ** **browser automation** ,** ** **audio/video synthesis** , and** ** **3D rendering** . Implementing this requires a modular "orchestrator" pattern.

To get the best code output from an AI, your prompt needs to define the architectural boundaries, specifically how to handle the "Heavy Lifting" (FFmpeg, Playwright, Blender/EEVEE).

Here is a comprehensive prompt you can use to generate the library implementation.

---

## The Prompt for Implementation

**Copy and paste the following into your AI coding assistant:**

> "I need to implement a Python library called** **`demobro` that parses and executes a specific DSL (YAML/JSON) for automated product demonstrations.
>
> ### Core Architecture Requirements:
>
> 1. **Model Layer** : Use** ****Pydantic (v2)** to define the schema for the entire YAML structure (Metadata, Voice, Audio, Device Rendering, Video, Scenarios, Pipeline). Ensure it handles optional fields and default values.
> 2. **Provider Pattern** : Implement a** **`Provider` system for external services:
>
> * `VoiceProvider`: Interface for TTS (ElevenLabs, Google, etc.).
> * `BrowserProvider`: Interface for UI interaction (Playwright preferred).
> * `RenderProvider`: Interface for video/3D processing (MoviePy + FFmpeg).
>
> 1. **The Pipeline Engine** : Create an orchestrator that:
>
> * Validates the YAML input.
> * Executes 'Scenarios' to capture raw video/screenshots using Playwright.
> * Passes captures to the 'Pipeline' stages (restoration, effect overlay, narration sync).
>
> 1. **State Management** : The library must maintain a temporary workspace for assets (audio clips, raw frames, rendered segments) before final assembly.
>
> ### Phase Implementation Details:
>
> * **Scenarios** : Use Playwright to navigate. Map the 'effects' (like spotlight or confetti) to JavaScript injections or post-processing metadata for the video editor.
> * **Voice** : Generate MP3s per step based on the** **`narration` field and sync them with the video duration.
> * **Audio** : Use** **`pydub` or** **`ffmpeg-python` to handle background music ducking (lowering volume when narration is active).
> * **Video/Device** : Use** **`MoviePy` for the final composition of intro, outro, transitions, and watermarks.
>
> ### Technical Task:
>
> Please provide the core structure of the library:
>
> 1. `models.py` (Pydantic schemas).
> 2. `engine.py` (The main Orchestrator class).
> 3. `cli.py` (A Typer-based CLI to run** **`demobro run demo.yaml`).
> 4. A brief explanation of how to handle the 3D 'Device Rendering' phase (e.g., as a subprocess call to Blender or a simplified CSS/Transform mockup)."

---

## Recommended Tech Stack for the Implementation

If you are building this yourself or guiding the AI, here is the "Gold Standard" stack for this specific DSL:

| **Phase**             | **Technology Recommendation**                                                    |
| --------------------------- | -------------------------------------------------------------------------------------- |
| **Parsing**           | `PyYAML` + `Pydantic` (for strict typing and validation)                           |
| **Browser Capturing** | `Playwright` and selenium (superior for headful recording and frame-perfect timing) |
| **Video Editing**     | `MoviePy`, `Manim, remotion` (if you want more math-based animations)             |
| **Audio Mixing**      | `Pydub` (for easy volume ducking/merging)                                            |
| **3D Rendering**      | `Blender (optional)` (headless/CLI mode) for the iPhone 15 rendering                 |
| **CLI**               | `Typer` or `Click or better`                                                       |

---

## Implementation Strategy: The "Three-Pass" Approach

Since your DSL is very complex, don't try to code it in one go. I recommend building it in these three passes:

### Pass 1: The "Puppeteer" (Scenarios)

Focus on reading the** **`scenarios` block. Use Playwright to open the browser, perform the actions (click, type, scroll), and record the screen as a high-quality** **`.mp4`.

### Pass 2: The "Voice & Audio" (Narration)

Parse the** **`narration` strings from the steps. Generate the audio files using ElevenLabs API. Calculate the duration of each audio file and use it to "stretch" the video frames of each step so the narration matches the visual action.

### Pass 3: The "Final Cut" (Post-Processing)

This is where the** **`pipeline` block comes in. Use FFmpeg to:

1. Attach the** **`intro` and** **`outro`.
2. Overlay the** **`watermark`.
3. Apply the** **`background_music` with a compressor/ducking filter.
4. Export the different formats (GIF, MP4, etc.).

**Would you like me to generate the Pydantic models (Phase 1) based on the YAML you provided to get the project started?**

# Complete DemoBro Demo - Using All 6 Phases

# This example demonstrates the full power of DemoBro v2.0.0

metadata:

title: "Complete Product Demo - All Phases"

description: "Showcase using all 6 DemoBro phases"

author: "DemoBro Team"

version: "2.0.0"

# Phase 3: Voice Configuration (TTS)

voice:

engine: "elevenlabs"# or "google", "azure", "aws_polly"

voice_id: "josh"# Natural-sounding voice

speed: 1.0

pitch: 0

# Phase 6: Audio Configuration

audio:

# Background music with auto-ducking

background_music:

file: "audio/upbeat_background.mp3"

volume: 0.3

ducking_mode: "moderate"# -12dB when voice plays

loop: true

# Voice processing

voice_processing:

normalize: true

target_dbfs: -20

remove_silence: true

silence_threshold: -40

enhance_clarity: true

enhance_warmth: true

noise_reduction: true

# Audio effects

effects:

eq_preset: "podcast"# Optimized for voice

reverb_preset: "small_room"# Subtle spatial feel

compression:

threshold: -20

ratio: 3.0

attack: 5

release: 50

# Phase 4: 3D Device Rendering

device_rendering:

device: "iphone_15_pro"

orientation: "portrait"

quality: "high"

render_engine: "eevee"# Fast, good quality

camera_animation: "orbit_smooth"

lighting: "studio"

# Phase 5: Video Editing

video:

# Intro sequence

intro:

duration: 3.0

type: "fade_in"

text: "Product Name"

subtitle: "Version 2.0"

font_size: 60

font_color: "#FFFFFF"

background_color: "#1a1a1a"

# Transitions between steps

transitions:

type: "crossfade"# or "slide", "zoom", "dissolve"

duration: 0.5

# Watermark

watermark:

image: "logo.png"

position: "bottom_right"

opacity: 0.7

size: 100

# Outro sequence

outro:

duration: 4.0

type: "fade_out"

text: "Try it today!"

subtitle: "www.product.com"

cta: "Get Started"

# Optimization

optimization:

target_size_mb: 50

web_optimized: true

compression_level: "balanced"

# Demo Scenario

scenarios:

- name: "Complete Product Walkthrough"

url: "https://app.example.com"

browser: "chrome"

viewport:

width: 1920

height: 1080

steps:

# Step 1: Landing Page

    - action: "navigate"

url: "https://app.example.com"

narration: |

Welcome to our revolutionary new product!

  Let me show you how easy it is to get started.

wait: 2.0

effects:  # Phase 2: Visual effects

    - type: "spotlight"

duration: 2.0

intensity: 0.8

# Step 2: Sign Up

    - action: "click"

locator:

type: "css"

value: "#signup-button"

narration: |

First, click the sign-up button to create your account.

effects:

    - type: "highlight"

duration: 1.5

color: "#FFD700"

intensity: 0.9

    - type: "confetti"

duration: 1.0

# Step 3: Fill Form

    - action: "type"

locator:

type: "id"

value: "email"

value: "demo@example.com"

narration: |

Enter your email address. The interface is clean and intuitive.

effects:

    - type: "typewriter"

speed: 0.1

    - action: "type"

locator:

type: "id"

value: "password"

value: "SecurePassword123!"

narration: |

Choose a strong password. We take security seriously.

effects:

    - type: "glow"

duration: 1.0

color: "#00FF00"

# Step 4: Submit

    - action: "click"

locator:

type: "css"

value: "button[type='submit']"

narration: |

Click submit, and you're all set!

effects:

    - type: "shockwave"

duration: 1.0

intensity: 0.7

    - type: "sparkle"

duration: 2.0

# Step 5: Dashboard

    - action: "wait_for"

locator:

type: "css"

value: ".dashboard"

timeout: 5.0

narration: |

Instantly, you're taken to your personalized dashboard.

  Everything is organized and easy to find.

effects:

    - type: "parallax"

duration: 2.0

depth: 5

    - type: "cursor_trail"

duration: 3.0

# Step 6: Feature 1

    - action: "click"

locator:

type: "css"

value: "#feature-1"

narration: |

Let's explore the first feature. Notice how responsive it is.

effects:

    - type: "zoom_pulse"

duration: 1.0

scale: 1.2

    - type: "ripple"

duration: 1.5

# Step 7: Feature 2

    - action: "scroll"

direction: "down"

pixels: 500

narration: |

Scroll down to see more amazing features.

effects:

    - type: "fade_in"

duration: 1.0

    - action: "click"

locator:

type: "css"

value: "#feature-2"

narration: |

Click to activate this powerful tool.

effects:

    - type: "glitch"

duration: 0.5

intensity: 0.3

    - type: "neon_glow"

duration: 2.0

color: "#FF00FF"

# Step 8: Settings

    - action: "navigate"

url: "https://app.example.com/settings"

narration: |

Customization is easy. Head to settings to personalize your experience.

effects:

    - type: "slide_in"

duration: 0.8

direction: "left"

# Step 9: Save Changes

    - action: "click"

locator:

type: "css"

value: "#save-settings"

narration: |

Save your preferences with one click.

effects:

    - type: "success_checkmark"

duration: 1.5

    - type: "confetti"

duration: 2.0

# Step 10: Wrap Up

    - action: "screenshot"

filename: "final_screen.png"

narration: |

And that's it! You're now ready to use the product like a pro.

  Start your journey today and experience the difference!

effects:

    - type: "vignette"

duration: 2.0

intensity: 0.5

    - type: "fade_out"

duration: 1.5

# Post-processing Pipeline

pipeline:

# Phase 1: Restoration (automatic)

- restore_audio:

denoise: true

normalize: true

- restore_video:

stabilize: true

sharpen: true

# Phase 2: Apply visual effects (from steps)

- apply_effects: {}

# Phase 3: Generate and sync narration

- generate_narration: {}

# Phase 4: Render in 3D device

- render_device_mockup: {}

# Phase 5: Edit video (intro, outro, transitions)

- edit_video: {}

# Phase 6: Mix audio (voice + music with ducking)

- mix_audio: {}

# Final optimization

- optimize:

format: "mp4"

codec: "h264"

quality: "high"

target_size_mb: 50

# Output Configuration

output:

filename: "complete_product_demo.mp4"

directory: "output/"

formats:

    - "mp4"# Standard video

    - "webm"# Web optimized

    - "gif"# Short preview

# Generate thumbnails

thumbnails:

    - timestamp: 0.0

    - timestamp: 5.0

    - timestamp: 10.0

# Social media versions

social:

    - platform: "youtube"

resolution: "1920x1080"

bitrate: "8000k"

    - platform: "instagram"

resolution: "1080x1080"

aspect_ratio: "1:1"

max_duration: 60

    - platform: "twitter"

resolution: "1280x720"

max_duration: 140

max_size_mb: 15

# Analytics (optional)

analytics:

track_engagement: true

heatmap: true

click_tracking: true
