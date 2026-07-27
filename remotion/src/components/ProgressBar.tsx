import { AbsoluteFill, useCurrentFrame } from "remotion";
import type { ProgressBarConfig } from "../types";

/**
 * Tour progress bar — a slim accent line that fills across the content.
 *
 * The quiet cue that tells a viewer "this is produced, and here is how far
 * along we are". Rendered over the content sequence only (intro/outro
 * excluded), with a soft glow head.
 */
export const ProgressBar: React.FC<ProgressBarConfig & { totalFrames: number }> = ({
  accent,
  position,
  height,
  totalFrames,
}) => {
  const frame = useCurrentFrame();
  const pct = totalFrames > 0 ? Math.min(1, frame / totalFrames) : 0;
  const h = height ?? 6;

  const vertical: React.CSSProperties =
    position === "bottom" ? { bottom: 0 } : { top: 0 };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          height: h,
          background: "rgba(255,255,255,.10)",
          ...vertical,
        }}
      >
        <div
          style={{
            width: `${(pct * 100).toFixed(2)}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${accent}cc, ${accent})`,
            boxShadow: `0 0 10px ${accent}aa`,
            borderRadius: `0 ${h / 2}px ${h / 2}px 0`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
