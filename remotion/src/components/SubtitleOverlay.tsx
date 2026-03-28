import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { SubtitleEntry } from "../types";

interface SubtitleOverlayProps {
  entry: SubtitleEntry;
}

export const SubtitleOverlay: React.FC<SubtitleOverlayProps> = ({ entry }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();

  const style = entry.style ?? {};
  const fontSize = style.fontSize ?? 48;
  const fontFamily = style.fontFamily ?? "Arial, sans-serif";
  const fontColor = style.fontColor ?? "#FFFFFF";
  const bgColor = style.backgroundColor ?? "rgba(0,0,0,0.6)";
  const position = style.position ?? "bottom";

  // Fade in/out
  const fadeFrames = Math.round(fps * 0.2);
  const totalFrames = Math.round((entry.endTime - entry.startTime) * fps);
  const opacity = interpolate(
    frame,
    [0, fadeFrames, totalFrames - fadeFrames, totalFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const positionStyles: Record<string, React.CSSProperties> = {
    bottom: { bottom: 60, left: 0, right: 0 },
    center: { top: "50%", left: 0, right: 0, transform: "translateY(-50%)" },
    top: { top: 60, left: 0, right: 0 },
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          display: "flex",
          justifyContent: "center",
          ...positionStyles[position],
        }}
      >
        <div
          style={{
            backgroundColor: bgColor,
            color: fontColor,
            fontSize,
            fontFamily,
            fontWeight: 600,
            padding: "8px 24px",
            borderRadius: 8,
            textAlign: "center",
            maxWidth: "80%",
            opacity,
          }}
        >
          {entry.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
