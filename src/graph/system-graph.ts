import { layoutDiagram } from "./layout";
import type { GraphDiagramDefinition, GraphScene, LayoutProfile } from "./model";

export type SystemGraphProfile = "desktop" | "mobile";

// Keep the blog's spatial rhythm while leaving a small margin for the portfolio artboard.
const DESKTOP_SCALE = 90 / 720;
const MOBILE_SCALE = 90 / 336;
const GLYPH_DIAMETER = 2.1;

const PROFILES: Record<SystemGraphProfile, LayoutProfile> = {
  desktop: {
    width: 100,
    nodeWidth: 152 * DESKTOP_SCALE,
    nodeHeight: 46 * DESKTOP_SCALE,
    nodeGap: 20 * DESKTOP_SCALE,
    rankGap: 60 * DESKTOP_SCALE,
    maxColumns: 4,
    direction: "auto",
    anchorWidth: GLYPH_DIAMETER,
    anchorHeight: GLYPH_DIAMETER,
  },
  mobile: {
    width: 100,
    nodeWidth: 134 * MOBILE_SCALE,
    nodeHeight: 46 * MOBILE_SCALE,
    nodeGap: 20 * MOBILE_SCALE,
    rankGap: 42 * MOBILE_SCALE,
    maxColumns: 2,
    direction: "TB",
    anchorWidth: GLYPH_DIAMETER,
    anchorHeight: GLYPH_DIAMETER,
  },
};

export const compileSystemGraph = (
  graph: GraphDiagramDefinition,
  profile: SystemGraphProfile = "desktop",
): GraphScene => layoutDiagram(graph, PROFILES[profile]);
