"use client";

import { useEffect, useRef, useState } from "react";

type AvatarStyle = {
  name: string;
  title: string;
  description: string;
};

const AVATAR_STYLES: AvatarStyle[] = [
  { name: "bounce", title: "bounce", description: "Scales up/down with audio" },
  { name: "waveform", title: "waveform", description: "Radial wave ring" },
  { name: "pulse", title: "pulse", description: "Glowing aura effect" },
  { name: "equalizer", title: "equalizer", description: "Neon retro bars" },
  { name: "xp_bliss", title: "xp_bliss", description: "Windows XP hills & notes" },
  { name: "clippy", title: "clippy", description: "Animated paperclip mascot" },
  { name: "visualizer", title: "visualizer", description: "Circular spectrum analyzer" },
  { name: "pacman", title: "pacman", description: "Arcade chomper & ghost" },
  { name: "space_invader", title: "space_invader", description: "Pixel-art alien arcade" },
  { name: "mario_block", title: "mario_block", description: "Bouncing \"?\" block with coins" },
  { name: "nyan_cat", title: "nyan_cat", description: "Rainbow trail pixel cat" },
  { name: "matrix", title: "matrix", description: "Cascading green code rain" },
  { name: "pickle_rick", title: "pickle_rick", description: "Pickle Rick with rat limbs" },
  { name: "chrome_dino", title: "chrome_dino", description: "Chrome's offline T-Rex" },
  { name: "marvin", title: "marvin", description: "Paranoid Android, depressive quotes" },
  { name: "mac128k", title: "mac128k", description: "Macintosh 128K retro green screen" },
  { name: "floppy_disk", title: "floppy_disk", description: "3.5\" floppy with 1.44 MB nostalgia" },
  { name: "bsod", title: "bsod", description: "Blue Screen of Death :(" },
  { name: "bugdroid", title: "bugdroid", description: "Android's green robot" },
  { name: "qr_code", title: "qr_code", description: "QR code pattern — SCAN ME!" },
  { name: "gpu_sweat", title: "gpu_sweat", description: "Sweating GPU with spinning fan" },
  { name: "rubber_duck", title: "rubber_duck", description: "Debugging companion duck" },
  { name: "fail_whale", title: "fail_whale", description: "Twitter's over capacity whale" },
  { name: "server_rack", title: "server_rack", description: "Overheating server with smoke" },
  { name: "cursor_hand", title: "cursor_hand", description: "Bossy pointing hand cursor" },
  { name: "vhs_tape", title: "vhs_tape", description: "VHS cassette — Be kind, rewind!" },
  { name: "cloud", title: "cloud", description: "Cute capricious cloud with rain" },
  { name: "wifi_low", title: "wifi_low", description: "One bar Wi-Fi, cuts off mid-sen—" },
  { name: "nokia3310", title: "nokia3310", description: "Indestructible Nokia with Snake" },
  { name: "cookie", title: "cookie", description: "Creepy browser cookie that knows all" },
  { name: "modem56k", title: "modem56k", description: "56k modem — psshhh-kkkk-ding" },
  { name: "esc_key", title: "esc_key", description: "Panicked Esc key — LET ME OUT!" },
  { name: "sad_mac", title: "sad_mac", description: "Dead Macintosh with X eyes" },
  { name: "usb_cable", title: "usb_cable", description: "Tangled USB — wrong side, again" },
  { name: "hourglass", title: "hourglass", description: "Slow hourglass — Please… wait…" },
  { name: "firewire", title: "firewire", description: "Forgotten cable in a drawer" },
  { name: "ai_hallucinated", title: "ai_hallucinated", description: "Glitching robot mixing facts" },
  { name: "tamagotchi", title: "tamagotchi", description: "Abandoned pet since 1998" },
  { name: "lasso_tool", title: "lasso_tool", description: "Obsessive selection tool" },
  { name: "battery_low", title: "battery_low", description: "1% battery — dying fast" },
  { name: "incognito", title: "incognito", description: "Chrome detective sees nothing" },
  { name: "rainbow_wheel", title: "rainbow_wheel", description: "Mac spinning wheel of doom" },
  { name: "error_404", title: "error_404", description: "Lost page, literally unfindable" },
  { name: "google_blob", title: "google_blob", description: "Old melted blob emoji, nostalgic" },
  { name: "bit", title: "bit", description: "Binary 0/1 — answers Yes or No" },
  { name: "pc_fan", title: "pc_fan", description: "Screaming fan — MAX RPM!" },
  { name: "captcha", title: "captcha", description: "PROVE YOU'RE HUMAN!" },
  { name: "bluetooth", title: "bluetooth", description: "Desperately searching, pairing failed" },
  { name: "registry_key", title: "registry_key", description: "Bureaucratic folder, controls all" },
  { name: "high_ping", title: "high_ping", description: "999ms — responds 10 sec late" },
  { name: "scratched_cd", title: "scratched_cd", description: "Sk-sk-skip! Stuttering CD" },
  { name: "kermit", title: "kermit", description: "None of my business… *sips tea*" },
  { name: "this_is_fine", title: "this_is_fine", description: "Dog in flames — everything is fine" },
  { name: "trollface", title: "trollface", description: "Problem? U mad bro?" },
  { name: "no_idea_dog", title: "no_idea_dog", description: "I have no idea what I'm doing" },
  { name: "surprised_pikachu", title: "surprised_pikachu", description: "Feigned surprise :O" },
  { name: "distracted_bf", title: "distracted_bf", description: "Looking at the new framework" },
  { name: "success_kid", title: "success_kid", description: "Fist pump! It compiled!" },
  { name: "expanding_brain", title: "expanding_brain", description: "Transcended the codebase" },
  { name: "doge", title: "doge", description: "Such code. Much wow. Very deploy." },
  { name: "wiki_globe", title: "wiki_globe", description: "[citation needed]" },
];

