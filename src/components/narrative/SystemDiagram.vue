<script setup lang="ts">
import { computed } from "vue";
import {
  compileSystemGraph,
  type GraphProfileName,
  type RoutedSystemEdge,
} from "../../graph/system-graph";
import type { SystemProject } from "../../experiences/systems-projects";

const props = defineProps<{ project: SystemProject }>();

const variants = computed(() =>
  (["desktop", "mobile"] as const).map((profile) => ({
    profile,
    model: compileSystemGraph(props.project.graph, profile),
  })),
);

const architectureDescription = computed(() => {
  const nodes = props.project.graph.nodes.map((node) => node.label).join(", ");
  const edges = props.project.graph.edges
    .map((edge) => edge.label || `${edge.from} to ${edge.to}`)
    .join("; ");
  return `Components: ${nodes}. Connections: ${edges}.`;
});

const variantClass = (profile: GraphProfileName) => [
  "systems-graph-variant",
  `systems-graph-variant--${profile}`,
];

const edgeLabelStyle = (edge: RoutedSystemEdge) => ({
  left: `${2 + edge.labelX * 0.96}%`,
  top: `${9 + (edge.labelY / 64) * 84}%`,
  "--edge-step": edge.step,
});
</script>

<template>
  <template v-for="variant in variants" :key="variant.profile">
    <div :class="variantClass(variant.profile)">
      <svg
        class="systems-graph"
        :viewBox="`0 0 ${variant.model.width} ${variant.model.height}`"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        :aria-labelledby="`system-graph-title-${project.id}-${variant.profile} system-graph-desc-${project.id}-${variant.profile}`"
      >
        <title :id="`system-graph-title-${project.id}-${variant.profile}`">
          {{ project.title }} architecture
        </title>
        <desc :id="`system-graph-desc-${project.id}-${variant.profile}`">
          {{ architectureDescription }}
        </desc>

        <g class="systems-graph__edges" aria-hidden="true">
          <template
            v-for="edge in variant.model.edges"
            :key="`${variant.profile}-${edge.from}-${edge.to}`"
          >
            <path
              class="systems-graph__edge systems-graph__edge--base"
              :class="{ 'is-feedback': edge.kind === 'feedback' }"
              :d="edge.path"
              pathLength="1"
            />
            <path
              class="systems-graph__edge systems-graph__edge--active"
              :class="{ 'is-feedback': edge.kind === 'feedback' }"
              :d="edge.path"
              pathLength="1"
              :style="{ '--edge-step': edge.step }"
            />
          </template>
        </g>

        <g class="systems-graph__nodes" aria-hidden="true">
          <g
            v-for="(node, nodeIndex) in variant.model.nodes"
            :key="`${variant.profile}-${node.id}`"
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
        v-for="edge in variant.model.edges.filter((item) => item.label)"
        :key="`label-${variant.profile}-${edge.from}-${edge.to}`"
        class="systems-graph__edge-label"
        :class="{ 'is-feedback': edge.kind === 'feedback' }"
        :style="edgeLabelStyle(edge)"
        aria-hidden="true"
      >
        {{ edge.label }}
      </span>
    </div>
  </template>
</template>
