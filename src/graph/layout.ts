import type {
  DiagramDefinition,
  DiagramScene,
  GraphDiagramDefinition,
  GraphLayoutKind,
  GraphNode,
  GraphScene,
  GraphSceneNode,
  GraphTopology,
  LayoutProfile
} from './model';
import { routeEdges, type ComponentBounds } from './routing';

const edgeKey = (from: string, to: string, kind: string, label: string): string =>
  `${kind}:${from}->${to}:${label}`;

const validateGraph = (graph: GraphDiagramDefinition): void => {
  if (graph.nodes.length === 0) throw new Error('Graph has no nodes.');

  const ids = new Set<string>();
  for (const node of graph.nodes) {
    if (ids.has(node.id)) throw new Error(`Duplicate node "${node.id}".`);
    ids.add(node.id);
  }

  const edges = new Set<string>();
  for (const edge of graph.edges) {
    if (!ids.has(edge.from) || !ids.has(edge.to)) {
      throw new Error(`Unknown node in edge ${edge.from} -> ${edge.to}.`);
    }
    const key = edgeKey(edge.from, edge.to, edge.kind ?? 'default', edge.label ?? '');
    if (edges.has(key)) throw new Error(`Duplicate edge ${edge.from} -> ${edge.to}.`);
    edges.add(key);
  }
};

const maxChars = (profile: LayoutProfile): number => {
  if (profile.nodeWidth < 40) return Number.POSITIVE_INFINITY;
  return Math.max(16, Math.floor(profile.nodeWidth / 7.6));
};

const wrapText = (label: string, profile: LayoutProfile): string[] => {
  const limit = maxChars(profile);
  if (!Number.isFinite(limit)) return label.split('\n');

  return label.split('\n').flatMap((rawLine) => {
    const line = rawLine.trim();
    if (line.length <= limit) return [line];
    const words = line.split(/\s+/);
    const lines: string[] = [];
    let current = '';

    for (const word of words) {
      const candidate = current ? `${current} ${word}` : word;
      if (candidate.length <= limit) {
        current = candidate;
        continue;
      }
      if (current) lines.push(current);
      current = word;
    }
    if (current) lines.push(current);
    return lines.length ? lines : [''];
  });
};

const nodeSize = (node: GraphNode, profile: LayoutProfile): GraphSceneNode => {
  const lines = wrapText(node.label, profile);
  const extraLines = Math.max(0, lines.length - 1);
  return {
    id: node.id,
    label: node.label,
    kind: node.kind ?? 'default',
    lines,
    x: 0,
    y: 0,
    width: profile.nodeWidth,
    height: profile.nodeHeight + extraLines * Math.max(1, profile.nodeHeight * 0.38)
  };
};

const classifyGraph = (graph: GraphDiagramDefinition): GraphTopology => {
  if (graph.edges.some((edge) => edge.kind === 'feedback')) return 'cycle';
  if (graph.nodes.length <= 1) return 'chain';

  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  const outdegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  for (const edge of graph.edges) {
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
    outdegree.set(edge.from, (outdegree.get(edge.from) ?? 0) + 1);
  }

  const isChain = graph.nodes.every(
    (node) => (indegree.get(node.id) ?? 0) <= 1 && (outdegree.get(node.id) ?? 0) <= 1
  );
  if (isChain) return 'chain';

  const fanout = graph.nodes.find((node) => (outdegree.get(node.id) ?? 0) === graph.nodes.length - 1);
  if (fanout && graph.edges.length === graph.nodes.length - 1) return 'fanout';

  const fanin = graph.nodes.find((node) => (indegree.get(node.id) ?? 0) === graph.nodes.length - 1);
  if (fanin && graph.edges.length === graph.nodes.length - 1) return 'fanin';

  const split = graph.nodes.some((node) => (outdegree.get(node.id) ?? 0) >= 2);
  const join = graph.nodes.some((node) => (indegree.get(node.id) ?? 0) >= 2);
  if (split && join) return 'branch-join';
  return 'layered';
};

type RankModel = {
  groups: string[][];
  rankByNode: Map<string, number>;
};

const forwardRanks = (graph: GraphDiagramDefinition): RankModel => {
  const order = new Map(graph.nodes.map((node, index) => [node.id, index]));
  const outgoing = new Map(graph.nodes.map((node) => [node.id, new Set<string>()]));
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  const rankByNode = new Map(graph.nodes.map((node) => [node.id, 0]));

  for (const edge of graph.edges) {
    if (edge.kind === 'feedback') continue;
    if (edge.from === edge.to) {
      throw new Error(`Self-loop ${edge.from} -> ${edge.to} must be declared as feedback.`);
    }
    const targets = outgoing.get(edge.from)!;
    if (targets.has(edge.to)) continue;
    targets.add(edge.to);
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
  }

  const queue = graph.nodes.filter((node) => (indegree.get(node.id) ?? 0) === 0).map((node) => node.id);
  let visited = 0;

  while (queue.length) {
    queue.sort((left, right) => (order.get(left) ?? 0) - (order.get(right) ?? 0));
    const current = queue.shift()!;
    visited += 1;

    for (const target of outgoing.get(current) ?? []) {
      rankByNode.set(target, Math.max(rankByNode.get(target) ?? 0, (rankByNode.get(current) ?? 0) + 1));
      const remaining = (indegree.get(target) ?? 0) - 1;
      indegree.set(target, remaining);
      if (remaining === 0) queue.push(target);
    }
  }

  if (visited !== graph.nodes.length) {
    throw new Error('Forward graph contains a cycle. Mark return edges explicitly as feedback.');
  }

  const maxRank = Math.max(...rankByNode.values(), 0);
  const groups = Array.from({ length: maxRank + 1 }, () => [] as string[]);
  for (const node of graph.nodes) groups[rankByNode.get(node.id) ?? 0]!.push(node.id);
  return { groups, rankByNode };
};

