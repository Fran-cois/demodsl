"use client";

import { useState } from "react";

const renderers = [
  {
    id: "moviepy" as const,
    label: "MoviePy (default)",
    icon: "🎬",
    description:
      "Python-native rendering via MoviePy + FFmpeg. Zero extra dependencies, fast for simple compositions.",
    pros: ["No Node.js required", "Fast for simple demos", "Proven & stable"],
    pipeline: `pipeline:
  - generate_narration: {}
  - edit_video: {}
  - burn_subtitles: {}
  - mix_audio: {}
  - optimize:
      format: "mp4"`,
    command: "demodsl run demo.yaml",
  },
  {
    id: "remotion" as const,
    label: "Remotion",
    icon: "⚛️",
    description:
      "React-based video composition via Remotion. Declarative effects, transitions & overlays rendered in a single pass.",
    pros: [
      "Single-pass rendering (effects + avatars + subtitles)",
      "React components for each effect",
      "Interactive preview via remotion preview",
    ],
    pipeline: `pipeline:
  - generate_narration: {}
  - edit_video: {}
  - burn_subtitles: {}
  - mix_audio: {}
  - optimize:
      format: "mp4"`,
    command: "demodsl run demo.yaml --renderer remotion",
  },
];

const comparison = [
  {
    feature: "Intro / Outro",
    moviepy: "ColorClip + TextClip → concatenate",
    remotion: "<IntroSlide> / <OutroSlide> React components",
  },
  {
    feature: "Post-effects (ken_burns, zoom…)",
    moviepy: "Frame-by-frame NumPy callbacks",
    remotion: "CSS transforms + interpolate()",
  },
  {
    feature: "Transitions",
    moviepy: "MoviePy crossfade",
    remotion: "@remotion/transitions",
  },
  {
    feature: "Avatar overlay",
    moviepy: "FFmpeg filter_complex subprocess",
    remotion: "<AvatarOverlay> component",
  },
  {
    feature: "Subtitles",
    moviepy: "FFmpeg drawtext / ASS",
    remotion: "<SubtitleOverlay> with CSS styling",
  },
  {
    feature: "Watermark",
    moviepy: "MoviePy ImageClip composite",
    remotion: "<WatermarkOverlay> with <Img>",
  },
  {
    feature: "Preview",
    moviepy: "—",
    remotion: "npx remotion preview (interactive)",
  },
];

const setupSteps = [
  {
    step: "1",
    label: "Install Node.js ≥ 18",
    code: "brew install node",
  },
  {
    step: "2",
    label: "Install Remotion deps",
    code: "demodsl setup-remotion",
  },
  {
    step: "3",
    label: "Run with Remotion",
    code: "demodsl run demo.yaml --renderer remotion",
  },
];

const effectComponents = [
  { name: "ken_burns", component: "EffectLayer → scale + translate", type: "camera" },
  { name: "zoom_pulse", component: "EffectLayer → sin(π) scale", type: "camera" },
  { name: "drone_zoom", component: "EffectLayer → ease-in-out scale", type: "camera" },
  { name: "camera_shake", component: "EffectLayer → sin/cos offset", type: "camera" },
  { name: "elastic_zoom", component: "EffectLayer → ease-out-back", type: "camera" },
  { name: "zoom_to", component: "EffectLayer → ease-out cubic", type: "camera" },
  { name: "parallax", component: "EffectLayer → depth scale", type: "camera" },
  { name: "vignette", component: "radial-gradient overlay", type: "cinematic" },
  { name: "letterbox", component: "Black bar divs", type: "cinematic" },
  { name: "glitch", component: "Random translateX flicker", type: "stylized" },
  { name: "film_grain", component: "SVG noise overlay", type: "cinematic" },
];

