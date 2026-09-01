import { layoutDiagram } from "./layout";
import type { FlowDiagramDefinition, FlowScene, LayoutProfile } from "./model";

export type SystemGraphProfile = "desktop" | "mobile";

const GLYPH_DIAMETER = 2.1;

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
  flow: FlowDiagramDefinition,
  profile: SystemGraphProfile = "desktop",
): FlowScene => layoutDiagram(flow, PROFILES[profile]) as FlowScene;
