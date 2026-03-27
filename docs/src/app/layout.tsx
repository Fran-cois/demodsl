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
        {children}
      </body>
    </html>
  );
}
