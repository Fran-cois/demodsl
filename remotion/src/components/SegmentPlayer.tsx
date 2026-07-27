import { AbsoluteFill, OffthreadVideo } from "remotion";
import { resolveSrc } from "../utils/resolveSrc";

interface SegmentPlayerProps {
  src: string;
  /** "cover" (default, 16:9 canvas) or "contain_blur" (vertical canvas:
   *  blurred cover copy behind a sharp contained copy, seated upper-third). */
  fit?: string;
}

export const SegmentPlayer: React.FC<SegmentPlayerProps> = ({ src, fit }) => {
  if (fit === "contain_blur") {
    return (
      <AbsoluteFill style={{ backgroundColor: "#0B1224" }}>
        <OffthreadVideo
          src={resolveSrc(src)}
          muted
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(26px) brightness(0.55)",
            transform: "scale(1.12)",
          }}
        />
        <OffthreadVideo
          src={resolveSrc(src)}
          style={{
            position: "absolute",
            width: "100%",
            height: "auto",
            top: "31%",
            left: 0,
            objectFit: "contain",
            borderRadius: 18,
            boxShadow: "0 18px 60px rgba(0,0,0,.55)",
          }}
        />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      <OffthreadVideo src={resolveSrc(src)} style={{ width: "100%", height: "100%" }} />
    </AbsoluteFill>
  );
};
