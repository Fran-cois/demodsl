const features = [
  {
    icon: "🎭",
    title: "Browser Automation",
    description:
      "Playwright-powered capture with Chrome, Firefox, and WebKit. Navigate, click, type, scroll — all from YAML or JSON.",
  },
  {
    icon: "🎙️",
    title: "Voice Narration",
    description:
      "ElevenLabs TTS integration with automatic duration sync. Narration stretches video to match audio.",
  },
  {
    icon: "✨",
    title: "18 Visual Effects",
    description:
      "Spotlight, confetti, glitch, neon glow, vignette, and more. Applied in real-time via JS injection or post-processing.",
  },
  {
    icon: "🎬",
    title: "Video Composition",
    description:
      "Dual renderer: MoviePy for classic editing, or Remotion for React-based single-pass video composition with declarative effects.",
  },
  {
    icon: "🎵",
    title: "Audio Mixing",
    description:
      "Background music with smart ducking. Volume drops during narration, normalizes during silence.",
  },
  {
    icon: "�",
    title: "11 Subtitle Styles",
    description:
      "TikTok, karaoke, cinema, typewriter, bounce, and more. Synced to narration with word-level timing.",
  },
  {
    icon: "�📦",
    title: "Multi-format Export",
    description:
      "MP4, WebM, GIF output. Social media presets for YouTube, Instagram, and Twitter with auto-crop.",
  },
];

export function Features() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="text-3xl font-bold text-center mb-4">
          Everything you need for automated demos
        </h2>
        <p className="text-center text-zinc-400 mb-12 max-w-2xl mx-auto">
          From browser capture to final export — seven integrated phases in one
          pipeline.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 hover:border-indigo-800 transition-colors"
            >
              <div className="text-3xl mb-4">{f.icon}</div>
              <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                {f.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
