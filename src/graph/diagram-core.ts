export type DiagramDirection = "TB" | "LR";
export type DiagramNodeKind = "default" | "terminal" | "accent" | "muted";
export type DiagramEdgeKind = "default" | "feedback";
export type DiagramLayoutKind = "serpentine" | "layered-tb" | "layered-lr" | "fanout";
export type DiagramProfile = "desktop" | "mobile";

export type DiagramNode = {
  id: string;
  label: string;
  kind?: DiagramNodeKind;
};

export type DiagramEdge = {
  from: string;
  to: string;
  label?: string;
  kind?: DiagramEdgeKind;
};

export type DiagramDefinition = {
  direction: DiagramDirection;
  nodes: DiagramNode[];
  edges: DiagramEdge[];
};

export type PositionedDiagramNode = DiagramNode & {
  x: number;
  y: number;
  rank: number;
};

export type RoutedDiagramEdge = DiagramEdge & {
  path: string;
  labelX: number;
  labelY: number;
  feedback: boolean;
};

export type CompiledDiagram = {
  width: number;
  height: number;
  layout: DiagramLayoutKind;
  nodes: PositionedDiagramNode[];
  edges: RoutedDiagramEdge[];
};

type LayoutProfile = {
  width: number;
  height: number;
  maxColumns: number;
  vertical: boolean;
};

const WIDTH = 100;
const HEIGHT = 64;
const NODE_WIDTH = 10;
const NODE_HEIGHT = 5;
const COLUMN_GAP = 4;
const RANK_GAP = 4;
const STACK_GAP = 4;
const MARGIN_X = 6;
const MARGIN_Y = 6;
const PORT = 1.6;
const FEEDBACK_LANE_GAP = 4;
const LONG_EDGE_LANE_GAP = 3;

const PROFILES: Record<DiagramProfile, LayoutProfile> = {
  desktop: { width: WIDTH, height: HEIGHT, maxColumns: 4, vertical: false },
  mobile: { width: WIDTH, height: HEIGHT, maxColumns: 2, vertical: true },
};

const isFeedback = (edge: DiagramEdge) => (edge.kind ?? "default") === "feedback";

const distribute = (count: number, min: number, max: number) => {
  if (count <= 0) return [];
  if (count === 1) return [(min + max) / 2];
  const gap = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, index) => min + gap * index);
};

const validate = (graph: DiagramDefinition) => {
  const ids = new Set<string>();
  for (const node of graph.nodes) {
    if (ids.has(node.id)) throw new Error(`Duplicate graph node "${node.id}".`);
    ids.add(node.id);
  }
  for (const edge of graph.edges) {
    if (!ids.has(edge.from) || !ids.has(edge.to)) {
      throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);
    }
  }
};

const buildRanks = (graph: DiagramDefinition) => {
  const order = new Map(graph.nodes.map((node, index) => [node.id, index]));
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(graph.nodes.map((node) => [node.id, [] as string[]]));

  for (const edge of graph.edges) {
    if (isFeedback(edge)) continue;
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from)?.push(edge.to);
  }

  const queue = graph.nodes
    .filter((node) => (indegree.get(node.id) ?? 0) === 0)
    .map((node) => node.id);
  const rankById = new Map(graph.nodes.map((node) => [node.id, 0]));
  let visited = 0;

  while (queue.length) {
    queue.sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
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
    throw new Error("Graph contains a structural cycle. Mark return relations as feedback.");
  }

  return rankById;
};

const groupRanks = (graph: DiagramDefinition, rankById: ReadonlyMap<string, number>) => {
  const maxRank = Math.max(...graph.nodes.map((node) => rankById.get(node.id) ?? 0));
  const ranks: DiagramNode[][] = Array.from({ length: maxRank + 1 }, () => []);
  for (const node of graph.nodes) ranks[rankById.get(node.id) ?? 0]?.push(node);
  return ranks;
};

const defaultSerpentineColumns = (count: number) => {
  if (count <= 3) return Math.max(1, count);
  if (count === 4) return 2;
  if (count <= 6) return 3;
  return 4;
};

const serpentineLayout = (
  ranks: readonly (readonly DiagramNode[])[],
  rankById: ReadonlyMap<string, number>,
  profile: LayoutProfile,
): PositionedDiagramNode[] => {
  const ordered = ranks.flat();
  const columns = Math.min(defaultSerpentineColumns(ordered.length), profile.maxColumns);
  const rows: DiagramNode[][] = [];
  for (let index = 0; index < ordered.length; index += columns) {
    rows.push(ordered.slice(index, index + columns));
  }

  const ys = distribute(rows.length, MARGIN_Y + NODE_HEIGHT / 2, profile.height - MARGIN_Y - NODE_HEIGHT / 2);
  return rows.flatMap((row, rowIndex) => {
    const rowWidth = row.length * NODE_WIDTH + Math.max(0, row.length - 1) * COLUMN_GAP;
    const startX = (profile.width - rowWidth) / 2 + NODE_WIDTH / 2;

    return row.map((node, itemIndex) => {
      const visualIndex = rowIndex % 2 === 0 ? itemIndex : row.length - 1 - itemIndex;
      return {
        ...node,
        x: startX + visualIndex * (NODE_WIDTH + COLUMN_GAP),
        y: ys[rowIndex] ?? profile.height / 2,
        rank: rankById.get(node.id) ?? 0,
      };
    });
  });
};

