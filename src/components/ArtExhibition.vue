<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

type Piece = {
  src: string;
  title: string;
  type: string;
  medium: string;
  statement: string;
};

type Placement = {
  ax: number;
  ay: number;
  az: number;
  ar: number;
  as: number;
  bx: number;
  by: number;
  bz: number;
  br: number;
  bs: number;
};

const pieces: Piece[] = [
  { src: "/studio/bench-detail.png", title: "Quiet Joinery", type: "Furniture study", medium: "Oak · leather · detail", statement: "A restrained structural language built from proportion, continuity and visible joints." },
  { src: "/studio/mortar.png", title: "Domestic Ritual", type: "Object design", medium: "Stone · timber · tactility", statement: "An everyday object treated as a study of weight, grip, temperature and ritual." },
  { src: "/studio/radios.png", title: "Portable Frequency", type: "Product language", medium: "CMF · series · image", statement: "A compact product family shaped through repetition, softness and controlled colour." },
  { src: "/studio/bench.png", title: "Linear Rest", type: "Furniture concept", medium: "Structure · rhythm · restraint", statement: "A public object reduced to a small number of legible structural gestures." },
  { src: "/studio/lounge-mint.png", title: "Soft Landscape", type: "Seating concept", medium: "Textile · tubular steel", statement: "Comfort understood as a suspended landscape over a precise supporting frame." },
  { src: "/studio/interior-shadow.png", title: "Shadow Room", type: "Spatial direction", medium: "Light · texture · atmosphere", statement: "Architecture becomes a stage for moving light, mineral surfaces and silence." },
  { src: "/studio/interior-blue.png", title: "Blue Alcove", type: "Interior image", medium: "Material · composition · mood", statement: "The same spatial grammar is shifted through temperature, contrast and tighter framing." },
  { src: "/studio/chairs.png", title: "Primary Structure", type: "Furniture system", medium: "Modularity · assembly · colour", statement: "A family of chairs constructed from repeated linear components and flexible braces." },
  { src: "/studio/kempu.png", title: "Kempu", type: "Visual direction", medium: "Campaign · typography · image", statement: "Typography behaves as architecture: it frames, interrupts and changes the image rhythm." },
  { src: "/studio/magnolias.png", title: "Magnolias", type: "Visual identity", medium: "Editorial · type · artwork", statement: "An intimate photographic world held together by an expressive editorial system." },
];

const placements: Placement[] = [
  { ax: -34, ay: -16, az: -60, ar: -5, as: 0.82, bx: -12, by: -25, bz: 40, br: 1, bs: 1.08 },
  { ax: 2, ay: -25, az: 20, ar: 2, as: 1.03, bx: 32, by: -12, bz: -55, br: 5, bs: 0.82 },
  { ax: 31, ay: -8, az: -30, ar: 5, as: 0.82, bx: 8, by: 14, bz: 45, br: -2, bs: 1.02 },
  { ax: -22, ay: 18, az: 42, ar: 2, as: 1.04, bx: -36, by: 8, bz: -20, br: -4, bs: 0.88 },
  { ax: 20, ay: 21, az: -40, ar: -3, as: 0.9, bx: 29, by: 24, bz: 25, br: 2, bs: 1.02 },
  { ax: -39, ay: 4, az: -105, ar: -2, as: 0.7, bx: -4, by: -2, bz: 90, br: 0, bs: 1.18 },
  { ax: 39, ay: 8, az: -110, ar: 4, as: 0.68, bx: -33, by: -15, bz: -10, br: -3, bs: 0.9 },
  { ax: -4, ay: 28, az: -85, ar: 0, as: 0.75, bx: 35, by: 5, bz: -15, br: 4, bs: 0.9 },
  { ax: 12, ay: -2, az: -130, ar: -4, as: 0.64, bx: 5, by: -26, bz: -5, br: -1, bs: 0.92 },
  { ax: -11, ay: 1, az: -145, ar: 3, as: 0.62, bx: -8, by: 27, bz: -35, br: 2, bs: 0.84 },
];

const root = ref<HTMLElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const selected = ref<number | null>(null);
const activeComposition = ref<"form" | "image">("form");
const selectedPiece = computed(() => selected.value === null ? null : pieces[selected.value]);

let context: gsap.Context | null = null;
let media: gsap.MatchMedia | null = null;

const openPiece = (index: number) => {
  selected.value = index;
  document.body.classList.add("has-overlay");
};

const closePiece = () => {
  selected.value = null;
  document.body.classList.remove("has-overlay");
};

