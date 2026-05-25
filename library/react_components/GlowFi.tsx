// GlowFi — sophisticated skeuomorphism (a.k.a. "Glow-Fi"):
// tactile materials (brushed metal, frosted glass, soft inner shadows),
// volumetric depth, ambient neon light leaks, fine bezels and pin lights.
//
// Designed for DemoDSL ReactLayer (mode: animated). Pure React.createElement
// so the bundle stays small. No emoji glyphs.

import React from "react";
const h = React.createElement;

type Track = { title: string; artist: string; duration: string };

type Props = {
  device?: string;
  track?: Track;
  hue?: number; // primary accent hue (cyan ~190, magenta ~310, lime ~120)
  level?: number; // 0..1 progress of the playhead
};

const DEFAULT_TRACK: Track = {
  title: "Lucid Drift",
  artist: "Neon Forest",
  duration: "03:42",
};

export default function GlowFi({
  device = "AURORA",
  track = DEFAULT_TRACK,
  hue = 195,
  level = 0.42,
}: Props) {
  const accent = `hsl(${hue}, 95%, 60%)`;
  const accent2 = `hsl(${(hue + 60) % 360}, 90%, 65%)`;
  const accentDim = `hsla(${hue}, 90%, 60%, 0.35)`;
  const accentFaint = `hsla(${hue}, 90%, 60%, 0.10)`;

  // 21 EQ bars staggered around a sine envelope
  const bars = Array.from({ length: 21 });

  return h(
    React.Fragment,
    null,
    h(
      "style",
      null,
      `
        @keyframes gf-knob   { from { transform: rotate(-130deg);} to { transform: rotate(130deg);} }
        @keyframes gf-knob-bg { from { transform: rotate(0deg);} to { transform: rotate(360deg);} }
        @keyframes gf-pulse  { 0%,100%{box-shadow:0 0 12px ${accent},0 0 24px ${accentDim};} 50%{box-shadow:0 0 24px ${accent},0 0 60px ${accentDim};} }
        @keyframes gf-eq     { 0%,100%{transform: scaleY(0.25);} 50%{transform: scaleY(1);} }
        @keyframes gf-aurora { 0%{transform:translate(-8%,-4%) scale(1);} 50%{transform:translate(6%,4%) scale(1.08);} 100%{transform:translate(-8%,-4%) scale(1);} }
        @keyframes gf-bezel  { 0%,100%{opacity:0.45;} 50%{opacity:0.85;} }
        @keyframes gf-needle { 0%{left:0%;} 100%{left:100%;} }
        @keyframes gf-led    { 0%,100%{opacity:0.35;} 50%{opacity:1;} }
      `,
    ),

    h(
      "div",
      {
        style: {
          width: "100%",
          height: "100%",
          position: "relative",
          background:
            "radial-gradient(120% 80% at 50% 0%, #1B2230 0%, #0A0E16 55%, #05070C 100%)",
          fontFamily: '"Inter", -apple-system, "SF Pro Text", sans-serif',
          color: "#E6EAF2",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 28,
          boxSizing: "border-box",
        },
      },

      // Ambient aurora behind everything
      h("div", {
        style: {
          position: "absolute",
          inset: -120,
          background: `radial-gradient(40% 30% at 30% 25%, ${accent}66, transparent 70%), radial-gradient(45% 35% at 75% 70%, ${accent2}55, transparent 70%)`,
          filter: "blur(40px)",
          animation: "gf-aurora 9s ease-in-out infinite",
          pointerEvents: "none",
        },
      }),

      // Faint vertical grain bezel pattern at edges
      h("div", {
        style: {
          position: "absolute",
          inset: 0,
          background:
            "repeating-linear-gradient(180deg, rgba(255,255,255,0.025) 0 1px, transparent 1px 4px)",
          pointerEvents: "none",
        },
      }),

      // ============== The device card ==============
      h(
        "div",
        {
          style: {
            position: "relative",
            width: 880,
            maxWidth: "100%",
            borderRadius: 36,
            padding: 28,
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015) 40%, rgba(0,0,0,0.35))",
            backdropFilter: "blur(28px) saturate(130%)",
            WebkitBackdropFilter: "blur(28px) saturate(130%)",
            border: "1px solid rgba(255,255,255,0.12)",
            boxShadow: [
              "inset 0 1px 0 rgba(255,255,255,0.22)",
              "inset 0 -1px 0 rgba(0,0,0,0.55)",
              "0 30px 80px rgba(0,0,0,0.55)",
              `0 0 80px ${accentFaint}`,
            ].join(", "),
          },
        },

        // Top bar: brand + device + status LED
        h(
          "div",
          {
            style: {
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 18,
              fontSize: 12,
              letterSpacing: "0.32em",
              color: "rgba(230,234,242,0.7)",
            },
          },
          h("div", null, "DEMODSL  \u2022  HIFI"),
          h(
            "div",
            {
              style: { display: "flex", alignItems: "center", gap: 8 },
            },
            h("div", {
              style: {
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: accent,
                boxShadow: `0 0 8px ${accent}`,
                animation: "gf-led 1.6s ease-in-out infinite",
              },
            }),
            h("div", null, device),
          ),
        ),

        // Main row: knob + display
        h(
          "div",
          { style: { display: "flex", gap: 24, alignItems: "stretch" } },

          // ====== Knob ======
          h(
            "div",
            {
              style: {
                position: "relative",
                width: 240,
                height: 240,
                flexShrink: 0,
              },
            },
            // Outer ring with rotating accent gradient
            h("div", {
              style: {
                position: "absolute",
                inset: 0,
                borderRadius: "50%",
                background: `conic-gradient(from 0deg, ${accent}, ${accent2}, transparent 60%, ${accent})`,
                filter: "blur(2px)",
                opacity: 0.85,
                animation: "gf-knob-bg 14s linear infinite",
              },
            }),
            // Bezel
            h("div", {
              style: {
                position: "absolute",
                inset: 8,
                borderRadius: "50%",
                background:
                  "radial-gradient(circle at 30% 25%, #2B3340 0%, #11151D 70%)",
                boxShadow: [
                  "inset 0 2px 4px rgba(255,255,255,0.18)",
                  "inset 0 -4px 10px rgba(0,0,0,0.85)",
                  "0 12px 30px rgba(0,0,0,0.6)",
                ].join(", "),
              },
            }),
            // Brushed metal cap
            h("div", {
              style: {
                position: "absolute",
                inset: 28,
                borderRadius: "50%",
                background:
                  "repeating-conic-gradient(from 0deg, #3C4554 0deg 2deg, #2A3140 2deg 4deg)",
                boxShadow:
                  "inset 0 2px 6px rgba(255,255,255,0.18), inset 0 -6px 14px rgba(0,0,0,0.7)",
              },
            }),
            // Tick marks
            h(
              "div",
              {
                style: {
                  position: "absolute",
                  inset: 0,
                  pointerEvents: "none",
                },
              },
              Array.from({ length: 11 }).map((_, i) => {
                const a = -130 + (i * 260) / 10;
                return h("div", {
                  key: i,
                  style: {
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    width: 3,
                    height: 12,
                    background:
                      i % 5 === 0 ? accent : "rgba(230,234,242,0.45)",
                    boxShadow: i % 5 === 0 ? `0 0 8px ${accent}` : "none",
                    borderRadius: 2,
                    transform: `rotate(${a}deg) translate(0, -116px)`,
                    transformOrigin: "center top",
                  },
                });
              }),
            ),
            // Knob pointer (animated sweep)
            h(
              "div",
              {
                style: {
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  justifyContent: "center",
                  animation: "gf-knob 4.2s ease-in-out infinite alternate",
                  transformOrigin: "center",
                },
              },
              h("div", {
                style: {
                  width: 6,
                  height: 70,
                  marginTop: 30,
                  background: accent,
                  borderRadius: 3,
                  boxShadow: `0 0 12px ${accent}, 0 0 28px ${accentDim}`,
                  animation: "gf-pulse 2.4s ease-in-out infinite",
                },
              }),
            ),
            // Center jewel
            h("div", {
              style: {
                position: "absolute",
                top: "50%",
                left: "50%",
                width: 36,
                height: 36,
                marginTop: -18,
                marginLeft: -18,
                borderRadius: "50%",
                background: `radial-gradient(circle at 35% 30%, #ffffff 0%, ${accent} 40%, #0A1118 90%)`,
                boxShadow: `inset 0 -3px 6px rgba(0,0,0,0.6), 0 0 16px ${accent}`,
              },
            }),
          ),

          // ====== Display ======
          h(
            "div",
            {
              style: {
                flex: 1,
                position: "relative",
                borderRadius: 22,
                padding: "20px 22px",
                background:
                  "linear-gradient(180deg, #060A12 0%, #0B121C 100%)",
                border: "1px solid rgba(255,255,255,0.06)",
                boxShadow: [
                  "inset 0 2px 8px rgba(0,0,0,0.85)",
                  "inset 0 -1px 0 rgba(255,255,255,0.05)",
                  `inset 0 0 60px ${accentFaint}`,
                ].join(", "),
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                overflow: "hidden",
              },
            },
            // Scanline veneer
            h("div", {
              style: {
                position: "absolute",
                inset: 0,
                background:
                  "repeating-linear-gradient(0deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 3px)",
                pointerEvents: "none",
              },
            }),

            // Now playing
            h(
              "div",
              null,
              h(
                "div",
                {
                  style: {
                    fontSize: 11,
                    letterSpacing: "0.34em",
                    color: accent,
                    textShadow: `0 0 10px ${accentDim}`,
                  },
                },
                "NOW PLAYING",
              ),
              h(
                "div",
                {
                  style: {
                    marginTop: 8,
                    fontSize: 28,
                    fontWeight: 700,
                    letterSpacing: "-0.01em",
                    background: `linear-gradient(180deg, #ffffff, ${accent})`,
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  },
                },
                track.title,
              ),
              h(
                "div",
                {
                  style: {
                    fontSize: 14,
                    color: "rgba(230,234,242,0.7)",
                    letterSpacing: "0.04em",
                  },
                },
                track.artist,
              ),
            ),

            // EQ visualizer
            h(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "flex-end",
                  justifyContent: "space-between",
                  height: 60,
                  margin: "16px 0 10px",
                  gap: 4,
                },
              },
              bars.map((_, i) => {
                const env = Math.sin((i / (bars.length - 1)) * Math.PI);
                const dur = 0.6 + ((i * 137) % 7) * 0.12;
                const delay = ((i * 53) % 11) * 0.06;
                return h("div", {
                  key: i,
                  style: {
                    flex: 1,
                    height: `${20 + env * 80}%`,
                    background: `linear-gradient(180deg, ${accent2}, ${accent})`,
                    borderRadius: 3,
                    transformOrigin: "bottom",
                    boxShadow: `0 0 6px ${accentDim}`,
                    animation: `gf-eq ${dur}s ease-in-out ${delay}s infinite`,
                  },
                });
              }),
            ),

            // Progress bar
            h(
              "div",
              {
                style: {
                  position: "relative",
                  height: 6,
                  borderRadius: 3,
                  background: "rgba(255,255,255,0.07)",
                  overflow: "hidden",
                  marginTop: 8,
                },
              },
              h("div", {
                style: {
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  left: 0,
                  width: `${Math.round(level * 100)}%`,
                  background: `linear-gradient(90deg, ${accent}, ${accent2})`,
                  boxShadow: `0 0 12px ${accent}`,
                },
              }),
              h("div", {
                style: {
                  position: "absolute",
                  top: -3,
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: "#ffffff",
                  boxShadow: `0 0 12px ${accent}, 0 0 24px ${accentDim}`,
                  animation: "gf-needle 12s linear infinite",
                  marginLeft: -6,
                },
              }),
            ),

            // Time row
            h(
              "div",
              {
                style: {
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11,
                  letterSpacing: "0.18em",
                  color: "rgba(230,234,242,0.55)",
                  marginTop: 6,
                  fontVariantNumeric: "tabular-nums",
                },
              },
              h("div", null, "01:33"),
              h("div", null, track.duration),
            ),
          ),
        ),

        // Bottom transport row
        h(
          "div",
          {
            style: {
              display: "flex",
              justifyContent: "center",
              gap: 18,
              marginTop: 22,
            },
          },
          ["prev", "play", "next"].map((kind) => {
            const isPlay = kind === "play";
            return h(
              "div",
              {
                key: kind,
                style: {
                  width: isPlay ? 76 : 56,
                  height: isPlay ? 76 : 56,
                  borderRadius: "50%",
                  background: isPlay
                    ? `linear-gradient(180deg, ${accent2}, ${accent})`
                    : "linear-gradient(180deg, #2A3140, #161B25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "1px solid rgba(255,255,255,0.12)",
                  boxShadow: isPlay
                    ? `inset 0 2px 4px rgba(255,255,255,0.4), inset 0 -3px 8px rgba(0,0,0,0.4), 0 10px 26px ${accentDim}, 0 0 30px ${accent}`
                    : "inset 0 2px 4px rgba(255,255,255,0.18), inset 0 -3px 8px rgba(0,0,0,0.8), 0 6px 14px rgba(0,0,0,0.6)",
                  animation: isPlay
                    ? "gf-pulse 2.2s ease-in-out infinite"
                    : undefined,
                },
              },
              // Glyph
              h(
                "svg",
                {
                  width: isPlay ? 26 : 18,
                  height: isPlay ? 26 : 18,
                  viewBox: "0 0 24 24",
                  fill: isPlay ? "#0A0E16" : "rgba(230,234,242,0.85)",
                },
                kind === "prev"
                  ? h("path", { d: "M6 5h2v14H6V5zm14 0v14L9 12 20 5z" })
                  : kind === "next"
                    ? h("path", { d: "M16 5h2v14h-2V5zM4 5l11 7L4 19V5z" })
                    : h("path", { d: "M7 5l13 7L7 19V5z" }),
              ),
            );
          }),
        ),

        // Footer bezel info line
        h(
          "div",
          {
            style: {
              display: "flex",
              justifyContent: "space-between",
              marginTop: 18,
              fontSize: 10,
              letterSpacing: "0.4em",
              color: "rgba(230,234,242,0.45)",
              animation: "gf-bezel 4s ease-in-out infinite",
            },
          },
          h("div", null, "24 BIT  /  192 kHz"),
          h("div", null, "SERIAL  04 \u2022 1914 \u2022 GF"),
        ),
      ),
    ),
  );
}
