export type GraphDirection = "LR" | "TB";
export type GraphEdgeKind = "default" | "feedback";
export type GraphProfileName = "desktop" | "mobile";

export type SystemGraphNode = {
  id: string;
  label: string;
  step: number;
  accent?: boolean;
};

export type SystemGraphEdge = {
  from: string;
  to: string;
  step: number;
  label?: string;
  kind?: GraphEdgeKind;
};

export type SystemGraphDefinition = {
  direction?: GraphDirection;
  nodes: SystemGraphNode[];
  edges: SystemGraphEdge[];
};

export type PositionedSystemNode = SystemGraphNode & {
  x: number;
  y: number;
  rank: number;
};

export type RoutedSystemEdge = SystemGraphEdge & {
  path: string;
  labelX: number;
  labelY: number;
};

export type CompiledSystemGraph = {
  width: number;
  height: number;
  nodes: PositionedSystemNode[];
  edges: RoutedSystemEdge[];
};

type LayoutProfile = {
  maxColumns: number;
  vertical: boolean;
};

const WIDTH = 100;
const HEIGHT = 64;
const X_MARGIN = 7;
const Y_MARGIN = 8;

const PROFILES: Record<GraphProfileName, LayoutProfile> = {
  desktop: { maxColumns: 4, vertical: false },
  mobile: { maxColumns: 2, vertical: true },
};

const isFeedback = (edge: SystemGraphEdge) => edge.kind === "feedback";

const buildRanks = (graph: SystemGraphDefinition) => {
  const nodeIds = new Set(graph.nodes.map((node) => node.id));
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(graph.nodes.map((node) => [node.id, [] as string[]]));
  const rankById = new Map(graph.nodes.map((node) => [node.id, 0]));

  for (const edge of graph.edges) {
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) {
      throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
    }
    if (isFeedback(edge)) continue;
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from)?.push(edge.to);
  }

  const order = new Map(graph.nodes.map((node, index) => [node.id, index]));
  const queue = graph.nodes
    .filter((node) => (indegree.get(node.id) ?? 0) === 0)
    .map((node) => node.id);
  let visited = 0;

  while (queue.length > 0) {
    queue.sort((left, right) => (order.get(left) ?? 0) - (order.get(right) ?? 0));
    const current = queue.shift();
    if (!current) break;
    visited += 1;

    for (const target of outgoing.get(current) ?? []) {
      rankById.set(target, Math.max(rankById.get(target) ?? 0, (rankById.get(current) ?? 0) + 1));
      const remaining = (indegree.get(target) ?? 0) - 1;
      indegree.set(target, remaining);
      if (remaining === 0) queue.push(target);
    }
  }

  if (visited !== graph.nodes.length) {
    throw new Error("Graph contains a structural cycle. Mark return relationships as feedback edges.");
  }

  return rankById;
};

const ranksFrom = (graph: SystemGraphDefinition, rankById: Map<string, number>) => {
  const count = Math.max(0, ...rankById.values()) + 1;
  const ranks: SystemGraphNode[][] = Array.from({ length: count }, () => []);
  for (const node of graph.nodes) ranks[rankById.get(node.id) ?? 0]?.push(node);
  return ranks;
};

const spread = (count: number, min: number, max: number) => {
  if (count <= 1) return [(min + max) / 2];
  const gap = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, index) => min + index * gap);
};

const horizontalLayout = (
  ranks: SystemGraphNode[][],
  rankById: Map<string, number>,
): PositionedSystemNode[] => {
  const xs = spread(ranks.length, X_MARGIN, WIDTH - X_MARGIN);

  return ranks.flatMap((rank, rankIndex) => {
    const ys = spread(rank.length, Y_MARGIN + 5, HEIGHT - Y_MARGIN - 5);
    return rank.map((node, index) => ({
      ...node,
      x: xs[rankIndex] ?? WIDTH / 2,
      y: ys[index] ?? HEIGHT / 2,
      rank: rankById.get(node.id) ?? 0,
    }));
  });
};

const verticalLayout = (
  ranks: SystemGraphNode[][],
  rankById: Map<string, number>,
  maxColumns: number,
): PositionedSystemNode[] => {
  const rows = ranks.flatMap((rank) => {
    const chunks: SystemGraphNode[][] = [];
    for (let index = 0; index < rank.length; index += maxColumns) {
      chunks.push(rank.slice(index, index + maxColumns));
    }
    return chunks;
  });
  const ys = spread(rows.length, Y_MARGIN, HEIGHT - Y_MARGIN);

  return rows.flatMap((row, rowIndex) => {
    const xs = row.length === 1
      ? [WIDTH / 2]
      : spread(row.length, 28, 72);
    return row.map((node, index) => ({
      ...node,
      x: xs[index] ?? WIDTH / 2,
      y: ys[rowIndex] ?? HEIGHT / 2,
      rank: rankById.get(node.id) ?? 0,
    }));
  });
};

const regularRoute = (
  from: PositionedSystemNode,
  to: PositionedSystemNode,
  vertical: boolean,
) => {
  if (vertical) {
    const middleY = (from.y + to.y) / 2;
    return {
      path: `M ${from.x} ${from.y} V ${middleY} H ${to.x} V ${to.y}`,
      labelX: (from.x + to.x) / 2 + 2.4,
      labelY: middleY - 1.8,
    };
  }

  const middleX = (from.x + to.x) / 2;
  return {
    path: `M ${from.x} ${from.y} H ${middleX} V ${to.y} H ${to.x}`,
    labelX: middleX,
    labelY: (from.y + to.y) / 2 - 2.4,
  };
};

const feedbackRoute = (
  from: PositionedSystemNode,
  to: PositionedSystemNode,
  vertical: boolean,
  index: number,
) => {
  if (vertical) {
    const laneX = index % 2 === 0 ? 5 : WIDTH - 5;
    return {
      path: `M ${from.x} ${from.y} H ${laneX} V ${to.y} H ${to.x}`,
      labelX: laneX + (laneX < WIDTH / 2 ? 3.5 : -3.5),
      labelY: (from.y + to.y) / 2,
    };
  }

  const laneY = index % 2 === 0 ? HEIGHT - 4 : 4;
  return {
    path: `M ${from.x} ${from.y} V ${laneY} H ${to.x} V ${to.y}`,
    labelX: (from.x + to.x) / 2,
    labelY: laneY + (laneY < HEIGHT / 2 ? 2.5 : -2.5),
  };
};

export const compileSystemGraph = (
  graph: SystemGraphDefinition,
  profileName: GraphProfileName,
): CompiledSystemGraph => {
  const profile = PROFILES[profileName];
  const rankById = buildRanks(graph);
  const ranks = ranksFrom(graph, rankById);
  const nodes = profile.vertical
    ? verticalLayout(ranks, rankById, profile.maxColumns)
    : horizontalLayout(ranks, rankById);
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  let feedbackIndex = 0;

  const edges = graph.edges.map((edge) => {
    const from = nodesById.get(edge.from);
    const to = nodesById.get(edge.to);
    if (!from || !to) throw new Error(`Unable to route edge ${edge.from} -> ${edge.to}.`);

    const route = isFeedback(edge)
      ? feedbackRoute(from, to, profile.vertical, feedbackIndex++)
      : regularRoute(from, to, profile.vertical);

    return { ...edge, ...route };
  });

  return { width: WIDTH, height: HEIGHT, nodes, edges };
};