export function RemotionSection() {
  const [activeRenderer, setActiveRenderer] = useState<"moviepy" | "remotion">(
    "remotion"
  );
  const renderer = renderers.find((r) => r.id === activeRenderer)!;

  return (
    <section id="remotion" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="text-center mb-12">
          <span className="inline-block text-xs font-medium text-indigo-400 bg-indigo-950 px-3 py-1 rounded-full mb-4">
            NEW
          </span>
          <h2 className="text-3xl font-bold mb-4">
            Remotion Renderer
          </h2>
          <p className="text-zinc-400 max-w-2xl mx-auto">
            Choose between the classic MoviePy pipeline or the new Remotion engine.
            Same YAML config, same CLI — just add{" "}
            <code className="text-indigo-400 bg-zinc-800 px-1.5 py-0.5 rounded text-sm">
              --renderer remotion
            </code>
          </p>
        </div>

        {/* Renderer toggle cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-12">
          {renderers.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveRenderer(r.id)}
              className={`rounded-xl border p-6 text-left transition-all ${
                activeRenderer === r.id
                  ? "border-indigo-600 bg-indigo-950/30 shadow-lg shadow-indigo-950/20"
                  : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700"
              }`}
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-2xl">{r.icon}</span>
                <h3 className="text-lg font-semibold">{r.label}</h3>
                {activeRenderer === r.id && (
                  <span className="ml-auto text-xs text-indigo-400 bg-indigo-950 px-2 py-0.5 rounded">
                    selected
                  </span>
                )}
              </div>
              <p className="text-sm text-zinc-400 mb-4">{r.description}</p>
              <ul className="space-y-1">
                {r.pros.map((p) => (
                  <li key={p} className="text-xs text-zinc-500 flex items-center gap-2">
                    <span className="text-green-500">✓</span> {p}
                  </li>
                ))}
              </ul>
            </button>
          ))}
        </div>

        {/* Command + config side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-12">
          {/* Command */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
            <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-950/50 flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
              <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
              <div className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
              <span className="ml-2 text-xs text-zinc-500 font-mono">
                terminal
              </span>
            </div>
            <pre className="p-5 text-sm">
              <code className="text-green-400 font-mono">
                $ {renderer.command}
              </code>
            </pre>
          </div>

          {/* Pipeline config */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
            <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-950/50">
              <span className="text-xs text-zinc-500 font-mono">
                pipeline config (same for both)
              </span>
            </div>
            <pre className="p-5 overflow-x-auto text-sm leading-relaxed">
              <code className="text-zinc-300 font-mono">
                {renderer.pipeline}
              </code>
            </pre>
          </div>
        </div>

        {/* Setup steps */}
        <h3 className="text-xl font-bold text-center mb-6">
          Remotion Setup
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-16">
          {setupSteps.map((s) => (
            <div
              key={s.step}
              className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5"
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="w-6 h-6 flex items-center justify-center rounded-full bg-indigo-950 text-indigo-400 text-xs font-bold">
                  {s.step}
                </span>
                <span className="text-sm text-zinc-400">{s.label}</span>
              </div>
              <code className="font-mono text-sm text-green-400">{s.code}</code>
            </div>
          ))}
        </div>

        {/* Comparison table */}
        <h3 className="text-xl font-bold text-center mb-6">
          MoviePy vs Remotion — Feature Comparison
        </h3>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden mb-16">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-950/50">
                  <th className="text-left px-5 py-3 text-zinc-400 font-medium">
                    Feature
                  </th>
                  <th className="text-left px-5 py-3 text-zinc-400 font-medium">
                    🎬 MoviePy
                  </th>
                  <th className="text-left px-5 py-3 text-zinc-400 font-medium">
                    ⚛️ Remotion
                  </th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((row) => (
                  <tr
                    key={row.feature}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/20"
                  >
                    <td className="px-5 py-3 font-medium text-zinc-300">
                      {row.feature}
                    </td>
                    <td className="px-5 py-3 text-zinc-500 font-mono text-xs">
                      {row.moviepy}
                    </td>
                    <td className="px-5 py-3 text-indigo-400 font-mono text-xs">
                      {row.remotion}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Effect components grid */}
        <h3 className="text-xl font-bold text-center mb-6">
          Remotion Effect Components
        </h3>
        <p className="text-center text-zinc-400 mb-8 text-sm max-w-xl mx-auto">
          Each post-effect is implemented as a React component using Remotion&apos;s{" "}
          <code className="text-indigo-400 bg-zinc-800 px-1 py-0.5 rounded text-xs">
            interpolate()
          </code>{" "}
          and CSS transforms.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {effectComponents.map((eff) => (
            <div
              key={eff.name}
              className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3"
            >
              <code className="font-mono text-sm text-zinc-300 shrink-0">
                {eff.name}
              </code>
              <span className="text-xs text-zinc-500 truncate">
                {eff.component}
              </span>
              <span
                className={`ml-auto text-xs px-2 py-0.5 rounded shrink-0 ${
                  eff.type === "camera"
                    ? "bg-blue-950 text-blue-400"
                    : eff.type === "cinematic"
                      ? "bg-amber-950 text-amber-400"
                      : "bg-purple-950 text-purple-400"
                }`}
              >
                {eff.type}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