const layeredTbLayout = (
  ranks: readonly (readonly DiagramNode[])[],
  rankById: ReadonlyMap<string, number>,
  profile: LayoutProfile,
): PositionedDiagramNode[] => {
  const rows: { nodes: readonly DiagramNode[]; rank: number }[] = [];
  ranks.forEach((rank, semanticRank) => {
    for (let index = 0; index < rank.length; index += profile.maxColumns) {
      rows.push({ nodes: rank.slice(index, index + profile.maxColumns), rank: semanticRank });
    }
  });

  const ys = distribute(rows.length, MARGIN_Y + NODE_HEIGHT / 2, profile.height - MARGIN_Y - NODE_HEIGHT / 2);
  return rows.flatMap((row, rowIndex) => {
    const rowWidth = row.nodes.length * NODE_WIDTH + Math.max(0, row.nodes.length - 1) * COLUMN_GAP;
    const startX = (profile.width - rowWidth) / 2 + NODE_WIDTH / 2;

    return row.nodes.map((node, index) => ({
      ...node,
      x: startX + index * (NODE_WIDTH + COLUMN_GAP),
      y: ys[rowIndex] ?? profile.height / 2,
      rank: rankById.get(node.id) ?? row.rank,
    }));
  });
};

const layeredLrLayout = (
  ranks: readonly (readonly DiagramNode[])[],
  rankById: ReadonlyMap<string, number>,
  profile: LayoutProfile,
): PositionedDiagramNode[] => {
  const contentWidth = ranks.length * NODE_WIDTH + Math.max(0, ranks.length - 1) * RANK_GAP;
  const startX = (profile.width - contentWidth) / 2 + NODE_WIDTH / 2;

  return ranks.flatMap((rank, rankIndex) => {
    const columnHeight = rank.length * NODE_HEIGHT + Math.max(0, rank.length - 1) * STACK_GAP;
    const startY = (profile.height - columnHeight) / 2 + NODE_HEIGHT / 2;
    return rank.map((node, index) => ({
      ...node,
      x: startX + rankIndex * (NODE_WIDTH + RANK_GAP),
      y: startY + index * (NODE_HEIGHT + STACK_GAP),
      rank: rankById.get(node.id) ?? rankIndex,
    }));
  });
};

const fanoutHub = (graph: DiagramDefinition) => {
  const structural = graph.edges.filter((edge) => !isFeedback(edge));
  if (graph.nodes.length < 5 || structural.length !== graph.nodes.length - 1) return undefined;
  const outgoing = new Map(graph.nodes.map((node) => [node.id, 0]));
  for (const edge of structural) outgoing.set(edge.from, (outgoing.get(edge.from) ?? 0) + 1);
  return graph.nodes.find((node) => (outgoing.get(node.id) ?? 0) === graph.nodes.length - 1)?.id;
};

const fanoutLayout = (
  graph: DiagramDefinition,
  hubId: string,
  rankById: ReadonlyMap<string, number>,
  profile: LayoutProfile,
): PositionedDiagramNode[] => {
  const hub = graph.nodes.find((node) => node.id === hubId);
  if (!hub) throw new Error(`Unknown fanout hub "${hubId}".`);
  const children = graph.nodes.filter((node) => node.id !== hubId);
  const rows = Math.ceil(children.length / 2);
  const ys = distribute(rows, 30, profile.height - MARGIN_Y - NODE_HEIGHT / 2);
  const result: PositionedDiagramNode[] = [
    { ...hub, x: profile.width / 2, y: MARGIN_Y + NODE_HEIGHT / 2, rank: rankById.get(hub.id) ?? 0 },
  ];

  children.forEach((node, index) => {
    result.push({
      ...node,
      x: index % 2 === 0 ? profile.width * 0.30 : profile.width * 0.70,
      y: ys[Math.floor(index / 2)] ?? profile.height / 2,
      rank: rankById.get(node.id) ?? 1,
    });
  });
  return result;
};

