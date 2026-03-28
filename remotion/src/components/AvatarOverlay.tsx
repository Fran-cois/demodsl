import { AbsoluteFill, OffthreadVideo, useVideoConfig } from "remotion";
import type { AvatarOverlay } from "../types";

const MARGIN = 20;

export const AvatarOverlayComp: React.FC<AvatarOverlay> = ({
  src,
  position,
  size,
}) => {
  const { width, height } = useVideoConfig();
  const canvasSize = Math.round(size * 1.4);

  const positionStyles: Record<string, React.CSSProperties> = {
    "bottom-right": { bottom: MARGIN, right: MARGIN },
    "bottom-left": { bottom: MARGIN, left: MARGIN },
    "top-right": { top: MARGIN, right: MARGIN },
    "top-left": { top: MARGIN, left: MARGIN },
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          width: canvasSize,
          height: canvasSize,
          borderRadius: "50%",
          overflow: "hidden",
          ...positionStyles[position],
        }}
      >
        <OffthreadVideo
          src={src}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    </AbsoluteFill>
  );
};