const pad = (profile: LayoutProfile): number => Math.max(profile.nodeGap, 4);

const layoutLr = (
  graph: GraphDiagramDefinition,
  profile: LayoutProfile,
  ranks: RankModel
): { nodes: GraphSceneNode[]; height: number; layout: GraphLayoutKind } => {
  const sized = new Map(graph.nodes.map((node) => [node.id, nodeSize(node, profile)]));
  const padding = pad(profile);
  const rankWidths = ranks.groups.map((group) => Math.max(...group.map((id) => sized.get(id)!.width), 0));
  const stackHeights = ranks.groups.map((group) =>
    group.reduce((sum, id, index) => sum + sized.get(id)!.height + (index ? profile.nodeGap : 0), 0)
  );

  const nodeWidth = rankWidths.reduce((sum, width) => sum + width, 0);
  const availableGap = ranks.groups.length > 1
    ? Math.max(0, (profile.width - padding * 2 - nodeWidth) / (ranks.groups.length - 1))
    : 0;
  const rankGap = ranks.groups.length > 1 ? Math.min(profile.rankGap, availableGap) : 0;
  const contentWidth = nodeWidth + Math.max(0, ranks.groups.length - 1) * rankGap;

  if (contentWidth > profile.width - padding * 2 + 0.001) {
    throw new Error('Graph is too wide for the desktop layout profile.');
  }

  const contentHeight = Math.max(...stackHeights, profile.nodeHeight);
  const height = contentHeight + padding * 2;
  const nodes: GraphSceneNode[] = [];
  let x = (profile.width - contentWidth) / 2;

  ranks.groups.forEach((group, rank) => {
    const rankWidth = rankWidths[rank] ?? profile.nodeWidth;
    const stackHeight = stackHeights[rank] ?? profile.nodeHeight;
    let y = padding + (contentHeight - stackHeight) / 2;

    for (const id of group) {
      const node = sized.get(id)!;
      nodes.push({
        ...node,
        x: x + rankWidth / 2,
        y: y + node.height / 2
      });
      y += node.height + profile.nodeGap;
    }
    x += rankWidth + rankGap;
  });

  return { nodes, height, layout: 'layered-lr' };
};

const layoutTb = (
  graph: GraphDiagramDefinition,
  profile: LayoutProfile,
  ranks: RankModel
): { nodes: GraphSceneNode[]; height: number; layout: GraphLayoutKind } => {
  const sized = new Map(graph.nodes.map((node) => [node.id, nodeSize(node, profile)]));
  const padding = pad(profile);
  const rowHeights = ranks.groups.map((group) => Math.max(...group.map((id) => sized.get(id)!.height), profile.nodeHeight));
  const rowWidths = ranks.groups.map((group) =>
    group.reduce((sum, id, index) => sum + sized.get(id)!.width + (index ? profile.nodeGap : 0), 0)
  );
  const contentHeight = rowHeights.reduce((sum, value, index) => sum + value + (index ? profile.rankGap : 0), 0);
  const height = contentHeight + padding * 2;
  const nodes: GraphSceneNode[] = [];
  let y = padding;

  ranks.groups.forEach((group, rank) => {
    const rowHeight = rowHeights[rank] ?? profile.nodeHeight;
    const rowWidth = rowWidths[rank] ?? profile.nodeWidth;
    let x = (profile.width - rowWidth) / 2;

    for (const id of group) {
      const node = sized.get(id)!;
      nodes.push({
        ...node,
        x: x + node.width / 2,
        y: y + rowHeight / 2
      });
      x += node.width + profile.nodeGap;
    }
    y += rowHeight + profile.rankGap;
  });

  return { nodes, height, layout: 'layered-tb' };
};

const nodeBounds = (node: GraphSceneNode): ComponentBounds => ({
  x: node.x - node.width / 2,
  y: node.y - node.height / 2,
  width: node.width,
  height: node.height
});

const layoutGraph = (graph: GraphDiagramDefinition, profile: LayoutProfile): GraphScene => {
  validateGraph(graph);
  if (profile.width <= 0 || profile.nodeWidth <= 0 || profile.nodeHeight <= 0) {
    throw new Error('Layout profile dimensions must be positive.');
  }

  const ranks = forwardRanks(graph);
  const topology = classifyGraph(graph);
  const direction = profile.direction && profile.direction !== 'auto' ? profile.direction : (graph.direction ?? 'LR');
  const placed = direction === 'TB' ? layoutTb(graph, profile, ranks) : layoutLr(graph, profile, ranks);

  const componentByNode = new Map(graph.nodes.map((node, index) => [node.id, index]));
  const byId = new Map(placed.nodes.map((node) => [node.id, node]));
  const boundsByComponent = new Map<number, ComponentBounds>();
  graph.nodes.forEach((node, index) => boundsByComponent.set(index, nodeBounds(byId.get(node.id)!)));
  const edges = routeEdges(graph, placed.nodes, componentByNode, boundsByComponent, profile);

  return {
    kind: 'graph',
    width: profile.width,
    height: placed.height,
    topology,
    layout: topology === 'cycle' && placed.layout === 'layered-lr' ? 'cycle' : placed.layout,
    nodes: placed.nodes,
    edges
  };
};

export function layoutDiagram(diagram: DiagramDefinition, profile: LayoutProfile): DiagramScene {
  switch (diagram.kind) {
    case 'graph':
      return layoutGraph(diagram, profile);
  }
}
