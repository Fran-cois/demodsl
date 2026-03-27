"use client";

import { useState } from "react";

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

const jsonExample = `{
  "metadata": { "title": "My Product Demo" },
  "voice": { "engine": "elevenlabs", "voice_id": "josh" },
  "scenarios": [
    {
      "name": "Quick Tour",
      "url": "https://myapp.com",
      "browser": "chrome",
      "viewport": { "width": 1920, "height": 1080 },
      "steps": [
        {
          "action": "navigate",
          "url": "https://myapp.com",
          "narration": "Welcome to our product!",
          "effects": [{ "type": "spotlight", "duration": 2.0 }]
        },
        {
          "action": "click",
          "locator": { "type": "css", "value": "#get-started" },
          "narration": "Click to get started.",
          "effects": [{ "type": "confetti", "duration": 1.5 }]
        }
      ]
    }
  ],
  "pipeline": [
    { "generate_narration": {} },
    { "edit_video": {} },
    { "mix_audio": {} },
    { "optimize": { "format": "mp4", "codec": "h264" } }
  ],
  "output": {
    "filename": "demo.mp4",
    "formats": ["mp4", "webm", "gif"]
  }
}`;

const tabs = [
  { id: "yaml" as const, label: "YAML", file: "demo.yaml", code: yamlExample },
  { id: "json" as const, label: "JSON", file: "demo.json", code: jsonExample },
];

export function CodeExample() {
  const [active, setActive] = useState<"yaml" | "json">("yaml");
  const tab = tabs.find((t) => t.id === active)!;

  return (
    <section className="px-6 py-20 bg-zinc-950/50">
      <div className="mx-auto max-w-4xl">
        <h2 className="text-3xl font-bold text-center mb-4">
          Declarative by design
        </h2>
        <p className="text-center text-zinc-400 mb-10 max-w-2xl mx-auto">
          Your entire demo is defined in a single YAML or JSON file. No scripts, no
          code — just declare what you want.
        </p>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-950/50">
            <div className="h-3 w-3 rounded-full bg-red-500/80" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
            <div className="h-3 w-3 rounded-full bg-green-500/80" />
            <div className="ml-auto flex gap-1">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActive(t.id)}
                  className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                    active === t.id
                      ? "bg-indigo-600 text-white"
                      : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <pre className="p-6 overflow-x-auto text-sm leading-relaxed">
            <code className="text-zinc-300 font-mono">{tab.code}</code>
          </pre>
        </div>

        <p className="text-center text-zinc-500 mt-6 text-sm">
          Then run:{" "}
          <code className="text-indigo-400 bg-zinc-800 px-2 py-1 rounded">
            demodsl run {tab.file}
          </code>
        </p>
      </div>
    </section>
  );
}
