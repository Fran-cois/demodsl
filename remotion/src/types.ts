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
  reviewer?: ReviewerConfig;
  liveAvatar?: LiveAvatarConfig;
  progressBar?: ProgressBarConfig;
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
  /** Layout: "cover" (default) or "contain_blur" (vertical shorts) */
  fit?: string;
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

export interface ReviewerConfig {
  /** Portrait image: absolute path or data URI */
  image: string;
  name: string;
  title: string;
  company: string;
  /** Accent color (ring, equalizer, company name) */
  accent: string;
  position: "bottom-left" | "bottom-right" | "top-left" | "top-right";
  /** Portrait bubble diameter in px */
  size: number;
}

export interface LiveAvatarConfig {
  /** Accent color (ring, headset mic dot, background tint) */
  accent: string;
  position: "bottom-left" | "bottom-right" | "top-left" | "top-right";
  /** Bubble diameter in px */
  size: number;
  /** Per-frame narration loudness 0..1 (30 fps) — drives the mouth */
  mouth: number[];
}

export interface ProgressBarConfig {
  accent: string;
  position: "top" | "bottom";
  /** Bar thickness in px */
  height?: number;
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

export interface SubtitleWord {
  word: string;
  /** Absolute start time in seconds (same clock as the entry) */
  start: number;
  /** Absolute end time in seconds */
  end: number;
}

export interface SubtitleEntry {
  text: string;
  startTime: number;
  endTime: number;
  /** Per-word timings, used by the word_by_word / karaoke styles */
  words?: SubtitleWord[];
  style?: SubtitleStyle;
}

export interface SubtitleStyle {
  /** Named preset: classic, word_by_word, karaoke, tiktok, … */
  style?: string;
  fontSize?: number;
  fontFamily?: string;
  fontColor?: string;
  backgroundColor?: string;
  highlightColor?: string;
  position?: "bottom" | "center" | "top";
  /** Safe-area floor: distance from the top/bottom frame edge in px */
  bottomOffset?: number;
  /** Left gutter in px — clears the overlay owning that corner */
  marginLeft?: number;
  /** Right gutter in px — clears the overlay owning that corner */
  marginRight?: number;
  /** Maximum height of the subtitle block in px; overflow is clipped */
  maxHeight?: number;
}

export interface TransitionConfig {
  type: "crossfade" | "wipe" | "iris" | "dissolve" | "slide";
  durationInSeconds: number;
}
