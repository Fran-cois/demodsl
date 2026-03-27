"use client";

import { useState } from "react";

/* ─── Sidebar navigation sections ─────────────────────────────────────── */

const sections = [
  { id: "overview", label: "Overview" },
  { id: "config-format", label: "Config Format" },
  { id: "metadata", label: "metadata" },
  { id: "voice", label: "voice" },
  { id: "audio", label: "audio" },
  { id: "device-rendering", label: "device_rendering" },
  { id: "video", label: "video" },
  { id: "scenarios", label: "scenarios" },
  { id: "steps", label: "steps" },
  { id: "effects", label: "effects" },
  { id: "pipeline", label: "pipeline" },
  { id: "output", label: "output" },
  { id: "analytics", label: "analytics" },
  { id: "cli", label: "CLI Reference" },
  { id: "edge-cases", label: "Edge Cases" },
  { id: "env-vars", label: "Environment Variables" },
];

/* ─── Reusable blocks ─────────────────────────────────────────────────── */

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-2xl font-bold mt-16 mb-4 scroll-mt-20 border-b border-zinc-800 pb-2">
      {children}
    </h2>
  );
}

function Sub({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h3 id={id} className="text-lg font-semibold mt-10 mb-3 scroll-mt-20 text-zinc-200">
      {children}
    </h3>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-zinc-400 leading-relaxed mb-4">{children}</p>;
}

function Code({ children }: { children: string }) {
  return (
    <code className="text-sm bg-zinc-800 text-indigo-300 px-1.5 py-0.5 rounded font-mono">
      {children}
    </code>
  );
}

function CodeBlock({ title, lang, children }: { title?: string; lang?: string; children: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden mb-6">
      {title && (
        <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-950/50">
          <span className="text-xs text-zinc-500 font-mono">{title}</span>
        </div>
      )}
      <pre className="p-4 overflow-x-auto text-sm leading-relaxed">
        <code className="text-zinc-300 font-mono">{children}</code>
      </pre>
    </div>
  );
}

function PropTable({ rows }: { rows: [string, string, string, string][] }) {
  return (
    <div className="overflow-x-auto mb-6">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-left">
            <th className="py-2 pr-4 text-zinc-400 font-medium">Property</th>
            <th className="py-2 pr-4 text-zinc-400 font-medium">Type</th>
            <th className="py-2 pr-4 text-zinc-400 font-medium">Default</th>
            <th className="py-2 text-zinc-400 font-medium">Description</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([prop, type, def, desc]) => (
            <tr key={prop} className="border-b border-zinc-800/50">
              <td className="py-2 pr-4 font-mono text-indigo-300">{prop}</td>
              <td className="py-2 pr-4 font-mono text-zinc-500">{type}</td>
              <td className="py-2 pr-4 font-mono text-zinc-500">{def}</td>
              <td className="py-2 text-zinc-400">{desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Callout({ type, children }: { type: "info" | "warn" | "tip"; children: React.ReactNode }) {
  const styles = {
    info: "border-indigo-800 bg-indigo-950/30 text-indigo-300",
    warn: "border-amber-800 bg-amber-950/30 text-amber-300",
    tip: "border-emerald-800 bg-emerald-950/30 text-emerald-300",
  };
  const icons = { info: "ℹ️", warn: "⚠️", tip: "💡" };
  return (
    <div className={`rounded-lg border p-4 mb-6 text-sm ${styles[type]}`}>
      <span className="mr-2">{icons[type]}</span>
      {children}
    </div>
  );
}

/* ─── Page ────────────────────────────────────────────────────────────── */

export default function DocsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Mobile sidebar toggle */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed bottom-6 right-6 z-50 bg-indigo-600 text-white p-3 rounded-full shadow-lg"
      >
        {sidebarOpen ? "✕" : "☰"}
      </button>

      {/* Sidebar */}
      <aside
        className={`fixed lg:sticky top-[53px] h-[calc(100vh-53px)] w-64 shrink-0 overflow-y-auto border-r border-zinc-800 bg-zinc-950 p-4 z-40 transition-transform lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
          Reference
        </p>
        <nav className="space-y-1">
          {sections.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              onClick={() => setSidebarOpen(false)}
              className="block text-sm text-zinc-400 hover:text-white py-1 px-2 rounded hover:bg-zinc-800 transition-colors"
            >
              {s.label}
            </a>
          ))}
        </nav>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0 px-6 md:px-12 py-12 max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">Documentation</h1>
        <p className="text-zinc-400 mb-8 text-lg">
          Complete configuration reference for DemoDSL v2.0.0
        </p>

        {/* ── Overview ────────────────────────────────────────────────── */}
        <SectionHeading id="overview">Overview</SectionHeading>
        <P>
          DemoDSL is a DSL-driven automated product demo video generator. You
          describe your demo in a single YAML or JSON configuration file covering
          browser automation, voice narration, visual effects, video editing, audio
          mixing, and multi-format export. DemoDSL then orchestrates the full
          pipeline to produce a polished video.
        </P>
        <P>
          A configuration file has 9 top-level sections. Only <Code>metadata</Code>{" "}
          is required — every other section is optional and has sensible defaults.
        </P>
        <CodeBlock title="Root structure">{`metadata:        # REQUIRED — title, description, author, version
voice:           # TTS engine configuration
audio:           # Background music, voice processing, effects
device_rendering: # 3D device mockup settings
video:           # Intro, outro, transitions, watermark
scenarios:       # Browser automation steps
pipeline:        # Post-processing chain
output:          # Export filenames, formats, social presets
analytics:       # Engagement tracking`}</CodeBlock>

        {/* ── Config Format ──────────────────────────────────────────── */}
        <SectionHeading id="config-format">Config Format</SectionHeading>
        <P>
          DemoDSL accepts both <strong>YAML</strong> (<Code>.yaml</Code> / <Code>.yml</Code>)
          and <strong>JSON</strong> (<Code>.json</Code>) configuration files. The format is
          auto-detected from the file extension.
        </P>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <CodeBlock title="demo.yaml">{`metadata:
  title: "My Demo"
scenarios:
  - name: "Tour"
    url: "https://example.com"
    steps:
      - action: "navigate"
        url: "https://example.com"`}</CodeBlock>
          <CodeBlock title="demo.json">{`{
  "metadata": {
    "title": "My Demo"
  },
  "scenarios": [{
    "name": "Tour",
    "url": "https://example.com",
    "steps": [{
      "action": "navigate",
      "url": "https://example.com"
    }]
  }]
}`}</CodeBlock>
        </div>
        <Callout type="tip">
          Use <Code>demodsl init</Code> to generate a YAML template, or{" "}
          <Code>demodsl init -o demo.json</Code> for JSON.
        </Callout>

        {/* ── Metadata ───────────────────────────────────────────────── */}
        <SectionHeading id="metadata">metadata</SectionHeading>
        <P>
          The only required top-level section. Provides descriptive information
          about the demo.
        </P>
        <PropTable
          rows={[
            ["title", "string", "—", "Required. The demo title used in logs and output metadata."],
            ["description", "string | null", "null", "Optional description for documentation."],
            ["author", "string | null", "null", "Author name."],
            ["version", "string | null", "null", "Version string (e.g. \"2.0.0\")."],
          ]}
        />
        <CodeBlock title="Minimal valid config">{`metadata:
  title: "My Demo"`}</CodeBlock>
        <Callout type="info">
          <Code>title</Code> is the only truly required field in the entire config.
          Every other section and property has defaults or is optional.
        </Callout>

        {/* ── Voice ──────────────────────────────────────────────────── */}
        <SectionHeading id="voice">voice</SectionHeading>
        <P>
          Configures the Text-to-Speech engine used to generate narration audio
          from the <Code>narration</Code> field in steps.
        </P>
        <PropTable
          rows={[
            ["engine", '"elevenlabs" | "google" | "azure" | "aws_polly" | "openai"', '"elevenlabs"', "TTS provider to use."],
            ["voice_id", "string", '"josh"', "Voice identifier. Provider-specific."],
            ["speed", "float", "1.0", "Playback speed multiplier (0.5 = half speed, 2.0 = double)."],
            ["pitch", "int", "0", "Pitch adjustment in semitones."],
          ]}
        />
        <CodeBlock title="Example">{`voice:
  engine: "elevenlabs"
  voice_id: "josh"
  speed: 1.0
  pitch: 0`}</CodeBlock>

        <Sub id="voice-engines">Supported Engines</Sub>
        <PropTable
          rows={[
            ["elevenlabs", "—", "—", "High-quality neural TTS. Requires ELEVENLABS_API_KEY."],
            ["openai", "—", "—", "OpenAI TTS (tts-1-hd). Voices: alloy, echo, fable, onyx, nova, shimmer. Requires OPENAI_API_KEY."],
            ["google", "—", "—", "Google Cloud TTS (Wavenet). Requires GOOGLE_APPLICATION_CREDENTIALS (service account JSON path)."],
            ["azure", "—", "—", "Azure Cognitive Services Speech (Neural). Requires AZURE_SPEECH_KEY + AZURE_SPEECH_REGION."],
            ["aws_polly", "—", "—", "Amazon Polly (Neural). Requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY."],
            ["cosyvoice", "—", "—", "CosyVoice (Alibaba/Qwen). Local server. COSYVOICE_API_URL (default localhost:50000)."],
            ["coqui", "—", "—", "Coqui XTTS v2. Local inference via TTS library. COQUI_MODEL to override model."],
            ["piper", "—", "—", "Piper TTS. Fast offline TTS via CLI. Requires PIPER_MODEL (path to .onnx)."],
            ["local_openai", "—", "—", "Any OpenAI-compatible local server (vLLM, LocalAI, AllTalk…). LOCAL_TTS_URL."],
          ]}
        />

        <Sub id="voice-ids">Voice IDs by Engine</Sub>
        <P>
          Each engine uses its own voice naming convention. Set <Code>voice_id</Code>{" "}
          to a valid identifier for your chosen engine:
        </P>
        <PropTable
          rows={[
            ["elevenlabs", "voice_id", '"josh"', 'ElevenLabs voice ID. Find IDs at elevenlabs.io/voices.'],
            ["openai", "voice_id", '"alloy"', 'One of: alloy, echo, fable, onyx, nova, shimmer.'],
            ["google", "voice_id", '"en-US-Wavenet-D"', 'Full voice name (e.g. "en-US-Wavenet-D", "fr-FR-Wavenet-A").'],
            ["azure", "voice_id", '"en-US-JennyNeural"', 'Full voice name. Must contain "Neural" for neural voices.'],
            ["aws_polly", "voice_id", '"Matthew"', 'Polly voice name (capitalized). E.g. "Joanna", "Matthew", "Léa".'],
            ["cosyvoice", "voice_id", '"中文女"', 'Speaker name supported by your CosyVoice model.'],
            ["coqui", "voice_id", '"speaker.wav"', 'Path to a reference .wav for voice cloning, or a built-in speaker name.'],
            ["piper", "voice_id", '"en_US-lessac-medium.onnx"', '.onnx model path, or same as PIPER_MODEL.'],
            ["local_openai", "voice_id", '"alloy"', 'Voice name supported by your local server.'],
          ]}
        />
        <Callout type="warn">
          If no API key is found for the selected engine, DemoDSL automatically
          falls back to a <strong>DummyVoiceProvider</strong> that generates silent
          audio clips sized to match the narration text (~150 words per minute).
          This is useful for development and dry-runs.
        </Callout>

        {/* ── Audio ──────────────────────────────────────────────────── */}
        <SectionHeading id="audio">audio</SectionHeading>
        <P>
          Controls background music, voice processing, and audio effects applied
          during the <Code>mix_audio</Code> pipeline stage.
        </P>

        <Sub id="audio-background-music">audio.background_music</Sub>
        <PropTable
          rows={[
            ["file", "string", "—", "Required. Path to the audio file (MP3, WAV, OGG)."],
            ["volume", "float", "0.3", "Base volume (0.0–1.0). Converted to dB internally."],
            ["ducking_mode", '"none" | "light" | "moderate" | "heavy"', '"moderate"', "Volume reduction during narration."],
            ["loop", "bool", "true", "Loop the music to cover the entire video duration."],
          ]}
        />
        <P>
          Ducking modes control how much the background music volume drops when
          narration is playing:
        </P>
        <PropTable
          rows={[
            ["none", "—", "0 dB", "No ducking — music stays at full volume."],
            ["light", "—", "−6 dB", "Subtle reduction. Music still audible."],
            ["moderate", "—", "−12 dB", "Balanced. Default for most demos."],
            ["heavy", "—", "−20 dB", "Near-silent music during speech."],
          ]}
        />

        <Sub id="audio-voice-processing">audio.voice_processing</Sub>
        <PropTable
          rows={[
            ["normalize", "bool", "true", "Normalize audio loudness."],
            ["target_dbfs", "int", "-20", "Target loudness in dBFS (decibels relative to full scale)."],
            ["remove_silence", "bool", "true", "Strip leading/trailing silence from clips."],
            ["silence_threshold", "int", "-40", "dBFS below which audio is considered silence."],
            ["enhance_clarity", "bool", "false", "Apply EQ boost to voice presence frequencies."],
            ["enhance_warmth", "bool", "false", "Apply low-end EQ warmth to voice."],
            ["noise_reduction", "bool", "false", "Remove background noise from recordings."],
          ]}
        />

        <Sub id="audio-effects">audio.effects</Sub>
        <PropTable
          rows={[
            ["eq_preset", "string | null", "null", 'EQ preset name (e.g. "podcast", "broadcast").'],
            ["reverb_preset", "string | null", "null", 'Reverb preset (e.g. "small_room", "hall").'],
            ["compression", "Compression | null", "null", "Dynamic range compression settings."],
          ]}
        />

        <Sub id="audio-compression">audio.effects.compression</Sub>
        <PropTable
          rows={[
            ["threshold", "int", "-20", "Compression threshold in dB."],
            ["ratio", "float", "3.0", "Compression ratio (e.g. 3.0 = 3:1)."],
            ["attack", "int", "5", "Attack time in milliseconds."],
            ["release", "int", "50", "Release time in milliseconds."],
          ]}
        />
        <CodeBlock title="Full audio example">{`audio:
  background_music:
    file: "audio/bg.mp3"
    volume: 0.3
    ducking_mode: "moderate"
    loop: true
  voice_processing:
    normalize: true
    target_dbfs: -20
    noise_reduction: true
  effects:
    eq_preset: "podcast"
    reverb_preset: "small_room"
    compression:
      threshold: -20
      ratio: 3.0
      attack: 5
      release: 50`}</CodeBlock>

        {/* ── Device Rendering ───────────────────────────────────────── */}
        <SectionHeading id="device-rendering">device_rendering</SectionHeading>
        <P>
          Wraps the captured browser video inside a 3D device mockup frame,
          processed during the <Code>render_device_mockup</Code> pipeline stage.
        </P>
        <PropTable
          rows={[
            ["device", "string", '"iphone_15_pro"', "Device model name."],
            ["orientation", '"portrait" | "landscape"', '"portrait"', "Screen orientation."],
            ["quality", '"low" | "medium" | "high"', '"high"', "Render quality level."],
            ["render_engine", '"eevee" | "cycles"', '"eevee"', "Blender render engine. Eevee is faster, Cycles is more realistic."],
            ["camera_animation", "string", '"orbit_smooth"', "Camera movement type around the device."],
            ["lighting", "string", '"studio"', "Lighting preset."],
          ]}
        />
        <CodeBlock title="Example">{`device_rendering:
  device: "iphone_15_pro"
  orientation: "portrait"
  quality: "high"
  render_engine: "eevee"
  camera_animation: "orbit_smooth"
  lighting: "studio"`}</CodeBlock>
        <Callout type="info">
          The <Code>render_device_mockup</Code> pipeline stage is optional. If it
          fails (e.g. Blender not installed), the pipeline continues with the raw
          video.
        </Callout>

        {/* ── Video ──────────────────────────────────────────────────── */}
        <SectionHeading id="video">video</SectionHeading>
        <P>
          Controls video editing: intro/outro sequences, transitions between steps,
          watermark overlay, and output optimization. Processed during the{" "}
          <Code>edit_video</Code> pipeline stage.
        </P>

        <Sub id="video-intro">video.intro</Sub>
        <PropTable
          rows={[
            ["duration", "float", "3.0", "Intro duration in seconds."],
            ["type", "string", '"fade_in"', "Animation type for the intro."],
            ["text", "string | null", "null", "Main title text overlay."],
            ["subtitle", "string | null", "null", "Subtitle text below the title."],
            ["font_size", "int", "60", "Font size in pixels."],
            ["font_color", "string", '"#FFFFFF"', "Font color (hex)."],
            ["background_color", "string", '"#1a1a1a"', "Background color (hex)."],
          ]}
        />

        <Sub id="video-transitions">video.transitions</Sub>
        <PropTable
          rows={[
            ["type", '"crossfade" | "slide" | "zoom" | "dissolve"', '"crossfade"', "Transition style between steps."],
            ["duration", "float", "0.5", "Transition duration in seconds."],
          ]}
        />

        <Sub id="video-watermark">video.watermark</Sub>
        <PropTable
          rows={[
            ["image", "string", "—", "Required. Path to the watermark image (PNG recommended)."],
            ["position", '"top_left" | "top_right" | "bottom_left" | "bottom_right" | "center"', '"bottom_right"', "Watermark position on the video."],
            ["opacity", "float", "0.7", "Watermark opacity (0.0–1.0)."],
            ["size", "int", "100", "Watermark size in pixels (longest side)."],
          ]}
        />

        <Sub id="video-outro">video.outro</Sub>
        <PropTable
          rows={[
            ["duration", "float", "4.0", "Outro duration in seconds."],
            ["type", "string", '"fade_out"', "Animation type for the outro."],
            ["text", "string | null", "null", "Main text overlay."],
            ["subtitle", "string | null", "null", "Subtitle text."],
            ["cta", "string | null", "null", "Call-to-action text (e.g. \"Get Started\")."],
          ]}
        />

        <Sub id="video-optimization">video.optimization</Sub>
        <PropTable
          rows={[
            ["target_size_mb", "int | null", "null", "Target file size. Bitrate is auto-calculated."],
            ["web_optimized", "bool", "true", "Move moov atom for fast web streaming start."],
            ["compression_level", '"low" | "balanced" | "high"', '"balanced"', "Encoding compression preset."],
          ]}
        />
        <CodeBlock title="Full video example">{`video:
  intro:
    duration: 3.0
    type: "fade_in"
    text: "Product Name"
    subtitle: "v2.0"
    font_size: 60
    font_color: "#FFFFFF"
    background_color: "#1a1a1a"
  transitions:
    type: "crossfade"
    duration: 0.5
  watermark:
    image: "logo.png"
    position: "bottom_right"
    opacity: 0.7
    size: 100
  outro:
    duration: 4.0
    type: "fade_out"
    text: "Try it today!"
    cta: "Get Started"
  optimization:
    target_size_mb: 50
    web_optimized: true
    compression_level: "balanced"`}</CodeBlock>

        {/* ── Scenarios ──────────────────────────────────────────────── */}
        <SectionHeading id="scenarios">scenarios</SectionHeading>
        <P>
          A list of browser automation scenarios. Each scenario captures a
          recording from a web application. Multiple scenarios are concatenated
          in the final video.
        </P>
        <PropTable
          rows={[
            ["name", "string", "—", "Required. Human-readable scenario name."],
            ["url", "string", "—", "Required. Base URL for the scenario."],
            ["browser", '"chrome" | "firefox" | "webkit"', '"chrome"', "Browser engine (Playwright)."],
            ["viewport", "Viewport", "1920×1080", "Browser viewport dimensions."],
            ["steps", "Step[]", "[]", "List of automation steps."],
          ]}
        />

        <Sub id="scenarios-viewport">scenarios[].viewport</Sub>
        <PropTable
          rows={[
            ["width", "int", "1920", "Viewport width in pixels."],
            ["height", "int", "1080", "Viewport height in pixels."],
          ]}
        />
        <Callout type="tip">
          Common viewport sizes: <Code>1920×1080</Code> (Full HD),{" "}
          <Code>1280×720</Code> (HD), <Code>390×844</Code> (iPhone 14),{" "}
          <Code>1024×768</Code> (tablet).
        </Callout>
        <CodeBlock title="Example">{`scenarios:
  - name: "Main Demo"
    url: "https://myapp.com"
    browser: "chrome"
    viewport:
      width: 1920
      height: 1080
    steps:
      - action: "navigate"
        url: "https://myapp.com"`}</CodeBlock>

        {/* ── Steps ──────────────────────────────────────────────────── */}
        <SectionHeading id="steps">steps</SectionHeading>
        <P>
          Steps define individual browser actions within a scenario. Each step
          has an <Code>action</Code> type and action-specific fields. All steps
          also support optional <Code>narration</Code>, <Code>wait</Code>, and{" "}
          <Code>effects</Code>.
        </P>

        <Sub id="steps-common">Common Fields (all actions)</Sub>
        <PropTable
          rows={[
            ["action", '"navigate" | "click" | "type" | "scroll" | "wait_for" | "screenshot"', "—", "Required. The action type."],
            ["narration", "string | null", "null", "Text-to-speech narration played during this step."],
            ["wait", "float | null", "null", "Seconds to wait after the action completes."],
            ["effects", "Effect[]", "null", "Visual effects to apply during this step."],
          ]}
        />

        <Sub id="steps-navigate">action: &quot;navigate&quot;</Sub>
        <P>Navigate the browser to a URL.</P>
        <PropTable
          rows={[
            ["url", "string", "—", "Required. The URL to navigate to."],
          ]}
        />
        <CodeBlock>{`- action: "navigate"
  url: "https://myapp.com/dashboard"
  narration: "Let's visit the dashboard."
  wait: 2.0`}</CodeBlock>

        <Sub id="steps-click">action: &quot;click&quot;</Sub>
        <P>Click on an element identified by a locator.</P>
        <PropTable
          rows={[
            ["locator.type", '"css" | "id" | "xpath" | "text"', '"css"', "Locator strategy."],
            ["locator.value", "string", "—", "Required. The selector/identifier."],
          ]}
        />
        <CodeBlock>{`- action: "click"
  locator:
    type: "css"
    value: "#submit-btn"
  narration: "Click submit."
  effects:
    - type: "highlight"
      color: "#FFD700"`}</CodeBlock>

        <Sub id="steps-type">action: &quot;type&quot;</Sub>
        <P>Type text into an input field.</P>
        <PropTable
          rows={[
            ["locator.type", '"css" | "id" | "xpath" | "text"', '"css"', "Locator strategy."],
            ["locator.value", "string", "—", "Required. The selector."],
            ["value", "string", "—", "Required. The text to type."],
          ]}
        />
        <CodeBlock>{`- action: "type"
  locator:
    type: "id"
    value: "email"
  value: "user@example.com"
  effects:
    - type: "typewriter"
      speed: 0.1`}</CodeBlock>

        <Sub id="steps-scroll">action: &quot;scroll&quot;</Sub>
        <P>Scroll the page in a direction.</P>
        <PropTable
          rows={[
            ["direction", '"up" | "down" | "left" | "right"', '"down"', "Scroll direction."],
            ["pixels", "int", "300", "Number of pixels to scroll."],
          ]}
        />
        <CodeBlock>{`- action: "scroll"
  direction: "down"
  pixels: 500
  narration: "Scrolling to see more features."`}</CodeBlock>

        <Sub id="steps-wait-for">action: &quot;wait_for&quot;</Sub>
        <P>Wait for an element to appear in the DOM.</P>
        <PropTable
          rows={[
            ["locator.type", '"css" | "id" | "xpath" | "text"', '"css"', "Locator strategy."],
            ["locator.value", "string", "—", "Required. The selector."],
            ["timeout", "float", "5.0", "Maximum wait time in seconds."],
          ]}
        />
        <CodeBlock>{`- action: "wait_for"
  locator:
    type: "css"
    value: ".dashboard-loaded"
  timeout: 10.0
  narration: "Waiting for the dashboard to load."`}</CodeBlock>
        <Callout type="warn">
          If the element is not found within <Code>timeout</Code> seconds, the
          step throws an error and the scenario stops.
        </Callout>

        <Sub id="steps-screenshot">action: &quot;screenshot&quot;</Sub>
        <P>Capture a screenshot of the current page.</P>
        <PropTable
          rows={[
            ["filename", "string", '"screenshot.png"', "Output filename. Saved to the workspace frames directory."],
          ]}
        />
        <CodeBlock>{`- action: "screenshot"
  filename: "final_state.png"
  narration: "Here's the final result."`}</CodeBlock>

        <Sub id="steps-locator-types">Locator Types</Sub>
        <P>
          Four locator strategies are available for identifying elements:
        </P>
        <PropTable
          rows={[
            ["css", "—", "—", 'CSS selector. Examples: "#id", ".class", "button[type=submit]"'],
            ["id", "—", "—", 'Element ID (shorthand for #id). Example: "email-input"'],
            ["xpath", "—", "—", 'XPath expression. Example: "//div[@class=\'card\']"'],
            ["text", "—", "—", 'Visible text content. Example: "Sign Up"'],
          ]}
        />
        <Callout type="tip">
          Prefer <Code>css</Code> selectors for stability. Use <Code>text</Code>{" "}
          locators for buttons or links where the visible text is more stable
          than the CSS structure.
        </Callout>

        {/* ── Effects ────────────────────────────────────────────────── */}
        <SectionHeading id="effects">effects</SectionHeading>
        <P>
          18 visual effects are available, split into two categories:{" "}
          <strong>browser effects</strong> (11 — injected as CSS/JS during capture)
          and <strong>post-processing effects</strong> (7 — applied to the rendered
          video via MoviePy). Effects are attached to individual steps.
        </P>
        <PropTable
          rows={[
            ["type", "EffectType", "—", "Required. Effect name (see tables below)."],
            ["duration", "float | null", "null", "Effect duration in seconds."],
            ["intensity", "float | null", "null", "Effect intensity (0.0–1.0)."],
            ["color", "string | null", "null", "Effect color (hex). Used by highlight, glow, neon_glow."],
            ["speed", "float | null", "null", "Animation speed. Used by typewriter."],
            ["scale", "float | null", "null", "Zoom scale factor. Used by zoom_pulse."],
            ["depth", "int | null", "null", "Parallax depth. Used by parallax."],
            ["direction", "string | null", "null", 'Direction ("left", "right", "up", "down"). Used by slide_in.'],
          ]}
        />

        <Sub id="effects-browser">Browser Effects (real-time JS injection)</Sub>
        <P>
          These effects inject CSS/JavaScript into the browser during capture,
          creating real-time visual overlays.
        </P>
        <PropTable
          rows={[
            ["spotlight", "duration, intensity", "—", "Radial gradient spotlight overlay, darkens edges."],
            ["highlight", "duration, color, intensity", "—", "Glowing box-shadow on hovered elements."],
            ["confetti", "duration", "—", "Animated falling confetti particles (canvas)."],
            ["typewriter", "speed", "—", "Blinking caret animation on input fields."],
            ["glow", "duration, color", "—", "Inner box-shadow glow around the viewport."],
            ["shockwave", "duration, intensity", "—", "Expanding ring animation from center."],
            ["sparkle", "duration", "—", "Random sparkling golden dots (canvas)."],
            ["cursor_trail", "duration", "—", "Trailing particles following the cursor."],
            ["ripple", "duration", "—", "Click ripple effect on interactions."],
            ["neon_glow", "duration, color", "—", "Neon-colored glow border around the viewport."],
            ["success_checkmark", "duration", "—", "Animated green checkmark overlay."],
          ]}
        />

        <Sub id="effects-post">Post-Processing Effects (MoviePy)</Sub>
        <P>
          These effects are applied to the video during the{" "}
          <Code>apply_effects</Code> pipeline stage.
        </P>
        <PropTable
          rows={[
            ["parallax", "duration, depth", "—", "Subtle zoom for a depth illusion."],
            ["zoom_pulse", "duration, scale", "—", "Pulsing zoom in/out following a sine wave."],
            ["fade_in", "duration", "—", "Clip fades in from black."],
            ["fade_out", "duration", "—", "Clip fades out to black."],
            ["vignette", "duration, intensity", "—", "Dark vignette border around the frame."],
            ["glitch", "duration, intensity", "—", "Random horizontal slice displacement."],
            ["slide_in", "duration, direction", "—", "Slide-in entrance animation (implemented as crossfade)."],
          ]}
        />

        <CodeBlock title="Combining effects">{`steps:
  - action: "click"
    locator: { type: "css", value: "#cta" }
    narration: "Click the call to action!"
    effects:
      - type: "highlight"
        color: "#FFD700"
        duration: 1.5
      - type: "confetti"
        duration: 2.0
      - type: "zoom_pulse"
        scale: 1.2
        duration: 1.0`}</CodeBlock>
        <Callout type="info">
          Browser effects execute <strong>before</strong> the step action. Multiple
          effects on one step are applied sequentially, each waiting for its{" "}
          <Code>duration</Code> before the next.
        </Callout>

        {/* ── Pipeline ───────────────────────────────────────────────── */}
        <SectionHeading id="pipeline">pipeline</SectionHeading>
        <P>
          The pipeline defines the post-processing chain using a{" "}
          <strong>Chain of Responsibility</strong> pattern. Each stage is a
          single-key dictionary. Stages execute in order, passing context to
          the next.
        </P>
        <P>
          Each stage is either <strong>critical</strong> (failure stops the pipeline)
          or <strong>optional</strong> (failure is logged and skipped).
        </P>
        <PropTable
          rows={[
            ["restore_audio", "optional", '{ denoise, normalize }', "Audio restoration: noise removal, loudness normalization."],
            ["restore_video", "optional", '{ stabilize, sharpen }', "Video restoration: stabilization, sharpening."],
            ["apply_effects", "optional", "{}", "Apply post-processing visual effects from step definitions."],
            ["generate_narration", "critical", "{}", "Generate TTS audio clips and sync to video timeline."],
            ["render_device_mockup", "optional", "{}", "Overlay video into a 3D device frame."],
            ["edit_video", "critical", "{}", "Apply intro, outro, transitions, and watermark."],
            ["mix_audio", "critical", "{}", "Mix voice narration with background music (ducking)."],
            ["optimize", "critical", '{ format, codec, quality, target_size_mb }', "Final encoding, compression, and format export."],
          ]}
        />
        <CodeBlock title="Pipeline syntax">{`pipeline:
  # Each stage is a single-key dict
  - restore_audio:
      denoise: true
      normalize: true
  - restore_video:
      stabilize: true
      sharpen: true
  - apply_effects: {}
  - generate_narration: {}
  - render_device_mockup: {}
  - edit_video: {}
  - mix_audio: {}
  - optimize:
      format: "mp4"
      codec: "h264"
      quality: "high"
      target_size_mb: 50`}</CodeBlock>

        <Sub id="pipeline-optimize">optimize stage parameters</Sub>
        <PropTable
          rows={[
            ["format", "string", '"mp4"', 'Output format: "mp4", "webm", "gif".'],
            ["codec", "string", '"h264"', 'Video codec: "h264", "h265", "vp9", etc.'],
            ["quality", "string", '"high"', 'Encoding quality: "low", "medium", "high".'],
            ["target_size_mb", "int | null", "null", "Target file size in MB. Overrides quality if set."],
          ]}
        />

        <Callout type="warn">
          Pipeline stages with <Code>{'{}'}</Code> (empty dict) use all defaults.
          Each stage dict must have <strong>exactly one key</strong> — multiple keys
          in a single dict will raise a validation error.
        </Callout>
        <Callout type="tip">
          You can reorder stages or omit optional ones. A minimal pipeline might
          be just <Code>generate_narration</Code>, <Code>edit_video</Code>,{" "}
          <Code>mix_audio</Code>, and <Code>optimize</Code>.
        </Callout>

        {/* ── Output ─────────────────────────────────────────────────── */}
        <SectionHeading id="output">output</SectionHeading>
        <P>
          Defines output filenames, formats, thumbnail generation, and social
          media export presets.
        </P>
        <PropTable
          rows={[
            ["filename", "string", '"output.mp4"', "Main output filename."],
            ["directory", "string", '"output/"', "Output directory path."],
            ["formats", "string[]", '["mp4"]', 'Export formats: "mp4", "webm", "gif".'],
            ["thumbnails", "Thumbnail[]", "null", "Auto-generated thumbnail frames."],
            ["social", "SocialExport[]", "null", "Platform-specific export presets."],
          ]}
        />

        <Sub id="output-thumbnails">output.thumbnails</Sub>
        <PropTable
          rows={[
            ["timestamp", "float", "—", "Required. Time in seconds to capture the thumbnail."],
          ]}
        />

        <Sub id="output-social">output.social</Sub>
        <P>
          Generate platform-optimized versions automatically. Each preset re-encodes
          the video with platform-specific constraints.
        </P>
        <PropTable
          rows={[
            ["platform", "string", "—", "Required. Platform name (for labeling)."],
            ["resolution", "string | null", "null", 'Output resolution (e.g. "1920x1080").'],
            ["bitrate", "string | null", "null", 'Target bitrate (e.g. "8000k").'],
            ["aspect_ratio", "string | null", "null", 'Crop to aspect ratio (e.g. "1:1", "9:16").'],
            ["max_duration", "int | null", "null", "Maximum duration in seconds (trims end)."],
            ["max_size_mb", "int | null", "null", "Maximum file size in MB."],
          ]}
        />
        <CodeBlock title="Full output example">{`output:
  filename: "demo.mp4"
  directory: "output/"
  formats:
    - "mp4"
    - "webm"
    - "gif"
  thumbnails:
    - timestamp: 0.0
    - timestamp: 5.0
    - timestamp: 10.0
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
      max_size_mb: 15`}</CodeBlock>

        {/* ── Analytics ──────────────────────────────────────────────── */}
        <SectionHeading id="analytics">analytics</SectionHeading>
        <P>
          Optional engagement tracking metadata embedded in the output.
        </P>
        <PropTable
          rows={[
            ["track_engagement", "bool", "false", "Track viewer engagement metrics."],
            ["heatmap", "bool", "false", "Generate click/attention heatmap data."],
            ["click_tracking", "bool", "false", "Track interactive click positions."],
          ]}
        />
        <CodeBlock>{`analytics:
  track_engagement: true
  heatmap: true
  click_tracking: true`}</CodeBlock>

        {/* ── CLI ────────────────────────────────────────────────────── */}
        <SectionHeading id="cli">CLI Reference</SectionHeading>

        <Sub id="cli-run">demodsl run</Sub>
        <P>Parse and execute a DemoDSL config file.</P>
        <CodeBlock>{`demodsl run <config> [OPTIONS]

Arguments:
  config    Path to the YAML or JSON config file.

Options:
  -o, --output-dir PATH  Output directory (default: output/)
  --dry-run              Validate and log all steps without executing
  --skip-voice           Skip TTS generation (development mode)
  -v, --verbose          Enable debug logging`}</CodeBlock>
        <Callout type="tip">
          Use <Code>--dry-run</Code> to validate your config and preview all
          steps without launching a browser or calling TTS APIs.
        </Callout>

        <Sub id="cli-validate">demodsl validate</Sub>
        <P>Validate a config file without executing any actions.</P>
        <CodeBlock>{`demodsl validate <config> [OPTIONS]

Arguments:
  config    Path to the YAML or JSON config file.

Options:
  -v, --verbose    Enable debug logging`}</CodeBlock>
        <P>
          Outputs a summary: title, version, number of scenarios, total steps,
          and pipeline stage count. Exits with code 1 on validation failure.
        </P>

        <Sub id="cli-init">demodsl init</Sub>
        <P>Generate a minimal config template.</P>
        <CodeBlock>{`demodsl init [OPTIONS]

Options:
  -o, --output PATH   Output file (default: demo.yaml)
                      Use .json extension for JSON output.

Examples:
  demodsl init                    # Creates demo.yaml
  demodsl init -o my-demo.yaml   # Custom filename
  demodsl init -o demo.json      # JSON format`}</CodeBlock>

        {/* ── Edge Cases ─────────────────────────────────────────────── */}
        <SectionHeading id="edge-cases">Edge Cases &amp; Gotchas</SectionHeading>

        <Sub id="edge-minimal">Minimal Config</Sub>
        <P>
          The smallest valid config requires only <Code>metadata.title</Code>.
          Everything else has defaults or is optional:
        </P>
        <CodeBlock title="Minimal valid config">{`metadata:
  title: "Empty Demo"`}</CodeBlock>
        <P>
          This will validate successfully but produce no output (no scenarios,
          no pipeline).
        </P>

        <Sub id="edge-format">YAML vs JSON Detection</Sub>
        <P>
          File format is detected <strong>by file extension only</strong>:{" "}
          <Code>.json</Code> → JSON parser, anything else → YAML parser. If you
          name a JSON file <Code>config.yaml</Code>, it will fail to parse.
        </P>

        <Sub id="edge-voice-fallback">Voice Provider Fallback</Sub>
        <P>
          If the configured TTS engine&apos;s API key is missing, DemoDSL falls back
          to <Code>DummyVoiceProvider</Code> which generates silent audio clips.
          The dummy calculates duration from word count at ~150 words per minute.
          This is intentional behavior for local development.
        </P>

        <Sub id="edge-pipeline-stage-format">Pipeline Stage Format</Sub>
        <P>
          Each pipeline entry must be a <strong>single-key dictionary</strong>.
          Multiple keys in one entry will raise a validation error:
        </P>
        <CodeBlock title="❌ Invalid — multiple keys">{`pipeline:
  - restore_audio: { denoise: true }
    restore_video: { sharpen: true }  # Error!`}</CodeBlock>
        <CodeBlock title="✅ Valid — one key per entry">{`pipeline:
  - restore_audio: { denoise: true }
  - restore_video: { sharpen: true }`}</CodeBlock>

        <Sub id="edge-pipeline-critical">Critical vs Optional Stages</Sub>
        <P>
          If a <strong>critical</strong> stage fails (generate_narration, edit_video,
          mix_audio, optimize), the entire pipeline stops and raises an error.
          If an <strong>optional</strong> stage fails (restore_audio, restore_video,
          apply_effects, render_device_mockup), it logs a warning and the pipeline
          continues.
        </P>

        <Sub id="edge-effects-order">Effect Execution Order</Sub>
        <P>
          Browser effects are injected <strong>before</strong> the step action and
          execute sequentially. If an effect has a <Code>duration</Code>, the engine
          sleeps for that duration before the next effect. All effects complete
          before the browser action fires.
        </P>

        <Sub id="edge-locator-required">Required Fields by Action</Sub>
        <PropTable
          rows={[
            ["navigate", "url", "—", 'Raises ValueError if url is missing.'],
            ["click", "locator", "—", 'Raises ValueError if locator is missing.'],
            ["type", "locator + value", "—", 'Raises ValueError if either is missing.'],
            ["scroll", "(none)", "—", 'Defaults: direction="down", pixels=300.'],
            ["wait_for", "locator", "—", 'Raises ValueError if locator is missing. Default timeout: 5s.'],
            ["screenshot", "(none)", "—", 'Default filename: "screenshot.png".'],
          ]}
        />

        <Sub id="edge-viewport-recording">Viewport and Recording</Sub>
        <P>
          The browser records video at the viewport resolution. For high-quality
          social media exports, set the scenario viewport to the maximum resolution
          you need — downscaling social presets is better than upscaling.
        </P>

        <Sub id="edge-ducking-no-music">Ducking Without Music</Sub>
        <P>
          If <Code>audio.background_music</Code> is not set or the file doesn&apos;t
          exist, the <Code>mix_audio</Code> stage skips music mixing entirely.
          Narration-only audio still works.
        </P>

        <Sub id="edge-empty-pipeline">Empty Pipeline</Sub>
        <P>
          If <Code>pipeline</Code> is an empty list or omitted, no post-processing
          runs. Raw browser recordings are copied directly to the output directory.
        </P>

        <Sub id="edge-multiple-scenarios">Multiple Scenarios</Sub>
        <P>
          Multiple scenarios are executed sequentially. Each gets its own browser
          instance. Currently, the pipeline processes only the first scenario&apos;s
          video. Multi-scenario concatenation is handled by the <Code>edit_video</Code>{" "}
          stage.
        </P>

        <Sub id="edge-dry-run">Dry Run Behavior</Sub>
        <P>
          With <Code>--dry-run</Code>, the engine validates the config, logs every
          step and effect with <Code>[DRY-RUN]</Code> prefix, but does not:
        </P>
        <ul className="list-disc list-inside text-zinc-400 mb-6 space-y-1 text-sm">
          <li>Launch a browser</li>
          <li>Call any TTS API</li>
          <li>Execute pipeline stages</li>
          <li>Produce any output files</li>
        </ul>

        {/* ── Environment Variables ──────────────────────────────────── */}
        <SectionHeading id="env-vars">Environment Variables</SectionHeading>
        <PropTable
          rows={[
            ["ELEVENLABS_API_KEY", "string", "—", "ElevenLabs TTS API key."],
            ["OPENAI_API_KEY", "string", "—", "OpenAI API key. Required for openai engine."],
            ["GOOGLE_APPLICATION_CREDENTIALS", "string", "—", "Path to Google Cloud service account JSON file."],
            ["AZURE_SPEECH_KEY", "string", "—", "Azure Cognitive Services Speech subscription key."],
            ["AZURE_SPEECH_REGION", "string", '"eastus"', "Azure region (e.g. eastus, westeurope)."],
            ["AWS_ACCESS_KEY_ID", "string", "—", "AWS access key for Polly."],
            ["AWS_SECRET_ACCESS_KEY", "string", "—", "AWS secret key for Polly."],
            ["AWS_DEFAULT_REGION", "string", '"us-east-1"', "AWS region for Polly."],
            ["COSYVOICE_API_URL", "string", '"http://localhost:50000"', "CosyVoice API server URL."],
            ["COQUI_MODEL", "string", '"xtts_v2"', "Coqui TTS model name (default: xtts_v2)."],
            ["COQUI_LANGUAGE", "string", '"en"', "Language code for Coqui TTS."],
            ["PIPER_BIN", "string", '"piper"', "Path to piper binary."],
            ["PIPER_MODEL", "string", "—", "Required. Path to Piper .onnx voice model."],
            ["LOCAL_TTS_URL", "string", '"http://localhost:8000"', "Base URL for OpenAI-compatible local TTS server."],
            ["LOCAL_TTS_API_KEY", "string", '"not-needed"', "API key for local server (if required)."],
            ["LOCAL_TTS_MODEL", "string", '"tts-1"', "Model name to pass to local server."],
          ]}
        />
        <P>
          If the required environment variable for the selected engine is not set,
          DemoDSL automatically falls back to <Code>DummyVoiceProvider</Code>{" "}
          which generates silent audio clips. This allows development without
          API credentials.
        </P>

        <div className="mt-20 border-t border-zinc-800 pt-8 text-center text-sm text-zinc-500">
          DemoDSL v2.0.0 — MIT License —{" "}
          <a
            href="https://github.com/Fran-cois/demodsl"
            className="text-indigo-400 hover:text-indigo-300"
          >
            GitHub
          </a>
        </div>
      </main>
    </div>
  );
}
