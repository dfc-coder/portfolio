export type GraphDirection = 'TB' | 'LR';
export type GraphNodeKind = 'default' | 'terminal' | 'accent' | 'muted';
export type GraphEdgeKind = 'default' | 'feedback';
export type FlowNodeRole = 'input' | 'step' | 'output';
export type FlowEdgeRole = 'spine' | 'branch' | 'feedback';

export interface GraphNode {
  readonly id: string;
  readonly label: string;
  readonly kind?: GraphNodeKind;
}

export interface FlowNode extends GraphNode {
  readonly role?: FlowNodeRole;
}

export interface GraphEdge {
  readonly from: string;
  readonly to: string;
  readonly label?: string;
  readonly kind?: GraphEdgeKind;
}

export interface GraphDiagramDefinition {
  readonly kind: 'graph';
  readonly title?: string;
  readonly direction?: GraphDirection;
  readonly nodes: readonly GraphNode[];
  readonly edges: readonly GraphEdge[];
}

export interface FlowDiagramDefinition {
  readonly kind: 'flow';
  readonly title?: string;
  readonly direction?: GraphDirection;
  readonly nodes: readonly FlowNode[];
  readonly edges: readonly GraphEdge[];
}

export type DiagramDefinition = GraphDiagramDefinition | FlowDiagramDefinition;

export type GraphTopology =
  | 'chain'
  | 'fanout'
  | 'fanin'
  | 'branch-join'
  | 'cycle'
  | 'layered';

export type FlowTopology =
  | 'linear'
  | 'branch'
  | 'join'
  | 'branch-join'
  | 'feedback'
  | 'mixed';

export type GraphLayoutKind =
  | 'serpentine'
  | 'layered-lr'
  | 'layered-tb'
  | 'fanout'
  | 'fanin'
  | 'cycle';

export type FlowLayoutKind = 'flow-lr' | 'flow-tb';

export interface Point {
  readonly x: number;
  readonly y: number;
}

export interface ScenePath {
  readonly kind: 'polyline';
  readonly points: readonly Point[];
}

export interface GraphSceneNode {
  readonly id: string;
  readonly label: string;
  readonly kind: GraphNodeKind;
  readonly role?: FlowNodeRole;
  readonly lines: readonly string[];
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface GraphSceneEdge {
  readonly from: string;
  readonly to: string;
  readonly label?: string;
  readonly kind: GraphEdgeKind;
  readonly role?: FlowEdgeRole;
  readonly path: ScenePath;
  readonly labelPosition?: Point;
}

export interface GraphScene {
  readonly kind: 'graph';
  readonly width: number;
  readonly height: number;
  readonly topology: GraphTopology;
  readonly layout: GraphLayoutKind;
  readonly nodes: readonly GraphSceneNode[];
  readonly edges: readonly GraphSceneEdge[];
}

export interface FlowScene {
  readonly kind: 'flow';
  readonly width: number;
  readonly height: number;
  readonly topology: FlowTopology;
  readonly layout: FlowLayoutKind;
  readonly spine: readonly string[];
  readonly nodes: readonly GraphSceneNode[];
  readonly edges: readonly GraphSceneEdge[];
}

export type DiagramScene = GraphScene | FlowScene;

export type LayoutDirection = 'auto' | GraphDirection;

export interface LayoutProfile {
  readonly width: number;
  readonly nodeWidth: number;
  readonly nodeHeight: number;
  readonly nodeGap: number;
  readonly rankGap: number;
  readonly maxColumns: number;
  readonly direction?: LayoutDirection;
  readonly anchorWidth?: number;
  readonly anchorHeight?: number;
}

export interface Theme {
  readonly classPrefix?: string;
}
