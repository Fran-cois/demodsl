export function DemoVideo() {
  return (
    <section className="px-6 py-20 bg-zinc-950/50">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-3xl font-bold text-center mb-4">
          See it in action
        </h2>
        <p className="text-center text-zinc-400 mb-10 max-w-2xl mx-auto">
          This video was generated automatically by DemoDSL — running{" "}
          <code className="text-indigo-400 bg-zinc-800 px-1.5 py-0.5 rounded text-sm">
            demodsl run demo_site.yaml
          </code>{" "}
          against this very documentation site.
        </p>

        <div className="rounded-2xl border border-zinc-800 overflow-hidden shadow-2xl shadow-indigo-950/20">
          <div className="flex items-center gap-2 px-4 py-3 bg-zinc-900 border-b border-zinc-800">
            <span className="h-3 w-3 rounded-full bg-red-500/80" />
            <span className="h-3 w-3 rounded-full bg-yellow-500/80" />
            <span className="h-3 w-3 rounded-full bg-green-500/80" />
            <span className="ml-3 text-xs text-zinc-500 font-mono">
              demodsl_site_demo.mp4
            </span>
          </div>
          <video
            className="w-full aspect-video bg-black"
            controls
            muted
            playsInline
            preload="metadata"
            autoPlay
            loop
          >
            <source src="/demodsl/videos/demodsl_site_demo.mp4" type="video/mp4" />
            <source src="/demodsl/videos/demodsl_site_demo.webm" type="video/webm" />
            Your browser does not support the video tag.
          </video>
        </div>

        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-950/50">
            <span className="text-xs text-zinc-500 font-mono">
              demo_site.yaml (excerpt)
            </span>
          </div>
          <pre className="p-4 overflow-x-auto text-sm leading-relaxed">
            <code className="text-zinc-300 font-mono">{`metadata:
  title: "DemoDSL Documentation Site Tour"

voice:
  engine: "gtts"
  voice_id: "en"

subtitle:
  enabled: true
  style: "cinema"
  speed: "normal"

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
        wait: 3.0
      - action: "scroll"
        direction: "down"
        pixels: 600
        narration: "Discover the Quick Start section..."
      # ... 5 more steps

pipeline:
  - generate_narration: {}
  - composite_avatar: {}
  - burn_subtitles: {}
  - edit_video: {}`}</code>
          </pre>
        </div>
      </div>
    </section>
  );
}
