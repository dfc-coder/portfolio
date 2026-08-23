<script setup lang="ts">
import { ref } from "vue";
import AgentOS from "./agent/AgentOS.vue";
import ChapterSignal from "./narrative/ChapterSignal.vue";
import SystemsScene from "./narrative/SystemsScene.vue";
import TrajectoryScene from "./narrative/TrajectoryScene.vue";
import { galleryItems as artworks } from "../experiences/gallery";
import { systemsProjects as projects } from "../experiences/systems-projects";
import { experiences } from "../experiences/trajectory-data";

const chapters = [
  {
    key: "career",
    index: "02",
    label: "THE RECORD",
    line: "First, the proof — where the practice was built.",
  },
  {
    key: "systems",
    index: "03",
    label: "THE EVIDENCE",
    line: "Roles condense into systems that shipped.",
  },
  {
    key: "gallery",
    index: "04",
    label: "A NOTE ON ORIGIN",
    line: "My first language was design — here the argument turns visual.",
  },
  {
    key: "agent",
    index: "05",
    label: "THE INTERFACE",
    line: "Enough archive. Ask the work a question.",
  },
] as const;

const sectionTitles = [
  ["career", "02", "PROFESSIONAL TRAJECTORY"],
  ["systems", "03", "SELECTED TECHNICAL SYSTEMS"],
  ["gallery", "04", "VISUAL / MATERIAL ARCHIVE"],
  ["agent", "05", "THE INTERFACE"],
] as const;

const menuOpen = ref(false);
</script>

<template>
  <div class="ref-portfolio">
    <a class="ref-skip" href="#ref-fallback">Skip motion experience</a>

    <header class="ref-header">
      <button type="button" class="ref-brand" aria-label="Return to opening">
        <strong>DC</strong>
        <span>SOFTWARE ENGINEER<br />+ CREATIVE TECHNOLOGIST</span>
      </button>
      <div class="ref-progress">
        <span>00</span>
        <i><b /></i>
        <span>100</span>
      </div>
      <button
        type="button"
        class="ref-index-toggle"
        :aria-expanded="menuOpen"
        @click="menuOpen = !menuOpen"
      >
        {{ menuOpen ? "CLOSE" : "MENU" }}
      </button>
    </header>

    <nav :class="['ref-index', { 'is-open': menuOpen }]" aria-label="Portfolio index">
      <button type="button"><span>01</span><strong>Opening</strong></button>
      <button type="button"><span>02</span><strong>Trajectory</strong></button>
      <button type="button"><span>03</span><strong>Systems</strong></button>
      <button type="button"><span>04</span><strong>Visual archive</strong></button>
      <button type="button"><span>05</span><strong>Agent</strong></button>
    </nav>

    <main class="ref-track">
      <section class="ref-stage" data-scene="hero" aria-label="Scroll-driven portfolio narrative">
        <div class="ref-grain" aria-hidden="true" />

        <div class="ref-section-chrome">
          <h2
            v-for="([key, index, label]) in sectionTitles"
            :key="key"
            :class="['ref-section-marker', `ref-section-marker--${key}`]"
          >
            <span>{{ index }}</span><i aria-hidden="true" /><span>{{ label }}</span>
          </h2>
        </div>

        <article class="ref-scene ref-scene--hero">
          <p class="ref-hero__meta">
            <span>BUENOS AIRES · ARGENTINA</span>
            <span>SELECTED PRACTICE / 2026</span>
          </p>
          <h1 class="ref-hero__title">
            <span><i><b class="ref-hero__initial">D</b><b class="ref-hero__tail">IEGO</b></i></span>
            <span><i><b class="ref-hero__initial">C</b><b class="ref-hero__tail">ANO</b></i></span>
          </h1>
          <p class="ref-hero__thesis">
            I design software systems, intelligent products and physical ideas with one principle:
            <em>complexity must become legible.</em>
          </p>
          <div class="ref-scroll-cue"><span>SCROLL TO ENTER</span><i /></div>
        </article>

        <article class="ref-scene ref-scene--career"><TrajectoryScene /></article>
        <article class="ref-scene ref-scene--systems"><SystemsScene /></article>

        <article class="ref-scene ref-scene--gallery">
          <div class="ref-gallery-stage" aria-label="Visual works">
            <button
              v-for="artwork in artworks"
              :key="artwork.src"
              class="ref-art-card"
              type="button"
              :aria-label="`Open ${artwork.title}`"
            >
              <img :src="artwork.src" :alt="artwork.title" draggable="false" />
            </button>
          </div>
        </article>

        <article class="ref-scene ref-scene--agent">
          <AgentOS />
        </article>

        <article
          v-for="chapter in chapters"
          :key="chapter.key"
          class="ref-scene ref-scene--chapter"
          :data-chapter="chapter.key"
          aria-hidden="true"
        >
          <div class="ref-chapter">
            <ChapterSignal :index="chapter.index" :label="chapter.label" />
            <p>{{ chapter.line }}</p>
          </div>
        </article>
      </section>
    </main>

    <section id="ref-fallback" class="ref-fallback">
      <header>
        <span>DIEGO CANO / ACCESSIBLE INDEX</span>
        <p class="ref-fallback__title">Software, AI and material practice.</p>
      </header>

      <div>
        <h2>Experience</h2>
        <article v-for="item in experiences" :key="item.period">
          <span>{{ item.period }} · {{ item.company }}</span>
          <h3>{{ item.role }}</h3>
          <p>{{ item.summary }}</p>
        </article>
      </div>

      <div>
        <h2>Technical systems</h2>
        <article v-for="item in projects" :key="item.id">
          <span>{{ item.id }} · {{ item.field }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.premise }}</p>
        </article>
      </div>

      <div>
        <h2>A note on origin</h2>
        <p>
          My first language was design — objects, proportion, material honesty. That eye never left the
          engineering; it only changed medium. What follows is the other half of the practice, where the
          argument is visual.
        </p>
      </div>

      <div class="ref-fallback-art">
        <h2>Visual archive</h2>
        <figure v-for="item in artworks" :key="item.src">
          <img :src="item.src" :alt="item.title" />
          <figcaption>{{ item.title }} · {{ item.type }}</figcaption>
        </figure>
      </div>
    </section>
  </div>
</template>
