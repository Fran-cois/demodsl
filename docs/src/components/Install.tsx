export function Install() {
  return (
    <section id="install" className="px-6 py-16">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-2xl font-bold text-center mb-8">Quick Start</h2>
        <div className="space-y-4">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <p className="text-sm text-zinc-500 mb-2">Install from PyPI</p>
            <pre className="text-green-400 font-mono text-sm">
              <code>pip install demodsl</code>
            </pre>
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <p className="text-sm text-zinc-500 mb-2">Install browser engine</p>
            <pre className="text-green-400 font-mono text-sm">
              <code>playwright install chromium</code>
            </pre>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-center">
              <p className="text-sm text-zinc-500 mb-1">YAML template</p>
              <code className="font-mono text-sm text-indigo-400">
                demodsl init
              </code>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-center">
              <p className="text-sm text-zinc-500 mb-1">JSON template</p>
              <code className="font-mono text-sm text-indigo-400">
                demodsl init -o demo.json
              </code>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-center">
              <p className="text-sm text-zinc-500 mb-1">Validate config</p>
              <code className="font-mono text-sm text-indigo-400">
                demodsl validate demo.yaml
              </code>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-center">
              <p className="text-sm text-zinc-500 mb-1">Run demo</p>
              <code className="font-mono text-sm text-indigo-400">
                demodsl run demo.yaml
              </code>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
