// VectorHeart — animated SVG heart for ReactLayer (mode: animated).
//
// Pure SVG with CSS keyframes: a glowing heart that beats, a soft gradient
// fill, an orbiting halo of small hearts, and a radial pulse ring on each
// systole. Emoji-free (no color glyphs — they crash headless Chromium).

import React from "react";

type Props = {
  label?: string;
  hueA?: number; // primary hue
  hueB?: number; // accent hue (orbit + ring)
  bpm?: number; // beats per minute (drives the pulse tempo)
};

const HEART_PATH =
  "M256 448s-176-112-176-240a96 96 0 0 1 176-53 96 96 0 0 1 176 53c0 128-176 240-176 240z";

export default function VectorHeart({
  label = "LOVE",
  hueA = 340,
  hueB = 280,
  bpm = 78,
}: Props) {
  const beat = 60 / bpm; // seconds per beat

  return (
    <>
      <style>{`
        @keyframes vh-beat {
          0%   { transform: scale(1);    filter: drop-shadow(0 0 18px hsla(${hueA},90%,60%,0.55)); }
          12%  { transform: scale(1.18); filter: drop-shadow(0 0 32px hsla(${hueA},90%,65%,0.85)); }
          28%  { transform: scale(0.97); }
          40%  { transform: scale(1.10); filter: drop-shadow(0 0 28px hsla(${hueA},90%,65%,0.75)); }
          60%  { transform: scale(1);    filter: drop-shadow(0 0 18px hsla(${hueA},90%,60%,0.55)); }
          100% { transform: scale(1);    filter: drop-shadow(0 0 18px hsla(${hueA},90%,60%,0.55)); }
        }
        @keyframes vh-ring {
          0%   { transform: scale(0.6); opacity: 0.85; }
          80%  { transform: scale(1.7); opacity: 0; }
          100% { transform: scale(1.7); opacity: 0; }
        }
        @keyframes vh-orbit {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes vh-counter {
          from { transform: rotate(0deg); }
          to   { transform: rotate(-360deg); }
        }
        @keyframes vh-float {
          0%, 100% { transform: translateY(0); }
          50%      { transform: translateY(-6px); }
        }
        @keyframes vh-fade {
          0%   { opacity: 0; transform: translateY(8px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: '"Inter", -apple-system, sans-serif',
          color: "white",
        }}
      >
        <div
          style={{
            position: "relative",
            width: 360,
            height: 360,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {/* Radial pulse ring synced to the heartbeat */}
          <div
            style={{
              position: "absolute",
              inset: 40,
              borderRadius: "50%",
              border: `3px solid hsla(${hueB}, 90%, 70%, 0.7)`,
              animation: `vh-ring ${beat}s ease-out infinite`,
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 40,
              borderRadius: "50%",
              border: `2px solid hsla(${hueA}, 90%, 70%, 0.5)`,
              animation: `vh-ring ${beat}s ease-out ${beat / 2}s infinite`,
            }}
          />

          {/* Orbiting halo of small hearts */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              animation: "vh-orbit 9s linear infinite",
            }}
          >
            {[0, 60, 120, 180, 240, 300].map((deg, i) => (
              <div
                key={i}
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  width: 0,
                  height: 0,
                  transform: `rotate(${deg}deg) translate(150px) rotate(${-deg}deg)`,
                }}
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 512 512"
                  style={{
                    transform: "translate(-50%, -50%)",
                    animation: `vh-float ${2 + (i % 3) * 0.3}s ease-in-out ${i * 0.15}s infinite`,
                    filter: `drop-shadow(0 0 6px hsla(${hueB},90%,65%,0.8))`,
                  }}
                >
                  <path d={HEART_PATH} fill={`hsl(${hueB}, 90%, 70%)`} />
                </svg>
              </div>
            ))}
          </div>

          {/* Main beating heart */}
          <svg
            viewBox="0 0 512 512"
            width="240"
            height="240"
            style={{
              animation: `vh-beat ${beat}s ease-in-out infinite`,
              transformOrigin: "center",
            }}
          >
            <defs>
              <radialGradient id="vh-grad" cx="40%" cy="35%" r="75%">
                <stop offset="0%" stopColor={`hsl(${hueA}, 95%, 78%)`} />
                <stop offset="55%" stopColor={`hsl(${hueA}, 90%, 58%)`} />
                <stop offset="100%" stopColor={`hsl(${(hueA + 320) % 360}, 80%, 35%)`} />
              </radialGradient>
              <linearGradient id="vh-stroke" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={`hsl(${hueB}, 95%, 80%)`} />
                <stop offset="100%" stopColor={`hsl(${hueA}, 95%, 70%)`} />
              </linearGradient>
            </defs>
            <path
              d={HEART_PATH}
              fill="url(#vh-grad)"
              stroke="url(#vh-stroke)"
              strokeWidth="10"
              strokeLinejoin="round"
            />
            {/* Specular highlight */}
            <path
              d="M180 160c20-30 70-40 90-15 8 10 4 25-8 30-30 12-70 5-82-15z"
              fill="rgba(255,255,255,0.45)"
            />
          </svg>
        </div>

        {/* Label below */}
        <div
          style={{
            marginTop: 18,
            padding: "8px 22px",
            borderRadius: 999,
            background: `linear-gradient(135deg, hsla(${hueA},90%,55%,0.85), hsla(${hueB},90%,55%,0.85))`,
            border: `1px solid hsla(${hueA},90%,80%,0.6)`,
            fontSize: 22,
            fontWeight: 800,
            letterSpacing: "0.18em",
            textShadow: "0 1px 6px rgba(0,0,0,0.5)",
            boxShadow: `0 10px 30px hsla(${hueA},90%,30%,0.45)`,
            animation: "vh-fade 0.8s ease-out both",
          }}
        >
          {label}
        </div>

        {/* BPM line */}
        <div
          style={{
            marginTop: 10,
            fontSize: 13,
            opacity: 0.75,
            letterSpacing: "0.12em",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {bpm} BPM
        </div>
      </div>
    </>
  );
}