function AvatarTile({ style, isActive, onClick }: { style: AvatarStyle; isActive: boolean; onClick: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "100px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      onClick={onClick}
      className={`group relative cursor-pointer rounded-xl border overflow-hidden transition-all duration-200 ${
        isActive
          ? "border-indigo-500 ring-2 ring-indigo-500/40 scale-[1.02]"
          : "border-zinc-800 hover:border-indigo-700/60 hover:scale-[1.01]"
      }`}
    >
      <div className="aspect-video bg-black">
        {isVisible ? (
          <video
            ref={videoRef}
            className="w-full h-full object-cover"
            muted
            playsInline
            loop
            preload="none"
            onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
            onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
          >
            <source src={`/demodsl/videos/demo_avatar_${style.name}.mp4`} type="video/mp4" />
          </video>
        ) : (
          <div className="w-full h-full bg-zinc-900" />
        )}
      </div>
      <div className="px-3 py-2 bg-zinc-900/90">
        <p className="text-xs font-mono font-semibold text-zinc-200 truncate">{style.name}</p>
        <p className="text-[10px] text-zinc-500 truncate">{style.description}</p>
      </div>
      {isActive && (
        <div className="absolute top-1.5 right-1.5">
          <span className="flex h-2.5 w-2.5 rounded-full bg-indigo-500 ring-2 ring-indigo-500/30" />
        </div>
      )}
    </div>
  );
}

export function AvatarGrid() {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const selected = selectedIdx !== null ? AVATAR_STYLES[selectedIdx] : null;

  useEffect(() => {
    if (selected && detailRef.current) {
      detailRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selected]);

  return (
    <div className="space-y-6">
      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {AVATAR_STYLES.map((style, idx) => (
          <AvatarTile
            key={style.name}
            style={style}
            isActive={selectedIdx === idx}
            onClick={() => setSelectedIdx(selectedIdx === idx ? null : idx)}
          />
        ))}
      </div>

      {/* Detail panel */}
      {selected && (
        <div
          ref={detailRef}
          className="rounded-2xl border border-indigo-900/50 bg-indigo-950/10 p-6 animate-in fade-in slide-in-from-bottom-2 duration-300"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-indigo-400 bg-indigo-950 px-2.5 py-1 rounded-full uppercase tracking-wider">
                Preview
              </span>
              <span className="text-sm text-zinc-300 font-mono">{selected.name}</span>
              <span className="text-sm text-zinc-500">— {selected.description}</span>
            </div>
            <button
              onClick={() => setSelectedIdx(null)}
              className="text-zinc-500 hover:text-zinc-300 transition-colors text-lg leading-none px-2"
              aria-label="Close preview"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border border-zinc-800 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
              </div>
              <video
                key={selected.name}
                className="w-full aspect-video bg-black"
                controls
                autoPlay
                muted
                loop
                playsInline
              >
                <source src={`/demodsl/videos/demo_avatar_${selected.name}.mp4`} type="video/mp4" />
              </video>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800 bg-zinc-950/50">
                <span className="text-xs text-zinc-500 font-mono">config.yaml</span>
                <button
                  onClick={() => {
                    const yaml = `avatar:\n  style: "${selected.name}"\n  size: 120\n  shape: "circle"`;
                    navigator.clipboard?.writeText(yaml);
                  }}
                  className="text-[10px] text-zinc-600 hover:text-indigo-400 transition-colors font-mono px-2 py-0.5 rounded border border-zinc-800 hover:border-indigo-800"
                >
                  Copy
                </button>
              </div>
              <pre className="p-3 overflow-x-auto text-xs leading-relaxed">
                <code className="text-zinc-300 font-mono">{`avatar:
  style: "${selected.name}"
  size: 120
  shape: "circle"`}</code>
              </pre>
            </div>
          </div>
          {/* Navigation */}
          <div className="flex items-center justify-between mt-4">
            <button
              onClick={() => setSelectedIdx(selectedIdx !== null && selectedIdx > 0 ? selectedIdx - 1 : AVATAR_STYLES.length - 1)}
              className="text-xs text-zinc-500 hover:text-indigo-400 transition-colors font-mono flex items-center gap-1"
            >
              ← {selectedIdx !== null && selectedIdx > 0 ? AVATAR_STYLES[selectedIdx - 1].name : AVATAR_STYLES[AVATAR_STYLES.length - 1].name}
            </button>
            <span className="text-[10px] text-zinc-600">
              {selectedIdx !== null ? selectedIdx + 1 : 0} / {AVATAR_STYLES.length}
            </span>
            <button
              onClick={() => setSelectedIdx(selectedIdx !== null && selectedIdx < AVATAR_STYLES.length - 1 ? selectedIdx + 1 : 0)}
              className="text-xs text-zinc-500 hover:text-indigo-400 transition-colors font-mono flex items-center gap-1"
            >
              {selectedIdx !== null && selectedIdx < AVATAR_STYLES.length - 1 ? AVATAR_STYLES[selectedIdx + 1].name : AVATAR_STYLES[0].name} →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
