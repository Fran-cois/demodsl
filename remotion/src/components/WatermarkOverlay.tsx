import { AbsoluteFill, Img, useVideoConfig } from "remotion";
import type { WatermarkConfig } from "../types";

export const WatermarkOverlay: React.FC<WatermarkConfig> = ({
  image,
  position,
  opacity,
  size,
}) => {
  const { width, height } = useVideoConfig();
  const margin = 10;

  const positionStyles: Record<string, React.CSSProperties> = {
    top_left: { top: margin, left: margin },
    top_right: { top: margin, right: margin },
    bottom_left: { bottom: margin, left: margin },
    bottom_right: { bottom: margin, right: margin },
    center: {
      top: "50%",
      left: "50%",
      transform: "translate(-50%, -50%)",
    },
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Img
        src={image}
        style={{
          position: "absolute",
          width: size,
          height: size,
          objectFit: "contain",
          opacity,
          ...positionStyles[position],
        }}
      />
    </AbsoluteFill>
  );
};
