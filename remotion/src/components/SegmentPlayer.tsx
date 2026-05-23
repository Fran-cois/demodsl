import { AbsoluteFill, OffthreadVideo } from "remotion";
import { resolveSrc } from "../utils/resolveSrc";

interface SegmentPlayerProps {
  src: string;
}

export const SegmentPlayer: React.FC<SegmentPlayerProps> = ({ src }) => {
  return (
    <AbsoluteFill>
      <OffthreadVideo src={resolveSrc(src)} style={{ width: "100%", height: "100%" }} />
    </AbsoluteFill>
  );
};
