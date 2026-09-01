import type { GraphEdge, GraphNode, SystemProject } from "../experiences/systems-projects";

export type DiagramLayoutMode = "fixed" | "auto";
export type DiagramProfile = "desktop" | "mobile";

type LayoutKind = "fixed" | "layered-lr" | "layered-tb";

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
  width: 100;
  height: 64;
  layout: LayoutKind;
  nodes: CompiledGraphNode[];
  edges: CompiledGraphEdge[];
};

const WIDTH = 100 as const;
const HEIGHT = 64 as const;
const CENTER_Y = HEIGHT / 2;
const DESKTOP_X_MIN = 7;
const DESKTOP_X_MAX = 93;
const DESKTOP_Y_MIN = 12;
const DESKTOP_Y_MAX = 52;
const MOBILE_X_MIN = 24;
const MOBILE_X_MAX = 76;
const MOBILE_Y_MIN = 7;
const MOBILE_Y_MAX = 57;

const distribute = (count: number, min: number, max: number): number[] => {
  if (count <= 0) return [];
  if (count === 1) return [(min + max) / 2];

  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, index) => min + step * index);
};

const graphNodeMap = (nodes: readonly GraphNode[]) => {
  const result = new Map<string, GraphNode>();

  for (const node of nodes) {
    if (result.has(node.id)) {
      throw new Error(`Duplicate graph node "${node.id}".`);
    }
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

const isFeedbackEdge = (
  edge: GraphEdge,
  nodesById: ReadonlyMap<string, GraphNode>,
) => {
  const typedEdge = edge as GraphEdge & { kind?: "default" | "feedback" };
  if (typedEdge.kind === "feedback") return true;

  const from = nodesById.get(edge.from);
  const to = nodesById.get(edge.to);
  return Boolean(from && to && to.step <= from.step);
};

const buildRanks = (
  graph: SystemProject["graph"],
  nodesById: ReadonlyMap<string, GraphNode>,
) => {
  const nodeOrder = new Map(graph.nodes.map((node, index) => [node.id, index]));
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(graph.nodes.map((node) => [node.id, [] as string[]]));

  for (const edge of graph.edges) {
    if (isFeedbackEdge(edge, nodesById)) continue;
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from)?.push(edge.to);
  }

  const queue = graph.nodes
    .filter((node) => (indegree.get(node.id) ?? 0) === 0)
    .map((node) => node.id);
  const rankById = new Map(graph.nodes.map((node) => [node.id, 0]));
  let visited = 0;

  while (queue.length > 0) {
    queue.sort((left, right) => (nodeOrder.get(left) ?? 0) - (nodeOrder.get(right) ?? 0));
    const current = queue.shift();
    if (!current) break;

    visited += 1;
    for (const target of outgoing.get(current) ?? []) {
      rankById.set(
        target,
        Math.max(rankById.get(target) ?? 0, (rankById.get(current) ?? 0) + 1),
      );
      const remaining = (indegree.get(target) ?? 0) - 1;
      indegree.set(target, remaining);
      if (remaining === 0) queue.push(target);
    }
  }

  if (visited !== graph.nodes.length) {
    throw new Error("Graph contains a structural cycle. Mark backward relations as feedback.");
  }

  return rankById;
};

const groupRanks = (
  nodes: readonly GraphNode[],
  rankById: ReadonlyMap<string, number>,
) => {
  const maxRank = Math.max(...nodes.map((node) => rankById.get(node.id) ?? 0));
  const ranks: GraphNode[][] = Array.from({ length: maxRank + 1 }, () => []);

  for (const node of nodes) {
    ranks[rankById.get(node.id) ?? 0]?.push(node);
  }

  return ranks;
};

const layeredLr = (
  ranks: readonly (readonly GraphNode[])[],
  rankById: ReadonlyMap<string, number>,
): CompiledGraphNode[] => {
  const xs = distribute(ranks.length, DESKTOP_X_MIN, DESKTOP_X_MAX);

  return ranks.flatMap((rank, rankIndex) => {
    const ys = distribute(rank.length, DESKTOP_Y_MIN, DESKTOP_Y_MAX);
    return rank.map((node, index) => ({
      ...node,
      x: xs[rankIndex] ?? WIDTH / 2,
      y: ys[index] ?? CENTER_Y,
      rank: rankById.get(node.id) ?? rankIndex,
    }));
  });
};

const layeredTb = (
  ranks: readonly (readonly GraphNode[])[],
  rankById: ReadonlyMap<string, number>,
  profile: DiagramProfile,
): CompiledGraphNode[] => {
  const maxColumns = profile === "mobile" ? 2 : 4;
  const rows: { nodes: readonly GraphNode[]; rank: number }[] = [];

  ranks.forEach((rank, semanticRank) => {
    for (let index = 0; index < rank.length; index += maxColumns) {
      rows.push({ nodes: rank.slice(index, index + maxColumns), rank: semanticRank });
    }
  });

  const ys = distribute(rows.length, MOBILE_Y_MIN, MOBILE_Y_MAX);
  return rows.flatMap((row, rowIndex) => {
    const minX = row.nodes.length === 1 ? WIDTH / 2 : MOBILE_X_MIN;
    const maxX = row.nodes.length === 1 ? WIDTH / 2 : MOBILE_X_MAX;
    const xs = distribute(row.nodes.length, minX, maxX);

    return row.nodes.map((node, index) => ({
      ...node,
      x: xs[index] ?? WIDTH / 2,
      y: ys[rowIndex] ?? CENTER_Y,
      rank: rankById.get(node.id) ?? row.rank,
    }));
  });
};

const resolveAutomaticLayout = (
  graph: SystemProject["graph"],
  profile: DiagramProfile,
  rankById: ReadonlyMap<string, number>,
) => {
  const ranks = groupRanks(graph.nodes, rankById);
  const direction = (graph as SystemProject["graph"] & { direction?: "LR" | "TB" }).direction ?? "LR";
  const canUseLr =
    profile === "desktop" &&
    direction === "LR" &&
    ranks.length <= 6 &&
    Math.max(...ranks.map((rank) => rank.length)) <= 3;

  return canUseLr
    ? { kind: "layered-lr" as const, nodes: layeredLr(ranks, rankById) }
    : { kind: "layered-tb" as const, nodes: layeredTb(ranks, rankById, profile) };
};

const orthogonalRoute = (
  from: CompiledGraphNode,
  to: CompiledGraphNode,
  layout: LayoutKind,
) => {
  if (Math.abs(from.y - to.y) < 1) {
    return `M ${from.x} ${from.y} H ${to.x}`;
  }
  if (Math.abs(from.x - to.x) < 1) {
    return `M ${from.x} ${from.y} V ${to.y}`;
  }

  if (layout === "layered-tb") {
    const midY = (from.y + to.y) / 2;
    return `M ${from.x} ${from.y} V ${midY} H ${to.x} V ${to.y}`;
  }

  const midX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} H ${midX} V ${to.y} H ${to.x}`;
};

const feedbackRoute = (from: CompiledGraphNode, to: CompiledGraphNode) => {
  const laneX = 2;
  const verticalBend = Math.min(12, Math.max(5, Math.abs(from.y - to.y) * 0.22));
  return `M ${from.x} ${from.y} C ${laneX} ${from.y - verticalBend} ${laneX} ${to.y + verticalBend} ${to.x} ${to.y}`;
};

const compileFixed = (graph: SystemProject["graph"]): CompiledSystemGraph => {
  const nodesById = graphNodeMap(graph.nodes);
  assertEdgeReferences(graph.edges, nodesById);

  const nodes = graph.nodes.map((node) => ({ ...node, rank: node.step }));
  const positionedById = new Map(nodes.map((node) => [node.id, node]));

  for (const node of nodes) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) {
      throw new Error(`Fixed graph node "${node.id}" requires x/y coordinates.`);
    }
  }

  const edges = graph.edges.map((edge) => {
    const from = positionedById.get(edge.from);
    const to = positionedById.get(edge.to);
    if (!from || !to) {
      throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
    }

    const path = edge.path ?? orthogonalRoute(from, to, "fixed");
    return {
      ...edge,
      path,
      labelX: (from.x + to.x) / 2,
      labelY: (from.y + to.y) / 2,
      feedback: isFeedbackEdge(edge, nodesById),
    };
  });

  return { width: WIDTH, height: HEIGHT, layout: "fixed", nodes, edges };
};

const compileAutomatic = (
  graph: SystemProject["graph"],
  profile: DiagramProfile,
): CompiledSystemGraph => {
  const nodesById = graphNodeMap(graph.nodes);
  assertEdgeReferences(graph.edges, nodesById);
  const rankById = buildRanks(graph, nodesById);
  const layout = resolveAutomaticLayout(graph, profile, rankById);
  const positionedById = new Map(layout.nodes.map((node) => [node.id, node]));

  const edges = graph.edges.map((edge) => {
    const from = positionedById.get(edge.from);
    const to = positionedById.get(edge.to);
    if (!from || !to) {
      throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
    }

    const feedback = isFeedbackEdge(edge, nodesById);
    return {
      ...edge,
      path: feedback ? feedbackRoute(from, to) : orthogonalRoute(from, to, layout.kind),
      labelX: feedback ? 7 : (from.x + to.x) / 2,
      labelY: (from.y + to.y) / 2,
      feedback,
    };
  });

  return {
    width: WIDTH,
    height: HEIGHT,
    layout: layout.kind,
    nodes: layout.nodes,
    edges,
  };
};

export const compileSystemGraph = (
  graph: SystemProject["graph"],
  options: CompileOptions = {},
): CompiledSystemGraph => {
  const mode = options.mode ?? "fixed";
  if (mode === "fixed") return compileFixed(graph);
  return compileAutomatic(graph, options.profile ?? "desktop");
};
