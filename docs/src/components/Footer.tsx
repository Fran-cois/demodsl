export function Footer() {
  return (
    <footer className="border-t border-zinc-800 px-6 py-12 mt-20">
      <div className="mx-auto max-w-6xl flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="font-bold">
            Demo<span className="text-indigo-400">DSL</span>
          </span>
          <span className="text-zinc-600 text-sm">v2.0.0</span>
        </div>

        <div className="flex items-center gap-6 text-sm text-zinc-500">
          <a
            href="https://pypi.org/project/demodsl/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            PyPI
          </a>
          <a
            href="https://github.com/Fran-cois/demodsl"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            GitHub
          </a>
          <a
            href="https://github.com/Fran-cois/demodsl/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            Issues
          </a>
        </div>

        <p className="text-xs text-zinc-600">MIT License</p>
      </div>
    </footer>
  );
}
