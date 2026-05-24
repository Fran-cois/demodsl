// Self-contained React component for demodsl ReactLayer smoke test.
// Pure CSS-in-JS, no external CSS needed.

import React from "react";

type Props = {
  title?: string;
  subtitle?: string;
  rating?: number;
  bg?: string;
  accent?: string;
};

export default function GlassCard({
  title = "DemoDSL",
  subtitle = "Demos as code.",
  rating = 5,
  bg = "#0F172A",
  accent = "#6366F1",
}: Props) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily:
          '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <div
        style={{
          padding: "32px 40px",
          borderRadius: "24px",
          background: `linear-gradient(135deg, ${bg}cc, ${bg}99)`,
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          border: `1px solid ${accent}33`,
          boxShadow: `0 20px 60px ${accent}40, inset 0 1px 0 #ffffff22`,
          color: "white",
          textAlign: "center",
          minWidth: "320px",
        }}
      >
        <div
          style={{
            fontSize: "12px",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: accent,
            marginBottom: "10px",
            fontWeight: 600,
          }}
        >
          ★ Featured
        </div>
        <div
          style={{
            fontSize: "44px",
            fontWeight: 800,
            letterSpacing: "-0.02em",
            background: `linear-gradient(90deg, #fff, ${accent})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            color: "transparent",
            lineHeight: 1.1,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: "16px",
            color: "#cbd5e1",
            marginTop: "8px",
          }}
        >
          {subtitle}
        </div>
        <div
          style={{
            marginTop: "20px",
            display: "flex",
            justifyContent: "center",
            gap: "4px",
            fontSize: "20px",
            color: "#F59E0B",
          }}
        >
          {Array.from({ length: 5 }).map((_, i) => (
            <span key={i} style={{ opacity: i < rating ? 1 : 0.25 }}>
              ★
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
