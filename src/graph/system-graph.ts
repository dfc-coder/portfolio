import type { GraphEdge, GraphNode, SystemProject } from "../experiences/systems-projects";
import {
  compileDiagram,
  type DiagramDefinition,
  type DiagramLayoutKind,
  type DiagramProfile,
} from "./diagram-core";

export type DiagramLayoutMode = "fixed" | "auto";
export type { DiagramProfile } from "./diagram-core";

type LayoutKind = "fixed" | DiagramLayoutKind;

type CompileOptions = {
  mode?: DiagramLayoutMode;
  profile?: DiagramProfile;
};

export type CompiledGraphNode = GraphNode & {
  x: number;
  y: number;
  rank: number;
};

export type CompiledGraphEdge = GraphEdge & {
  path: string;
  labelX: number;
  labelY: number;
  feedback: boolean;
};

export type CompiledSystemGraph = {
  width: number;
  height: number;
  layout: LayoutKind;
  nodes: CompiledGraphNode[];
  edges: CompiledGraphEdge[];
};

const WIDTH = 100;
const HEIGHT = 64;

const graphNodeMap = (nodes: readonly GraphNode[]) => {
  const result = new Map<string, GraphNode>();
  for (const node of nodes) {
    if (result.has(node.id)) throw new Error(`Duplicate graph node "${node.id}".`);
    result.set(node.id, node);
  }
  return result;
};

const assertEdgeReferences = (
  edges: readonly GraphEdge[],
  nodesById: ReadonlyMap<string, GraphNode>,
) => {
  for (const edge of edges) {
    if (!nodesById.has(edge.from) || !nodesById.has(edge.to)) {
      throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
    }
  }
};

const explicitOrNarrativeFeedback = (
  edge: GraphEdge,
  nodesById: ReadonlyMap<string, GraphNode>,
) => {
  const typedEdge = edge as GraphEdge & { kind?: "default" | "feedback" };
  if (typedEdge.kind === "feedback") return true;
  const from = nodesById.get(edge.from);
  const to = nodesById.get(edge.to);
  return Boolean(from && to && to.step <= from.step);
};

const fixedRoute = (from: GraphNode, to: GraphNode) => {
  if (Math.abs(from.y - to.y) < 2) return `M ${from.x} ${from.y} H ${to.x}`;
  const middleX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} H ${middleX} V ${to.y} H ${to.x}`;
};

const compileFixed = (graph: SystemProject["graph"]): CompiledSystemGraph => {
  const nodesById = graphNodeMap(graph.nodes);
  assertEdgeReferences(graph.edges, nodesById);

  const nodes = graph.nodes.map((node) => ({ ...node, rank: node.step }));
  const positioned = new Map(nodes.map((node) => [node.id, node]));

  const edges = graph.edges.map((edge) => {
    const from = positioned.get(edge.from);
    const to = positioned.get(edge.to);
    if (!from || !to) throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);

    return {
      ...edge,
      path: edge.path ?? fixedRoute(from, to),
      labelX: (from.x + to.x) / 2,
      labelY: (from.y + to.y) / 2,
      feedback: explicitOrNarrativeFeedback(edge, nodesById),
    };
  });

  return { width: WIDTH, height: HEIGHT, layout: "fixed", nodes, edges };
};

// Adapter boundary: project content is translated into the semantic graph model;
// layout and routing decisions belong exclusively to diagram-core.
const toDefinition = (graph: SystemProject["graph"]): DiagramDefinition => {
  const nodesById = graphNodeMap(graph.nodes);
  assertEdgeReferences(graph.edges, nodesById);
  const graphWithDirection = graph as SystemProject["graph"] & { direction?: "LR" | "TB" };

  return {
    direction: graphWithDirection.direction ?? "LR",
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      kind: node.accent ? "accent" : "default",
    })),
    edges: graph.edges.map((edge) => ({
      from: edge.from,
      to: edge.to,
      label: edge.label,
      kind: explicitOrNarrativeFeedback(edge, nodesById) ? "feedback" : "default",
    })),
  };
};

const compileAutomatic = (
  graph: SystemProject["graph"],
  profile: DiagramProfile,
): CompiledSystemGraph => {
  const core = compileDiagram(toDefinition(graph), profile);
  const sourceNodes = new Map(graph.nodes.map((node) => [node.id, node]));

  const nodes = core.nodes.map((node) => {
    const source = sourceNodes.get(node.id);
    if (!source) throw new Error(`Unknown graph node "${node.id}".`);
    return { ...source, x: node.x, y: node.y, rank: node.rank };
  });

  const edges = core.edges.map((edge, index) => {
    const source = graph.edges[index];
    if (!source) throw new Error(`Missing source graph edge ${edge.from} -> ${edge.to}.`);
    return {
      ...source,
      path: edge.path,
      labelX: edge.labelX,
      labelY: edge.labelY,
      feedback: edge.feedback,
    };
  });

  return {
    width: core.width,
    height: core.height,
    layout: core.layout,
    nodes,
    edges,
  };
};

export const compileSystemGraph = (
  graph: SystemProject["graph"],
  options: CompileOptions = {},
): CompiledSystemGraph => {
  if ((options.mode ?? "fixed") === "fixed") return compileFixed(graph);
  return compileAutomatic(graph, options.profile ?? "desktop");
};
