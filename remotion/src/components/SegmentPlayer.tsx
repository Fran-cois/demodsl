import { AbsoluteFill, OffthreadVideo } from "remotion";

interface SegmentPlayerProps {
  src: string;
}

export const SegmentPlayer: React.FC<SegmentPlayerProps> = ({ src }) => {
  return (
    <AbsoluteFill>
      <OffthreadVideo src={src} style={{ width: "100%", height: "100%" }} />
    </AbsoluteFill>
  );
};
