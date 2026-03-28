import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { DemoProps } from "./types";
import { IntroSlide } from "./components/IntroSlide";
import { OutroSlide } from "./components/OutroSlide";
import { SegmentPlayer } from "./components/SegmentPlayer";
import { WatermarkOverlay } from "./components/WatermarkOverlay";
import { AvatarOverlayComp } from "./components/AvatarOverlay";
import { SubtitleOverlay } from "./components/SubtitleOverlay";
import { EffectLayer } from "./components/EffectLayer";

export const DemoComposition: React.FC<DemoProps> = ({
  segments,
  intro,
  outro,
  watermark,
  stepEffects,
  avatars,
  subtitles,
}) => {
  const { fps } = useVideoConfig();

  // Calculate frame offsets for each section
  let currentFrame = 0;

  const introFrames = intro
    ? Math.round(intro.durationInSeconds * fps)
    : 0;

  // Segment layout
  const segmentLayouts = segments.map((seg) => {
    const frames = Math.round(seg.durationInSeconds * fps);
    const start = currentFrame + introFrames;
    currentFrame += frames;
    return { ...seg, startFrame: start, durationInFrames: frames };
  });

  const segmentsTotalFrames = currentFrame;
  const outroFrames = outro ? Math.round(outro.durationInSeconds * fps) : 0;
  const contentStartFrame = introFrames;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Intro */}
      {intro && introFrames > 0 && (
        <Sequence from={0} durationInFrames={introFrames} name="Intro">
          <IntroSlide {...intro} />
        </Sequence>
      )}

      {/* Video segments */}
      {segmentLayouts.map((seg, i) => (
        <Sequence
          key={i}
          from={seg.startFrame}
          durationInFrames={seg.durationInFrames}
          name={`Segment-${i}`}
        >
          <SegmentPlayer src={seg.src} />
        </Sequence>
      ))}

      {/* Per-step post-effects */}
      {stepEffects.map((group, i) => {
        const fromFrame = Math.round(group.startTime * fps) + contentStartFrame;
        const dur = Math.round((group.endTime - group.startTime) * fps);
        return (
          <Sequence
            key={`fx-${i}`}
            from={fromFrame}
            durationInFrames={dur}
            name={`Effects-${i}`}
          >
            <EffectLayer effects={group.effects} />
          </Sequence>
        );
      })}

      {/* Avatar overlays */}
      {avatars.map((av, i) => {
        const fromFrame = Math.round(av.startTime * fps) + contentStartFrame;
        const dur = Math.round(av.durationInSeconds * fps);
        return (
          <Sequence
            key={`avatar-${i}`}
            from={fromFrame}
            durationInFrames={dur}
            name={`Avatar-${i}`}
          >
            <AvatarOverlayComp {...av} />
          </Sequence>
        );
      })}

      {/* Subtitles */}
      {subtitles.map((sub, i) => {
        const fromFrame = Math.round(sub.startTime * fps) + contentStartFrame;
        const dur = Math.round((sub.endTime - sub.startTime) * fps);
        return (
          <Sequence
            key={`sub-${i}`}
            from={fromFrame}
            durationInFrames={dur}
            name={`Subtitle-${i}`}
          >
            <SubtitleOverlay entry={sub} />
          </Sequence>
        );
      })}

      {/* Watermark (full duration) */}
      {watermark && (
        <Sequence
          from={contentStartFrame}
          durationInFrames={segmentsTotalFrames}
          name="Watermark"
        >
          <WatermarkOverlay {...watermark} />
        </Sequence>
      )}

      {/* Outro */}
      {outro && outroFrames > 0 && (
        <Sequence
          from={introFrames + segmentsTotalFrames}
          durationInFrames={outroFrames}
          name="Outro"
        >
          <OutroSlide {...outro} />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
