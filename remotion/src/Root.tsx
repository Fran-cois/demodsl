import { Composition } from "remotion";
import { DemoComposition } from "./DemoComposition";
import type { DemoProps } from "./types";

const defaultProps: DemoProps = {
  fps: 30,
  width: 1920,
  height: 1080,
  segments: [],
  stepEffects: [],
  avatars: [],
  subtitles: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="DemoComposition"
      component={DemoComposition}
      durationInFrames={300}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
    />
  );
};
