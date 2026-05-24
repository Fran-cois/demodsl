// Animated React ad component for ReactLayer.
// Self-contained: pure React.createElement (no JSX) + a small keyframes
// style block. Designed to sit on top of a fractal-noise background.

import React from "react";

type Chip = { label: string; tone?: string };
type Props = {
  brand?: string;
  headline?: string;
  subhead?: string;
  cta?: string;
  price?: string;
  chips?: Chip[];
  accent?: string;
};

const KEYFRAMES = `
@keyframes adhero-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
@keyframes adhero-pulse {
  0%,100%{ box-shadow: 0 12px 40px rgba(168,85,247,0.45), 0 0 0 0 rgba(168,85,247,0.55); }
  50%    { box-shadow: 0 18px 60px rgba(168,85,247,0.75), 0 0 0 18px rgba(168,85,247,0); }
}
@keyframes adhero-fade { from{opacity:0; transform:translateY(20px)} to{opacity:1; transform:translateY(0)} }
@keyframes adhero-pop  { 0%{transform:scale(.6) rotate(-12deg); opacity:0} 60%{transform:scale(1.15) rotate(-12deg); opacity:1} 100%{transform:scale(1) rotate(-12deg); opacity:1} }
`;

const DEFAULT_CHIPS: Chip[] = [
  { label: "Fast", tone: "#22D3EE" },
  { label: "Beautiful", tone: "#F472B6" },
  { label: "Open source", tone: "#A3E635" },
];

export default function AdHero(props: Props) {
  const {
    brand = "DEMODSL",
    headline = "Demos as code.",
    subhead = "Ship product videos from a YAML file.",
    cta = "Try it free",
    price = "$0",
    chips = DEFAULT_CHIPS,
    accent = "#A855F7",
  } = props;

  const h = React.createElement;

  return h(
    "div",
    {
      style: {
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily:
          '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        color: "white",
        padding: "60px",
        boxSizing: "border-box",
      },
    },
    h("style", null, KEYFRAMES),
    h(
      "div",
      {
        style: {
          position: "relative",
          width: "100%",
          maxWidth: 980,
          padding: "56px 64px",
          borderRadius: 32,
          background:
            "linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,27,75,0.88))",
          border: `1px solid ${accent}55`,
          boxShadow:
            "0 30px 90px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.12)",
        },
      },
      h(
        "div",
        {
          style: {
            position: "absolute",
            top: -32,
            right: -32,
            width: 130,
            height: 130,
            borderRadius: "50%",
            background: "radial-gradient(circle at 30% 30%, #FBBF24, #F59E0B)",
            color: "#1F2937",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 900,
            fontSize: 30,
            boxShadow: "0 12px 36px rgba(245,158,11,0.6)",
            animation: "adhero-pop 0.9s cubic-bezier(.34,1.56,.64,1) both",
          },
        },
        price,
      ),
      h(
        "div",
        {
          style: {
            fontSize: 13,
            letterSpacing: "0.32em",
            color: accent,
            fontWeight: 700,
            marginBottom: 16,
            animation: "adhero-fade 0.6s ease-out both",
          },
        },
        brand,
      ),
      h(
        "div",
        {
          style: {
            fontSize: 72,
            fontWeight: 900,
            lineHeight: 1.02,
            letterSpacing: "-0.03em",
            color: "white",
            marginBottom: 18,
            animation: "adhero-fade 0.8s ease-out 0.1s both",
          },
        },
        headline,
      ),
      h(
        "div",
        {
          style: {
            fontSize: 22,
            lineHeight: 1.4,
            color: "#CBD5E1",
            maxWidth: 720,
            marginBottom: 32,
            animation: "adhero-fade 0.8s ease-out 0.25s both",
          },
        },
        subhead,
      ),
      h(
        "div",
        {
          style: {
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            marginBottom: 40,
          },
        },
        chips.map((c, i) =>
          h(
            "div",
            {
              key: c.label,
              style: {
                padding: "10px 18px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.08)",
                border: `1px solid ${c.tone || accent}66`,
                color: c.tone || "#E5E7EB",
                fontSize: 16,
                fontWeight: 600,
                animation: `adhero-float ${3 + (i % 3) * 0.4}s ease-in-out infinite`,
                animationDelay: `${i * 0.2}s`,
              },
            },
            c.label,
          ),
        ),
      ),
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: 24 } },
        h(
          "button",
          {
            style: {
              border: "none",
              padding: "20px 36px",
              borderRadius: 16,
              background: `linear-gradient(135deg, ${accent}, #6366F1)`,
              color: "white",
              fontSize: 22,
              fontWeight: 800,
              cursor: "pointer",
              animation: "adhero-pulse 2.2s ease-in-out infinite",
            },
          },
          cta,
        ),
        h(
          "div",
          { style: { fontSize: 14, color: "#94A3B8" } },
          h(
            "div",
            { style: { color: "#E5E7EB", fontWeight: 600 } },
            "4.9 / 5",
          ),
          "Loved by 2,400+ devs",
        ),
      ),
    ),
  );
}
