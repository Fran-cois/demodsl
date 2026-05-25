export type StyleName =
  | "tech_minimalism"
  | "vorticism"
  | "glowfi"
  | "glowfi_focus"
  | "glowfi_prism"
  | "glowfi_signal"
  | "neo_brutalism"
  | "layered_product";

export type Meta = { label: string; value: string };
export type Props = {
  style?: StyleName;
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  cta?: string;
  cta2?: string;
  accent?: string;
  meta?: Meta[];
};

const DEFAULTS = {
  eyebrow: "VOL. 04 - ISSUE 03",
  title: "Composing motion, frame by frame.",
  subtitle:
    "A reusable layout where only the animation language changes. Same content, eight different feelings.",
  cta: "Get started",
  cta2: "View docs",
  accent: "#1F6FEB",
  meta: [
    { label: "Frames", value: "1,728" },
    { label: "Layers", value: "12" },
    { label: "Render", value: "117 s" },
  ] as Meta[],
};

export type Resolved = Required<
  Pick<Props, "eyebrow" | "title" | "subtitle" | "cta" | "cta2" | "accent" | "meta">
>;

export function resolveProps(props: Props): Resolved {
  return {
    eyebrow: props.eyebrow ?? DEFAULTS.eyebrow,
    title: props.title ?? DEFAULTS.title,
    subtitle: props.subtitle ?? DEFAULTS.subtitle,
    cta: props.cta ?? DEFAULTS.cta,
    cta2: props.cta2 ?? DEFAULTS.cta2,
    accent: props.accent ?? DEFAULTS.accent,
    meta: props.meta ?? DEFAULTS.meta,
  };
}
