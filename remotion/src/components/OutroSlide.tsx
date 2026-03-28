import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { OutroConfig } from "../types";

export const OutroSlide: React.FC<OutroConfig> = ({
  text,
  subtitle,
  cta,
  fontColor = "#FFFFFF",
  backgroundColor = "#1a1a1a",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  const fadeOutStart = durationInFrames - Math.round(fps * 1.0);
  const opacity = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const enterFrames = Math.round(fps * 0.5);
  const enterOpacity = interpolate(frame, [0, enterFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        opacity: Math.min(opacity, enterOpacity),
      }}
    >
      {text && (
        <div
          style={{
            color: fontColor,
            fontSize: 60,
            fontFamily: "Arial, sans-serif",
            fontWeight: 700,
            textAlign: "center",
            maxWidth: "80%",
          }}
        >
          {text}
        </div>
      )}
      {subtitle && (
        <div
          style={{
            color: fontColor,
            fontSize: 30,
            fontFamily: "Arial, sans-serif",
            marginTop: 16,
            textAlign: "center",
            opacity: 0.8,
            maxWidth: "70%",
          }}
        >
          {subtitle}
        </div>
      )}
      {cta && (
        <div
          style={{
            color: "#4CAF50",
            fontSize: 40,
            fontFamily: "Arial, sans-serif",
            fontWeight: 600,
            marginTop: 40,
            textAlign: "center",
          }}
        >
          {cta}
        </div>
      )}
    </AbsoluteFill>
  );
};
