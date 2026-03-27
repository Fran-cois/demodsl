const yamlExample = `metadata:
  title: "My Product Demo"

voice:
  engine: "elevenlabs"
  voice_id: "josh"

scenarios:
  - name: "Quick Tour"
    url: "https://myapp.com"
    browser: "chrome"
    viewport: { width: 1920, height: 1080 }
    steps:
      - action: "navigate"
        url: "https://myapp.com"
        narration: "Welcome to our product!"
        effects:
          - type: "spotlight"
            duration: 2.0

      - action: "click"
        locator: { type: "css", value: "#get-started" }
        narration: "Click to get started."
        effects:
          - type: "confetti"
            duration: 1.5

pipeline:
  - generate_narration: {}
  - edit_video: {}
  - mix_audio: {}
  - optimize:
      format: "mp4"
      codec: "h264"

output:
  filename: "demo.mp4"
  formats: ["mp4", "webm", "gif"]`;

export function CodeExample() {
  return (
    <section className="px-6 py-20 bg-zinc-950/50">
      <div className="mx-auto max-w-4xl">
        <h2 className="text-3xl font-bold text-center mb-4">
          Declarative by design
        </h2>
        <p className="text-center text-zinc-400 mb-10 max-w-2xl mx-auto">
          Your entire demo is defined in a single YAML file. No scripts, no
          code — just declare what you want.
        </p>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-950/50">
            <div className="h-3 w-3 rounded-full bg-red-500/80" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
            <div className="h-3 w-3 rounded-full bg-green-500/80" />
            <span className="ml-3 text-xs text-zinc-500 font-mono">
              demo.yaml
            </span>
          </div>
          <pre className="p-6 overflow-x-auto text-sm leading-relaxed">
            <code className="text-zinc-300 font-mono">{yamlExample}</code>
          </pre>
        </div>

        <p className="text-center text-zinc-500 mt-6 text-sm">
          Then run:{" "}
          <code className="text-indigo-400 bg-zinc-800 px-2 py-1 rounded">
            demodsl run demo.yaml
          </code>
        </p>
      </div>
    </section>
  );
}
