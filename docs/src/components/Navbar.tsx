"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home" },
  { href: "/docs", label: "Documentation" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto max-w-6xl flex items-center justify-between px-6 py-3">
        <Link href="/" className="font-bold text-lg">
          Demo<span className="text-indigo-400">DSL</span>
        </Link>
        <div className="flex items-center gap-6">
          {links.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`text-sm transition-colors ${
                  active
                    ? "text-white font-medium"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
          <Link
            href="/#remotion"
            scroll
            className="text-sm text-zinc-400 hover:text-white transition-colors"
            onClick={(e) => {
              if (pathname === "/") {
                e.preventDefault();
                document.getElementById("remotion")?.scrollIntoView({ behavior: "smooth" });
              }
            }}
          >
            Remotion
          </Link>
          <a
            href="https://pypi.org/project/demodsl/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-zinc-400 hover:text-white transition-colors"
          >
            PyPI
          </a>
          <a
            href="https://github.com/Fran-cois/demodsl"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-zinc-400 hover:text-white transition-colors"
          >
            GitHub
          </a>
        </div>
      </div>
    </nav>
  );
}
