import type {
  DiagramDefinition,
  DiagramScene,
  FlowDiagramDefinition,
  FlowNode,
  FlowNodeRole,
  FlowScene,
  FlowTopology,
  GraphDiagramDefinition,
  GraphLayoutKind,
  GraphNode,
  GraphScene,
  GraphSceneNode,
  GraphTopology,
  LayoutProfile
} from './model';
import { routeEdges, type ComponentBounds } from './routing';

type DirectedDiagram = GraphDiagramDefinition | FlowDiagramDefinition;

type RankModel = {
  groups: string[][];
  rankByNode: Map<string, number>;
  incoming: Map<string, Set<string>>;
  outgoing: Map<string, Set<string>>;
  order: Map<string, number>;
};

const edgeKey = (from: string, to: string, kind: string, label: string): string =>
  `${kind}:${from}->${to}:${label}`;

const validateDiagram = (diagram: DirectedDiagram): void => {
  if (diagram.nodes.length === 0) throw new Error('Diagram has no nodes.');

  const ids = new Set<string>();
  for (const node of diagram.nodes) {
    if (ids.has(node.id)) throw new Error(`Duplicate node "${node.id}".`);
    ids.add(node.id);
  }

  const edges = new Set<string>();
  for (const edge of diagram.edges) {
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

const nodeSize = (
  node: GraphNode,
  profile: LayoutProfile,
  role?: FlowNodeRole
): GraphSceneNode => {
  const lines = wrapText(node.label, profile);
  const extraLines = Math.max(0, lines.length - 1);
  return {
    id: node.id,
    label: node.label,
    kind: node.kind ?? 'default',
    ...(role ? { role } : {}),
    lines,
    x: 0,
    y: 0,
    width: profile.nodeWidth,
    height: profile.nodeHeight + extraLines * Math.max(1, profile.nodeHeight * 0.38)
  };
};

const forwardRanks = (diagram: DirectedDiagram): RankModel => {
  const order = new Map(diagram.nodes.map((node, index) => [node.id, index]));
  const outgoing = new Map(diagram.nodes.map((node) => [node.id, new Set<string>()]));
  const incoming = new Map(diagram.nodes.map((node) => [node.id, new Set<string>()]));
  const indegree = new Map(diagram.nodes.map((node) => [node.id, 0]));
  const rankByNode = new Map(diagram.nodes.map((node) => [node.id, 0]));

  for (const edge of diagram.edges) {
    if (edge.kind === 'feedback') continue;
    if (edge.from === edge.to) {
      throw new Error(`Self-loop ${edge.from} -> ${edge.to} must be declared as feedback.`);
    }
    const targets = outgoing.get(edge.from)!;
    if (targets.has(edge.to)) continue;
    targets.add(edge.to);
    incoming.get(edge.to)!.add(edge.from);
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
  }

  const queue = diagram.nodes.filter((node) => (indegree.get(node.id) ?? 0) === 0).map((node) => node.id);
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

  if (visited !== diagram.nodes.length) {
    throw new Error('Forward graph contains a cycle. Mark return edges explicitly as feedback.');
  }

  const maxRank = Math.max(...rankByNode.values(), 0);
  const groups = Array.from({ length: maxRank + 1 }, () => [] as string[]);
  for (const node of diagram.nodes) groups[rankByNode.get(node.id) ?? 0]!.push(node.id);
  return { groups, rankByNode, incoming, outgoing, order };
};

const classifyGraph = (graph: GraphDiagramDefinition): GraphTopology => {
  if (graph.edges.some((edge) => edge.kind === 'feedback')) return 'cycle';
  if (graph.nodes.length <= 1) return 'chain';

  const ranks = forwardRanks(graph);
  const isChain = graph.nodes.every(
    (node) => (ranks.incoming.get(node.id)?.size ?? 0) <= 1 && (ranks.outgoing.get(node.id)?.size ?? 0) <= 1
  );
  if (isChain) return 'chain';

  const fanout = graph.nodes.find((node) => (ranks.outgoing.get(node.id)?.size ?? 0) === graph.nodes.length - 1);
  if (fanout && graph.edges.length === graph.nodes.length - 1) return 'fanout';

  const fanin = graph.nodes.find((node) => (ranks.incoming.get(node.id)?.size ?? 0) === graph.nodes.length - 1);
  if (fanin && graph.edges.length === graph.nodes.length - 1) return 'fanin';

  const split = graph.nodes.some((node) => (ranks.outgoing.get(node.id)?.size ?? 0) >= 2);
  const join = graph.nodes.some((node) => (ranks.incoming.get(node.id)?.size ?? 0) >= 2);
  if (split && join) return 'branch-join';
  return 'layered';
};

const classifyFlow = (flow: FlowDiagramDefinition, ranks: RankModel): FlowTopology => {
  if (flow.edges.some((edge) => edge.kind === 'feedback')) return 'feedback';
  const split = flow.nodes.some((node) => (ranks.outgoing.get(node.id)?.size ?? 0) >= 2);
  const join = flow.nodes.some((node) => (ranks.incoming.get(node.id)?.size ?? 0) >= 2);
  if (split && join) return 'branch-join';
  if (split) return 'branch';
  if (join) return 'join';
  if (flow.nodes.every((node) => (ranks.incoming.get(node.id)?.size ?? 0) <= 1 && (ranks.outgoing.get(node.id)?.size ?? 0) <= 1)) {
    return 'linear';
  }
  return 'mixed';
};

const pad = (profile: LayoutProfile): number => Math.max(profile.nodeGap, 4);

const layoutGraphLr = (
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
      nodes.push({ ...node, x: x + rankWidth / 2, y: y + node.height / 2 });
      y += node.height + profile.nodeGap;
    }
    x += rankWidth + rankGap;
  });

  return { nodes, height, layout: 'layered-lr' };
};

