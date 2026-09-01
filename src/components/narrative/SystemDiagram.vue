<script setup lang="ts">
import { computed } from "vue";
import {
  compileSystemGraph,
  type CompiledGraphEdge,
  type CompiledSystemGraph,
} from "../../graph/system-graph";
import type { SystemProject } from "../../experiences/systems-projects";

const props = defineProps<{ project: SystemProject }>();

// Temporary validation switch. Fixed mode remains the production baseline
// until the automatic engine is visually approved across every System.
const automaticLayout =
  typeof window !== "undefined" &&
  new URLSearchParams(window.location.search).get("diagramEngine") === "auto";

const graphVariants = computed(() => {
  if (!automaticLayout) {
    return [
      {
        key: "fixed",
        graph: compileSystemGraph(props.project.graph),
      },
    ];
  }

  return [
    {
      key: "desktop",
      graph: compileSystemGraph(props.project.graph, { mode: "auto", profile: "desktop" }),
    },
    {
      key: "mobile",
      graph: compileSystemGraph(props.project.graph, { mode: "auto", profile: "mobile" }),
    },
  ];
});

const architectureDescription = computed(() => {
  const nodes = props.project.graph.nodes.map((node) => node.label).join(", ");
  const edges = props.project.graph.edges
    .map((edge) => edge.label || `${edge.from} to ${edge.to}`)
    .join("; ");
  return `Components: ${nodes}. Connections: ${edges}.`;
});

const edgeLabelStyle = (edge: CompiledGraphEdge, graph: CompiledSystemGraph) => {
  const automatic = graph.layout !== "fixed";
  return {
    left: `${automatic ? (edge.labelX / graph.width) * 100 : edge.labelX}%`,
    top: `${automatic ? (edge.labelY / graph.height) * 100 : edge.labelY}%`,
    "--edge-step": edge.step,
  };
};

const graphId = (variant: string) => `${props.project.id}-${variant}`;
</script>

<template>
  <div class="systems-diagram" :class="{ 'is-auto': automaticLayout }">
    <div
      v-for="variant in graphVariants"
      :key="variant.key"
      class="systems-diagram__variant"
      :class="`systems-diagram__variant--${variant.key}`"
    >
      <svg
        class="systems-graph"
        :viewBox="`0 0 ${variant.graph.width} ${variant.graph.height}`"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        :aria-labelledby="`system-graph-title-${graphId(variant.key)} system-graph-desc-${graphId(variant.key)}`"
      >
        <title :id="`system-graph-title-${graphId(variant.key)}`">{{ project.title }} architecture</title>
        <desc :id="`system-graph-desc-${graphId(variant.key)}`">{{ architectureDescription }}</desc>

        <g class="systems-graph__edges" aria-hidden="true">
          <template v-for="edge in variant.graph.edges" :key="`${edge.from}-${edge.to}`">
            <path
              class="systems-graph__edge systems-graph__edge--base"
              :class="{ 'systems-graph__edge--feedback': edge.feedback }"
              :d="edge.path"
              pathLength="1"
            />
            <path
              class="systems-graph__edge systems-graph__edge--active"
              :class="{ 'systems-graph__edge--feedback': edge.feedback }"
              :d="edge.path"
              pathLength="1"
              :style="{ '--edge-step': edge.step }"
            />
          </template>
        </g>

        <g class="systems-graph__nodes" aria-hidden="true">
          <g
            v-for="(node, nodeIndex) in variant.graph.nodes"
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
        v-for="edge in variant.graph.edges.filter((item) => item.label)"
        :key="`label-${edge.from}-${edge.to}`"
        class="systems-graph__edge-label"
        :style="edgeLabelStyle(edge, variant.graph)"
        aria-hidden="true"
      >
        {{ edge.label }}
      </span>
    </div>
  </div>
</template>

<style>
.systems-diagram,
.systems-diagram__variant {
  position: absolute;
  inset: 0;
}

.systems-diagram.is-auto .systems-diagram__variant--mobile {
  display: none;
}

@media (max-width: 680px) {
  .systems-diagram.is-auto .systems-diagram__variant--desktop {
    display: none;
  }

  .systems-diagram.is-auto .systems-diagram__variant--mobile {
    display: block;
  }
}
</style>
