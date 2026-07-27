import { AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { ReviewerConfig } from "../types";
import { resolveSrc } from "../utils/resolveSrc";

const MARGIN = 24;

const resolvePortrait = (src: string): string =>
  src.startsWith("data:") ? src : resolveSrc(src);

/**
 * DemoBro reviewer badge — persistent human presence for review videos.
 *
 * Composited at the video level (like the watermark) so it never zooms or
 * scrolls with the recorded page: a portrait bubble with an accent ring, a
 * name/title plate on dark glass, and a frame-driven speaking equalizer.
 */
export const ReviewerBadge: React.FC<ReviewerConfig> = ({
  image,
  name,
  title,
  company,
  accent,
  position,
  size,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 14, mass: 0.8 } });
  const translateY = interpolate(enter, [0, 1], [18, 0]);

  // Speaking equalizer: 4 bars on layered sine waves — organic, loopless.
  const bars = [0, 1, 2, 3].map((i) => {
    const t = frame / fps;
    const v =
      0.5 +
      0.32 * Math.sin(t * (5.1 + i * 1.3) + i * 1.7) +
      0.18 * Math.sin(t * (11.7 - i * 0.9) + i * 0.6);
    return Math.max(0.22, Math.min(1, v));
  });

  // Gentle ping on the accent ring every ~2.4s.
  const ringT = ((frame / fps) % 2.4) / 2.4;
  const ringSpread = interpolate(ringT, [0, 1], [0, 12]);
  const ringAlpha = interpolate(ringT, [0, 1], [0.45, 0]);

  const pos: React.CSSProperties =
    position === "bottom-right"
      ? { bottom: MARGIN, right: MARGIN, flexDirection: "row-reverse" }
      : position === "top-left"
        ? { top: MARGIN, left: MARGIN }
        : position === "top-right"
          ? { top: MARGIN, right: MARGIN, flexDirection: "row-reverse" }
          : { bottom: MARGIN, left: MARGIN };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          display: "flex",
          alignItems: "center",
          gap: 14,
          opacity: enter,
          transform: `translateY(${translateY}px)`,
          fontFamily: "-apple-system, 'SF Pro Text', 'Segoe UI', sans-serif",
          ...pos,
        }}
      >
        <div
          style={{
            width: size,
            height: size,
            borderRadius: "50%",
            flex: "none",
            overflow: "hidden",
            border: `3px solid ${accent}`,
            boxShadow: `0 6px 22px rgba(0,0,0,.4), 0 0 0 ${ringSpread}px ${accent}${Math.round(
              ringAlpha * 255,
            )
              .toString(16)
              .padStart(2, "0")}`,
            background: "#111527",
          }}
        >
          <Img
            src={resolvePortrait(image)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </div>
        <div
          style={{
            background: "rgba(11,18,36,.88)",
            border: "1px solid rgba(255,255,255,.14)",
            borderRadius: 15,
            padding: "10px 16px 10px 14px",
            color: "#fff",
            boxShadow: "0 6px 22px rgba(0,0,0,.35)",
            display: "flex",
            alignItems: "center",
            gap: 13,
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, lineHeight: 1.25 }}>
              {name}
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.35, color: "#c7cbe0" }}>
              {title} ·{" "}
              <span style={{ color: accent, fontWeight: 600 }}>{company}</span>
            </div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 3,
              height: 20,
            }}
          >
            {bars.map((v, i) => (
              <div
                key={i}
                style={{
                  width: 3.5,
                  height: 20,
                  borderRadius: 2,
                  background: accent,
                  transform: `scaleY(${v})`,
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