const layoutGraphTb = (
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
      nodes.push({ ...node, x: x + node.width / 2, y: y + rowHeight / 2 });
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

const sceneBounds = (nodes: readonly GraphSceneNode[]): ComponentBounds => {
  const minX = Math.min(...nodes.map((node) => node.x - node.width / 2));
  const minY = Math.min(...nodes.map((node) => node.y - node.height / 2));
  const maxX = Math.max(...nodes.map((node) => node.x + node.width / 2));
  const maxY = Math.max(...nodes.map((node) => node.y + node.height / 2));
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
};

const layoutGraph = (graph: GraphDiagramDefinition, profile: LayoutProfile): GraphScene => {
  validateDiagram(graph);
  if (profile.width <= 0 || profile.nodeWidth <= 0 || profile.nodeHeight <= 0) {
    throw new Error('Layout profile dimensions must be positive.');
  }

  const ranks = forwardRanks(graph);
  const topology = classifyGraph(graph);
  const direction = profile.direction && profile.direction !== 'auto' ? profile.direction : (graph.direction ?? 'LR');
  const placed = direction === 'TB' ? layoutGraphTb(graph, profile, ranks) : layoutGraphLr(graph, profile, ranks);

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

const findFlowSpine = (flow: FlowDiagramDefinition, ranks: RankModel): string[] => {
  const score = new Map(flow.nodes.map((node) => [node.id, Number.NEGATIVE_INFINITY]));
  const previous = new Map<string, string>();
  const explicitInputs = new Set(flow.nodes.filter((node) => node.role === 'input').map((node) => node.id));
  const hasExplicitInputs = explicitInputs.size > 0;

  for (const group of ranks.groups) {
    for (const id of group) {
      const isInput = (ranks.incoming.get(id)?.size ?? 0) === 0;
      if (isInput && (!hasExplicitInputs || explicitInputs.has(id))) score.set(id, 1);

      for (const target of ranks.outgoing.get(id) ?? []) {
        const current = score.get(id) ?? Number.NEGATIVE_INFINITY;
        if (!Number.isFinite(current)) continue;
        const candidate = current + 1;
        if (candidate > (score.get(target) ?? Number.NEGATIVE_INFINITY)) {
          score.set(target, candidate);
          previous.set(target, id);
        }
      }
    }
  }

  const explicitOutputs = flow.nodes.filter((node) => node.role === 'output').map((node) => node.id);
  const outputs = explicitOutputs.length
    ? explicitOutputs
    : flow.nodes.filter((node) => (ranks.outgoing.get(node.id)?.size ?? 0) === 0).map((node) => node.id);

  const candidates = outputs.length ? outputs : flow.nodes.map((node) => node.id);
  candidates.sort((left, right) => {
    const scoreDiff = (score.get(right) ?? Number.NEGATIVE_INFINITY) - (score.get(left) ?? Number.NEGATIVE_INFINITY);
    if (scoreDiff !== 0) return scoreDiff;
    return (ranks.order.get(left) ?? 0) - (ranks.order.get(right) ?? 0);
  });

  const end = candidates[0];
  if (!end || !Number.isFinite(score.get(end) ?? Number.NEGATIVE_INFINITY)) return [flow.nodes[0]!.id];

  const spine: string[] = [];
  let current: string | undefined = end;
  while (current) {
    spine.push(current);
    current = previous.get(current);
  }
  return spine.reverse();
};

const sideLane = (index: number): number => {
  const distance = Math.floor(index / 2) + 1;
  return index % 2 === 0 ? distance : -distance;
};

const flowLanes = (flow: FlowDiagramDefinition, ranks: RankModel, spine: readonly string[]): Map<string, number> => {
  const spineSet = new Set(spine);
  const laneByNode = new Map<string, number>(spine.map((id) => [id, 0]));
  let nextLane = 0;

  for (const group of ranks.groups) {
    for (const id of group) {
      if (spineSet.has(id)) continue;
      const predecessors = [...(ranks.incoming.get(id) ?? [])]
        .sort((left, right) => (ranks.order.get(left) ?? 0) - (ranks.order.get(right) ?? 0));
      const inherited = predecessors.find((parent) => !spineSet.has(parent) && laneByNode.has(parent));
      if (inherited) {
        laneByNode.set(id, laneByNode.get(inherited)!);
      } else {
        laneByNode.set(id, sideLane(nextLane));
        nextLane += 1;
      }
    }
  }

  return laneByNode;
};

const inferredRole = (node: FlowNode, ranks: RankModel): FlowNodeRole => {
  if (node.role) return node.role;
  if ((ranks.incoming.get(node.id)?.size ?? 0) === 0) return 'input';
  if ((ranks.outgoing.get(node.id)?.size ?? 0) === 0) return 'output';
  return 'step';
};

const layoutFlowLr = (
  flow: FlowDiagramDefinition,
  profile: LayoutProfile,
  ranks: RankModel,
  lanes: ReadonlyMap<string, number>
): { nodes: GraphSceneNode[]; height: number } => {
  const padding = pad(profile);
  const feedbackMargin = flow.edges.some((edge) => edge.kind === 'feedback')
    ? Math.max(profile.nodeGap, profile.rankGap * 0.65)
    : 0;
  const laneGap = Math.max(profile.nodeHeight + profile.nodeGap, 12);
  const maxLane = Math.max(...lanes.values(), 0);
  const minLane = Math.min(...lanes.values(), 0);
  const verticalSpan = (maxLane - minLane) * laneGap + profile.nodeHeight;
  const height = Math.max(44, verticalSpan + padding * 2 + feedbackMargin * 2);
  const centerY = height / 2 - ((maxLane + minLane) * laneGap) / 2;
  const left = padding + profile.nodeWidth / 2;
  const right = profile.width - padding - profile.nodeWidth / 2;
  const rankCount = Math.max(1, ranks.groups.length - 1);
  const rankStep = ranks.groups.length <= 1 ? 0 : (right - left) / rankCount;
  const nodes: GraphSceneNode[] = [];

  for (const node of flow.nodes) {
    const rank = ranks.rankByNode.get(node.id) ?? 0;
    const lane = lanes.get(node.id) ?? 0;
    const sized = nodeSize(node, profile, inferredRole(node, ranks));
    nodes.push({
      ...sized,
      x: ranks.groups.length <= 1 ? profile.width / 2 : left + rank * rankStep,
      y: centerY + lane * laneGap
    });
  }

  return { nodes, height };
};

const layoutFlowTb = (
  flow: FlowDiagramDefinition,
  profile: LayoutProfile,
  ranks: RankModel,
  lanes: ReadonlyMap<string, number>
): { nodes: GraphSceneNode[]; height: number } => {
  const padding = pad(profile);
  const feedbackMargin = flow.edges.some((edge) => edge.kind === 'feedback')
    ? Math.max(profile.nodeGap, profile.rankGap * 0.65)
    : 0;
  const maxAbsLane = Math.max(...[...lanes.values()].map((lane) => Math.abs(lane)), 0);
  const desiredLaneGap = Math.max(profile.nodeWidth + profile.nodeGap, 18);
  const availableHalf = profile.width / 2 - padding - feedbackMargin - profile.nodeWidth / 2;
  const laneGap = maxAbsLane > 0 ? Math.min(desiredLaneGap, availableHalf / maxAbsLane) : desiredLaneGap;
  const rankStep = profile.nodeHeight + profile.rankGap;
  const height = padding * 2 + profile.nodeHeight + Math.max(0, ranks.groups.length - 1) * rankStep;
  const centerX = profile.width / 2;
  const nodes: GraphSceneNode[] = [];

  for (const node of flow.nodes) {
    const rank = ranks.rankByNode.get(node.id) ?? 0;
    const lane = lanes.get(node.id) ?? 0;
    const sized = nodeSize(node, profile, inferredRole(node, ranks));
    nodes.push({
      ...sized,
      x: centerX + lane * laneGap,
      y: padding + profile.nodeHeight / 2 + rank * rankStep
    });
  }

  return { nodes, height };
};

const layoutFlow = (flow: FlowDiagramDefinition, profile: LayoutProfile): FlowScene => {
  validateDiagram(flow);
  if (profile.width <= 0 || profile.nodeWidth <= 0 || profile.nodeHeight <= 0) {
    throw new Error('Layout profile dimensions must be positive.');
  }

  const ranks = forwardRanks(flow);
  const spine = findFlowSpine(flow, ranks);
  const lanes = flowLanes(flow, ranks, spine);
  const direction = profile.direction && profile.direction !== 'auto' ? profile.direction : (flow.direction ?? 'LR');
  const placed = direction === 'TB'
    ? layoutFlowTb(flow, profile, ranks, lanes)
    : layoutFlowLr(flow, profile, ranks, lanes);

  const componentByNode = new Map(flow.nodes.map((node) => [node.id, 0]));
  const boundsByComponent = new Map<number, ComponentBounds>([[0, sceneBounds(placed.nodes)]]);
  const spineEdges = new Set(spine.slice(0, -1).map((id, index) => `${id}->${spine[index + 1]}`));
  const edges = routeEdges(flow, placed.nodes, componentByNode, boundsByComponent, profile).map((edge) => ({
    ...edge,
    role: edge.kind === 'feedback'
      ? 'feedback' as const
      : spineEdges.has(`${edge.from}->${edge.to}`)
        ? 'spine' as const
        : 'branch' as const
  }));

  return {
    kind: 'flow',
    width: profile.width,
    height: placed.height,
    topology: classifyFlow(flow, ranks),
    layout: direction === 'TB' ? 'flow-tb' : 'flow-lr',
    spine,
    nodes: placed.nodes,
    edges
  };
};

export function layoutDiagram(diagram: DiagramDefinition, profile: LayoutProfile): DiagramScene {
  switch (diagram.kind) {
    case 'graph':
      return layoutGraph(diagram, profile);
    case 'flow':
      return layoutFlow(diagram, profile);
  }
}
