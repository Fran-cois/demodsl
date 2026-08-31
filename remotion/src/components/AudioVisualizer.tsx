import { AbsoluteFill, useCurrentFrame } from "remotion";
import type { AudioVisualizerConfig } from "../types";

const MARGIN = 24;

/** HSL hue sweep across band index (low = warm, high = cool) when rainbow is on. */
function bandColor(i: number, n: number, rainbow: boolean, accent: string): string {
  if (!rainbow) return accent;
  const hue = (i / Math.max(1, n - 1)) * 300;
  return `hsl(${hue}, 85%, 60%)`;
}

interface SubProps {
  bands: number[];
  size: number;
  rainbow?: boolean;
  accent: string;
}

const Bars: React.FC<SubProps> = ({ bands, size, rainbow, accent }) => {
  const gap = 3;
  const h = size * 0.4;
  const barW = (size - gap * (bands.length - 1)) / bands.length;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", width: size, height: h, gap }}>
      {bands.map((v, i) => (
        <div
          key={i}
          style={{
            width: barW,
            height: Math.max(2, v * h),
            borderRadius: 2,
            background: bandColor(i, bands.length, !!rainbow, accent),
          }}
        />
      ))}
    </div>
  );
};

const Spectrum: React.FC<SubProps> = ({ bands, size, accent }) => {
  const h = size * 0.4;
  const step = size / Math.max(1, bands.length - 1);
  const points = bands.map((v, i) => `${i * step},${h - v * h}`).join(" ");
  const areaPoints = `0,${h} ${points} ${size},${h}`;
  return (
    <svg width={size} height={h} style={{ overflow: "visible" }}>
      <polygon points={areaPoints} fill={accent} opacity={0.35} />
      <polyline points={points} fill="none" stroke={accent} strokeWidth={2} />
    </svg>
  );
};

const VuMeter: React.FC<SubProps> = ({ bands, size, rainbow, accent }) => {
  // Collapse the full band spread into a handful of big segmented meters
  // (real VU meters have ~5 needles/columns, not one per FFT band).
  const meters = 5;
  const perMeter = Math.max(1, Math.floor(bands.length / meters));
  const levels: number[] = [];
  for (let m = 0; m < meters; m++) {
    const slice = bands.slice(m * perMeter, (m + 1) * perMeter);
    levels.push(slice.length ? slice.reduce((a, b) => a + b, 0) / slice.length : 0);
  }
  const h = size * 0.4;
  const gap = 6;
  const w = (size - gap * (meters - 1)) / meters;
  const segCount = 8;
  return (
    <div style={{ display: "flex", gap, width: size, height: h }}>
      {levels.map((lvl, m) => (
        <div
          key={m}
          style={{
            display: "flex",
            flexDirection: "column-reverse",
            width: w,
            height: h,
            gap: 2,
          }}
        >
          {Array.from({ length: segCount }).map((_, s) => {
            const lit = s < Math.round(lvl * segCount);
            const hot = s >= segCount - 2; // top two segments read as the "red zone"
            return (
              <div
                key={s}
                style={{
                  flex: 1,
                  borderRadius: 1,
                  background: lit
                    ? hot
                      ? "#EF4444"
                      : bandColor(m, meters, !!rainbow, accent)
                    : "rgba(255,255,255,0.12)",
                }}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
};

const Radial: React.FC<SubProps> = ({ bands, size, rainbow, accent }) => {
  const cx = size / 2;
  const cy = size / 2;
  const rInner = size * 0.22;
  const rOuter = size * 0.48;
  return (
    <svg width={size} height={size} style={{ overflow: "visible" }}>
      {bands.map((v, i) => {
        const angle = (i / bands.length) * Math.PI * 2 - Math.PI / 2;
        const r2 = rInner + (rOuter - rInner) * Math.max(0.04, v);
        const x1 = cx + rInner * Math.cos(angle);
        const y1 = cy + rInner * Math.sin(angle);
        const x2 = cx + r2 * Math.cos(angle);
        const y2 = cy + r2 * Math.sin(angle);
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={bandColor(i, bands.length, !!rainbow, accent)}
            strokeWidth={Math.max(2, (rOuter - rInner) / bands.length)}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
};

/**
 * Audio-reactive animated graphic (bars / radial / spectrum / vu_meter),
 * driven by per-frame frequency-band amplitudes computed in Python
 * (see demodsl/effects/audio_bands.py) — same split as LiveAvatar's mouth.
 */
export const AudioVisualizer: React.FC<AudioVisualizerConfig> = ({
  style,
  accent,
  position,
  size,
  rainbow,
  bandData,
}) => {
  const frame = useCurrentFrame();
  const bandCount = bandData && bandData.length > 0 ? bandData[0].length : 16;
  const bands: number[] =
    bandData && bandData.length > 0
      ? (bandData[Math.min(frame, bandData.length - 1)] ?? new Array(bandCount).fill(0))
      : new Array(bandCount).fill(0);

  const posStyle: React.CSSProperties =
    position === "bottom-left"
      ? { bottom: MARGIN, left: MARGIN }
      : position === "top-right"
        ? { top: MARGIN, right: MARGIN }
        : position === "top-left"
          ? { top: MARGIN, left: MARGIN }
          : position === "bottom-center"
            ? { bottom: MARGIN, left: "50%", transform: "translateX(-50%)" }
            : { bottom: MARGIN, right: MARGIN };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          width: size,
          height: style === "radial" ? size : size * 0.4,
          ...posStyle,
        }}
      >
        {style === "bars" && <Bars bands={bands} size={size} rainbow={rainbow} accent={accent} />}
        {style === "radial" && (
          <Radial bands={bands} size={size} rainbow={rainbow} accent={accent} />
        )}
        {style === "spectrum" && (
          <Spectrum bands={bands} size={size} rainbow={rainbow} accent={accent} />
        )}
        {style === "vu_meter" && (
          <VuMeter bands={bands} size={size} rainbow={rainbow} accent={accent} />
        )}
      </div>
    </AbsoluteFill>
  );
};
