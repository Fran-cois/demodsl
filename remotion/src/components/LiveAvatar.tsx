import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { LiveAvatarConfig } from "../types";

const MARGIN = 24;

/**
 * Live avatar — a stylized, audio-reactive presenter bubble.
 *
 * Deliberately flat-vector with soft shading (no photorealism, no uncanny
 * valley). Everything is frame-driven and deterministic:
 * - mouth opens with the narration's amplitude envelope (teeth + tongue
 *   appear with openness, width narrows as it opens — pseudo-visemes),
 * - eyes blink on a schedule and the pupils saccade between rest points,
 * - the head bobs/tilts with speech energy, brows lift on onsets,
 * - shoulders breathe slowly underneath it all.
 */
export const LiveAvatar: React.FC<LiveAvatarConfig> = ({
  accent,
  position,
  size,
  mouth,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const enter = spring({ frame, fps, config: { damping: 13, mass: 0.7 } });

  // Speech energy for this frame (0..1); idle micro-motion when no envelope.
  const idle = 0.05 + 0.03 * Math.sin(t / 1.7);
  const env = mouth && mouth.length > 0 ? (mouth[Math.min(frame, mouth.length - 1)] ?? 0) : idle;
  const envPrev =
    mouth && mouth.length > 0 ? (mouth[Math.max(0, Math.min(frame - 2, mouth.length - 1))] ?? 0) : idle;
  const denv = env - envPrev; // opening vs closing → mouth shape variance

  // Head: gentle bob + tilt scaled by speech energy.
  const bob = env * 2.4 * Math.sin(t * 5.3) + 1.0 * Math.sin(t * 1.1);
  const tilt = env * 2.0 * Math.sin(t * 2.3 + 1.2) + 0.8 * Math.sin(t * 0.7);

  // Breathing shoulders (~14 breaths/min).
  const breath = 1 + 0.008 * Math.sin(t * 1.5);

  // Blink: deterministic ~ every 3s, 4-frame close, occasional double blink.
  const blinkCycle = Math.floor(t / 3.1);
  const blinkAt = (blinkCycle * 3.1 + 2.2 + 0.7 * Math.sin(blinkCycle * 7.3)) * fps;
  const dbl = Math.sin(blinkCycle * 13.7) > 0.72 ? 7 : 0; // second blink 7 frames later
  const blinkD = Math.min(Math.abs(frame - blinkAt), dbl ? Math.abs(frame - blinkAt - dbl) : 1e9);
  const eyeOpen = blinkD < 3 ? Math.max(0.1, blinkD / 3) : 1;

  // Pupil saccades: rest points change every ~2.4s, quick 3-frame hop.
  const sacCycle = Math.floor(t / 2.4);
  const sacTargetX = 1.4 * Math.sin(sacCycle * 5.9) + 0.6 * Math.sin(sacCycle * 2.3);
  const sacTargetY = 0.5 * Math.sin(sacCycle * 3.7);
  const sacPrevX = 1.4 * Math.sin((sacCycle - 1) * 5.9) + 0.6 * Math.sin((sacCycle - 1) * 2.3);
  const sacPrevY = 0.5 * Math.sin((sacCycle - 1) * 3.7);
  const sacP = Math.min(1, ((t % 2.4) * fps) / 3);
  const pupilX = sacPrevX + (sacTargetX - sacPrevX) * sacP;
  const pupilY = sacPrevY + (sacTargetY - sacPrevY) * sacP;

  // Brows lift on energy peaks.
  const browLift = env > 0.6 ? (env - 0.6) * 8 : 0;

  // Mouth: height from envelope; width narrows as it opens (O-shape) and
  // widens on closing/plosive frames (E-shape) — reads as articulation.
  const openness = Math.max(0.06, env);
  const mouthH = 1.4 + openness * 9.5;
  const mouthW = 13.5 - openness * 3.2 + (denv < -0.06 ? 2.2 : 0);

  const pos: React.CSSProperties =
    position === "bottom-left"
      ? { bottom: MARGIN, left: MARGIN }
      : position === "top-right"
        ? { top: MARGIN, right: MARGIN }
        : position === "top-left"
          ? { top: MARGIN, left: MARGIN }
          : { bottom: MARGIN, right: MARGIN };

  // Soft accent ring ping, offset from the badge's rhythm.
  const ringT = ((t + 1.1) % 2.8) / 2.8;
  const ringSpread = interpolate(ringT, [0, 1], [0, 14]);
  const ringAlpha = Math.round(interpolate(ringT, [0, 1], [0.4, 0]) * 255)
    .toString(16)
    .padStart(2, "0");

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          width: size,
          height: size,
          borderRadius: "50%",
          overflow: "hidden",
          border: `4px solid ${accent}`,
          boxShadow: `0 8px 26px rgba(0,0,0,.42), 0 0 0 ${ringSpread}px ${accent}${ringAlpha}`,
          opacity: enter,
          transform: `translateY(${interpolate(enter, [0, 1], [20, 0])}px)`,
          background: `linear-gradient(135deg, ${accent} 0%, #1d1f33 100%)`,
          ...pos,
        }}
      >
        <svg viewBox="0 0 96 96" width="100%" height="100%">
          <defs>
            <radialGradient id="dbrSkin" cx="0.42" cy="0.32" r="0.85">
              <stop offset="0" stopColor="#f7cfa8" />
              <stop offset="0.75" stopColor="#f0bd92" />
              <stop offset="1" stopColor="#e0a67a" />
            </radialGradient>
            <linearGradient id="dbrShirt" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#f4f5fb" />
              <stop offset="1" stopColor="#d9dcf0" />
            </linearGradient>
            <linearGradient id="dbrHair" x1="0" y1="0" x2="0.6" y2="1">
              <stop offset="0" stopColor="#4a3a32" />
              <stop offset="1" stopColor="#2f2521" />
            </linearGradient>
          </defs>

          {/* shoulders — breathing */}
          <g transform={`scale(1 ${breath.toFixed(4)})`} style={{ transformOrigin: "48px 96px" }}>
            <path d="M14 96c2-21 15-29 34-29s32 8 34 29z" fill="url(#dbrShirt)" />
            <path d="M14 96c2-21 15-29 34-29s32 8 34 29z" fill={accent} opacity=".22" />
            {/* collar */}
            <path d="M42 68l6 7 6-7" stroke="#c3c8e4" strokeWidth="2" fill="none" strokeLinecap="round" />
          </g>

          {/* neck + chin shadow */}
          <rect x="41" y="53" width="14" height="15" rx="6" fill="#eab388" />
          <path d="M41 56c2 2.4 12 2.4 14 0v4c-2 2.2-12 2.2-14 0z" fill="#d99a6c" opacity=".55" />

          {/* head group — bobs and tilts with speech */}
          <g transform={`translate(0 ${bob.toFixed(2)}) rotate(${tilt.toFixed(2)} 48 44)`}>
            {/* ears */}
            <circle cx="30.5" cy="42.5" r="3.6" fill="#eab388" />
            <circle cx="65.5" cy="42.5" r="3.6" fill="#eab388" />
            <circle cx="30.8" cy="42.5" r="1.5" fill="#d99a6c" opacity=".6" />
            <circle cx="65.2" cy="42.5" r="1.5" fill="#d99a6c" opacity=".6" />

            {/* face */}
            <ellipse cx="48" cy="40.5" rx="17.5" ry="19.5" fill="url(#dbrSkin)" />

            {/* hair — swept with a highlight */}
            <path
              d="M30 39c-1.6-15 8.4-23.5 18-23.5S67.6 24 66 39c-1.8-8.5-5.6-11.5-9-11.8 1.8 2.6 2.2 4.8 2.2 4.8s-5.2-3.8-11.2-3.8-12 3.2-14.6 8.2c-1.2 1.4-2.4 2.6-3.4 2.6z"
              fill="url(#dbrHair)"
            />
            <path
              d="M39 18.5c3.4-1.7 9.4-2.1 13.4-.5"
              stroke="#6b564a"
              strokeWidth="1.6"
              fill="none"
              strokeLinecap="round"
              opacity=".7"
            />

            {/* brows — lift on loud onsets */}
            <g transform={`translate(0 ${(-browLift).toFixed(2)})`}>
              <path d="M38.4 36c2.2-1.9 5-1.9 7-.4" stroke="#3b2f2a" strokeWidth="1.9" fill="none" strokeLinecap="round" />
              <path d="M50.6 35.6c2-1.5 4.8-1.5 7 .4" stroke="#3b2f2a" strokeWidth="1.9" fill="none" strokeLinecap="round" />
            </g>

            {/* eyes — sclera + saccading pupils, blink via scaleY */}
            <g
              transform={`translate(0 ${(41.2 * (1 - eyeOpen)).toFixed(2)}) scale(1 ${eyeOpen.toFixed(2)})`}
              style={{ transformOrigin: "48px 41.2px" }}
            >
              <ellipse cx="42" cy="41.2" rx="3.1" ry="2.5" fill="#fff" />
              <ellipse cx="54" cy="41.2" rx="3.1" ry="2.5" fill="#fff" />
              <circle cx={42 + pupilX} cy={41.2 + pupilY} r="1.55" fill="#33323e" />
              <circle cx={54 + pupilX} cy={41.2 + pupilY} r="1.55" fill="#33323e" />
              <circle cx={42.6 + pupilX} cy={40.6 + pupilY} r="0.45" fill="#fff" opacity=".9" />
              <circle cx={54.6 + pupilX} cy={40.6 + pupilY} r="0.45" fill="#fff" opacity=".9" />
            </g>

            {/* nose + blush */}
            <path d="M47.4 44.5c-.8 1.8-.6 3 .8 3.6" stroke="#d99a6c" strokeWidth="1.4" fill="none" strokeLinecap="round" />
            <ellipse cx="37.5" cy="47" rx="2.6" ry="1.4" fill="#e8927c" opacity=".28" />
            <ellipse cx="58.5" cy="47" rx="2.6" ry="1.4" fill="#e8927c" opacity=".28" />

            {/* mouth — amplitude-driven with teeth + tongue */}
            <g>
              <ellipse cx="48" cy="52" rx={mouthW / 2} ry={Math.max(0.9, mouthH / 2)} fill="#6d3526" />
              {mouthH > 4 && (
                <rect
                  x={48 - mouthW / 2.9}
                  y={52 - mouthH / 2 + 0.4}
                  width={(mouthW / 2.9) * 2}
                  height={Math.min(2.6, mouthH * 0.28)}
                  rx="1.1"
                  fill="#fff"
                  opacity=".95"
                />
              )}
              {mouthH > 6 && (
                <ellipse
                  cx="48"
                  cy={52 + mouthH / 4}
                  rx={mouthW / 3.4}
                  ry={Math.max(0.6, mouthH / 4.6)}
                  fill="#c96f63"
                />
              )}
            </g>

            {/* headset */}
            <path d="M28.5 40c0-12.6 8.3-20.8 19.5-20.8S67.5 27.4 67.5 40" stroke="#23253a" strokeWidth="4" fill="none" strokeLinecap="round" />
            <rect x="25.4" y="37.5" width="7.2" height="12.5" rx="3.6" fill="#23253a" />
            <rect x="63.4" y="37.5" width="7.2" height="12.5" rx="3.6" fill="#23253a" />
            <rect x="26.6" y="39" width="2" height="9.5" rx="1" fill="#3c3f5e" />
            <rect x="67.4" y="39" width="2" height="9.5" rx="1" fill="#3c3f5e" />
            <path d="M30.5 50c0 6.2 6.5 9.4 13 10.4" stroke="#23253a" strokeWidth="3" fill="none" strokeLinecap="round" />
            <circle cx="45" cy="60.8" r="3.1" fill={accent} />
            <circle cx="44.2" cy="60" r="0.9" fill="#fff" opacity=".7" />
          </g>
        </svg>
      </div>
    </AbsoluteFill>
  );
};
