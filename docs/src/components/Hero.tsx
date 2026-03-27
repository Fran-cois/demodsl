export function Hero() {
  return (
    <section className="relative overflow-hidden px-6 py-24 sm:py-32 lg:py-40">
      {/* Gradient background */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-indigo-950/40 to-transparent" />
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 h-[600px] w-[600px] rounded-full bg-indigo-600/10 blur-3xl" />
      </div>

      <div className="mx-auto max-w-4xl text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-4 py-1.5 text-sm text-zinc-400">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          v2.0.0 — Now available on PyPI
        </div>

        <h1 className="text-5xl font-bold tracking-tight sm:text-7xl">
          <span className="text-white">Demo</span>
          <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
            DSL
          </span>
        </h1>

        <p className="mt-6 text-lg leading-8 text-zinc-400 sm:text-xl max-w-2xl mx-auto">
          Define product demos in{" "}
          <span className="text-white font-medium">YAML</span>. Browser
          automation, voice narration, visual effects, video editing — all
          from a single config file.
        </p>

        <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
          <a
            href="#install"
            className="rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 hover:bg-indigo-500 transition-colors"
          >
            Get Started
          </a>
          <a
            href="https://github.com/Fran-cois/demodsl"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-6 py-3 text-sm font-semibold text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
          >
            GitHub →
          </a>
        </div>
      </div>
    </section>
  );
}
