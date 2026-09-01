import { layoutDiagram } from "./layout";
import type { GraphDiagramDefinition, GraphScene, LayoutProfile } from "./model";

export type SystemGraphProfile = "desktop" | "mobile";

const GLYPH_DIAMETER = 2.1;

// Portfolio Systems are read as architecture maps: ranks form horizontal columns on desktop
// and vertical rows on mobile. The small virtual footprint keeps 5–6 ranks readable without
// collapsing the scene into a top-to-bottom tower.
const PROFILES: Record<SystemGraphProfile, LayoutProfile> = {
  desktop: {
    width: 100,
    nodeWidth: 6,
    nodeHeight: 5,
    nodeGap: 8,
    rankGap: 9,
    maxColumns: 4,
    direction: "LR",
    anchorWidth: GLYPH_DIAMETER,
    anchorHeight: GLYPH_DIAMETER,
  },
  mobile: {
    width: 100,
    nodeWidth: 12,
    nodeHeight: 7,
    nodeGap: 8,
    rankGap: 10,
    maxColumns: 3,
    direction: "TB",
    anchorWidth: GLYPH_DIAMETER,
    anchorHeight: GLYPH_DIAMETER,
  },
};

export const compileSystemGraph = (
  graph: GraphDiagramDefinition,
  profile: SystemGraphProfile = "desktop",
): GraphScene => layoutDiagram(graph, PROFILES[profile]);
