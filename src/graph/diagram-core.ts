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
  id: DiagramProfile;
  width: number;
  maxColumns: number;
  vertical: boolean;
};

type SizedNode = {
  node: DiagramNode;
  width: number;
  height: number;
  rank: number;
};

type PositionedInternalNode = DiagramNode & {
  x: number;
  y: number;
  width: number;
  height: number;
  rank: number;
};

type InternalLayout = {
  kind: DiagramLayoutKind;
  width: number;
  height: number;
  nodes: PositionedInternalNode[];
  ranks: PositionedInternalNode[][];
};

type EdgeRoute = {
  path: string;
  labelX: number;
  labelY: number;
};

const ARTBOARD_WIDTH = 720;
const MOBILE_ARTBOARD_WIDTH = 336;
const ARTBOARD_MIN_HEIGHT = 220;
const NODE_WIDTH = 152;
const NODE_LINE_HEIGHT = 18;
const NODE_PADDING_Y = 14;
const NODE_HEIGHT = NODE_LINE_HEIGHT + NODE_PADDING_Y * 2;
const MAX_LABEL_CHARS = 20;
const COLUMN_GAP = 20;
const ROW_GAP = 64;
const RANK_GAP = 60;
const STACK_GAP = 22;
const MARGIN_X = 24;
const MARGIN_Y = 28;
const LONG_EDGE_LANE_GAP = 10;

const PROFILES: Record<DiagramProfile, LayoutProfile> = {
  desktop: { id: "desktop", width: ARTBOARD_WIDTH, maxColumns: 4, vertical: false },
  mobile: { id: "mobile", width: MOBILE_ARTBOARD_WIDTH, maxColumns: 2, vertical: true },
};

const isFeedback = (edge: DiagramEdge) => (edge.kind ?? "default") === "feedback";

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

const resolveNodeWidth = (profile: LayoutProfile) => {
  const totalGaps = Math.max(profile.maxColumns - 1, 0) * COLUMN_GAP;
  const available = profile.width - MARGIN_X * 2 - totalGaps;
  return Math.min(NODE_WIDTH, Math.floor(available / profile.maxColumns));
};

const maxLabelChars = (nodeWidth: number) =>
  Math.max(16, Math.floor((MAX_LABEL_CHARS * nodeWidth) / NODE_WIDTH));

const wrapLine = (line: string, nodeWidth: number): string[] => {
  const limit = maxLabelChars(nodeWidth);
  const trimmed = line.trim();
  if (trimmed.length <= limit) return [trimmed];

  const words = trimmed.split(/\s+/);
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    if (word.length > limit) {
      if (current) {
        lines.push(current);
        current = "";
      }
      for (let offset = 0; offset < word.length; offset += limit) {
        lines.push(word.slice(offset, offset + limit));
      }
      continue;
    }

    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= limit) current = candidate;
    else {
      lines.push(current);
      current = word;
    }
  }

  if (current) lines.push(current);
  return lines.length ? lines : [""];
};

const nodeLines = (label: string, nodeWidth: number) =>
  label.split("\n").flatMap((line) => wrapLine(line, nodeWidth));

const estimateNodeSize = (node: DiagramNode, nodeWidth: number) => {
  const lineCount = Math.max(nodeLines(node.label, nodeWidth).length, 1);
  return {
    width: nodeWidth,
    height: NODE_HEIGHT + (lineCount - 1) * NODE_LINE_HEIGHT,
  };
};

const buildRanks = (graph: DiagramDefinition) => {
  const nodeIndex = new Map(graph.nodes.map((node, index) => [node.id, index]));
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
    queue.sort((left, right) => (nodeIndex.get(left) ?? 0) - (nodeIndex.get(right) ?? 0));
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
    throw new Error("Graph contains a structural cycle. Mark return relations as feedback.");
  }

  return graph.nodes.map((node) => rankById.get(node.id) ?? 0);
};

const buildRawRanks = (
  graph: DiagramDefinition,
  nodeRanks: readonly number[],
  nodeWidth: number,
): SizedNode[][] => {
  const rankCount = Math.max(...nodeRanks) + 1;
  const ranks: SizedNode[][] = Array.from({ length: rankCount }, () => []);

  graph.nodes.forEach((node, index) => {
    const rank = nodeRanks[index] ?? 0;
    ranks[rank]?.push({ node, ...estimateNodeSize(node, nodeWidth), rank });
  });

  return ranks;
};

const centerArtboardHeight = (contentHeight: number) => {
  const height = Math.max(ARTBOARD_MIN_HEIGHT, contentHeight + MARGIN_Y * 2);
  return { height, offsetY: (height - contentHeight) / 2 };
};

