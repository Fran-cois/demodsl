import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DemoDSL — Automated Product Demo Videos from YAML",
  description:
    "Define product demos in YAML. DemoDSL handles browser automation, voice narration, visual effects, video editing, and multi-format export.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
