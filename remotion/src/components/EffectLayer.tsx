import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { EffectConfig } from "../types";

interface EffectLayerProps {
  effects: EffectConfig[];
}

/**
 * Applies post-processing visual effects as CSS transforms/overlays.
 * Each effect type maps to a React-based implementation using
 * Remotion's interpolate() and spring() for animation.
 */
export const EffectLayer: React.FC<EffectLayerProps> = ({ effects }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  if (!effects || effects.length === 0) return null;

  // Combine transforms from all effects
  let transform = "";
  const overlays: React.ReactNode[] = [];

  for (const effect of effects) {
    const progress = frame / durationInFrames;

    switch (effect.type) {
      case "ken_burns": {
        const maxScale = effect.scale ?? 1.15;
        const direction = effect.direction ?? "right";
        const scale = interpolate(frame, [0, durationInFrames], [1, maxScale], {
          extrapolateRight: "clamp",
        });
        let tx = 0;
        let ty = 0;
        const drift = (maxScale - 1) * 50;
        if (direction === "right") tx = -drift * progress;
        else if (direction === "left") tx = drift * progress;
        else if (direction === "up") ty = drift * progress;
        else if (direction === "down") ty = -drift * progress;
        transform += ` scale(${scale}) translate(${tx}%, ${ty}%)`;
        break;
      }
      case "zoom_pulse": {
        const maxScale = effect.scale ?? 1.2;
        const s =
          1 +
          (maxScale - 1) *
            Math.abs(Math.sin(progress * Math.PI));
        transform += ` scale(${s})`;
        break;
      }
      case "parallax": {
        const depth = effect.intensity ?? 0.05;
        const scale = 1 + depth;
        transform += ` scale(${scale})`;
        break;
      }
      case "drone_zoom": {
        const maxScale = effect.scale ?? 1.5;
        const tx = effect.targetX ?? 0.5;
        const ty = effect.targetY ?? 0.5;
        // Ease-in-out
        const p = progress * progress * (3 - 2 * progress);
        const s = 1 + (maxScale - 1) * p;
        const ox = -(tx - 0.5) * (s - 1) * 100;
        const oy = -(ty - 0.5) * (s - 1) * 100;
        transform += ` scale(${s}) translate(${ox}%, ${oy}%)`;
        break;
      }
      case "camera_shake": {
        const intensity = effect.intensity ?? 0.3;
        const speed = effect.speed ?? 8;
        const t = frame / fps;
        const maxShift = intensity * 10;
        const dx = maxShift * Math.sin(t * speed * 2 * Math.PI);
        const dy = maxShift * Math.cos(t * speed * 2.7 * Math.PI);
        transform += ` translate(${dx}px, ${dy}px)`;
        break;
      }
      case "elastic_zoom": {
        const maxScale = effect.scale ?? 1.3;
        const p = Math.min(progress * 2, 1);
        const c1 = 1.70158;
        const c3 = c1 + 1;
        const ease = 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
        const s = 1 + (maxScale - 1) * Math.max(ease, 0);
        transform += ` scale(${s})`;
        break;
      }
      case "zoom_to": {
        const maxScale = effect.scale ?? 1.8;
        const tx = effect.targetX ?? 0.5;
        const ty = effect.targetY ?? 0.5;
        const p = 1 - Math.pow(1 - Math.min(progress * 2, 1), 3);
        const s = 1 + (maxScale - 1) * p;
        const ox = -(tx - 0.5) * (s - 1) * 100;
        const oy = -(ty - 0.5) * (s - 1) * 100;
        transform += ` scale(${s}) translate(${ox}%, ${oy}%)`;
        break;
      }
      case "vignette": {
        const intensity = effect.intensity ?? 0.5;
        overlays.push(
          <div
            key="vignette"
            style={{
              position: "absolute",
              inset: 0,
              background: `radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,${intensity}) 100%)`,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "letterbox": {
        const ratio = effect.ratio ?? 2.35;
        // Calculate bar height for target aspect ratio
        overlays.push(
          <div key="letterbox-top" style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: `${((1 - (16 / 9) / ratio) / 2) * 100}%`,
            backgroundColor: "#000",
            pointerEvents: "none",
          }} />,
          <div key="letterbox-bottom" style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: `${((1 - (16 / 9) / ratio) / 2) * 100}%`,
            backgroundColor: "#000",
            pointerEvents: "none",
          }} />
        );
        break;
      }
      case "glitch": {
        const intensity = effect.intensity ?? 0.3;
        // Simulate glitch with random-ish transform flicker
        const seed = Math.sin(frame * 127.1) * 43758.5453;
        const flicker = (seed - Math.floor(seed)) * intensity * 20;
        if (frame % 4 === 0) {
          transform += ` translateX(${flicker}px)`;
        }
        break;
      }
      case "film_grain": {
        overlays.push(
          <div
            key="grain"
            style={{
              position: "absolute",
              inset: 0,
              opacity: effect.intensity ?? 0.15,
              backgroundImage:
                "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
              mixBlendMode: "overlay",
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "fade_in": {
        const dur = effect.duration ?? 1.0;
        const fadeFrames = Math.max(1, Math.round(dur * fps));
        const opacity = interpolate(frame, [0, fadeFrames], [0, 1], {
          extrapolateRight: "clamp",
        });
        overlays.push(
          <div
            key="fade-in"
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "#000",
              opacity: 1 - opacity,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "fade_out": {
        const dur = effect.duration ?? 1.0;
        const fadeFrames = Math.max(1, Math.round(dur * fps));
        const opacity = interpolate(
          frame,
          [durationInFrames - fadeFrames, durationInFrames],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );
        overlays.push(
          <div
            key="fade-out"
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "#000",
              opacity,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "slide_in": {
        const direction = (effect.direction as string) ?? "left";
        const dur = effect.duration ?? 0.6;
        const slideFrames = Math.max(1, Math.round(dur * fps));
        const p = interpolate(frame, [0, slideFrames], [0, 1], {
          extrapolateRight: "clamp",
        });
        const ease = 1 - Math.pow(1 - p, 3); // ease-out cubic
        const offset = (1 - ease) * 100;
        let tx = 0;
        let ty = 0;
        if (direction === "left") tx = -offset;
        else if (direction === "right") tx = offset;
        else if (direction === "top") ty = -offset;
        else if (direction === "bottom") ty = offset;
        transform += ` translate(${tx}%, ${ty}%)`;
        break;
      }
      case "dolly_zoom": {
        const intensity = effect.intensity ?? 0.3;
        const zoom = 1 + intensity * progress;
        const cropExpand = 1 - intensity * 0.5 * progress;
        // Approximate vertigo: outer scale up, inner scale down
        const net = zoom / cropExpand;
        transform += ` scale(${net})`;
        break;
      }
      case "whip_pan": {
        const direction = (effect.direction as string) ?? "right";
        // Blur peaks in middle (20%-80%)
        const blurZone = Math.max(0, Math.min(1, (progress - 0.2) / 0.6));
        const blurAmount = 20 * Math.sin(blurZone * Math.PI);
        const shift = 5 * Math.sin(blurZone * Math.PI);
        const sx = direction === "right" ? -shift : direction === "left" ? shift : 0;
        const sy = direction === "down" ? -shift : direction === "up" ? shift : 0;
        if (blurAmount >= 0.5) {
          const blurAxis =
            direction === "right" || direction === "left"
              ? `${blurAmount}px 0`
              : `0 ${blurAmount}px`;
          overlays.push(
            <div
              key="whip-blur"
              style={{
                position: "absolute",
                inset: 0,
                backdropFilter: `blur(${blurAmount / 2}px)`,
                WebkitBackdropFilter: `blur(${blurAmount / 2}px)`,
                // motion-blur hint: tiny shadow trail
                boxShadow: `inset 0 0 0 transparent`,
                pointerEvents: "none",
                // expose the axis for debugging
                ["--whip-axis" as never]: blurAxis,
              }}
            />
          );
        }
        transform += ` translate(${sx}%, ${sy}%)`;
        break;
      }
      case "rotate": {
        const maxAngle = effect.angle ?? 3.0;
        const speed = effect.speed ?? 1.0;
        const angle = (maxAngle as number) * Math.sin(progress * (speed as number) * 2 * Math.PI);
        transform += ` scale(1.05) rotate(${angle}deg)`;
        break;
      }
      case "color_grade": {
        const preset = (effect.preset as string) ?? "cinematic";
        let filter = "";
        switch (preset) {
          case "warm":
            filter = "saturate(1.1) sepia(0.15)";
            break;
          case "cool":
            filter = "saturate(1.05) hue-rotate(-10deg) brightness(0.98)";
            break;
          case "desaturate":
            filter = "saturate(0.4)";
            break;
          case "vintage":
            filter = "sepia(0.35) saturate(1.1) contrast(1.05) brightness(0.95)";
            break;
          case "cinematic":
            filter = "contrast(1.1) saturate(1.05) brightness(0.98)";
            break;
          case "noir":
            filter = "grayscale(1) contrast(1.4) brightness(0.9)";
            break;
          case "pastel":
            filter = "saturate(0.6) brightness(1.15)";
            break;
          case "high_contrast":
            filter = "contrast(1.5) saturate(1.1)";
            break;
        }
        overlays.push(
          <div
            key={`grade-${preset}`}
            style={{
              position: "absolute",
              inset: 0,
              backdropFilter: filter,
              WebkitBackdropFilter: filter,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "focus_pull": {
        const direction = (effect.direction as string) ?? "out";
        const intensity = (effect.intensity as number) ?? 0.5;
        const blur =
          direction === "in"
            ? intensity * 15 * (1 - progress)
            : intensity * 15 * progress;
        if (blur >= 0.5) {
          overlays.push(
            <div
              key="focus-pull"
              style={{
                position: "absolute",
                inset: 0,
                backdropFilter: `blur(${blur}px)`,
                WebkitBackdropFilter: `blur(${blur}px)`,
                pointerEvents: "none",
              }}
            />
          );
        }
        break;
      }
      case "tilt_shift": {
        const intensity = (effect.intensity as number) ?? 0.6;
        const focusPos = ((effect.focus_position as number) ?? 0.5) * 100;
        const blurPx = intensity * 12;
        overlays.push(
          <div
            key="tilt-shift"
            style={{
              position: "absolute",
              inset: 0,
              backdropFilter: `blur(${blurPx}px)`,
              WebkitBackdropFilter: `blur(${blurPx}px)`,
              maskImage: `linear-gradient(to bottom, black 0%, transparent ${focusPos - 15}%, transparent ${focusPos + 15}%, black 100%)`,
              WebkitMaskImage: `linear-gradient(to bottom, black 0%, transparent ${focusPos - 15}%, transparent ${focusPos + 15}%, black 100%)`,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "crt_scanlines": {
        const intensity = (effect.intensity as number) ?? 0.4;
        const spacing = (effect.line_spacing as number) ?? 3;
        overlays.push(
          <div
            key="crt"
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage: `repeating-linear-gradient(0deg, rgba(0,0,0,${intensity}) 0, rgba(0,0,0,${intensity}) 1px, transparent 1px, transparent ${spacing}px)`,
              pointerEvents: "none",
              mixBlendMode: "multiply",
            }}
          />
        );
        break;
      }
      case "chromatic_aberration": {
        const offset = (effect.offset as number) ?? 3;
        overlays.push(
          <div
            key="chroma"
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              filter: `drop-shadow(${offset}px 0 0 rgba(255,0,0,0.5)) drop-shadow(-${offset}px 0 0 rgba(0,0,255,0.5))`,
              mixBlendMode: "screen",
            }}
          />
        );
        break;
      }
      case "vhs_distortion": {
        const intensity = (effect.intensity as number) ?? 0.4;
        // Scanlines + slight jitter + noise overlay
        const jitter = (Math.sin(frame * 7.3) * intensity * 4);
        transform += ` translate(${jitter}px, 0)`;
        overlays.push(
          <div
            key="vhs-lines"
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage: `repeating-linear-gradient(0deg, rgba(0,0,0,${intensity * 0.3}) 0, rgba(0,0,0,${intensity * 0.3}) 1px, transparent 1px, transparent 2px)`,
              pointerEvents: "none",
              mixBlendMode: "multiply",
            }}
          />,
          <div
            key="vhs-noise"
            style={{
              position: "absolute",
              inset: 0,
              opacity: intensity * 0.5,
              backgroundImage:
                "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='1.4' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
              mixBlendMode: "overlay",
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "bloom": {
        const intensity = (effect.intensity as number) ?? 0.6;
        overlays.push(
          <div
            key="bloom"
            style={{
              position: "absolute",
              inset: 0,
              backdropFilter: `brightness(${1 + intensity * 0.3}) blur(${(effect.radius as number) ?? 10}px)`,
              WebkitBackdropFilter: `brightness(${1 + intensity * 0.3}) blur(${(effect.radius as number) ?? 10}px)`,
              opacity: intensity,
              mixBlendMode: "screen",
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "bokeh_blur": {
        const focusArea = ((effect.focus_area as number) ?? 0.3) * 100;
        const radius = (effect.radius as number) ?? 8;
        overlays.push(
          <div
            key="bokeh"
            style={{
              position: "absolute",
              inset: 0,
              backdropFilter: `blur(${radius}px)`,
              WebkitBackdropFilter: `blur(${radius}px)`,
              maskImage: `radial-gradient(circle at center, transparent ${focusArea}%, black ${focusArea + 30}%)`,
              WebkitMaskImage: `radial-gradient(circle at center, transparent ${focusArea}%, black ${focusArea + 30}%)`,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "light_leak": {
        const color = (effect.color as string) ?? "#FF8C00";
        const intensity = (effect.intensity as number) ?? 0.35;
        const speed = (effect.speed as number) ?? 1.0;
        const sweep = (((frame / fps) * speed) % (durationInFrames / fps)) / (durationInFrames / fps);
        const cx = sweep * 100;
        overlays.push(
          <div
            key="light-leak"
            style={{
              position: "absolute",
              inset: 0,
              background: `radial-gradient(ellipse at ${cx}% 50%, ${color} 0%, transparent 30%)`,
              opacity: intensity,
              mixBlendMode: "screen",
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "wipe": {
        const direction = (effect.direction as string) ?? "left";
        let clip = "";
        if (direction === "left") clip = `inset(0 ${100 - progress * 100}% 0 0)`;
        else if (direction === "right") clip = `inset(0 0 0 ${100 - progress * 100}%)`;
        else if (direction === "down") clip = `inset(0 0 ${100 - progress * 100}% 0)`;
        else clip = `inset(${100 - progress * 100}% 0 0 0)`;
        overlays.push(
          <div
            key="wipe"
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "#000",
              clipPath: clip,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "iris": {
        const direction = (effect.direction as string) ?? "in";
        const p = direction === "out" ? 1 - progress : progress;
        const radius = p * 75; // % of frame
        overlays.push(
          <div
            key="iris"
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "#000",
              clipPath: `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 0, 50% 50%, 50% 50%)`,
              // Use radial mask to cut out a hole
              maskImage: `radial-gradient(circle at center, transparent ${radius}%, black ${radius + 1}%)`,
              WebkitMaskImage: `radial-gradient(circle at center, transparent ${radius}%, black ${radius + 1}%)`,
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      case "dissolve_noise": {
        overlays.push(
          <div
            key="dissolve"
            style={{
              position: "absolute",
              inset: 0,
              opacity: progress,
              backgroundColor: "#000",
              maskImage:
                "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
              WebkitMaskImage:
                "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
              pointerEvents: "none",
            }}
          />
        );
        break;
      }
      // Effects that can't be done at the React layer (need video preprocessing):
      // - pixel_sort: per-pixel sort (would require WebGL shader)
      // - speed_ramp / freeze_frame / reverse: change clip duration (must
      //   be applied as an ffmpeg pre-pass before the Remotion stage).
      // These are silently no-ops on the Remotion path for now.
      case "pixel_sort":
      case "speed_ramp":
      case "freeze_frame":
      case "reverse":
        break;
    }
  }

  return (
    <AbsoluteFill
      style={{
        transform: transform || undefined,
        transformOrigin: "center center",
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      {overlays}
    </AbsoluteFill>
  );
};
