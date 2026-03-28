"use client";

import { useEffect, useRef, useState } from "react";

/* ─── Sidebar navigation sections ─────────────────────────────────────── */

type NavItem = { id: string; label: string; children?: NavItem[]; beta?: boolean };

const sections: NavItem[] = [
  { id: "overview", label: "Overview" },
  { id: "config-format", label: "Config Format" },
  { id: "metadata", label: "metadata" },
  {
    id: "voice", label: "voice", children: [
      { id: "voice-engines", label: "engines" },
      { id: "voice-ids", label: "voice IDs" },
      { id: "voice-cloning", label: "voice cloning" },
    ],
  },
  {
    id: "audio", label: "audio", children: [
      { id: "audio-background-music", label: "background_music" },
      { id: "audio-voice-processing", label: "voice_processing" },
      { id: "audio-effects", label: "effects" },
    ],
  },
  { id: "device-rendering", label: "device_rendering", beta: true },
  {
    id: "video", label: "video", children: [
      { id: "video-intro", label: "intro" },
      { id: "video-transitions", label: "transitions" },
      { id: "video-watermark", label: "watermark" },
      { id: "video-outro", label: "outro" },
      { id: "video-optimization", label: "optimization" },
    ],
  },
  {
    id: "subtitle", label: "subtitle", children: [
      { id: "subtitle-styles", label: "styles" },
      { id: "subtitle-style-demos", label: "style demos" },
      { id: "subtitle-speed", label: "speed presets" },
    ],
  },
  {
    id: "scenarios", label: "scenarios", children: [
      { id: "scenarios-viewport", label: "viewport" },
      { id: "scenarios-cursor", label: "cursor" },
      { id: "scenarios-glow-select", label: "glow_select" },
      { id: "scenarios-popup-card", label: "popup_card" },
      { id: "scenarios-avatar", label: "avatar" },
      { id: "scenarios-avatar-styles", label: "avatar styles" },
    ],
  },
  {
    id: "steps", label: "steps", children: [
      { id: "steps-common", label: "common fields" },
      { id: "steps-navigate", label: "navigate" },
      { id: "steps-click", label: "click" },
      { id: "steps-type", label: "type" },
      { id: "steps-scroll", label: "scroll" },
      { id: "steps-wait-for", label: "wait_for" },
      { id: "steps-screenshot", label: "screenshot" },
      { id: "steps-locator-types", label: "locator types" },
    ],
  },
  {
    id: "effects", label: "effects", children: [
      { id: "effects-browser", label: "browser effects" },
      { id: "effects-cursor-trails", label: "cursor trails" },
      { id: "effects-fun", label: "fun / celebration" },
      { id: "effects-post", label: "post-processing" },
    ],
  },
  {
    id: "effects-camera", label: "camera effects", children: [
      { id: "effects-camera-movement", label: "camera movement" },
      { id: "effects-cinematic", label: "cinematic" },
    ],
  },
  {
    id: "pipeline", label: "pipeline", children: [
      { id: "pipeline-optimize", label: "optimize stage" },
    ],
  },
  {
    id: "output", label: "output", children: [
      { id: "output-thumbnails", label: "thumbnails" },
      { id: "output-social", label: "social presets" },
    ],
  },
  { id: "analytics", label: "analytics", beta: true },
  {
    id: "cli", label: "CLI Reference", children: [
      { id: "cli-run", label: "demodsl run" },
      { id: "cli-validate", label: "demodsl validate" },
      { id: "cli-init", label: "demodsl init" },
    ],
  },
  {
    id: "edge-cases", label: "Edge Cases", children: [
      { id: "edge-minimal", label: "minimal config" },
      { id: "edge-format", label: "YAML vs JSON" },
      { id: "edge-voice-fallback", label: "voice fallback" },
      { id: "edge-pipeline-stage-format", label: "pipeline stage format" },
    ],
  },
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

function Code({ children }: { children: React.ReactNode }) {
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

function FeatureDemo({ videoSrc, title, yamlConfig }: { videoSrc: string; title: string; yamlConfig: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className="rounded-2xl border border-indigo-900/50 bg-indigo-950/10 p-6 mb-8">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs font-semibold text-indigo-400 bg-indigo-950 px-2.5 py-1 rounded-full uppercase tracking-wider">Live Example</span>
        <span className="text-sm text-zinc-400">{title}</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800">
            <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
          </div>
          {isVisible ? (
            <video className="w-full aspect-video bg-black" controls muted playsInline preload="none">
              <source src={videoSrc} type="video/mp4" />
            </video>
          ) : (
            <div className="w-full aspect-video bg-black" />
          )}
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="px-3 py-2 border-b border-zinc-800 bg-zinc-950/50">
            <span className="text-xs text-zinc-500 font-mono">config.yaml</span>
          </div>
          <pre className="p-3 overflow-x-auto text-xs leading-relaxed max-h-[300px] overflow-y-auto">
            <code className="text-zinc-300 font-mono">{yamlConfig}</code>
          </pre>
        </div>
      </div>
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
        <nav className="space-y-0.5">
          {sections.map((s) => (
            <div key={s.id}>
              <a
                href={`#${s.id}`}
                onClick={() => setSidebarOpen(false)}
                className="block text-sm text-zinc-400 hover:text-white py-1 px-2 rounded hover:bg-zinc-800 transition-colors"
              >
                {s.label}
                {s.beta && <span className="ml-1.5 text-[10px] font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-1.5 py-0.5 rounded-full">Beta</span>}
              </a>
              {s.children && (
                <div className="ml-3 border-l border-zinc-800 pl-2 space-y-0.5">
                  {s.children.map((c) => (
                    <a
                      key={c.id}
                      href={`#${c.id}`}
                      onClick={() => setSidebarOpen(false)}
                      className="block text-xs text-zinc-500 hover:text-zinc-300 py-0.5 px-2 rounded hover:bg-zinc-800/60 transition-colors"
                    >
                      {c.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
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
          A configuration file has 10 top-level sections. Only <Code>metadata</Code>{" "}
          is required — every other section is optional and has sensible defaults.
        </P>
        <CodeBlock title="Root structure">{`metadata:        # REQUIRED — title, description, author, version
voice:           # TTS engine configuration
audio:           # Background music, voice processing, effects
device_rendering: # 3D device mockup settings
video:           # Intro, outro, transitions, watermark
subtitle:        # Subtitle overlay styles and timing
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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_tab_switch.mp4"
          title="YAML / JSON format switching"
          yamlConfig={`scenarios:
  - name: "Tab Switching"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport: { width: 1280, height: 720 }
    steps:
      - action: "scroll"
        direction: "down"
        pixels: 1800
        narration: "Scroll to the code example section."
        wait: 2.0
      - action: "click"
        locator:
          type: "text"
          value: "JSON"
        narration: "Click JSON tab to see JSON format."
        wait: 2.5
      - action: "click"
        locator:
          type: "text"
          value: "YAML"
        narration: "Switch back to YAML."
        wait: 2.0`}
        />

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
            ["engine", '"elevenlabs" | "google" | "azure" | "aws_polly" | "openai" | "custom"', '"elevenlabs"', "TTS provider to use."],
            ["voice_id", "string", '"josh"', "Voice identifier. Provider-specific."],
            ["speed", "float", "1.0", "Playback speed multiplier (0.5 = half speed, 2.0 = double)."],
            ["pitch", "int", "0", "Pitch adjustment in semitones."],
            ["reference_audio", "string", "null", "Path to a .wav/.mp3 sample of your voice for voice cloning. Supported by: elevenlabs, coqui, cosyvoice, custom."],
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
            ["espeak", "—", "—", "eSpeak-NG — robotic vintage voice. Zero-dependency debug TTS. ESPEAK_BIN to override binary."],
            ["gtts", "—", "—", "Google Translate TTS (gTTS) — free, no API key. pip install gtts."],
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
            ["espeak", "voice_id", '"en"', 'eSpeak voice/language code. E.g. "en", "fr", "de", "en+whisper".'],
            ["gtts", "voice_id", '"en"', 'Language code (ISO 639-1). E.g. "en", "fr", "es", "ja".'],
            ["custom", "voice_id", '"default"', 'Any string. Passed as-is in the JSON body to your endpoint.'],
          ]}
        />
        <Callout type="warn">
          If no API key is found for the selected engine, DemoDSL automatically
          falls back to a <strong>DummyVoiceProvider</strong> that generates silent
          audio clips sized to match the narration text (~150 words per minute).
          This is useful for development and dry-runs.
        </Callout>

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_voice_narration.mp4"
          title="gTTS voice narration synced to actions"
          yamlConfig={`voice:
  engine: "gtts"
  voice_id: "en"
  speed: 1.0

scenarios:
  - name: "Narrated Tour"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: >
          Welcome to DemoDSL. Every step can include
          a narration field converted to speech.
        wait: 3.0
      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: >
          DemoDSL supports twelve voice engines,
          from ElevenLabs to local Piper and eSpeak.
        wait: 3.0`}
        />

        <CodeBlock title="Custom TTS endpoint">{`voice:
  engine: "custom"
  voice_id: "my-voice"
  speed: 1.0

# Environment variables:
#   CUSTOM_TTS_URL=https://my-tts-server.com/synthesize
#   CUSTOM_TTS_API_KEY=sk-...          (optional)
#   CUSTOM_TTS_RESPONSE_FORMAT=mp3     (mp3 or wav)`}</CodeBlock>
        <Callout type="info">
          The <Code>custom</Code> engine POSTs a JSON body{" "}
          <Code>{`{text, voice_id, speed, pitch}`}</Code> to your endpoint and
          expects raw audio bytes in the response. This lets you integrate any
          TTS service with a simple HTTP wrapper.
        </Callout>

        <Sub id="voice-cloning">Voice Cloning (reference_audio)</Sub>
        <P>
          Set <Code>reference_audio</Code> to a path to your own voice recording
          (.wav or .mp3) and DemoDSL will clone your voice on engines that
          support it. This way, the narration uses <em>your</em> voice instead
          of a stock voice.
        </P>
        <PropTable
          rows={[
            ["elevenlabs", "\u2713", "Instant Voice Cloning", "Uploads your sample via the Add Voice API. The cloned voice is cached for the session."],
            ["coqui", "\u2713", "XTTS v2 speaker_wav", "Passes reference audio directly to tts_to_file(speaker_wav=...). Zero-shot cloning."],
            ["cosyvoice", "\u2713", "Zero-shot mode", 'Sends base64-encoded reference audio with mode="zero_shot" in the API payload.'],
            ["custom", "\u2713", "Forwarded in JSON", "Adds a base64-encoded reference_audio field to the JSON payload for your endpoint."],
            ["openai", "\u2717", "Not supported", "OpenAI TTS does not support voice cloning."],
            ["google", "\u2717", "Not supported", "Google Cloud TTS does not support voice cloning."],
            ["azure", "\u2717", "Not supported", "Azure TTS does not support voice cloning."],
            ["aws_polly", "\u2717", "Not supported", "Amazon Polly does not support voice cloning."],
            ["piper", "\u2717", "Not supported", "Piper uses pre-trained .onnx models."],
            ["espeak", "\u2717", "Not supported", "eSpeak is a formant synthesizer."],
            ["gtts", "\u2717", "Not supported", "gTTS uses Google Translate voices."],
          ]}
        />
        <CodeBlock title="Voice cloning with Coqui XTTS">{`voice:
  engine: "coqui"
  voice_id: "default"
  reference_audio: "samples/my_voice.wav"
  speed: 1.0`}</CodeBlock>
        <CodeBlock title="Voice cloning with ElevenLabs">{`voice:
  engine: "elevenlabs"
  voice_id: "josh"          # fallback if cloning fails
  reference_audio: "samples/my_voice.wav"
  speed: 1.0`}</CodeBlock>
        <Callout type="info">
          When <Code>reference_audio</Code> is set on an unsupported engine, a
          warning is logged and the field is ignored. The narration still generates
          using the standard <Code>voice_id</Code>.
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
        <SectionHeading id="device-rendering">device_rendering <span className="text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-2 py-0.5 rounded-full ml-2 align-middle">Beta</span></SectionHeading>
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

        {/* ── Subtitle ───────────────────────────────────────────────── */}
        <SectionHeading id="subtitle">subtitle</SectionHeading>
        <P>
          Burns styled subtitles into the video, synced word-by-word to narration
          timing. Subtitles are generated as ASS files and composited via ffmpeg.
          Can be set at the top level (applies to all scenarios) or per-scenario.
        </P>
        <PropTable
          rows={[
            ["enabled", "bool", "true", "Enable subtitle overlay."],
            ["style", '"classic" | "tiktok" | "color" | "word_by_word" | "typewriter" | "karaoke" | "bounce" | "cinema" | "highlight_line" | "fade_word" | "emoji_react"', '"classic"', "Subtitle display style (see table below)."],
            ["speed", '"slow" | "normal" | "fast" | "tiktok"', '"normal"', "Display speed preset — controls words per second."],
            ["font_size", "int", "48", "Font size in pixels."],
            ["font_family", "string", '"Arial"', "Font family name."],
            ["font_color", "string", '"#FFFFFF"', "Primary text color (hex)."],
            ["background_color", "string", '"rgba(0,0,0,0.6)"', "Background fill behind text (hex or rgba)."],
            ["position", '"bottom" | "center" | "top"', '"bottom"', "Vertical position on screen."],
            ["highlight_color", "string", '"#FFD700"', "Accent color for highlighted words."],
            ["max_words_per_line", "int", "8", "Maximum words per subtitle line."],
            ["animation", '"none" | "fade" | "pop" | "slide"', '"none"', "Text entrance animation."],
          ]}
        />

        <Sub id="subtitle-styles">Subtitle Styles</Sub>
        <P>
          Each style preset configures defaults for font size, position, colors,
          and animation. User values always override the preset.
        </P>
        <PropTable
          rows={[
            ["classic", "42px, bottom, white on dark box", "—", "Traditional subtitle bar at the bottom. Clean, readable."],
            ["tiktok", "64px, center, bold word-by-word", "—", "Large centered text, one highlighted word at a time. Social media style."],
            ["color", "48px, bottom, word highlight", "—", "Full line visible, current word changes to accent color."],
            ["word_by_word", "56px, center, single word", "—", "One word at a time, centered. Maximum emphasis."],
            ["typewriter", "44px, bottom, green on black", "—", "Characters appear letter by letter. Terminal/hacker aesthetic."],
            ["karaoke", "52px, bottom, progressive fill", "—", "Words fill with color progressively, karaoke-bar style."],
            ["bounce", "60px, center, scale animation", "—", "Words pop in with a bounce scale effect (120% → 100%)."],
            ["cinema", "38px, bottom, italic serif", "—", "Elegant italic serif font with shadow. Film subtitle look."],
            ["highlight_line", "46px, bottom, dim/bright", "—", "Current line is bright white, rest stays dimmed gray."],
            ["fade_word", "50px, center, fade-in", "—", "Each word fades in with a smooth alpha transition."],
            ["emoji_react", "52px, bottom, emoji prefix", "—", "Auto-picks a contextual emoji based on narration keywords."],
          ]}
        />

        <Sub id="subtitle-style-demos">Style Demos</Sub>
        <P>
          Each video below shows a subtitle style in action on short sample
          narration text.
        </P>

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_classic.mp4"
          title="classic — traditional bottom bar"
          yamlConfig={`subtitle:
  style: "classic"
  speed: "normal"
  font_size: 42
  position: "bottom"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_tiktok.mp4"
          title="tiktok — bold centered word-by-word"
          yamlConfig={`subtitle:
  style: "tiktok"
  speed: "fast"
  font_size: 64
  position: "center"
  highlight_color: "#FFD700"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_color.mp4"
          title="color — current word highlight"
          yamlConfig={`subtitle:
  style: "color"
  speed: "normal"
  highlight_color: "#00FF88"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_word_by_word.mp4"
          title="word_by_word — one word at a time"
          yamlConfig={`subtitle:
  style: "word_by_word"
  speed: "normal"
  font_size: 56
  position: "center"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_typewriter.mp4"
          title="typewriter — letter-by-letter reveal"
          yamlConfig={`subtitle:
  style: "typewriter"
  font_color: "#00FF00"
  background_color: "rgba(0,0,0,0.8)"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_karaoke.mp4"
          title="karaoke — progressive color fill"
          yamlConfig={`subtitle:
  style: "karaoke"
  highlight_color: "#FF4444"
  position: "bottom"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_bounce.mp4"
          title="bounce — scale-pop animation"
          yamlConfig={`subtitle:
  style: "bounce"
  font_size: 60
  position: "center"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_cinema.mp4"
          title="cinema — italic serif with shadow"
          yamlConfig={`subtitle:
  style: "cinema"
  font_family: "Georgia"
  font_size: 38`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_highlight_line.mp4"
          title="highlight_line — dim/bright current line"
          yamlConfig={`subtitle:
  style: "highlight_line"
  highlight_color: "#FFFFFF"
  font_color: "#888888"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_fade_word.mp4"
          title="fade_word — smooth alpha fade-in"
          yamlConfig={`subtitle:
  style: "fade_word"
  font_size: 50
  position: "center"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_subtitle_emoji_react.mp4"
          title="emoji_react — contextual emoji prefix"
          yamlConfig={`subtitle:
  style: "emoji_react"
  font_size: 52
  highlight_color: "#FFD700"`}
        />

        <Sub id="subtitle-speed">Speed Presets</Sub>
        <PropTable
          rows={[
            ["slow", "1.5 wps", "—", "Slow pace — good for technical content or tutorials."],
            ["normal", "2.5 wps", "—", "Standard reading pace."],
            ["fast", "4.0 wps", "—", "Fast pace for experienced viewers."],
            ["tiktok", "6.0 wps", "—", "Very fast — matches TikTok/Reels pacing."],
          ]}
        />

        <CodeBlock title="Top-level subtitle (all scenarios)">{`subtitle:
  enabled: true
  style: "tiktok"
  speed: "fast"
  font_size: 64
  highlight_color: "#FFD700"
  position: "center"

scenarios:
  - name: "Demo"
    url: "https://myapp.com"
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "This text becomes a subtitle!"

pipeline:
  - generate_narration: {}
  - burn_subtitles: {}
  - edit_video: {}`}</CodeBlock>

        <CodeBlock title="Per-scenario subtitle override">{`scenarios:
  - name: "Intro"
    url: "https://myapp.com"
    subtitle:
      enabled: true
      style: "cinema"
      speed: "slow"
      font_family: "Georgia"
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "An elegant introduction."
  - name: "Features"
    subtitle:
      style: "bounce"
      speed: "fast"
    steps:
      - action: "scroll"
        direction: "down"
        pixels: 500
        narration: "Fast-paced feature showcase!"`}</CodeBlock>

        <Callout type="tip">
          Add <Code>burn_subtitles: {'{}'}</Code> to your pipeline to enable
          subtitle rendering. Subtitles are generated from the{" "}
          <Code>narration</Code> field of each step — no separate subtitle file
          needed.
        </Callout>

        <Callout type="info">
          The <Code>emoji_react</Code> style automatically picks emojis based on
          narration keywords: 👆 for &quot;click&quot;, 📜 for &quot;scroll&quot;, ⚡ for
          &quot;fast&quot;, 🎬 for &quot;video&quot;, and more. A 💬 default is used when no
          keyword matches.
        </Callout>

        {/* ── Scenarios ──────────────────────────────────────────────── */}
        <SectionHeading id="scenarios">scenarios</SectionHeading>
        <P>
          A list of browser automation scenarios. Each scenario captures a
          recording from a web application. Multiple scenarios are concatenated
          in the final video.
        </P>

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_multi_scenario.mp4"
          title="Two scenarios in one config"
          yamlConfig={`scenarios:
  - name: "Landing Page Overview"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Scenario one: the landing page."
        wait: 2.0
      - action: "scroll"
        direction: "down"
        pixels: 800
        narration: "Scroll through features."
        wait: 2.0

  - name: "Docs Deep Dive"
    url: "https://fran-cois.github.io/demodsl/docs"
    browser: "webkit"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/docs"
        narration: "Scenario two: the docs page."
        wait: 2.0`}
        />

        <PropTable
          rows={[
            ["name", "string", "—", "Required. Human-readable scenario name."],
            ["url", "string", "—", "Required. Base URL for the scenario."],
            ["browser", '"chrome" | "firefox" | "webkit"', '"chrome"', "Browser engine (Playwright)."],
            ["viewport", "Viewport", "1920×1080", "Browser viewport dimensions."],
            ["cursor", "CursorConfig", "null", "Visible cursor overlay mode. Shows mouse movement and click effects."],
            ["glow_select", "GlowSelectConfig", "null", "Apple Intelligence-style animated glow highlight around clicked elements."],
            ["popup_card", "PopupCardConfig", "null", "Popup card overlay synced with narration. Shows text and progressive item reveals."],
            ["avatar", "AvatarConfig", "null", "Animated avatar overlay synced with narration audio. Free (animated) or paid (D-ID, HeyGen) providers."],
            ["subtitle", "SubtitleConfig", "null", "Subtitle overlay config (per-scenario override). Overrides top-level subtitle settings."],
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

        <Sub id="scenarios-cursor">scenarios[].cursor</Sub>
        <P>
          Injects a visible fake cursor overlay captured in the recorded video.
          The cursor animates towards each target element before click/type
          actions and plays a visual effect on click.
        </P>
        <PropTable
          rows={[
            ["visible", "bool", "true", "Whether the cursor is shown."],
            ["style", '"dot" | "pointer"', '"dot"', "Cursor shape. Dot = circle, pointer = arrow SVG."],
            ["color", "string", '"#ef4444"', "Cursor color (hex)."],
            ["size", "int", "20", "Cursor size in pixels."],
            ["click_effect", '"ripple" | "pulse" | "none"', '"ripple"', "Visual effect on click."],
            ["smooth", "float", "0.4", "Animation duration in seconds (ease-out)."],
          ]}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_cursor.mp4"
          title="Cursor overlay — visible mouse movement + click ripple"
          yamlConfig={`scenarios:
  - name: "Cursor Showcase"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    cursor:
      visible: true
      style: "dot"
      color: "#ef4444"
      size: 20
      click_effect: "ripple"
      smooth: 0.4
    steps:
      - action: "click"
        locator:
          type: "text"
          value: "Get Started"
        narration: "Cursor moves to the button and clicks."
        wait: 2.0
      - action: "click"
        locator:
          type: "text"
          value: "Documentation"
        narration: "Smooth animation to each target."
        wait: 2.0`}
        />

        <Sub id="scenarios-glow-select">scenarios[].glow_select</Sub>
        <P>
          Apple Intelligence-style animated gradient glow that highlights
          elements before click and type actions. The glow pulses with a
          rotating hue and fades out after the action.
        </P>
        <PropTable
          rows={[
            ["enabled", "bool", "true", "Whether glow-select is active."],
            ["colors", "string[]", '["#a855f7","#6366f1","#ec4899","#a855f7"]', "Gradient color stops for the glow border."],
            ["duration", "float", "0.8", "Hue rotation cycle duration in seconds."],
            ["padding", "int", "8", "Extra padding around the element bounding box."],
            ["border_radius", "int", "12", "Border radius of the glow overlay."],
            ["intensity", "float", "0.9", "Glow opacity (0–1)."],
          ]}
        />
        <Callout type="tip">
          Combine <Code>cursor</Code> and <Code>glow_select</Code> for a polished
          demo experience. The cursor animates into the glowing element, then
          clicks.
        </Callout>

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_glow_select.mp4"
          title="Glow select — Apple Intelligence-style highlight on click"
          yamlConfig={`scenarios:
  - name: "Glow Select Showcase"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    cursor:
      style: "dot"
      color: "#a855f7"
    glow_select:
      enabled: true
      colors: ["#a855f7","#6366f1","#ec4899","#a855f7"]
      duration: 0.8
      padding: 8
      border_radius: 12
    steps:
      - action: "click"
        locator:
          type: "text"
          value: "Get Started"
        narration: "Glow appears around the button."
        wait: 2.0
      - action: "click"
        locator:
          type: "text"
          value: "Documentation"
        narration: "Each element gets the glow treatment."
        wait: 2.0`}
        />

        <Sub id="scenarios-popup-card">scenarios[].popup_card</Sub>
        <P>
          The <Code>popup_card</Code> mode injects styled overlay cards that appear synced
          with narration. When a step has a <Code>card</Code> field with a list of <Code>items</Code>,
          they are revealed progressively — each bullet appears one by one, timed to match the narrator.
        </P>
        <PropTable
          rows={[
            ["enabled", "boolean", "true", "Enable the popup card overlay."],
            ["position", '"bottom-right" | "bottom-left" | "top-right" | "top-left" | "bottom-center" | "top-center"', '"bottom-right"', "Card position on screen."],
            ["theme", '"glass" | "dark" | "light" | "gradient"', '"glass"', "Visual theme for the card."],
            ["max_width", "number", "420", "Maximum card width in pixels."],
            ["animation", '"slide" | "fade" | "scale"', '"slide"', "Entrance/exit animation style."],
            ["accent_color", "string", '"#818cf8"', "Accent color for bullets and progress bar."],
            ["show_icon", "boolean", "true", "Show emoji icon in the card header."],
            ["show_progress", "boolean", "true", "Show a progress bar synced with narration duration."],
          ]}
        />
        <P>
          Each step can include a <Code>card</Code> object with:
        </P>
        <PropTable
          rows={[
            ["card.title", "string", "null", "Card title text."],
            ["card.body", "string", "null", "Card body/description text."],
            ["card.items", "string[]", "null", "Bullet-point list. Revealed progressively when narration is present."],
            ["card.icon", "string", "null", 'Emoji or short text shown in the header (e.g. "🚀").'],
          ]}
        />
        <FeatureDemo
          videoSrc="/demodsl/videos/demo_popup_card.mp4"
          title="Popup cards — synced text overlays with progressive item reveal"
          yamlConfig={`scenarios:
  - name: "Card Overlay Tour"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    popup_card:
      enabled: true
      position: "bottom-right"
      theme: "glass"
      animation: "slide"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Welcome to DemoDSL."
        card:
          title: "DemoDSL"
          body: "A DSL-driven automated demo generator."
          icon: "🎬"
      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Six integrated phases."
        card:
          title: "Six Phases"
          icon: "⚡"
          items:
            - "Browser Automation"
            - "Voice Narration"
            - "Visual Effects"
            - "Video Composition"
            - "Audio Mixing"
            - "Multi-format Export"`}
        />

        <Sub id="scenarios-avatar">scenarios[].avatar</Sub>
        <P>
          An animated avatar overlay that reacts to narration audio in real time.
          The avatar lip-syncs to TTS amplitude and is composited on top of the
          video at the chosen corner. Two provider types are available:{" "}
          <strong>animated</strong> (free, Pillow-generated) and{" "}
          <strong>API-based</strong> (D-ID, HeyGen, SadTalker — paid or
          self-hosted).
        </P>
        <PropTable
          rows={[
            ["enabled", "bool", "true", "Whether the avatar overlay is active."],
            ["provider", '"animated" | "d-id" | "heygen" | "sadtalker"', '"animated"', "Avatar generation engine. Animated is free, others require an API key."],
            ["image", "string | null", "null", 'Path, URL (http/https), or preset name ("default", "robot", "circle"). URLs are downloaded and cached locally.'],
            ["position", '"bottom-right" | "bottom-left" | "top-right" | "top-left"', '"bottom-right"', "Corner position of the avatar on the video."],
            ["size", "int", "120", "Avatar diameter in pixels."],
            ["style", '"bounce" | "waveform" | "pulse" | "equalizer" | "xp_bliss" | "clippy" | "visualizer"', '"bounce"', "Animation style (animated provider only). See table below."],
            ["shape", '"circle" | "rounded" | "square"', '"circle"', "Avatar outline shape."],
            ["background", "string", '"rgba(0,0,0,0.5)"', "Background fill behind the avatar (CSS color or rgba)."],
            ["api_key", "string | null", "null", 'API key for paid providers. Supports env-var syntax: "${D_ID_API_KEY}".'],
            ["show_subtitle", "bool", "false", "Display narration text below the avatar box during playback."],
            ["subtitle_font_size", "int", "18", "Font size for the avatar subtitle text."],
            ["subtitle_font_color", "string", '"#FFFFFF"', "Font color for the avatar subtitle."],
            ["subtitle_bg_color", "string", '"rgba(0,0,0,0.7)"', "Background color for the avatar subtitle box."],
          ]}
        />

        <Sub id="scenarios-avatar-styles">Animation Styles (free)</Sub>
        <P>
          These styles are available with the <Code>animated</Code> provider.
          Each generates a different visual animation from the narration audio
          waveform.
        </P>
        <PropTable
          rows={[
            ["bounce", "—", "—", "A circle that scales up and down with audio amplitude. Simple and clean."],
            ["waveform", "—", "—", "Radial wave ring that expands from the center with audio pulses."],
            ["pulse", "—", "—", "Glowing disc with a pulsing aura effect. Subtle and professional."],
            ["equalizer", "—", "—", "Neon equalizer bars (Windows XP era). Retro audio visualizer look."],
            ["xp_bliss", "—", "—", "Windows XP Bliss-inspired hills, sun and floating music notes."],
            ["clippy", "—", "—", 'Animated paperclip with googly eyes. A nostalgic Microsoft Office mascot.'],
            ["visualizer", "—", "—", "Circular spectrum analyzer with rainbow gradient bars."],
            ["pacman", "—", "—", "Pac-Man chomping dots with a colorful ghost. Arcade nostalgia."],
            ["space_invader", "—", "—", "Pixel-art Space Invaders alien with shields and cannon. Retro arcade."],
            ["mario_block", "—", "—", "Bouncing Mario \"?\" block that pops coins on loud audio. Iconic gaming."],
            ["nyan_cat", "—", "—", "Pixel-art cat on a rainbow trail with scrolling stars. Internet classic."],
            ["matrix", "—", "—", "Cascading green Matrix code rain with avatar in the center."],
            ["pickle_rick", "—", "—", "Pickle Rick with rat limbs, expressive eyes, and yelling mouth. Wubba lubba dub dub!"],
            ["chrome_dino", "—", "—", "Chrome's offline T-Rex dinosaur with desert, cacti, and 'No internet' message."],
            ["marvin", "—", "—", "Marvin the Paranoid Android with sad eyes and depressive quotes. H2G2 classic."],
            ["mac128k", "—", "—", "Macintosh 128K with expressive face on green screen. Retro computing icon."],
            ["floppy_disk", "—", "—", "3.5\" floppy disk with face, label, and '1.44 MB' nostalgia."],
            ["bsod", "—", "—", "Blue Screen of Death with progressive error text and sad :( emoticon."],
            ["bugdroid", "—", "—", "Android's green Bugdroid robot with waving arms and antennae."],
            ["qr_code", "—", "—", "QR code pattern with expressive eyes in the center. 'SCAN ME!'"],
            ["gpu_sweat", "—", "—", "Sweating GPU with spinning fan, temperature display, and sweat drops."],
            ["rubber_duck", "—", "—", "Yellow rubber duck debugging companion with judgmental speech bubbles."],
            ["fail_whale", "—", "—", "Twitter's Fail Whale carried by birds. 'Twitter is over capacity.'"],
            ["server_rack", "—", "—", "Overheating server rack with red eyes, smoke, blinking LEDs, and temp bar."],
            ["cursor_hand", "—", "—", "Windows pointing hand cursor that bosses you around. 'Click here!'"],
            ["vhs_tape", "—", "—", "VHS cassette with spinning reels, label, and scanlines. 'Be kind, rewind!'"],
            ["cloud", "—", "—", "Cute but capricious cloud with rain, lightning, and data ownership jokes."],
            ["wifi_low", "—", "—", "Wi-Fi icon with one bar that stutters and cuts off mid-sen—"],
            ["nokia3310", "—", "—", "The indestructible Nokia 3310 with Snake and warrior quotes."],
            ["cookie", "—", "—", "Browser cookie with creepy eyes that knows your browsing habits."],
            ["modem56k", "—", "—", "56k modem with blinking LEDs, dial-up sounds, and green waveform."],
            ["esc_key", "—", "—", "Panicked Escape key trying to break free — sweat drops & frantic quotes."],
            ["sad_mac", "—", "—", "Classic dead Macintosh with X-eyed icon, error codes & hardware trauma."],
            ["usb_cable", "—", "—", "Tangled USB-A cable frustrated by 3-try insertion. Always wrong side."],
            ["hourglass", "—", "—", "Windows hourglass that speaks very slowly while sand trickles down."],
            ["firewire", "—", "—", "Forgotten FireWire 400 cable living in a drawer, reminiscing glory days."],
            ["ai_hallucinated", "—", "—", "Glitching robot mixing facts with recipes — spiral eye & glitch lines."],
            ["tamagotchi", "—", "—", "Abandoned pixel egg pet asking why you haven't fed it since 1998."],
            ["lasso_tool", "—", "—", "Obsessive Photoshop selection tool with marching ants on checkerboard."],
            ["battery_low", "—", "—", "Battery at 1% — red, blinking, talks fast then cuts off abruptly."],
            ["incognito", "—", "—", "Chrome Incognito detective with fedora & glasses. Sees nothing."],
          ]}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_bounce.mp4"
          title="bounce — scales up/down with audio"
          yamlConfig={`avatar:
  style: "bounce"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_waveform.mp4"
          title="waveform — radial wave ring"
          yamlConfig={`avatar:
  style: "waveform"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_pulse.mp4"
          title="pulse — glowing aura effect"
          yamlConfig={`avatar:
  style: "pulse"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_equalizer.mp4"
          title="equalizer — neon retro bars"
          yamlConfig={`avatar:
  style: "equalizer"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_xp_bliss.mp4"
          title="xp_bliss — Windows XP hills & notes"
          yamlConfig={`avatar:
  style: "xp_bliss"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_clippy.mp4"
          title="clippy — animated paperclip mascot"
          yamlConfig={`avatar:
  style: "clippy"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_visualizer.mp4"
          title="visualizer — circular spectrum analyzer"
          yamlConfig={`avatar:
  style: "visualizer"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_pacman.mp4"
          title="pacman — arcade chomper & ghost"
          yamlConfig={`avatar:
  style: "pacman"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_space_invader.mp4"
          title="space_invader — pixel-art alien arcade"
          yamlConfig={`avatar:
  style: "space_invader"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_mario_block.mp4"
          title='mario_block — bouncing "?" block with coins'
          yamlConfig={`avatar:
  style: "mario_block"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_nyan_cat.mp4"
          title="nyan_cat — rainbow trail pixel cat"
          yamlConfig={`avatar:
  style: "nyan_cat"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_matrix.mp4"
          title="matrix — cascading green code rain"
          yamlConfig={`avatar:
  style: "matrix"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_pickle_rick.mp4"
          title="pickle_rick — I'M PICKLE RICK!"
          yamlConfig={`avatar:
  style: "pickle_rick"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_chrome_dino.mp4"
          title="chrome_dino — No internet? No problem!"
          yamlConfig={`avatar:
  style: "chrome_dino"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_marvin.mp4"
          title="marvin — brain the size of a planet"
          yamlConfig={`avatar:
  style: "marvin"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_mac128k.mp4"
          title="mac128k — hello from 1984"
          yamlConfig={`avatar:
  style: "mac128k"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_floppy_disk.mp4"
          title="floppy_disk — I AM the save icon!"
          yamlConfig={`avatar:
  style: "floppy_disk"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_bsod.mp4"
          title="bsod — your PC ran into a problem :("
          yamlConfig={`avatar:
  style: "bsod"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_bugdroid.mp4"
          title="bugdroid — Android says hello"
          yamlConfig={`avatar:
  style: "bugdroid"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_qr_code.mp4"
          title="qr_code — SCAN ME!"
          yamlConfig={`avatar:
  style: "qr_code"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_gpu_sweat.mp4"
          title="gpu_sweat — too hot to handle"
          yamlConfig={`avatar:
  style: "gpu_sweat"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_rubber_duck.mp4"
          title="rubber_duck — have you tried reading the docs?"
          yamlConfig={`avatar:
  style: "rubber_duck"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_fail_whale.mp4"
          title="fail_whale — Twitter is over capacity"
          yamlConfig={`avatar:
  style: "fail_whale"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_server_rack.mp4"
          title="server_rack — everything is fine 🔥"
          yamlConfig={`avatar:
  style: "server_rack"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_cursor_hand.mp4"
          title="cursor_hand — click here! No, not THERE!"
          yamlConfig={`avatar:
  style: "cursor_hand"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_vhs_tape.mp4"
          title="vhs_tape — be kind, rewind!"
          yamlConfig={`avatar:
  style: "vhs_tape"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_cloud.mp4"
          title="cloud — I own your data"
          yamlConfig={`avatar:
  style: "cloud"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_wifi_low.mp4"
          title="wifi_low — Can you hea—"
          yamlConfig={`avatar:
  style: "wifi_low"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_nokia3310.mp4"
          title="nokia3310 — I AM indestructible"
          yamlConfig={`avatar:
  style: "nokia3310"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_cookie.mp4"
          title="cookie — I know what you browsed"
          yamlConfig={`avatar:
  style: "cookie"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_modem56k.mp4"
          title="modem56k — psshhh-kkkk-ding-ding"
          yamlConfig={`avatar:
  style: "modem56k"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_esc_key.mp4"
          title="esc_key — LET ME OUT!"
          yamlConfig={`avatar:
  style: "esc_key"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_sad_mac.mp4"
          title="sad_mac — I've seen things…"
          yamlConfig={`avatar:
  style: "sad_mac"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_usb_cable.mp4"
          title="usb_cable — Wrong side. Again."
          yamlConfig={`avatar:
  style: "usb_cable"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_hourglass.mp4"
          title="hourglass — Please… wait…"
          yamlConfig={`avatar:
  style: "hourglass"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_firewire.mp4"
          title="firewire — I was the future!"
          yamlConfig={`avatar:
  style: "firewire"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_ai_hallucinated.mp4"
          title="ai_hallucinated — Add 2 eggs to your TCP/IP stack"
          yamlConfig={`avatar:
  style: "ai_hallucinated"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_tamagotchi.mp4"
          title="tamagotchi — Hungry since 1998"
          yamlConfig={`avatar:
  style: "tamagotchi"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_lasso_tool.mp4"
          title="lasso_tool — I WILL select it."
          yamlConfig={`avatar:
  style: "lasso_tool"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_battery_low.mp4"
          title="battery_low — I'm dying here—"
          yamlConfig={`avatar:
  style: "battery_low"
  size: 120
  shape: "circle"`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_avatar_incognito.mp4"
          title="incognito — Your secrets are safe. Maybe."
          yamlConfig={`avatar:
  style: "incognito"
  size: 120
  shape: "circle"`}
        />

        <CodeBlock title="Free animated avatar (equalizer)">{`scenarios:
  - name: "Demo with Avatar"
    url: "https://myapp.com"
    avatar:
      enabled: true
      provider: "animated"
      style: "equalizer"
      position: "bottom-right"
      size: 100
      shape: "circle"
      background: "rgba(0,0,0,0.6)"
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "The avatar reacts to this narration."
        wait: 2.0`}</CodeBlock>

        <CodeBlock title="Avatar with custom image from URL">{`scenarios:
  - name: "Demo with Custom Avatar"
    url: "https://myapp.com"
    avatar:
      enabled: true
      provider: "animated"
      image: "https://avatars.githubusercontent.com/u/22380190?v=4"
      style: "bounce"
      position: "bottom-right"
      size: 120
      shape: "circle"
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "My avatar uses an image loaded from a URL."
        wait: 2.0`}</CodeBlock>

        <CodeBlock title="Paid D-ID avatar (talking head)">{`scenarios:
  - name: "Demo with Talking Head"
    url: "https://myapp.com"
    avatar:
      enabled: true
      provider: "d-id"
      image: "presenter.jpg"
      position: "bottom-left"
      size: 200
      api_key: "\${D_ID_API_KEY}"
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "A real talking-head avatar powered by D-ID."
        wait: 3.0`}</CodeBlock>

        <Callout type="tip">
          Combine <Code>avatar</Code> with <Code>cursor</Code> and{" "}
          <Code>glow_select</Code> for a fully polished demo experience. Add{" "}
          <Code>composite_avatar</Code> to your pipeline to enable the overlay.
        </Callout>

        <CodeBlock title="Avatar with inline subtitles">{`scenarios:
  - name: "Demo with Avatar Subtitles"
    url: "https://myapp.com"
    avatar:
      enabled: true
      provider: "animated"
      style: "clippy"
      position: "bottom-right"
      size: 100
      show_subtitle: true
      subtitle_font_size: 16
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "Narration text appears right below the avatar."
        wait: 2.0`}</CodeBlock>

        <FeatureDemo
          videoSrc="/demodsl/videos/demodsl_site_demo.mp4"
          title="Avatar + subtitles — synced to narration"
          yamlConfig={`subtitle:
  enabled: true
  style: "cinema"
  speed: "normal"

scenarios:
  - name: "Site Tour"
    url: "https://fran-cois.github.io/demodsl/"
    avatar:
      enabled: true
      provider: "animated"
      style: "clippy"
      position: "bottom-right"
      size: 100
      shape: "circle"
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "The avatar pulses to each narration."
        wait: 2.0
      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Subtitles appear in cinema style."
        wait: 2.0

pipeline:
  - composite_avatar: {}
  - burn_subtitles: {}
  - edit_video: {}
  - mix_audio: {}
  - optimize: {}`}
        />

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
            ["card", "CardContent | null", "null", 'Popup card content (title, body, items, icon). Shown synced with narration when popup_card mode is enabled.'],
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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_click.mp4"
          title="Click Actions — using text locators"
          yamlConfig={`scenarios:
  - name: "Click Interactions"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport: { width: 1280, height: 720 }
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Open the documentation site."
        wait: 2.0
      - action: "click"
        locator:
          type: "text"
          value: "Get Started"
        narration: "Click Get Started via text locator."
        wait: 1.5
      - action: "click"
        locator:
          type: "text"
          value: "GitHub →"
        narration: "Click the GitHub link."
        wait: 2.0`}
        />

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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_navigate_scroll.mp4"
          title="Navigate & Scroll — generated from this config"
          yamlConfig={`scenarios:
  - name: "Navigate and Scroll"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport: { width: 1280, height: 720 }
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Navigate to the target URL."
        wait: 2.0
      - action: "scroll"
        direction: "down"
        pixels: 400
        narration: "Scroll down 400 pixels."
        wait: 1.5
      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Continue scrolling."
        wait: 1.5
      - action: "scroll"
        direction: "up"
        pixels: 300
        narration: "Scroll back up."
        wait: 1.5`}
        />

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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_waitfor.mp4"
          title="wait_for — wait for elements before interacting"
          yamlConfig={`steps:
  - action: "navigate"
    url: "https://fran-cois.github.io/demodsl/docs"
    narration: "Navigate to the docs page."
    wait: 2.0
  - action: "wait_for"
    locator:
      type: "css"
      value: "nav a"
    timeout: 5.0
    narration: "Wait for the sidebar nav to load."
    wait: 1.5
  - action: "click"
    locator:
      type: "css"
      value: "a[href='#effects']"
    narration: "Click the effects link."
    wait: 2.0
  - action: "wait_for"
    locator:
      type: "css"
      value: "#effects"
    timeout: 5.0
    narration: "Wait for effects heading to appear."
    wait: 1.5`}
        />

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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_mobile_screenshot.mp4"
          title="Mobile Viewport & Screenshot capture"
          yamlConfig={`scenarios:
  - name: "Mobile Capture"
    url: "https://fran-cois.github.io/demodsl/"
    browser: "webkit"
    viewport:
      width: 390
      height: 844
    steps:
      - action: "navigate"
        url: "https://fran-cois.github.io/demodsl/"
        narration: "Load in mobile viewport, 390x844."
        wait: 2.0
      - action: "scroll"
        direction: "down"
        pixels: 400
        narration: "See the responsive layout."
        wait: 1.5
      - action: "screenshot"
        filename: "mobile_capture.png"
        narration: "Take a screenshot."
        wait: 1.0`}
        />

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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_locators.mp4"
          title="All locator types in action"
          yamlConfig={`steps:
  - action: "click"
    locator:
      type: "text"
      value: "Get Started"
    narration: "Text locator: click by visible text."
    wait: 2.0
  - action: "click"
    locator:
      type: "text"
      value: "Documentation"
    narration: "Text locator: click Documentation."
    wait: 2.0
  - action: "click"
    locator:
      type: "css"
      value: "a[href='#pipeline']"
    narration: "CSS locator: jump to pipeline."
    wait: 2.0
  - action: "scroll"
    direction: "down"
    pixels: 400
    narration: "Supports css, id, xpath, and text."
    wait: 1.5`}
        />

        {/* ── Effects ────────────────────────────────────────────────── */}
        <SectionHeading id="effects">effects</SectionHeading>
        <P>
          43 visual effects are available, split into five categories:{" "}
          <strong>browser effects</strong> (11 — injected as CSS/JS during capture),{" "}
          <strong>cursor trail variants</strong> (6 — animated trails following the cursor),{" "}
          <strong>fun / celebration effects</strong> (6 — confetti-style canvas overlays),{" "}
          <strong>post-processing effects</strong> (7 — applied to the rendered
          video via MoviePy), and <strong>camera &amp; cinematic effects</strong>{" "}
          (13 — advanced camera movements and cinematic post-processing).
          Effects are attached to individual steps.
        </P>
        <PropTable
          rows={[
            ["type", "EffectType", "—", "Required. Effect name (see tables below)."],
            ["duration", "float | null", "null", "Effect duration in seconds."],
            ["intensity", "float | null", "null", "Effect intensity (0.0–1.0)."],
            ["color", "string | null", "null", "Effect color (hex). Used by highlight, glow, neon_glow."],
            ["speed", "float | null", "null", "Animation speed. Used by typewriter, camera_shake, rotate."],
            ["scale", "float | null", "null", "Zoom scale factor. Used by zoom_pulse, drone_zoom, ken_burns, zoom_to, elastic_zoom."],
            ["depth", "int | null", "null", "Parallax depth. Used by parallax."],
            ["direction", "string | null", "null", 'Direction (\"left\", \"right\", \"up\", \"down\"). Used by slide_in, ken_burns, whip_pan, focus_pull.'],
            ["target_x", "float | null", "null", "Normalized X position (0.0–1.0). Used by drone_zoom, zoom_to."],
            ["target_y", "float | null", "null", "Normalized Y position (0.0–1.0). Used by drone_zoom, zoom_to."],
            ["angle", "float | null", "null", "Rotation angle in degrees. Used by rotate."],
            ["ratio", "float | null", "null", "Aspect ratio (e.g. 2.35 for cinemascope). Used by letterbox."],
            ["preset", "string | null", "null", 'Color grade preset (\"warm\", \"cool\", \"desaturate\", \"vintage\", \"cinematic\"). Used by color_grade.'],
            ["focus_position", "float | null", "null", "Focus band position (0.0–1.0). Used by tilt_shift."],
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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_spotlight.mp4"
          title="spotlight — radial gradient overlay"
          yamlConfig={`effects:
  - type: "spotlight"
    intensity: 0.8
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_highlight.mp4"
          title="highlight — glowing box-shadow on hover"
          yamlConfig={`effects:
  - type: "highlight"
    color: "#FFD700"
    intensity: 0.9
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_confetti.mp4"
          title="confetti — falling particles"
          yamlConfig={`effects:
  - type: "confetti"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_typewriter.mp4"
          title="typewriter — blinking caret on inputs"
          yamlConfig={`effects:
  - type: "typewriter"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_glow.mp4"
          title="glow — inner box-shadow glow"
          yamlConfig={`effects:
  - type: "glow"
    color: "#6366f1"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_shockwave.mp4"
          title="shockwave — expanding ring animation"
          yamlConfig={`effects:
  - type: "shockwave"
    intensity: 1.0
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_sparkle.mp4"
          title="sparkle — golden sparkling dots"
          yamlConfig={`effects:
  - type: "sparkle"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail.mp4"
          title="cursor_trail — trailing particles"
          yamlConfig={`effects:
  - type: "cursor_trail"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_ripple.mp4"
          title="ripple — click ripple effect"
          yamlConfig={`effects:
  - type: "ripple"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_neon_glow.mp4"
          title="neon_glow — vivid neon border"
          yamlConfig={`effects:
  - type: "neon_glow"
    color: "#FF00FF"
    duration: 2.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_success_checkmark.mp4"
          title="success_checkmark — animated green ✓"
          yamlConfig={`effects:
  - type: "success_checkmark"
    duration: 2.0`}
        />

        <Sub id="effects-cursor-trails">Cursor Trail Variants</Sub>
        <P>
          Six animated cursor trail styles — each follows mouse movement with
          a unique visual style. All are browser-injected effects.
        </P>
        <PropTable
          rows={[
            ["cursor_trail_rainbow", "duration", "—", "Rainbow-colored dots cycling through hues."],
            ["cursor_trail_comet", "duration", "—", "Comet tail with size gradient (3 particles per move)."],
            ["cursor_trail_glow", "duration, color", "—", "Soft glowing trail with radial gradient and box-shadow."],
            ["cursor_trail_line", "duration", "—", "Connected SVG line segments following the cursor."],
            ["cursor_trail_particles", "duration", "—", "Particle burst on each mouse move (5 per event)."],
            ["cursor_trail_fire", "duration", "—", "Warm orange/red fire sparks rising and fading."],
          ]}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail_rainbow.mp4"
          title="cursor_trail_rainbow — rainbow cycling dots"
          yamlConfig={`effects:
  - type: "cursor_trail_rainbow"
    duration: 3.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail_comet.mp4"
          title="cursor_trail_comet — size gradient tail"
          yamlConfig={`effects:
  - type: "cursor_trail_comet"
    duration: 3.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail_glow.mp4"
          title="cursor_trail_glow — soft glowing trail"
          yamlConfig={`effects:
  - type: "cursor_trail_glow"
    color: "#00BFFF"
    duration: 3.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail_line.mp4"
          title="cursor_trail_line — connected SVG segments"
          yamlConfig={`effects:
  - type: "cursor_trail_line"
    duration: 3.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail_particles.mp4"
          title="cursor_trail_particles — particle burst"
          yamlConfig={`effects:
  - type: "cursor_trail_particles"
    duration: 3.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_cursor_trail_fire.mp4"
          title="cursor_trail_fire — fire sparks"
          yamlConfig={`effects:
  - type: "cursor_trail_fire"
    duration: 3.0`}
        />

        <Sub id="effects-fun">Fun / Celebration Effects</Sub>
        <P>
          Six celebration-style canvas overlays for joyful moments.
          All auto-cleanup after their animation completes.
        </P>
        <PropTable
          rows={[
            ["emoji_rain", "duration", "—", "Rain of emojis (🎉🔥❤️⭐🚀💯) falling from the top."],
            ["fireworks", "duration", "—", "Rockets launching and exploding into colorful particles."],
            ["bubbles", "duration", "—", "Translucent bubbles rising with sinusoidal wobble."],
            ["snow", "duration", "—", "Snowflakes drifting down with gentle wind drift."],
            ["star_burst", "duration", "—", "5-pointed stars exploding from the center."],
            ["party_popper", "duration", "—", "Confetti shapes (rect/circle/triangle) from both bottom corners."],
          ]}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_emoji_rain.mp4"
          title="emoji_rain — falling emojis 🎉🔥⭐"
          yamlConfig={`effects:
  - type: "emoji_rain"
    duration: 4.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_fireworks.mp4"
          title="fireworks — rockets and explosions 🎆"
          yamlConfig={`effects:
  - type: "fireworks"
    duration: 5.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_bubbles.mp4"
          title="bubbles — translucent rising bubbles"
          yamlConfig={`effects:
  - type: "bubbles"
    duration: 4.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_snow.mp4"
          title="snow — drifting snowflakes ❄️"
          yamlConfig={`effects:
  - type: "snow"
    duration: 6.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_star_burst.mp4"
          title="star_burst — exploding stars ⭐"
          yamlConfig={`effects:
  - type: "star_burst"
    duration: 3.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_party_popper.mp4"
          title="party_popper — corner confetti 🎊"
          yamlConfig={`effects:
  - type: "party_popper"
    duration: 4.0`}
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

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_browser_effects.mp4"
          title="5 browser effects: spotlight, highlight, glow, neon_glow, checkmark"
          yamlConfig={`steps:
  - action: "navigate"
    url: "https://fran-cois.github.io/demodsl/"
    narration: "Effects are injected via JS during capture."
    wait: 2.0
    effects:
      - type: "spotlight"
        duration: 2.0
        intensity: 0.8
  - action: "scroll"
    direction: "down"
    pixels: 500
    narration: "Highlight adds a glowing box-shadow."
    effects:
      - type: "highlight"
        duration: 2.0
        color: "#FFD700"
  - action: "scroll"
    direction: "down"
    pixels: 500
    narration: "Glow creates an inner glow."
    effects:
      - type: "glow"
        duration: 2.0
        color: "#6366f1"
  - action: "scroll"
    direction: "down"
    pixels: 500
    narration: "Neon glow adds a vivid border."
    effects:
      - type: "neon_glow"
        duration: 2.0
        color: "#FF00FF"
  - action: "screenshot"
    narration: "Success checkmark overlay."
    effects:
      - type: "success_checkmark"
        duration: 2.0`}
        />

        {/* ── Camera & Cinematic Effects ──────────────────────────── */}
        <SectionHeading id="effects-camera">Camera &amp; Cinematic Effects</SectionHeading>
        <P>
          13 advanced camera and cinematic effects for professional-looking demos.
          These are all post-processing effects applied via MoviePy — they simulate
          real camera movements and cinematic grading on the rendered video.
        </P>

        <Sub id="effects-camera-movement">Camera Movement Effects</Sub>
        <PropTable
          rows={[
            ["drone_zoom", "scale, target_x, target_y", "—", "Smooth progressive zoom towards a target point — simulates a drone descent."],
            ["ken_burns", "scale, direction", "—", "Classic documentary pan + zoom (slow push with lateral drift)."],
            ["zoom_to", "scale, target_x, target_y", "—", "Zoom to a specific point and hold — great for highlighting UI elements."],
            ["dolly_zoom", "intensity", "—", "Vertigo / dolly-zoom: zoom in while widening the crop."],
            ["elastic_zoom", "scale", "—", "Zoom with elastic overshoot bounce (ease-out-back)."],
            ["camera_shake", "intensity, speed", "—", "Subtle camera shake / handheld feel."],
            ["whip_pan", "direction", "—", "Fast horizontal/vertical pan with motion blur — great for transitions."],
            ["rotate", "angle, speed", "—", "Gentle animated rotation — subtle tilt for dynamic feel."],
          ]}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_drone_zoom.mp4"
          title="drone_zoom — smooth descent towards a target"
          yamlConfig={`effects:
  - type: "drone_zoom"
    scale: 1.4
    target_x: 0.5   # center horizontally
    target_y: 0.3   # focus on upper third`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_ken_burns.mp4"
          title="ken_burns — classic documentary pan + zoom"
          yamlConfig={`effects:
  - type: "ken_burns"
    scale: 1.15
    direction: "right"  # left, right, up, down`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_zoom_to.mp4"
          title="zoom_to — zoom and hold on a UI element"
          yamlConfig={`effects:
  - type: "zoom_to"
    scale: 1.8
    target_x: 0.5
    target_y: 0.4`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_dolly_zoom.mp4"
          title="dolly_zoom — dramatic vertigo effect"
          yamlConfig={`effects:
  - type: "dolly_zoom"
    intensity: 0.3`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_elastic_zoom.mp4"
          title="elastic_zoom — bouncy zoom with overshoot"
          yamlConfig={`effects:
  - type: "elastic_zoom"
    scale: 1.3`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_camera_shake.mp4"
          title="camera_shake — subtle handheld feel"
          yamlConfig={`effects:
  - type: "camera_shake"
    intensity: 0.3
    speed: 8.0`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_whip_pan.mp4"
          title="whip_pan — fast transition with motion blur"
          yamlConfig={`effects:
  - type: "whip_pan"
    direction: "right"  # left, right, up, down`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_rotate.mp4"
          title="rotate — gentle animated tilt"
          yamlConfig={`effects:
  - type: "rotate"
    angle: 3.0    # degrees
    speed: 1.0    # oscillations per clip`}
        />

        <Sub id="effects-cinematic">Cinematic Effects</Sub>
        <PropTable
          rows={[
            ["letterbox", "ratio", "—", "Cinematic black bars (e.g. 2.35:1 cinemascope)."],
            ["film_grain", "intensity", "—", "Analog film grain overlay."],
            ["color_grade", "preset", "—", 'Color grading presets: warm, cool, desaturate, vintage, cinematic.'],
            ["focus_pull", "direction, intensity", "—", "Rack focus: transition from sharp to blurry (or reverse)."],
            ["tilt_shift", "intensity, focus_position", "—", "Miniature / tilt-shift: sharp band in center, blurred edges."],
          ]}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_letterbox.mp4"
          title="letterbox — cinematic 2.35:1 black bars"
          yamlConfig={`effects:
  - type: "letterbox"
    ratio: 2.35   # cinemascope`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_film_grain.mp4"
          title="film_grain — analog film texture"
          yamlConfig={`effects:
  - type: "film_grain"
    intensity: 0.3`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_color_grade.mp4"
          title="color_grade — cinematic color grading"
          yamlConfig={`effects:
  - type: "color_grade"
    preset: "cinematic"  # warm, cool, desaturate, vintage, cinematic`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_focus_pull.mp4"
          title="focus_pull — rack focus transition"
          yamlConfig={`effects:
  - type: "focus_pull"
    direction: "out"   # in = blur→sharp, out = sharp→blur
    intensity: 0.5`}
        />

        <FeatureDemo
          videoSrc="/demodsl/videos/demo_effect_tilt_shift.mp4"
          title="tilt_shift — miniature effect"
          yamlConfig={`effects:
  - type: "tilt_shift"
    intensity: 0.6
    focus_position: 0.5  # 0.0=top, 0.5=center, 1.0=bottom`}
        />

        <Callout type="tip">
          Combine camera effects for professional results: pair{" "}
          <Code>letterbox</Code> + <Code>color_grade</Code> + <Code>film_grain</Code>{" "}
          for a cinematic look, or <Code>drone_zoom</Code> + <Code>vignette</Code>{" "}
          for a dramatic reveal.
        </Callout>

        <CodeBlock title="Full cinematic combo example">{`steps:
  - action: "navigate"
    url: "https://example.com"
    narration: "A cinematic reveal of our product."
    effects:
      - type: "drone_zoom"
        scale: 1.4
        target_x: 0.5
        target_y: 0.3
      - type: "letterbox"
        ratio: 2.35
      - type: "color_grade"
        preset: "cinematic"
      - type: "film_grain"
        intensity: 0.2
      - type: "vignette"
        intensity: 0.4`}</CodeBlock>

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
            ["composite_avatar", "optional", "{}", "Overlay avatar clips on the video. Requires avatar config in the scenario."],
            ["burn_subtitles", "optional", "{}", "Burn ASS subtitles into the video. Requires subtitle config (top-level or per-scenario)."],
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
  - composite_avatar: {}
  - burn_subtitles: {}
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
        <SectionHeading id="analytics">analytics <span className="text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-2 py-0.5 rounded-full ml-2 align-middle">Beta</span></SectionHeading>
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
            ["ESPEAK_BIN", "string", '"espeak-ng"', "Path to eSpeak-NG binary."],
            ["CUSTOM_TTS_URL", "string", "—", "Required. Full URL of your custom TTS HTTP endpoint."],
            ["CUSTOM_TTS_API_KEY", "string", "—", "Bearer token for custom TTS (optional)."],
            ["CUSTOM_TTS_RESPONSE_FORMAT", "string", '"mp3"', 'Audio format returned by the endpoint: "mp3" or "wav".'],
            ["D_ID_API_KEY", "string", "—", "D-ID API key for talking-head avatar generation."],
            ["HEYGEN_API_KEY", "string", "—", "HeyGen API key for avatar video generation."],
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
