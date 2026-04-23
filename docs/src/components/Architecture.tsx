const patterns = [
  {
    name: "Abstract Factory",
    scope: "Providers",
    description: "Voice, Browser, and Render providers instantiated via factory pattern",
  },
  {
    name: "Command",
    scope: "Browser Actions",
    description: "Navigate, Click, Type, Scroll, WaitFor, Screenshot — each with execute() + describe()",
  },
  {
    name: "Chain of Responsibility",
    scope: "Pipeline",
    description: "8 stages with critical/optional error handling. Critical failure stops the chain.",
  },
  {
    name: "Registry + Strategy",
    scope: "Visual Effects",
    description: "18 effects in 2 registries — browser JS injection and post-processing via MoviePy",
  },
  {
    name: "Builder",
    scope: "Video Composition",
    description: "Progressive assembly: intro → segments → transitions → watermark → outro → build(). Powered by MoviePy + FFmpeg.",
  },
];

const pipeline = [
  { name: "restore_audio", critical: false, desc: "Denoise + normalize" },
  { name: "restore_video", critical: false, desc: "Stabilize + sharpen" },
  { name: "apply_effects", critical: false, desc: "Post-processing FX" },
  { name: "generate_narration", critical: true, desc: "TTS + video sync" },
  { name: "render_device_mockup", critical: false, desc: "Device frame" },
  { name: "edit_video", critical: true, desc: "Intro/outro/transitions" },
  { name: "mix_audio", critical: true, desc: "Voice + music ducking" },
  { name: "optimize", critical: true, desc: "Encoding + compression" },
];

export function Architecture() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="text-3xl font-bold text-center mb-4">Architecture</h2>
        <p className="text-center text-zinc-400 mb-12 max-w-2xl mx-auto">
          Built on 5 proven design patterns for modularity and extensibility.
        </p>

        {/* Design Patterns */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-16">
          {patterns.map((p) => (
            <div
              key={p.name}
              className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-indigo-400 bg-indigo-950 px-2 py-0.5 rounded">
                  {p.scope}
                </span>
              </div>
              <h3 className="font-semibold mb-1">{p.name}</h3>
              <p className="text-sm text-zinc-400">{p.description}</p>
            </div>
          ))}
        </div>

        {/* Pipeline */}
        <h3 className="text-xl font-bold text-center mb-6">
          Pipeline Stages
        </h3>
        <div className="mx-auto max-w-2xl space-y-2">
          {pipeline.map((s, i) => (
            <div
              key={s.name}
              className="flex items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-900/50 px-5 py-3"
            >
              <span className="text-xs text-zinc-600 font-mono w-4">
                {i + 1}
              </span>
              <code className="font-mono text-sm text-zinc-300 flex-1">
                {s.name}
              </code>
              <span className="text-xs text-zinc-500 hidden sm:block flex-1">
                {s.desc}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded font-medium ${
                  s.critical
                    ? "bg-red-950 text-red-400"
                    : "bg-zinc-800 text-zinc-500"
                }`}
              >
                {s.critical ? "critical" : "optional"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