const defaultSerpentineColumns = (nodeCount: number) => {
  if (nodeCount <= 3) return Math.max(nodeCount, 1);
  if (nodeCount === 4) return 2;
  if (nodeCount <= 6) return 3;
  return 4;
};

const resolveSerpentineColumns = (nodeCount: number, profile: LayoutProfile) =>
  Math.max(1, Math.min(defaultSerpentineColumns(nodeCount), Math.min(nodeCount, profile.maxColumns)));

const serpentineLayout = (
  rawRanks: readonly (readonly SizedNode[])[],
  profile: LayoutProfile,
  nodeWidth: number,
): InternalLayout => {
  const ordered = rawRanks.flat();
  const columns = resolveSerpentineColumns(ordered.length, profile);
  const rows: SizedNode[][] = [];
  for (let index = 0; index < ordered.length; index += columns) {
    rows.push(ordered.slice(index, index + columns));
  }

  const rowHeights = rows.map((row) => Math.max(...row.map((item) => item.height), NODE_HEIGHT));
  const contentHeight = rowHeights.reduce(
    (total, height, index) => total + height + (index > 0 ? ROW_GAP : 0),
    0,
  );
  const { height, offsetY } = centerArtboardHeight(contentHeight);
  const positionedRows: PositionedInternalNode[][] = [];
  let y = offsetY;

  rows.forEach((row, rowIndex) => {
    const rowHeight = rowHeights[rowIndex] ?? NODE_HEIGHT;
    const rowWidth = row.length * nodeWidth + Math.max(row.length - 1, 0) * COLUMN_GAP;
    const startX = (profile.width - rowWidth) / 2;
    const positioned: PositionedInternalNode[] = [];

    row.forEach((item, itemIndex) => {
      const visualIndex = rowIndex % 2 === 0 ? itemIndex : row.length - 1 - itemIndex;
      positioned.push({
        ...item.node,
        width: item.width,
        height: item.height,
        x: startX + visualIndex * (nodeWidth + COLUMN_GAP) + nodeWidth / 2,
        y: y + rowHeight / 2,
        rank: item.rank,
      });
    });

    positionedRows.push(positioned);
    y += rowHeight + ROW_GAP;
  });

  return {
    kind: "serpentine",
    width: profile.width,
    height,
    nodes: positionedRows.flat(),
    ranks: positionedRows,
  };
};

const layeredTbLayout = (
  rawRanks: readonly (readonly SizedNode[])[],
  profile: LayoutProfile,
  nodeWidth: number,
): InternalLayout => {
  const visualRows: { items: readonly SizedNode[]; semanticRank: number }[] = [];

  rawRanks.forEach((rank, semanticRank) => {
    for (let index = 0; index < rank.length; index += profile.maxColumns) {
      visualRows.push({ items: rank.slice(index, index + profile.maxColumns), semanticRank });
    }
  });

  const rowHeights = visualRows.map(({ items }) =>
    Math.max(...items.map((item) => item.height), NODE_HEIGHT),
  );
  let contentHeight = rowHeights.reduce((total, rowHeight) => total + rowHeight, 0);
  for (let index = 1; index < visualRows.length; index += 1) {
    contentHeight +=
      visualRows[index - 1]?.semanticRank === visualRows[index]?.semanticRank
        ? STACK_GAP
        : RANK_GAP;
  }

  const { height, offsetY } = centerArtboardHeight(contentHeight);
  const positionedRows: PositionedInternalNode[][] = [];
  let y = offsetY;

  visualRows.forEach((row, rowIndex) => {
    const rowHeight = rowHeights[rowIndex] ?? NODE_HEIGHT;
    const rowWidth = row.items.length * nodeWidth + Math.max(row.items.length - 1, 0) * COLUMN_GAP;
    let x = (profile.width - rowWidth) / 2;
    const positioned: PositionedInternalNode[] = [];

    for (const item of row.items) {
      positioned.push({
        ...item.node,
        width: item.width,
        height: item.height,
        x: x + nodeWidth / 2,
        y: y + rowHeight / 2,
        rank: item.rank,
      });
      x += nodeWidth + COLUMN_GAP;
    }

    positionedRows.push(positioned);
    const next = visualRows[rowIndex + 1];
    if (next) {
      y += rowHeight + (next.semanticRank === row.semanticRank ? STACK_GAP : RANK_GAP);
    }
  });

  return {
    kind: "layered-tb",
    width: profile.width,
    height,
    nodes: positionedRows.flat(),
    ranks: positionedRows,
  };
};

