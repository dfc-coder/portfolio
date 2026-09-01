import { layoutDiagram } from "./layout";
import type { GraphDiagramDefinition, GraphScene, LayoutProfile } from "./model";

export type SystemGraphProfile = "desktop" | "mobile";

const PROFILES: Record<SystemGraphProfile, LayoutProfile> = {
  desktop: {
    width: 134,
    nodeWidth: 15,
    nodeHeight: 7,
    nodeGap: 6,
    rankGap: 6,
    maxColumns: 4,
    direction: "auto",
  },
  mobile: {
    width: 100,
    nodeWidth: 16,
    nodeHeight: 8,
    nodeGap: 8,
    rankGap: 10,
    maxColumns: 2,
    direction: "TB",
  },
};

export const compileSystemGraph = (
  graph: GraphDiagramDefinition,
  profile: SystemGraphProfile = "desktop",
): GraphScene => layoutDiagram(graph, PROFILES[profile]);
