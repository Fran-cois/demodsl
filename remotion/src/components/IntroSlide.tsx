import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { IntroConfig } from "../types";

export const IntroSlide: React.FC<IntroConfig> = ({
  text,
  subtitle,
  fontSize = 60,
  fontColor = "#FFFFFF",
  backgroundColor = "#1a1a1a",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  // Fade in over 0.5s
  const fadeInFrames = Math.round(fps * 0.5);
  const opacity = interpolate(frame, [0, fadeInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Scale entrance
  const scale = interpolate(frame, [0, fadeInFrames], [0.9, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      {text && (
        <div
          style={{
            color: fontColor,
            fontSize,
            fontFamily: "Arial, sans-serif",
            fontWeight: 700,
            textAlign: "center",
            transform: `scale(${scale})`,
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
            fontSize: fontSize / 2,
            fontFamily: "Arial, sans-serif",
            fontWeight: 400,
            textAlign: "center",
            marginTop: 20,
            opacity: interpolate(
              frame,
              [fadeInFrames * 0.5, fadeInFrames * 1.5],
              [0, 0.8],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
            maxWidth: "70%",
          }}
        >
          {subtitle}
        </div>
      )}
    </AbsoluteFill>
  );
};
