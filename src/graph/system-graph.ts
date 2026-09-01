import { layoutDiagram } from "./layout";
import type { GraphDiagramDefinition, GraphScene, LayoutProfile } from "./model";

export type SystemGraphProfile = "desktop" | "mobile";

const PROFILES: Record<SystemGraphProfile, LayoutProfile> = {
  desktop: {
    width: 100,
    nodeWidth: 10,
    nodeHeight: 6,
    nodeGap: 5,
    rankGap: 3,
    maxColumns: 4,
    direction: "auto",
  },
  mobile: {
    width: 100,
    nodeWidth: 14,
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