const layeredLrLayout = (
  rawRanks: readonly (readonly SizedNode[])[],
  profile: LayoutProfile,
  nodeWidth: number,
): InternalLayout => {
  const columnHeights = rawRanks.map((rank) =>
    rank.reduce((total, item, index) => total + item.height + (index > 0 ? STACK_GAP : 0), 0),
  );
  const contentHeight = Math.max(...columnHeights, NODE_HEIGHT);
  const { height, offsetY } = centerArtboardHeight(contentHeight);
  const contentWidth = rawRanks.length * nodeWidth + Math.max(rawRanks.length - 1, 0) * RANK_GAP;
  let x = (profile.width - contentWidth) / 2;
  const positionedRanks: PositionedInternalNode[][] = [];

  rawRanks.forEach((rank, rankIndex) => {
    const columnHeight = columnHeights[rankIndex] ?? NODE_HEIGHT;
    let y = offsetY + (contentHeight - columnHeight) / 2;
    const positioned: PositionedInternalNode[] = [];

    for (const item of rank) {
      positioned.push({
        ...item.node,
        width: item.width,
        height: item.height,
        x: x + nodeWidth / 2,
        y: y + item.height / 2,
        rank: item.rank,
      });
      y += item.height + STACK_GAP;
    }

    positionedRanks.push(positioned);
    x += nodeWidth + RANK_GAP;
  });

  return {
    kind: "layered-lr",
    width: profile.width,
    height,
    nodes: positionedRanks.flat(),
    ranks: positionedRanks,
  };
};

const fanoutHub = (graph: DiagramDefinition) => {
  const structural = graph.edges.filter((edge) => !isFeedback(edge));
  if (structural.length !== graph.nodes.length - 1 || graph.nodes.length < 5) return undefined;
  const outgoing = new Map(graph.nodes.map((node) => [node.id, 0]));
  for (const edge of structural) outgoing.set(edge.from, (outgoing.get(edge.from) ?? 0) + 1);
  return graph.nodes.find((node) => (outgoing.get(node.id) ?? 0) === graph.nodes.length - 1)?.id;
};

const fanoutLayout = (
  graph: DiagramDefinition,
  nodeRanks: readonly number[],
  hubId: string,
  profile: LayoutProfile,
  nodeWidth: number,
): InternalLayout => {
  const hubIndex = graph.nodes.findIndex((node) => node.id === hubId);
  const hub = graph.nodes[hubIndex];
  if (!hub) throw new Error(`Unknown fanout hub "${hubId}".`);

  const hubSize = estimateNodeSize(hub, nodeWidth);
  const children = graph.nodes
    .map((node, index) => ({ node, index }))
    .filter(({ node }) => node.id !== hubId);
  const rowCount = Math.ceil(children.length / 2);
  const childRows = children.map(({ node }) => estimateNodeSize(node, nodeWidth));
  const rowHeight = Math.max(...childRows.map((size) => size.height), NODE_HEIGHT);
  const childGap = 32;
  const contentHeight =
    hubSize.height + 62 + rowCount * rowHeight + Math.max(rowCount - 1, 0) * childGap;
  const { height, offsetY } = centerArtboardHeight(contentHeight);
  const hubPosition: PositionedInternalNode = {
    ...hub,
    ...hubSize,
    x: profile.width / 2,
    y: offsetY + hubSize.height / 2,
    rank: nodeRanks[hubIndex] ?? 0,
  };
  const leftX = profile.width * 0.28;
  const rightX = profile.width * 0.72;
  const positionedChildren: PositionedInternalNode[] = [];
  let childY = offsetY + hubSize.height + 62 + rowHeight / 2;

  children.forEach(({ node, index }, childIndex) => {
    const size = estimateNodeSize(node, nodeWidth);
    positionedChildren.push({
      ...node,
      ...size,
      x: childIndex % 2 === 0 ? leftX : rightX,
      y: childY,
      rank: nodeRanks[index] ?? 1,
    });
    if (childIndex % 2 === 1) childY += rowHeight + childGap;
  });

  return {
    kind: "fanout",
    width: profile.width,
    height,
    nodes: [hubPosition, ...positionedChildren],
    ranks: [[hubPosition], positionedChildren],
  };
};

const createLayout = (graph: DiagramDefinition, profile: LayoutProfile): InternalLayout => {
  const nodeWidth = resolveNodeWidth(profile);
  const nodeRanks = buildRanks(graph);
  const rawRanks = buildRawRanks(graph, nodeRanks, nodeWidth);
  const hub = fanoutHub(graph);

  if (hub) return fanoutLayout(graph, nodeRanks, hub, profile, nodeWidth);
  if (rawRanks.every((rank) => rank.length === 1)) {
    return serpentineLayout(rawRanks, profile, nodeWidth);
  }

  const lrWidth = rawRanks.length * nodeWidth + Math.max(rawRanks.length - 1, 0) * RANK_GAP;
  const canUseLr =
    !profile.vertical &&
    graph.direction === "LR" &&
    Math.max(...rawRanks.map((rank) => rank.length)) <= 3;

  if (canUseLr && lrWidth <= profile.width - MARGIN_X * 2) {
    return layeredLrLayout(rawRanks, profile, nodeWidth);
  }

  return layeredTbLayout(rawRanks, profile, nodeWidth);
};