const handleKey = (event: KeyboardEvent) => {
  if (event.key === "Escape") closePiece();
  if (selected.value === null) return;
  if (event.key === "ArrowRight") selected.value = (selected.value + 1) % pieces.length;
  if (event.key === "ArrowLeft") selected.value = (selected.value - 1 + pieces.length) % pieces.length;
};

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  context = gsap.context(() => {
    media = gsap.matchMedia();
    media.add("(min-width: 901px)", () => {
      const artwork = gsap.utils.toArray<HTMLElement>(".art-piece");
      artwork.forEach((element, index) => {
        const placement = placements[index];
        gsap.set(element, {
          xPercent: placement.ax,
          yPercent: placement.ay,
          z: placement.az,
          rotation: placement.ar,
          scale: placement.as,
        });
      });

      if (reduced || !stage.value) return;

      const timeline = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: {
          trigger: stage.value,
          start: "top top",
          end: "+=190%",
          pin: true,
          scrub: 0.9,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            activeComposition.value = self.progress < 0.52 ? "form" : "image";
          },
        },
      });

      artwork.forEach((element, index) => {
        const placement = placements[index];
        timeline.to(element, {
          xPercent: placement.bx,
          yPercent: placement.by,
          z: placement.bz,
          rotation: placement.br,
          scale: placement.bs,
          duration: 1,
        }, 0);
      });

      timeline
        .to(".art-exhibition__intro", { y: -70, opacity: 0, duration: 0.34 }, 0.08)
        .fromTo(".art-exhibition__counter", { opacity: 0.25 }, { opacity: 1, duration: 0.4 }, 0.5)
        .to(".art-exhibition__light", { xPercent: 42, yPercent: -10, scale: 1.25, duration: 1 }, 0);
    });
  }, root.value ?? undefined);

  addEventListener("keydown", handleKey);
});

onBeforeUnmount(() => {
  removeEventListener("keydown", handleKey);
  document.body.classList.remove("has-overlay");
  media?.revert();
  context?.revert();
});
</script>

<template>
  <section ref="root" class="art-exhibition" aria-labelledby="art-title">
    <header class="art-exhibition__header">
      <span>VISUAL PRACTICE / TEN WORKS</span>
      <h2 id="art-title">Form, material<br />and <em>visual direction.</em></h2>
      <p>This is the only part of the portfolio treated as an exhibition. The technical work remains outside this visual archive.</p>
    </header>

    <div ref="stage" class="art-exhibition__stage">
      <div class="art-exhibition__light" aria-hidden="true" />
      <div class="art-exhibition__intro" aria-hidden="true">
        <span>COMPOSITION I</span>
        <strong>Objects are read through mass,<br />silhouette and distance.</strong>
      </div>
      <div class="art-exhibition__counter" aria-live="polite">
        <span>{{ activeComposition === "form" ? "FORM / MATERIAL" : "IMAGE / DIRECTION" }}</span>
        <strong>{{ activeComposition === "form" ? "01" : "02" }}</strong>
      </div>

      <div class="art-exhibition__space">
        <button
          v-for="(piece, index) in pieces"
          :key="piece.src"
          class="art-piece"
          type="button"
          :aria-label="`Open ${piece.title}`"
          @click="openPiece(index)"
        >
          <span class="art-piece__image"><img :src="piece.src" :alt="piece.title" loading="lazy" /></span>
          <span class="art-piece__meta"><small>{{ String(index + 1).padStart(2, "0") }}</small><strong>{{ piece.title }}</strong><i>{{ piece.type }}</i></span>
        </button>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="art-dialog">
        <div v-if="selectedPiece" class="art-detail" role="dialog" aria-modal="true" :aria-label="selectedPiece.title">
          <button class="art-detail__backdrop" type="button" aria-label="Close artwork" @click="closePiece" />
          <article>
            <header><span>VISUAL ARCHIVE / {{ String(selected! + 1).padStart(2, "0") }}</span><button type="button" @click="closePiece">CLOSE ×</button></header>
            <div class="art-detail__image"><img :src="selectedPiece.src" :alt="selectedPiece.title" /></div>
            <div class="art-detail__copy">
              <span>{{ selectedPiece.type }}</span>
              <h3>{{ selectedPiece.title }}</h3>
              <p>{{ selectedPiece.statement }}</p>
              <dl><dt>LANGUAGE</dt><dd>{{ selectedPiece.medium }}</dd></dl>
            </div>
            <footer>
              <button type="button" @click="selected = (selected! - 1 + pieces.length) % pieces.length">← PREVIOUS</button>
              <span>{{ String(selected! + 1).padStart(2, "0") }} / {{ String(pieces.length).padStart(2, "0") }}</span>
              <button type="button" @click="selected = (selected! + 1) % pieces.length">NEXT →</button>
            </footer>
          </article>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>
