import type { Metadata } from "next";
import { Navbar } from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "DemoDSL — Automated Product Demo Videos from YAML & JSON",
  description:
    "Define product demos in YAML or JSON. DemoDSL handles browser automation, voice narration, visual effects, video editing, and multi-format export.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Navbar />
        <div className="border-b border-zinc-800 bg-indigo-950/20 px-6 py-3 text-center text-sm text-zinc-400">
          DemoDSL powers DemoBro, a hosted service for personalized product demo videos.{" "}
          <a
            href="https://demobro.com/"
            className="font-medium text-indigo-300 underline underline-offset-4 hover:text-indigo-200"
          >
            Try DemoBro →
          </a>
        </div>
        {children}
      </body>
    </html>
  );
}
