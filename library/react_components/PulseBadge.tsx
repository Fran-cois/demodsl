// Animated React component for ReactLayer (mode: animated) smoke test.
// Animates a pulsing circular badge using CSS keyframes (no JS animation
// needed — Playwright's wall-clock pacing captures one frame at a time).

import React from "react";

type Props = {
  label?: string;
  hue?: number;
};

export default function PulseBadge({ label = "LIVE", hue = 0 }: Props) {
  // Inject keyframes once via a <style> tag.
  return (
    <>
      <style>{`
        @keyframes demodsl-pulse {
          0%   { transform: scale(1);   box-shadow: 0 0 0 0 hsla(${hue}, 90%, 60%, 0.7); }
          70%  { transform: scale(1.15); box-shadow: 0 0 0 40px hsla(${hue}, 90%, 60%, 0); }
          100% { transform: scale(1);   box-shadow: 0 0 0 0 hsla(${hue}, 90%, 60%, 0); }
        }
        @keyframes demodsl-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: '"Inter", -apple-system, sans-serif',
        }}
      >
        <div
          style={{
            position: "relative",
            width: 200,
            height: 200,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              border: `3px dashed hsla(${hue}, 90%, 60%, 0.6)`,
              animation: "demodsl-spin 4s linear infinite",
            }}
          />
          <div
            style={{
              width: 140,
              height: 140,
              borderRadius: "50%",
              background: `linear-gradient(135deg, hsl(${hue}, 90%, 55%), hsl(${(hue + 40) % 360}, 90%, 65%))`,
              color: "white",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 26,
              fontWeight: 800,
              letterSpacing: "0.05em",
              animation: "demodsl-pulse 1.6s ease-out infinite",
            }}
          >
            {label}
          </div>
        </div>
      </div>
    </>
  );
}