const regularRoute = (from: PositionedInternalNode, to: PositionedInternalNode): EdgeRoute => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;

  if (Math.abs(dx) > Math.abs(dy)) {
    const direction = Math.sign(dx) || 1;
    const startX = from.x + (from.width / 2) * direction;
    const endX = to.x - (to.width / 2) * direction;
    const middleX = (startX + endX) / 2;
    return {
      path: `M ${startX} ${from.y} H ${middleX} V ${to.y} H ${endX}`,
      labelX: middleX,
      labelY: (from.y + to.y) / 2 - 8,
    };
  }

  const direction = Math.sign(dy) || 1;
  const startY = from.y + (from.height / 2) * direction;
  const endY = to.y - (to.height / 2) * direction;
  const middleY = (startY + endY) / 2;
  return {
    path: `M ${from.x} ${startY} V ${middleY} H ${to.x} V ${endY}`,
    labelX: (from.x + to.x) / 2 + 8,
    labelY: middleY - 8,
  };
};

const fanoutRoute = (
  from: PositionedInternalNode,
  to: PositionedInternalNode,
  profile: LayoutProfile,
): EdgeRoute => {
  const goesLeft = to.x < from.x;
  const laneX = goesLeft ? MARGIN_X / 2 : profile.width - MARGIN_X / 2;
  const startX = from.x + (goesLeft ? -from.width / 2 : from.width / 2);
  const endX = to.x + (goesLeft ? -to.width / 2 : to.width / 2);
  return {
    path: `M ${startX} ${from.y} H ${laneX} V ${to.y} H ${endX}`,
    labelX: laneX + (goesLeft ? 8 : -8),
    labelY: (from.y + to.y) / 2,
  };
};

const longRoute = (
  from: PositionedInternalNode,
  to: PositionedInternalNode,
  index: number,
  profile: LayoutProfile,
): EdgeRoute => {
  const laneX = profile.width - 8 - index * LONG_EDGE_LANE_GAP;
  const startX = from.x + from.width / 2;
  const endX = to.x + to.width / 2;
  return {
    path: `M ${startX} ${from.y} H ${laneX} V ${to.y} H ${endX}`,
    labelX: laneX - 8,
    labelY: (from.y + to.y) / 2 - 8,
  };
};

const feedbackRoute = (
  from: PositionedInternalNode,
  to: PositionedInternalNode,
  layout: InternalLayout,
): EdgeRoute => {
  const startX = from.x;
  const startY = from.y - from.height / 2;
  const endX = to.x;
  const endY = to.y + to.height / 2;
  const leftNodeBoundary = Math.min(...layout.nodes.map((node) => node.x - node.width / 2));
  const laneX = Math.max(MARGIN_X / 2, leftNodeBoundary - 20);
  const verticalBend = Math.min(44, Math.max(28, Math.abs(startY - endY) * 0.18));

  return {
    path: `M ${startX} ${startY} C ${laneX} ${startY - verticalBend} ${laneX} ${endY + verticalBend} ${endX} ${endY}`,
    labelX: laneX + 10,
    labelY: (startY + endY) / 2 - 6,
  };
};

const routeEdges = (
  graph: DiagramDefinition,
  layout: InternalLayout,
  profile: LayoutProfile,
): RoutedDiagramEdge[] => {
  const byId = new Map(layout.nodes.map((node) => [node.id, node]));
  let longIndex = 0;

  return graph.edges.map((edge) => {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    if (!from || !to) throw new Error(`Unknown graph node in edge ${edge.from} -> ${edge.to}.`);

    const feedback = isFeedback(edge);
    const long = !feedback && to.rank - from.rank > 1;
    const route = feedback
      ? feedbackRoute(from, to, layout)
      : layout.kind === "fanout"
        ? fanoutRoute(from, to, profile)
        : long
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
  const layout = createLayout(graph, profile);
  const edges = routeEdges(graph, layout, profile);

  return {
    width: layout.width,
    height: layout.height,
    layout: layout.kind,
    nodes: layout.nodes.map(({ id, label, kind, x, y, rank }) => ({
      id,
      label,
      kind,
      x,
      y,
      rank,
    })),
    edges,
  };
};
