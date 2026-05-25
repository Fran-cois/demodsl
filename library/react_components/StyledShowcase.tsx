import { GlowFiFocusFrame, GlowFiFrame, GlowFiPrismFrame, GlowFiSignalFrame } from "./styled_showcase/frames/glowfi";
import { LayeredProductFrame, NeoBrutalismFrame, TechMinimalismFrame, VorticismFrame } from "./styled_showcase/frames/classic";
import { h } from "./styled_showcase/shared";
import type { Props, StyleName } from "./styled_showcase/types";
import { resolveProps } from "./styled_showcase/types";

export type { Meta, Props, Resolved, StyleName } from "./styled_showcase/types";

export default function StyledShowcase(props: Props) {
  const style: StyleName = props.style ?? "tech_minimalism";
  const c = resolveProps(props);

  switch (style) {
    case "vorticism":
      return h(VorticismFrame, c);
    case "glowfi":
      return h(GlowFiFrame, c);
    case "glowfi_focus":
      return h(GlowFiFocusFrame, c);
    case "glowfi_prism":
      return h(GlowFiPrismFrame, c);
    case "glowfi_signal":
      return h(GlowFiSignalFrame, c);
    case "neo_brutalism":
      return h(NeoBrutalismFrame, c);
    case "layered_product":
      return h(LayeredProductFrame, c);
    default:
      return h(TechMinimalismFrame, c);
  }
}
