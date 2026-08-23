<script setup lang="ts">
import ChapterSignal from "./ChapterSignal.vue";
import {
  systemsProjects as projects,
  type GraphEdge,
  type SystemProject,
} from "../../experiences/systems-projects";

const edgePath = (project: SystemProject, edge: GraphEdge) => {
  if (edge.path) return edge.path;

  const from = project.graph.nodes.find((node) => node.id === edge.from);
  const to = project.graph.nodes.find((node) => node.id === edge.to);
  if (!from || !to) return "";
  if (Math.abs(from.y - to.y) < 2) return `M ${from.x} ${from.y} H ${to.x}`;

  const midX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} H ${midX} V ${to.y} H ${to.x}`;
};

const edgeLabelStyle = (project: SystemProject, edge: GraphEdge) => {
  const from = project.graph.nodes.find((node) => node.id === edge.from);
  const to = project.graph.nodes.find((node) => node.id === edge.to);
  if (!from || !to) return {};

  return {
    left: `${(from.x + to.x) / 2}%`,
    top: `${(from.y + to.y) / 2}%`,
    "--edge-step": edge.step,
  };
};

const architectureDescription = (project: SystemProject) => {
  const nodes = project.graph.nodes.map((node) => node.label).join(", ");
  const edges = project.graph.edges
    .map((edge) => edge.label || `${edge.from} to ${edge.to}`)
    .join("; ");
  return `Components: ${nodes}. Connections: ${edges}.`;
};
</script>

<template>
  <div class="systems-experience" aria-label="Selected technical systems">
    <h2 class="sr-only">Selected technical systems</h2>

    <div class="systems-intro" aria-hidden="true">
      <ChapterSignal class="systems-intro__kicker" index="03" label="THE EVIDENCE" />
      <p>The work becomes evidence —<br /><em>systems designed, built and shipped.</em></p>
    </div>

    <div class="systems-axis narrative-rail" aria-hidden="true">
      <i class="systems-axis__progress" />
    </div>

    <div class="systems-axis-items narrative-rail" aria-hidden="true">
      <div
        v-for="(project, index) in projects"
        :key="project.id"
        class="systems-axis-item"
        :data-index="index"
        :style="{ '--axis-slot': projects.length > 1 ? index / (projects.length - 1) : 0 }"
      >
        <i /><b>{{ project.code }}</b>
      </div>
    </div>

    <div class="systems-static-chrome" aria-hidden="true">
      <div class="systems-static-chrome__architecture">
        <span>SYSTEM ARCHITECTURE</span><i />
      </div>
      <div class="systems-static-chrome__detail"><span>SYSTEM NOTE</span></div>
      <div class="systems-static-chrome__evidence"><span>EVIDENCE</span><i /></div>
      <div class="systems-static-chrome__implementation"><span>IMPLEMENTATION</span></div>
    </div>

    <div class="systems-projects">
      <article
        v-for="(project, index) in projects"
        :key="project.id"
        class="systems-project"
        :data-index="index"
      >
        <div class="systems-project__identity">
          <h3>{{ project.title }}</h3>
          <p class="systems-project__premise">{{ project.premise }}</p>
        </div>

        <section class="systems-project__architecture">
          <h4 class="sr-only">System architecture</h4>

          <div class="systems-graph-field">
            <div class="systems-graph-field__crosshair" aria-hidden="true" />
            <svg
              class="systems-graph"
              viewBox="0 0 100 64"
              preserveAspectRatio="xMidYMid meet"
              role="img"
              :aria-labelledby="`system-graph-title-${project.id} system-graph-desc-${project.id}`"
            >
              <title :id="`system-graph-title-${project.id}`">{{ project.title }} architecture</title>
              <desc :id="`system-graph-desc-${project.id}`">{{ architectureDescription(project) }}</desc>
              <g class="systems-graph__edges" aria-hidden="true">
                <template v-for="edge in project.graph.edges" :key="`${edge.from}-${edge.to}`">
                  <path
                    class="systems-graph__edge systems-graph__edge--base"
                    :d="edgePath(project, edge)"
                    pathLength="1"
                  />
                  <path
                    class="systems-graph__edge systems-graph__edge--active"
                    :d="edgePath(project, edge)"
                    pathLength="1"
                    :style="{ '--edge-step': edge.step }"
                  />
                </template>
              </g>
              <g class="systems-graph__nodes" aria-hidden="true">
                <g
                  v-for="(node, nodeIndex) in project.graph.nodes"
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
              v-for="edge in project.graph.edges.filter((item) => item.label)"
              :key="`label-${edge.from}-${edge.to}`"
              class="systems-graph__edge-label"
              :style="edgeLabelStyle(project, edge)"
              aria-hidden="true"
            >
              {{ edge.label }}
            </span>
          </div>
        </section>

        <section class="systems-project__detail">
          <h4 class="sr-only">System note</h4>
          <p>{{ project.detail }}</p>
        </section>

        <section class="systems-project__evidence">
          <h4 class="sr-only">Evidence</h4>
          <p>{{ project.outcome }}</p>
        </section>

        <section class="systems-project__implementation">
          <h4 class="sr-only">Implementation</h4>
          <ul>
            <li
              v-for="(item, stackIndex) in project.stack"
              :key="item"
              :style="{ '--stack-index': stackIndex }"
            >
              {{ item }}
            </li>
          </ul>
        </section>
      </article>
    </div>
  </div>
</template>
