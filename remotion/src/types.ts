/**
 * DemoDSL Remotion — Type definitions for the Python→Remotion bridge.
 *
 * These types define the JSON contract between the Python engine
 * and the Remotion composition renderer.
 */

export interface DemoProps {
  fps: number;
  width: number;
  height: number;
  segments: Segment[];
  intro?: IntroConfig;
  outro?: OutroConfig;
  watermark?: WatermarkConfig;
  stepEffects: StepEffectGroup[];
  avatars: AvatarOverlay[];
  subtitles: SubtitleEntry[];
  transitions?: TransitionConfig;
}

export interface Segment {
  /** Absolute path to the raw MP4 clip */
  src: string;
  /** Duration in seconds */
  durationInSeconds: number;
}

export interface IntroConfig {
  durationInSeconds: number;
  text?: string;
  subtitle?: string;
  fontSize?: number;
  fontColor?: string;
  backgroundColor?: string;
}

export interface OutroConfig {
  durationInSeconds: number;
  text?: string;
  subtitle?: string;
  cta?: string;
  fontColor?: string;
  backgroundColor?: string;
}

export interface WatermarkConfig {
  /** Absolute path to the watermark image */
  image: string;
  position: "top_left" | "top_right" | "bottom_left" | "bottom_right" | "center";
  opacity: number;
  size: number;
}

export interface StepEffectGroup {
  /** Start time in seconds within the composed video */
  startTime: number;
  /** End time in seconds */
  endTime: number;
  /** Effects to apply to this segment */
  effects: EffectConfig[];
}

export interface EffectConfig {
  type: string;
  duration?: number;
  intensity?: number;
  color?: string;
  speed?: number;
  scale?: number;
  direction?: string;
  targetX?: number;
  targetY?: number;
  [key: string]: unknown;
}

export interface AvatarOverlay {
  /** Absolute path to the avatar MP4 clip */
  src: string;
  /** Start time in seconds */
  startTime: number;
  /** Duration in seconds */
  durationInSeconds: number;
  /** Position on screen */
  position: "bottom-right" | "bottom-left" | "top-right" | "top-left";
  /** Size in pixels */
  size: number;
}

export interface SubtitleEntry {
  text: string;
  startTime: number;
  endTime: number;
  style?: SubtitleStyle;
}

export interface SubtitleStyle {
  fontSize?: number;
  fontFamily?: string;
  fontColor?: string;
  backgroundColor?: string;
  highlightColor?: string;
  position?: "bottom" | "center" | "top";
}

export interface TransitionConfig {
  type: "crossfade" | "wipe" | "iris" | "dissolve" | "slide";
  durationInSeconds: number;
}
