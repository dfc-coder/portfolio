<script setup lang="ts">
import MobileAgent from "./MobileAgent.vue";
import { experiences } from "../experiences/trajectory-data";
import { systemsProjects, type GraphEdge, type SystemProject } from "../experiences/systems-projects";
import { galleryItems } from "../experiences/gallery";

const edgePath = (project: SystemProject, edge: GraphEdge) => {
  if (edge.path) return edge.path;
  const from = project.graph.nodes.find((node) => node.id === edge.from);
  const to = project.graph.nodes.find((node) => node.id === edge.to);
  if (!from || !to) return "";
  if (Math.abs(from.y - to.y) < 2) return `M ${from.x} ${from.y} H ${to.x}`;
  const midX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} H ${midX} V ${to.y} H ${to.x}`;
};
</script>

<template>
  <div class="m-shell">
    <header class="m-header">
      <a class="m-brand" href="#top">DC</a>
      <span>SOFTWARE ENGINEER<br />+ CREATIVE TECHNOLOGIST</span>
      <nav aria-label="Portfolio sections">
        <a href="#experience">02</a>
        <a href="#systems">03</a>
        <a href="#archive">04</a>
        <a href="#agent">05</a>
      </nav>
    </header>

    <main id="top">
      <section class="m-hero">
        <p class="m-eyebrow">BUENOS AIRES · ARGENTINA</p>
        <div class="m-hero__title" aria-label="Diego Cano">
          <span>DIEGO</span>
          <span>CANO</span>
        </div>
        <p class="m-hero__thesis">
          I design software systems, intelligent products and physical ideas with one principle:
          <em>complexity must become legible.</em>
        </p>
        <a class="m-enter" href="#experience"><span>SCROLL TO ENTER</span><i /></a>
      </section>

      <section id="experience" class="m-section m-experience">
        <header class="m-section__header">
          <span>02</span><i /><h2>PROFESSIONAL TRAJECTORY</h2>
        </header>

        <article v-for="(item, index) in experiences" :key="item.period" class="m-role">
          <div class="m-role__meta">
            <span>{{ String(index + 1).padStart(2, "0") }}</span><i /><time>{{ item.period }}</time>
          </div>
          <h3>{{ item.role }}</h3>
          <dl>
            <div><dt>ORGANIZATION</dt><dd>{{ item.company.split(' · ')[0] }}</dd></div>
            <div><dt>CONTEXT</dt><dd>{{ item.company.split(' · ').slice(1).join(' · ') || 'Remote' }}</dd></div>
          </dl>
          <blockquote>{{ item.summary }}</blockquote>
          <ul class="m-tags" aria-label="Role focus">
            <li v-for="focus in item.focus" :key="focus">{{ focus }}</li>
          </ul>
        </article>
      </section>

      <section id="systems" class="m-section m-systems">
        <header class="m-section__header">
          <span>03</span><i /><h2>SELECTED TECHNICAL SYSTEMS</h2>
        </header>

        <details v-for="project in systemsProjects" :key="project.id" class="m-system">
          <summary>
            <div class="m-system__code"><span>{{ project.id }}</span><i />{{ project.field }}</div>
            <h3>{{ project.title }}</h3>
            <p>{{ project.premise }}</p>
            <b aria-hidden="true">+</b>
          </summary>
          <div class="m-system__body">
            <div class="m-system__graph">
              <svg viewBox="0 0 100 64" role="img" :aria-label="`${project.title} architecture`">
                <g class="m-graph__grid" aria-hidden="true">
                  <path d="M 0 16 H 100 M 0 32 H 100 M 0 48 H 100 M 20 0 V 64 M 40 0 V 64 M 60 0 V 64 M 80 0 V 64" />
                </g>
                <g class="m-graph__edges" aria-hidden="true">
                  <path v-for="edge in project.graph.edges" :key="`${edge.from}-${edge.to}`" :d="edgePath(project, edge)" />
                </g>
                <g v-for="(node, nodeIndex) in project.graph.nodes" :key="node.id" :transform="`translate(${node.x} ${node.y})`" class="m-graph__node">
                  <circle r="1.25" :class="{ accent: node.accent }" />
                  <text x="2.2" y="-1">{{ String(nodeIndex + 1).padStart(2, "0") }}</text>
                  <text x="2.2" y="2.7" class="label">{{ node.label }}</text>
                </g>
              </svg>
            </div>
            <p class="m-system__detail">{{ project.detail }}</p>
            <div class="m-system__outcome"><span>EVIDENCE</span><strong>{{ project.outcome }}</strong></div>
            <ul class="m-tags"><li v-for="item in project.stack" :key="item">{{ item }}</li></ul>
          </div>
        </details>
      </section>

      <section id="archive" class="m-section m-archive">
        <header class="m-section__header">
          <span>04</span><i /><h2>VISUAL / MATERIAL ARCHIVE</h2>
        </header>
        <p class="m-archive__intro">My first language was design — objects, proportion and material honesty. That eye never left the engineering; it only changed medium.</p>
        <div class="m-gallery" aria-label="Visual archive">
          <figure v-for="item in galleryItems" :key="item.src">
            <img :src="item.src" :alt="item.title" loading="lazy" decoding="async" />
            <figcaption><strong>{{ item.title }}</strong><span>{{ item.type }}</span></figcaption>
          </figure>
        </div>
      </section>

      <section id="agent" class="m-section m-agent-section">
        <header class="m-section__header">
          <span>05</span><i /><h2>THE INTERFACE</h2>
        </header>
        <p class="m-agent-section__intro">Enough archive. Ask the work a question.</p>
        <MobileAgent />
      </section>
    </main>

    <footer class="m-footer"><span>DC · BUENOS AIRES</span><a href="#top">BACK TO TOP ↑</a></footer>
  </div>
</template>
