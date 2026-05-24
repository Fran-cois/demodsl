// Vorticism — animated React component inspired by the British Vorticist
// art movement (Wyndham Lewis, 1914): sharp angular vectors, bold red /
// black / yellow / white geometric shards, machine-like rhythm.
//
// Pure SVG + CSS keyframes — no emoji, no images. Designed for the
// DemoDSL ReactLayer (mode: animated).

import React from "react";

type Props = {
  title?: string;
  subtitle?: string;
  year?: string;
  speed?: number; // global tempo multiplier (1.0 = baseline)
};

export default function Vorticism({
  title = "VORTICISM",
  subtitle = "MANIFESTO OF THE VORTEX",
  year = "1914",
  speed = 1.0,
}: Props) {
  const t = (s: number) => `${s / speed}s`;

  // Bold Vorticist palette
  const RED = "#D62828";
  const YELLOW = "#F1B400";
  const BLACK = "#0B0B0B";
  const BONE = "#F4EFE6";
  const STEEL = "#1F2A36";

  return (
    <>
      <style>{`
        @keyframes vort-spin       { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes vort-spin-rev   { from { transform: rotate(0deg); } to { transform: rotate(-360deg); } }
        @keyframes vort-shard-l    {
          0%, 100% { transform: translate(0,0) rotate(0deg); }
          50%      { transform: translate(-14px,8px) rotate(-3deg); }
        }
        @keyframes vort-shard-r    {
          0%, 100% { transform: translate(0,0) rotate(0deg); }
          50%      { transform: translate(16px,-10px) rotate(4deg); }
        }
        @keyframes vort-stamp {
          0%   { transform: scale(0.6) rotate(-12deg); opacity: 0; }
          60%  { transform: scale(1.08) rotate(-8deg); opacity: 1; }
          100% { transform: scale(1) rotate(-8deg);   opacity: 1; }
        }
        @keyframes vort-strike {
          0%   { stroke-dashoffset: 1200; }
          100% { stroke-dashoffset: 0; }
        }
        @keyframes vort-bar {
          0%, 100% { transform: scaleX(1); }
          50%      { transform: scaleX(1.15); }
        }
        @keyframes vort-flicker {
          0%, 100% { opacity: 1; }
          47%, 53% { opacity: 0.55; }
        }
      `}</style>

      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          background: BONE,
          overflow: "hidden",
          fontFamily: '"Helvetica Neue", Inter, sans-serif',
          color: BLACK,
        }}
      >
        {/* Mechanical gear silhouette behind everything */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: 760,
            height: 760,
            marginTop: -380,
            marginLeft: -380,
            animation: `vort-spin ${t(28)} linear infinite`,
          }}
        >
          <svg viewBox="-100 -100 200 200" width="100%" height="100%">
            {Array.from({ length: 16 }).map((_, i) => {
              const a = (i * 360) / 16;
              return (
                <rect
                  key={i}
                  x="-6"
                  y="-94"
                  width="12"
                  height="22"
                  fill={STEEL}
                  transform={`rotate(${a})`}
                />
              );
            })}
            <circle cx="0" cy="0" r="72" fill="none" stroke={STEEL} strokeWidth="6" />
            <circle cx="0" cy="0" r="34" fill={STEEL} />
          </svg>
        </div>

        {/* Counter-rotating ring of red triangles */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: 620,
            height: 620,
            marginTop: -310,
            marginLeft: -310,
            animation: `vort-spin-rev ${t(18)} linear infinite`,
          }}
        >
          <svg viewBox="-100 -100 200 200" width="100%" height="100%">
            {Array.from({ length: 8 }).map((_, i) => {
              const a = (i * 360) / 8;
              return (
                <polygon
                  key={i}
                  points="-10,-92 10,-92 0,-66"
                  fill={i % 2 === 0 ? RED : BLACK}
                  transform={`rotate(${a})`}
                />
              );
            })}
          </svg>
        </div>

        {/* Central vortex — stacked angular shards */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: 520,
            height: 520,
            marginTop: -260,
            marginLeft: -260,
          }}
        >
          <svg viewBox="0 0 520 520" width="100%" height="100%">
            {/* Big yellow wedge */}
            <polygon
              points="260,260 60,80 60,440"
              fill={YELLOW}
              style={{ transformOrigin: "260px 260px", animation: `vort-shard-l ${t(4.2)} ease-in-out infinite` }}
            />
            {/* Red diagonal slab */}
            <polygon
              points="260,260 480,90 460,260"
              fill={RED}
              style={{ transformOrigin: "260px 260px", animation: `vort-shard-r ${t(3.6)} ease-in-out infinite` }}
            />
            {/* Black blade */}
            <polygon
              points="260,260 200,500 320,500"
              fill={BLACK}
              style={{ transformOrigin: "260px 260px", animation: `vort-shard-l ${t(5.0)} ease-in-out infinite` }}
            />
            {/* Bone counter-shard */}
            <polygon
              points="260,260 460,260 500,440"
              fill={BONE}
              stroke={BLACK}
              strokeWidth="3"
              style={{ transformOrigin: "260px 260px", animation: `vort-shard-r ${t(4.6)} ease-in-out infinite` }}
            />
            {/* Hard diagonal strike */}
            <line
              x1="40"
              y1="40"
              x2="500"
              y2="500"
              stroke={BLACK}
              strokeWidth="6"
              strokeDasharray="1200"
              style={{ animation: `vort-strike ${t(2.4)} ease-out infinite alternate` }}
            />
            {/* Pivot dot */}
            <circle cx="260" cy="260" r="14" fill={BLACK} />
            <circle cx="260" cy="260" r="6" fill={YELLOW} />
          </svg>
        </div>

        {/* Top-left red corner block */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: 220,
            height: 36,
            background: RED,
            transformOrigin: "left center",
            animation: `vort-bar ${t(2.0)} ease-in-out infinite`,
          }}
        />

        {/* Bottom-right black wedge */}
        <svg
          width="260"
          height="180"
          viewBox="0 0 260 180"
          style={{ position: "absolute", right: 0, bottom: 0 }}
        >
          <polygon points="260,0 260,180 0,180" fill={BLACK} />
          <polygon points="260,20 260,160 40,160" fill={YELLOW} opacity="0.9" />
        </svg>

        {/* Title stamp */}
        <div
          style={{
            position: "absolute",
            top: "8%",
            left: "8%",
            padding: "10px 22px",
            background: BLACK,
            color: BONE,
            fontWeight: 900,
            fontSize: 44,
            letterSpacing: "0.14em",
            transform: "rotate(-8deg)",
            animation: `vort-stamp ${t(0.9)} cubic-bezier(.2,1.2,.3,1) both`,
            boxShadow: `8px 8px 0 ${RED}`,
          }}
        >
          {title}
        </div>

        {/* Subtitle */}
        <div
          style={{
            position: "absolute",
            bottom: "9%",
            left: "8%",
            maxWidth: "55%",
            fontWeight: 700,
            fontSize: 18,
            letterSpacing: "0.32em",
            lineHeight: 1.4,
            color: BLACK,
            animation: `vort-flicker ${t(3.0)} steps(1, end) infinite`,
          }}
        >
          {subtitle}
        </div>

        {/* Year — big sideways */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            right: "4%",
            transform: "translateY(-50%) rotate(90deg)",
            transformOrigin: "right center",
            fontWeight: 900,
            fontSize: 96,
            letterSpacing: "0.06em",
            color: RED,
            opacity: 0.92,
          }}
        >
          {year}
        </div>
      </div>
    </>
  );
}
