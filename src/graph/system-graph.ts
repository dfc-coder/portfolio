import type { GraphEdge, GraphNode, SystemProject } from "../experiences/systems-projects";

export type CompiledGraphEdge = GraphEdge & {
  path: string;
  labelX: number;
  labelY: number;
};

export type CompiledSystemGraph = {
  width: 100;
  height: 64;
  nodes: GraphNode[];
  edges: CompiledGraphEdge[];
};

const resolveEdgePath = (
  nodesById: ReadonlyMap<string, GraphNode>,
  edge: GraphEdge,
) => {
  if (edge.path) return edge.path;

  const from = nodesById.get(edge.from);
  const to = nodesById.get(edge.to);
  if (!from || !to) {
    throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
  }

  if (Math.abs(from.y - to.y) < 2) {
    return `M ${from.x} ${from.y} H ${to.x}`;
  }

  const midX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} H ${midX} V ${to.y} H ${to.x}`;
};

export const compileSystemGraph = (
  graph: SystemProject["graph"],
): CompiledSystemGraph => {
  const nodes = graph.nodes.map((node) => ({ ...node }));
  const nodesById = new Map(nodes.map((node) => [node.id, node]));

  const edges = graph.edges.map((edge) => {
    const from = nodesById.get(edge.from);
    const to = nodesById.get(edge.to);
    if (!from || !to) {
      throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
    }

    return {
      ...edge,
      path: resolveEdgePath(nodesById, edge),
      labelX: (from.x + to.x) / 2,
      labelY: (from.y + to.y) / 2,
    };
  });

  return {
    width: 100,
    height: 64,
    nodes,
    edges,
  };
};
