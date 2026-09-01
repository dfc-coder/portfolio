import type {
  GraphDiagramDefinition,
  GraphSceneEdge,
  GraphSceneNode,
  LayoutProfile,
  Point
} from './model';

export type ComponentBounds = {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
};

const nodeMap = (nodes: readonly GraphSceneNode[]) => new Map(nodes.map((node) => [node.id, node]));

const nodeBounds = (node: GraphSceneNode): ComponentBounds => ({
  x: node.x - node.width / 2,
  y: node.y - node.height / 2,
  width: node.width,
  height: node.height
});

const anchorBounds = (node: GraphSceneNode, profile: LayoutProfile): ComponentBounds => {
  const width = profile.anchorWidth ?? node.width;
  const height = profile.anchorHeight ?? node.height;
  return {
    x: node.x - width / 2,
    y: node.y - height / 2,
    width,
    height
  };
};

const regularRoute = (
  from: GraphSceneNode,
  to: GraphSceneNode,
  profile: LayoutProfile
): readonly Point[] => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const fromBox = anchorBounds(from, profile);
  const toBox = anchorBounds(to, profile);

  if (Math.abs(dx) >= Math.abs(dy)) {
    const direction = Math.sign(dx) || 1;
    const start = { x: direction > 0 ? fromBox.x + fromBox.width : fromBox.x, y: from.y };
    const end = { x: direction > 0 ? toBox.x : toBox.x + toBox.width, y: to.y };
    const middleX = (start.x + end.x) / 2;
    return [start, { x: middleX, y: start.y }, { x: middleX, y: end.y }, end];
  }

  const direction = Math.sign(dy) || 1;
  const start = { x: from.x, y: direction > 0 ? fromBox.y + fromBox.height : fromBox.y };
  const end = { x: to.x, y: direction > 0 ? toBox.y : toBox.y + toBox.height };
  const middleY = (start.y + end.y) / 2;
  return [start, { x: start.x, y: middleY }, { x: end.x, y: middleY }, end];
};

const compactPolyline = (points: readonly Point[]): readonly Point[] => {
  const compact: Point[] = [];
  for (const point of points) {
    const previous = compact[compact.length - 1];
    if (previous && previous.x === point.x && previous.y === point.y) continue;
    compact.push(point);
  }

  if (compact.length <= 2) return compact;
  const simplified: Point[] = [compact[0]!];
  for (let index = 1; index < compact.length - 1; index += 1) {
    const previous = simplified[simplified.length - 1]!;
    const current = compact[index]!;
    const next = compact[index + 1]!;
    const sameX = previous.x === current.x && current.x === next.x;
    const sameY = previous.y === current.y && current.y === next.y;
    if (!sameX && !sameY) simplified.push(current);
  }
  simplified.push(compact[compact.length - 1]!);
  return simplified;
};

const labelPosition = (points: readonly Point[]): Point | undefined => {
  if (points.length < 2) return undefined;
  let bestStart = points[0]!;
  let bestEnd = points[1]!;
  let bestLength = 0;

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index]!;
    const end = points[index + 1]!;
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    if (length > bestLength) {
      bestLength = length;
      bestStart = start;
      bestEnd = end;
    }
  }

  return {
    x: (bestStart.x + bestEnd.x) / 2,
    y: (bestStart.y + bestEnd.y) / 2 - 2
  };
};

const feedbackRoute = (
  from: GraphSceneNode,
  to: GraphSceneNode,
  bounds: ComponentBounds,
  index: number,
  profile: LayoutProfile
): readonly Point[] => {
  const fromBox = anchorBounds(from, profile);
  const toBox = anchorBounds(to, profile);
  const laneGap = Math.max(profile.nodeGap, profile.rankGap * 0.65);
  const direction = profile.direction && profile.direction !== 'auto' ? profile.direction : 'LR';

  if (direction === 'TB') {
    const useLeft = index % 2 === 0;
    const laneX = useLeft ? bounds.x - laneGap : bounds.x + bounds.width + laneGap;
    const start = useLeft
      ? { x: fromBox.x, y: from.y }
      : { x: fromBox.x + fromBox.width, y: from.y };
    const end = useLeft
      ? { x: toBox.x, y: to.y }
      : { x: toBox.x + toBox.width, y: to.y };

    return compactPolyline([
      start,
      { x: laneX, y: start.y },
      { x: laneX, y: end.y },
      end
    ]);
  }

  const useTop = index % 2 === 0;
  const laneY = useTop ? bounds.y - laneGap : bounds.y + bounds.height + laneGap;
  const start = useTop
    ? { x: from.x, y: fromBox.y }
    : { x: from.x, y: fromBox.y + fromBox.height };
  const end = useTop
    ? { x: to.x, y: toBox.y }
    : { x: to.x, y: toBox.y + toBox.height };

  return compactPolyline([
    start,
    { x: start.x, y: laneY },
    { x: end.x, y: laneY },
    end
  ]);
};

const unionBounds = (left: ComponentBounds, right: ComponentBounds): ComponentBounds => {
  const x = Math.min(left.x, right.x);
  const y = Math.min(left.y, right.y);
  const maxX = Math.max(left.x + left.width, right.x + right.width);
  const maxY = Math.max(left.y + left.height, right.y + right.height);
  return { x, y, width: maxX - x, height: maxY - y };
};

export function routeEdges(
  graph: GraphDiagramDefinition,
  nodes: readonly GraphSceneNode[],
  componentByNode: ReadonlyMap<string, number>,
  componentBounds: ReadonlyMap<number, ComponentBounds>,
  profile: LayoutProfile
): GraphSceneEdge[] {
  const byId = nodeMap(nodes);
  let feedbackIndex = 0;

  return graph.edges.map((edge) => {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    if (!from || !to) throw new Error(`Unknown node in edge ${edge.from} -> ${edge.to}.`);

    const kind = edge.kind ?? 'default';
    if (kind !== 'feedback') {
      const points = compactPolyline(regularRoute(from, to, profile));
      return {
        from: edge.from,
        to: edge.to,
        ...(edge.label ? { label: edge.label } : {}),
        kind,
        path: { kind: 'polyline', points },
        ...(edge.label ? { labelPosition: labelPosition(points) } : {})
      };
    }

    const fromComponent = componentByNode.get(edge.from);
    const toComponent = componentByNode.get(edge.to);
    const fromBounds = fromComponent === undefined ? nodeBounds(from) : componentBounds.get(fromComponent) ?? nodeBounds(from);
    const toBounds = toComponent === undefined ? nodeBounds(to) : componentBounds.get(toComponent) ?? nodeBounds(to);
    const bounds = unionBounds(fromBounds, toBounds);
    const points = feedbackRoute(from, to, bounds, feedbackIndex, profile);
    feedbackIndex += 1;

    return {
      from: edge.from,
      to: edge.to,
      ...(edge.label ? { label: edge.label } : {}),
      kind,
      path: { kind: 'polyline', points },
      ...(edge.label ? { labelPosition: labelPosition(points) } : {})
    };
  });
}
