<script setup lang="ts">
import { computed } from "vue";
import { compileSystemGraph } from "../../graph/system-graph";
import type { SystemProject } from "../../experiences/systems-projects";

const props = defineProps<{ project: SystemProject }>();

const graph = computed(() => compileSystemGraph(props.project.graph));

const architectureDescription = computed(() => {
  const nodes = props.project.graph.nodes.map((node) => node.label).join(", ");
  const edges = props.project.graph.edges
    .map((edge) => edge.label || `${edge.from} to ${edge.to}`)
    .join("; ");
  return `Components: ${nodes}. Connections: ${edges}.`;
});

const edgeLabelStyle = (edge: (typeof graph.value.edges)[number]) => ({
  left: `${edge.labelX}%`,
  top: `${edge.labelY}%`,
  "--edge-step": edge.step,
});
</script>

<template>
  <svg
    class="systems-graph"
    :viewBox="`0 0 ${graph.width} ${graph.height}`"
    preserveAspectRatio="xMidYMid meet"
    role="img"
    :aria-labelledby="`system-graph-title-${project.id} system-graph-desc-${project.id}`"
  >
    <title :id="`system-graph-title-${project.id}`">{{ project.title }} architecture</title>
    <desc :id="`system-graph-desc-${project.id}`">{{ architectureDescription }}</desc>

    <g class="systems-graph__edges" aria-hidden="true">
      <template v-for="edge in graph.edges" :key="`${edge.from}-${edge.to}`">
        <path
          class="systems-graph__edge systems-graph__edge--base"
          :d="edge.path"
          pathLength="1"
        />
        <path
          class="systems-graph__edge systems-graph__edge--active"
          :d="edge.path"
          pathLength="1"
          :style="{ '--edge-step': edge.step }"
        />
      </template>
    </g>

    <g class="systems-graph__nodes" aria-hidden="true">
      <g
        v-for="(node, nodeIndex) in graph.nodes"
        :key="node.id"
        class="systems-graph__node"
        :class="{ 'is-accent': node.accent }"
        :transform="`translate(${node.x} ${node.y})`"
        :style="{ '--node-step': node.step }"
      >
        <circle r="1.05" />
        <circle class="systems-graph__node-halo" r="3.25" />
        <text x="2.4" y=".8">{{ String(nodeIndex + 1).padStart(2, "0") }}</text>
        <text class="systems-graph__node-label" x="2.4" y="4.2">{{ node.label }}</text>
      </g>
    </g>
  </svg>

  <span
    v-for="edge in graph.edges.filter((item) => item.label)"
    :key="`label-${edge.from}-${edge.to}`"
    class="systems-graph__edge-label"
    :style="edgeLabelStyle(edge)"
    aria-hidden="true"
  >
    {{ edge.label }}
  </span>
</template>
