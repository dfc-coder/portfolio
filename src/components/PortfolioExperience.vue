<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import AgentOS from "./agent/AgentOS.vue";
import { galleryItems as artworks } from "../experiences/gallery";
import { systemsProjects as projects } from "../experiences/systems-projects";
import { experiences } from "../experiences/trajectory";

const chapters = [
  {
    key: "career",
    kicker: "CHAPTER 02 · THE RECORD",
    line: "First, the proof — where the practice was built.",
  },
  {
    key: "systems",
    kicker: "CHAPTER 03 · THE EVIDENCE",
    line: "Roles condense into systems that shipped.",
  },
  {
    key: "gallery",
    kicker: "CHAPTER 04 · A NOTE ON ORIGIN",
    line: "My first language was design — here the argument turns visual.",
  },
  {
    key: "agent",
    kicker: "CHAPTER 05 · THE INTERFACE",
    line: "Enough archive. Ask the work a question.",
  },
] as const;

const menuOpen = ref(false);
const cursorDot = ref<HTMLElement | null>(null);
const cursorRing = ref<HTMLElement | null>(null);
const cursorState = ref<"idle" | "hover" | "press" | "text">("idle");
const cursorEnabled = ref(false);

let cursorFrame = 0;
let pointerX = 0;
let pointerY = 0;
let ringX = 0;
let ringY = 0;
let cursorSeen = false;

const CURSOR_INTERACTIVE = "button, a, input, textarea, select, [data-cursor]";

const cursorStateFor = (element: Element | null): "idle" | "hover" | "text" => {
  if (!element) return "idle";
  return element.matches("input, textarea") ? "text" : "hover";
};

const onCursorMove = (event: PointerEvent) => {
  pointerX = event.clientX;
  pointerY = event.clientY;

  if (!cursorSeen) {
    cursorSeen = true;
    ringX = pointerX;
    ringY = pointerY;
    cursorDot.value?.classList.add("is-on");
    cursorRing.value?.classList.add("is-on");
  }

  if (cursorDot.value) {
    cursorDot.value.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0)`;
  }
};

const onCursorOver = (event: PointerEvent) => {
  const interactive = (event.target as Element | null)?.closest(CURSOR_INTERACTIVE) ?? null;
  cursorState.value = cursorStateFor(interactive);
};

const onCursorDown = () => {
  if (cursorState.value !== "text") cursorState.value = "press";
};

const onCursorUp = (event: PointerEvent) => {
  const interactive = (event.target as Element | null)?.closest(CURSOR_INTERACTIVE) ?? null;
  cursorState.value = cursorStateFor(interactive);
};

const onCursorLeaveWindow = (event: PointerEvent) => {
  if (event.relatedTarget) return;
  cursorSeen = false;
  cursorDot.value?.classList.remove("is-on");
  cursorRing.value?.classList.remove("is-on");
};

const startCursorLoop = () => {
  const tick = () => {
    ringX += (pointerX - ringX) * 0.16;
    ringY += (pointerY - ringY) * 0.16;
    if (cursorRing.value) {
      cursorRing.value.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
    }
    cursorFrame = requestAnimationFrame(tick);
  };

  cursorFrame = requestAnimationFrame(tick);
};

onMounted(async () => {
  cursorEnabled.value = matchMedia("(pointer: fine) and (prefers-reduced-motion: no-preference)").matches;
  if (!cursorEnabled.value) return;

  await nextTick();
  addEventListener("pointermove", onCursorMove, { passive: true });
  addEventListener("pointerover", onCursorOver, { passive: true });
  addEventListener("pointerdown", onCursorDown, { passive: true });
  addEventListener("pointerup", onCursorUp, { passive: true });
  document.documentElement.addEventListener("pointerout", onCursorLeaveWindow);
  startCursorLoop();
});

onBeforeUnmount(() => {
  cancelAnimationFrame(cursorFrame);
  removeEventListener("pointermove", onCursorMove);
  removeEventListener("pointerover", onCursorOver);
  removeEventListener("pointerdown", onCursorDown);
  removeEventListener("pointerup", onCursorUp);
  document.documentElement.removeEventListener("pointerout", onCursorLeaveWindow);
});
</script>

<template>
  <div :class="['ref-portfolio', { 'has-cursor': cursorEnabled }]">
    <div
      v-if="cursorEnabled"
      ref="cursorDot"
      class="ref-cursor"
      :data-state="cursorState"
      aria-hidden="true"
    />
    <div
      v-if="cursorEnabled"
      ref="cursorRing"
      class="ref-cursor-ring"
      :data-state="cursorState"
      aria-hidden="true"
    />

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

        <article class="ref-scene ref-scene--career" />
        <article class="ref-scene ref-scene--systems" />

        <article class="ref-scene ref-scene--gallery">
          <div class="ref-marker"><span>04</span><i />VISUAL / MATERIAL ARCHIVE</div>
          <div class="ref-gallery-stage" aria-label="Visual works">
            <button
              v-for="artwork in artworks"
              :key="artwork.src"
              class="ref-art-card"
              type="button"
              :aria-label="`Open ${artwork.title}`"
            >
              <img :src="artwork.src" :alt="artwork.title" />
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
          :aria-label="chapter.kicker"
        >
          <div class="ref-chapter">
            <i />
            <span>{{ chapter.kicker }}</span>
            <p>{{ chapter.line }}</p>
          </div>
        </article>
      </section>
    </main>

    <section id="ref-fallback" class="ref-fallback">
      <header>
        <span>DIEGO CANO / ACCESSIBLE INDEX</span>
        <h1>Software, AI and material practice.</h1>
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

<style>
.ref-portfolio .ref-hero__initial,
.ref-portfolio .ref-hero__tail {
  display: inline-block;
  font: inherit;
  font-style: normal;
  font-weight: inherit;
  line-height: inherit;
  letter-spacing: inherit;
  color: inherit;
  vertical-align: baseline;
  will-change: opacity, clip-path;
}
</style>
