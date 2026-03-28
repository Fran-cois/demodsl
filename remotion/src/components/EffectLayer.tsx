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