const chooseLayout = (
  graph: DiagramDefinition,
  ranks: readonly (readonly DiagramNode[])[],
  profile: LayoutProfile,
): DiagramLayoutKind => {
  if (fanoutHub(graph)) return "fanout";
  if (ranks.every((rank) => rank.length === 1)) return "serpentine";

  // Feedback-heavy graphs read more clearly as compact vertical systems. This
  // is the same structural idea used by the blog: feedback does not drive DAG ranks.
  if (graph.edges.some(isFeedback)) return "layered-tb";

  const lrWidth = ranks.length * NODE_WIDTH + Math.max(0, ranks.length - 1) * RANK_GAP;
  const canUseLr =
    !profile.vertical &&
    graph.direction === "LR" &&
    Math.max(...ranks.map((rank) => rank.length)) <= 3 &&
    lrWidth <= profile.width - MARGIN_X * 2;

  return canUseLr ? "layered-lr" : "layered-tb";
};

const nodeMap = (nodes: readonly PositionedDiagramNode[]) => new Map(nodes.map((node) => [node.id, node]));

const regularRoute = (from: PositionedDiagramNode, to: PositionedDiagramNode) => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;

  if (Math.abs(dx) > Math.abs(dy)) {
    const direction = Math.sign(dx) || 1;
    const startX = from.x + PORT * direction;
    const endX = to.x - PORT * direction;
    const middleX = (startX + endX) / 2;
    return {
      path: `M ${startX} ${from.y} H ${middleX} V ${to.y} H ${endX}`,
      labelX: middleX,
      labelY: (from.y + to.y) / 2 - 2,
    };
  }

  const direction = Math.sign(dy) || 1;
  const startY = from.y + PORT * direction;
  const endY = to.y - PORT * direction;
  const middleY = (startY + endY) / 2;
  return {
    path: `M ${from.x} ${startY} V ${middleY} H ${to.x} V ${endY}`,
    labelX: (from.x + to.x) / 2 + 2,
    labelY: middleY - 1.5,
  };
};

const longRoute = (
  from: PositionedDiagramNode,
  to: PositionedDiagramNode,
  index: number,
  profile: LayoutProfile,
) => {
  const laneX = profile.width - MARGIN_X / 2 - index * LONG_EDGE_LANE_GAP;
  return {
    path: `M ${from.x + PORT} ${from.y} H ${laneX} V ${to.y} H ${to.x + PORT}`,
    labelX: laneX - 2,
    labelY: (from.y + to.y) / 2 - 2,
  };
};

const feedbackRoute = (
  from: PositionedDiagramNode,
  to: PositionedDiagramNode,
  nodes: readonly PositionedDiagramNode[],
  index: number,
) => {
  const leftBoundary = Math.min(...nodes.map((node) => node.x - NODE_WIDTH / 2));
  const laneX = Math.max(3, leftBoundary - 4 - index * FEEDBACK_LANE_GAP);
  const startY = from.y - PORT;
  const endY = to.y + PORT;
  const bend = Math.min(7, Math.max(4, Math.abs(startY - endY) * 0.18));
  return {
    path: `M ${from.x} ${startY} C ${laneX} ${startY - bend} ${laneX} ${endY + bend} ${to.x} ${endY}`,
    labelX: laneX + 2,
    labelY: (startY + endY) / 2 - 1,
  };
};

const routeEdges = (
  graph: DiagramDefinition,
  nodes: readonly PositionedDiagramNode[],
  layout: DiagramLayoutKind,
  profile: LayoutProfile,
): RoutedDiagramEdge[] => {
  const byId = nodeMap(nodes);
  let longIndex = 0;
  let feedbackIndex = 0;

  return graph.edges.map((edge) => {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    if (!from || !to) throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);

    const feedback = isFeedback(edge);
    const route = feedback
      ? feedbackRoute(from, to, nodes, feedbackIndex++)
      : to.rank - from.rank > 1
        ? longRoute(from, to, longIndex++, profile)
        : regularRoute(from, to);

    return { ...edge, ...route, feedback };
  });
};

export const compileDiagram = (
  graph: DiagramDefinition,
  profileName: DiagramProfile = "desktop",
): CompiledDiagram => {
  validate(graph);
  const profile = PROFILES[profileName];
  const rankById = buildRanks(graph);
  const ranks = groupRanks(graph, rankById);
  const hub = fanoutHub(graph);
  const layout = chooseLayout(graph, ranks, profile);

  const nodes = layout === "fanout" && hub
    ? fanoutLayout(graph, hub, rankById, profile)
    : layout === "serpentine"
      ? serpentineLayout(ranks, rankById, profile)
      : layout === "layered-lr"
        ? layeredLrLayout(ranks, rankById, profile)
        : layeredTbLayout(ranks, rankById, profile);

  return {
    width: profile.width,
    height: profile.height,
    layout,
    nodes,
    edges: routeEdges(graph, nodes, layout, profile),
  };
};
