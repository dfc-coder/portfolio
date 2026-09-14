<script setup lang="ts">
import { computed } from "vue";
import {
  compileSystemGraph,
  type SystemGraphProfile,
} from "../../graph/system-graph";
import type { FlowScene, GraphSceneEdge, ScenePath } from "../../graph/model";
import type { SystemProject } from "../../experiences/systems-projects";

const props = defineProps<{
  project: SystemProject;
  mode: SystemGraphProfile;
}>();

const scene = computed(() => compileSystemGraph(props.project.graph, props.mode));

const nodeSteps = computed(() =>
  new Map(props.project.graph.nodes.map((node, index) => [node.id, index])),
);

const architectureDescription = computed(() => {
  const nodes = props.project.graph.nodes.map((node) => node.label).join(", ");
  const edges = props.project.graph.edges
    .map((edge) => edge.label || `${edge.from} to ${edge.to}`)
    .join("; ");
  return `Flow components: ${nodes}. Directed transitions: ${edges}.`;
});

const svgPath = (path: ScenePath) => {
  const [first, ...rest] = path.points;
  if (!first) return "";
  return `M ${first.x} ${first.y}${rest.map((point) => ` L ${point.x} ${point.y}`).join("")}`;
};

const edgeLabelStyle = (edge: GraphSceneEdge, currentScene: FlowScene, edgeIndex: number) => {
  const position = edge.labelPosition;
  if (!position) return { display: "none" };

  return {
    left: `${2 + (position.x / currentScene.width) * 96}%`,
    top: `${9 + (position.y / currentScene.height) * 84}%`,
    "--edge-step": edgeIndex,
  };
};

const labeledEdges = (currentScene: FlowScene) =>
  currentScene.edges
    .map((edge, index) => ({ edge, index }))
    .filter(({ edge }) => edge.label);

const edgeOpacity = (edge: GraphSceneEdge) => {
  if (edge.role === "spine") return 1;
  if (edge.role === "feedback") return 0.58;
  return 0.68;
};

const graphId = computed(() => `${props.project.id}-${props.mode}`);
const arrowId = computed(() => `system-flow-arrow-${graphId.value}`);
</script>

<template>
  <div class="systems-diagram">
    <svg
      class="systems-graph"
      :viewBox="`0 0 ${scene.width} ${scene.height}`"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      :aria-labelledby="`system-graph-title-${graphId} system-graph-desc-${graphId}`"
    >
      <title :id="`system-graph-title-${graphId}`">{{ project.title }} flow</title>
      <desc :id="`system-graph-desc-${graphId}`">{{ architectureDescription }}</desc>

      <defs>
        <marker
          :id="arrowId"
          viewBox="0 0 2.2 2.2"
          refX="2"
          refY="1.1"
          markerWidth="2.2"
          markerHeight="2.2"
          markerUnits="userSpaceOnUse"
          orient="auto"
        >
          <path d="M 0 0 L 2.2 1.1 L 0 2.2 Z" fill="rgba(238, 234, 226, .62)" />
        </marker>
      </defs>

      <g class="systems-graph__edges" aria-hidden="true">
        <template
          v-for="(edge, edgeIndex) in scene.edges"
          :key="`${edge.from}-${edge.to}-${edgeIndex}`"
        >
          <path
            class="systems-graph__edge systems-graph__edge--base"
            :class="{
              'systems-graph__edge--feedback': edge.kind === 'feedback',
              'systems-graph__edge--spine': edge.role === 'spine',
              'systems-graph__edge--branch': edge.role === 'branch',
            }"
            :d="svgPath(edge.path)"
            :marker-end="`url(#${arrowId})`"
            pathLength="1"
            :style="{ opacity: edgeOpacity(edge) }"
          />
          <path
            class="systems-graph__edge systems-graph__edge--active"
            :class="{
              'systems-graph__edge--feedback': edge.kind === 'feedback',
              'systems-graph__edge--spine': edge.role === 'spine',
              'systems-graph__edge--branch': edge.role === 'branch',
            }"
            :d="svgPath(edge.path)"
            pathLength="1"
            :style="{ '--edge-step': edgeIndex, opacity: edgeOpacity(edge) }"
          />
        </template>
      </g>

      <g class="systems-graph__nodes" aria-hidden="true">
        <g
          v-for="node in scene.nodes"
          :key="node.id"
          class="systems-graph__node"
          :class="{
            'is-accent': node.kind === 'accent',
            'is-input': node.role === 'input',
            'is-output': node.role === 'output',
          }"
          :transform="`translate(${node.x} ${node.y})`"
          :style="{ '--node-step': nodeSteps.get(node.id) ?? 0 }"
        >
          <circle :r="node.role === 'output' ? 1.2 : 1.05" />
          <circle class="systems-graph__node-halo" r="3.25" />
          <text x="2.4" y=".8">{{ String((nodeSteps.get(node.id) ?? 0) + 1).padStart(2, "0") }}</text>
          <text class="systems-graph__node-label" x="2.4" y="4.2">{{ node.label }}</text>
        </g>
      </g>
    </svg>

    <span
      v-for="item in labeledEdges(scene)"
      :key="`label-${item.edge.from}-${item.edge.to}-${item.index}`"
      class="systems-graph__edge-label"
      :style="edgeLabelStyle(item.edge, scene, item.index)"
      aria-hidden="true"
    >
      {{ item.edge.label }}
    </span>
  </div>
</template>

<style>
.systems-diagram {
  position: absolute;
  inset: 0;
}
</style>
