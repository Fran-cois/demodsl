import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { SubtitleEntry, SubtitleWord } from "../types";

interface SubtitleOverlayProps {
  entry: SubtitleEntry;
}

/** Styles that reveal/highlight the narration word by word. */
const WORD_STYLES = new Set([
  "word_by_word",
  "karaoke",
  "tiktok",
  "highlight_line",
  "fade_word",
  "bounce",
]);

/** Styles that show only the word currently being spoken. */
const REVEAL_ONLY = new Set(["word_by_word", "fade_word"]);

export const SubtitleOverlay: React.FC<SubtitleOverlayProps> = ({ entry }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const style = entry.style ?? {};
  const styleName = style.style ?? "classic";
  const fontSize = style.fontSize ?? 48;
  const fontFamily = style.fontFamily ?? "Arial, sans-serif";
  const fontColor = style.fontColor ?? "#FFFFFF";
  const bgColor = style.backgroundColor ?? "rgba(0,0,0,0.6)";
  const highlightColor = style.highlightColor ?? "#FFD700";
  const position = style.position ?? "bottom";
  // Safe area (issue #32). The burn used to grow upward from a flat 60px with
  // no floor and no ceiling, so a 3-4 line block covered the bottom third of
  // the frame, ran under the reviewer badge / avatar bubble, and lost its last
  // line off the edge. The orchestrator now sends a real safe area.
  const bottomOffset = style.bottomOffset ?? 60;
  const marginLeft = style.marginLeft ?? 0;
  const marginRight = style.marginRight ?? 0;
  const maxHeight = style.maxHeight;

  // Fade in/out. Word-level chunks can be a few frames long, so the fade has
  // to shrink with them — interpolate() rejects a non-increasing range, and
  // anything shorter than 4 frames simply pops in.
  const totalFrames = Math.max(1, Math.round((entry.endTime - entry.startTime) * fps));
  const fadeFrames = Math.min(Math.round(fps * 0.2), Math.floor(totalFrames / 3));
  const opacity =
    fadeFrames < 1
      ? 1
      : interpolate(
          frame,
          [0, fadeFrames, totalFrames - fadeFrames, totalFrames],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

  const positionStyles: Record<string, React.CSSProperties> = {
    bottom: { bottom: bottomOffset, left: marginLeft, right: marginRight },
    center: {
      top: "50%",
      left: marginLeft,
      right: marginRight,
      transform: "translateY(-50%)",
    },
    top: { top: bottomOffset, left: marginLeft, right: marginRight },
  };

  const words = entry.words ?? [];
  const wordMode = WORD_STYLES.has(styleName) && words.length > 0;
  const revealOnly = REVEAL_ONLY.has(styleName);
  // Word timings are absolute; this sequence starts at entry.startTime.
  const t = entry.startTime + frame / fps;

  const isActive = (w: SubtitleWord) => t >= w.start && t < w.end;

  const renderWord = (w: SubtitleWord, i: number) => {
    const active = isActive(w);
    const spoken = t >= w.start;
    // Pop the active word; keep the layout stable for the rest of the line.
    const scale = active ? 1.12 : 1;
    const color = active ? highlightColor : fontColor;
    const wordOpacity = revealOnly ? 1 : spoken ? 1 : 0.45;

    return (
      <span
        key={`${w.word}-${i}`}
        style={{
          display: "inline-block",
          margin: "0 0.18em",
          color,
          opacity: wordOpacity,
          transform: `scale(${scale})`,
        }}
      >
        {w.word}
      </span>
    );
  };

  // word_by_word shows a single word at a time — nothing else on screen.
  const visible = revealOnly ? words.filter(isActive) : words;
  const body = wordMode ? <span>{visible.map(renderWord)}</span> : entry.text;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          display: "flex",
          justifyContent: "center",
          ...positionStyles[position],
        }}
      >
        <div
          style={{
            backgroundColor: wordMode ? "transparent" : bgColor,
            color: fontColor,
            fontSize,
            fontFamily,
            fontWeight: wordMode ? 800 : 600,
            padding: "8px 24px",
            borderRadius: 8,
            textAlign: "center",
            maxWidth: "100%",
            lineHeight: 1.15,
            // Bounded block: past this the caption stops narrating the page
            // and starts hiding it, so the overflow is clipped instead.
            maxHeight,
            overflow: maxHeight ? "hidden" : undefined,
            opacity,
            // Without the background plate, a hard shadow keeps the text
            // readable on top of any screenshot.
            textShadow: wordMode
              ? "0 4px 18px rgba(0,0,0,0.85), 0 0 3px rgba(0,0,0,0.9)"
              : "none",
            WebkitTextStroke: wordMode ? "2px rgba(0,0,0,0.55)" : undefined,
          }}
        >
          {body}
        </div>
      </div>
    </AbsoluteFill>
  );
};
