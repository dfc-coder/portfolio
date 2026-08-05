<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import * as THREE from "three";
import ContactAssistant from "./ContactAssistant.vue";

type Experience = { period: string; role: string; company: string; summary: string; focus: string[] };
type Project = { id: string; code: string; field: string; title: string; premise: string; detail: string; stack: string[]; outcome: string };
type Artwork = { src: string; title: string; type: string; meta: string };

const experiences: Experience[] = [
  { period: "2025 — NOW", role: "AI Engineer", company: "aiRoss · Madrid / Remote", summary: "Private document-intelligence systems, structured extraction and production workflows where security, evidence and human review remain visible.", focus: ["Local LLMs", "Document AI", "Python", "Product architecture"] },
  { period: "2024 — 2025", role: "Independent AI Engineer", company: "Applied AI · Remote", summary: "Agentic systems, retrieval pipelines and natural-language interfaces designed around operational constraints instead of isolated model demonstrations.", focus: ["RAG", "Agents", "NL→SQL", "Evaluation"] },
  { period: "2023 — 2025", role: "Software Engineer", company: "FK Tech · Argentina", summary: "Full-stack products and integrations with an emphasis on maintainable architecture, secure APIs and delivery across the complete software lifecycle.", focus: ["TypeScript", "Backend", "Integrations", "Cloud"] },
];

const projects: Project[] = [
  { id: "01", code: "DOC—AI", field: "PRIVATE AI / BANKING", title: "Secure Document Extractor", premise: "Sensitive documents become structured financial data without leaving isolated infrastructure.", detail: "PDF and image documents are segmented, ranked by field and processed by local models. Typed validation and evidence links keep uncertainty reviewable instead of hiding it behind a confident answer.", stack: ["Python", "FastAPI", "Docling", "Local LLM", "Redis"], outcome: "Private by design · evidence-linked output" },
  { id: "02", code: "NL→SQL", field: "AGENTS / DATA ACCESS", title: "Natural Language to SQL", premise: "A conversational question reaches data without granting unrestricted database access.", detail: "A planner resolves intent, retrieves only relevant schema, applies business rules and rejects ambiguous or unsafe operations before generating a guarded query.", stack: ["Python", "Tool calling", "Schema RAG", "SQL policies", "Evaluation"], outcome: "Grounded questions · guarded execution" },
  { id: "03", code: "MCP—03", field: "FINTECH / AGENT TOOLS", title: "Financial MCP Server", premise: "Market data becomes explicit, reusable instruments rather than an opaque recommendation engine.", detail: "Each capability exposes a strict contract, identifiable source and predictable output so specialised agents can combine evidence without hiding how an interpretation was produced.", stack: ["MCP", "Python", "Market data", "Typed tools", "Agents"], outcome: "Signals organised as auditable tools" },
  { id: "04", code: "SEARCH", field: "SEMANTIC SEARCH / PRODUCT", title: "Intent-aware Shopping Assistant", premise: "Product discovery starts from a real need, not from exact keyword matching.", detail: "Incomplete language is converted into comparable attributes, hybrid retrieval candidates and explainable ranking signals evaluated independently from the conversational layer.", stack: ["TypeScript", "Embeddings", "Hybrid search", "Catalog API", "Metrics"], outcome: "Faster discovery · explainable relevance" },
];

const artworks: Artwork[] = [
  { src: "/studio/bench-detail.png", title: "Quiet Joinery", type: "Furniture system", meta: "Oak · leather · structural detail" },
  { src: "/studio/mortar.png", title: "Domestic Ritual", type: "Object design", meta: "Stone · timber · material contrast" },
  { src: "/studio/radios.png", title: "Portable Frequency", type: "Product language", meta: "CMF · retro-futurism · series" },
  { src: "/studio/bench.png", title: "Linear Rest", type: "Furniture design", meta: "Structure · proportion · restraint" },
  { src: "/studio/lounge-mint.png", title: "Soft Landscape", type: "Seating concept", meta: "Textile · tubular steel · comfort" },
  { src: "/studio/interior-shadow.png", title: "Shadow Room", type: "Spatial direction", meta: "Light · texture · atmosphere" },
  { src: "/studio/interior-blue.png", title: "Blue Alcove", type: "Interior visualisation", meta: "Materiality · composition · mood" },
  { src: "/studio/chairs.png", title: "Primary Structure", type: "Furniture family", meta: "Modularity · colour · assembly" },
  { src: "/studio/kempu.png", title: "Kempu", type: "Art direction", meta: "Campaign · typography · image" },
  { src: "/studio/magnolias.png", title: "Magnolias", type: "Visual identity", meta: "Editorial · type system · artwork" },
];

const track = ref<HTMLElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
const activeExperience = ref(0);
const activeProject = ref(0);
const activeArtwork = ref(0);
const menuOpen = ref(false);
const progressLabel = ref("00");
const reducedMotion = ref(false);

const currentExperience = computed(() => experiences[activeExperience.value]);
const currentProject = computed(() => projects[activeProject.value]);
const currentArtwork = computed(() => artworks[activeArtwork.value]);

let trigger: ScrollTrigger | null = null;
let frame = 0;
let renderer: THREE.WebGLRenderer | null = null;
let cleanupThree: (() => void) | null = null;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const smooth = (value: number) => { const x = clamp01(value); return x * x * (3 - 2 * x); };
const range = (value: number, start: number, end: number) => smooth((value - start) / (end - start));
const windowValue = (value: number, enterStart: number, enterEnd: number, exitStart: number, exitEnd: number) => range(value, enterStart, enterEnd) * (1 - range(value, exitStart, exitEnd));

const renderProgress = (progress: number) => {
  if (!stage.value) return;
  const hero = 1 - range(progress, 0.08, 0.2);
  const career = windowValue(progress, 0.1, 0.2, 0.34, 0.4);
  const systems = windowValue(progress, 0.32, 0.4, 0.56, 0.63);
  const gallery = windowValue(progress, 0.55, 0.64, 0.86, 0.92);
  const agent = range(progress, 0.86, 0.96);

  stage.value.style.setProperty("--progress", progress.toFixed(5));
  stage.value.style.setProperty("--hero", hero.toFixed(5));
  stage.value.style.setProperty("--career", career.toFixed(5));
  stage.value.style.setProperty("--systems", systems.toFixed(5));
  stage.value.style.setProperty("--gallery", gallery.toFixed(5));
  stage.value.style.setProperty("--agent", agent.toFixed(5));
  progressLabel.value = String(Math.round(progress * 100)).padStart(2, "0");

  activeExperience.value = Math.min(experiences.length - 1, Math.floor(clamp01((progress - 0.16) / 0.2) * experiences.length));
  activeProject.value = Math.min(projects.length - 1, Math.floor(clamp01((progress - 0.38) / 0.2) * projects.length));
  activeArtwork.value = Math.min(artworks.length - 1, Math.floor(clamp01((progress - 0.62) / 0.25) * artworks.length));
  window.dispatchEvent(new CustomEvent("portfolio-progress", { detail: progress }));
};

const goTo = (progress: number) => {
  if (!track.value) return;
  const rect = track.value.getBoundingClientRect();
  const start = scrollY + rect.top;
  const distance = Math.max(1, track.value.offsetHeight - innerHeight);
  scrollTo({ top: start + distance * progress, behavior: reducedMotion.value ? "auto" : "smooth" });
  menuOpen.value = false;
};

const initThree = () => {
  if (!canvas.value) return;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 0.1, 40);
  camera.position.z = 7.5;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas.value, alpha: true, antialias: innerWidth > 760, powerPreference: "high-performance" });
  } catch {
    canvas.value.style.display = "none";
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, innerWidth < 760 ? 1.1 : 1.5));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const group = new THREE.Group();
  scene.add(group);
  const ribbonGeometry = new THREE.PlaneGeometry(9.5, 2.5, 110, 18);
  const position = ribbonGeometry.attributes.position as THREE.BufferAttribute;
  const original = Float32Array.from(position.array as ArrayLike<number>);
  const ribbonMaterial = new THREE.MeshBasicMaterial({ color: 0xb7b1a6, transparent: true, opacity: 0.16, wireframe: true, depthWrite: false });
  const ribbon = new THREE.Mesh(ribbonGeometry, ribbonMaterial);
  ribbon.rotation.x = -0.45;
  ribbon.rotation.z = -0.08;
  group.add(ribbon);

  const pointGeometry = new THREE.BufferGeometry();
  const pointCount = innerWidth < 760 ? 90 : 180;
  const points = new Float32Array(pointCount * 3);
  for (let index = 0; index < pointCount; index += 1) {
    points[index * 3] = (Math.random() - 0.5) * 10;
    points[index * 3 + 1] = (Math.random() - 0.5) * 6;
    points[index * 3 + 2] = (Math.random() - 0.5) * 4;
  }
  pointGeometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
  const pointMaterial = new THREE.PointsMaterial({ color: 0xe9e5dc, size: 0.018, transparent: true, opacity: 0.26, depthWrite: false });
  const pointCloud = new THREE.Points(pointGeometry, pointMaterial);
  group.add(pointCloud);

  let sceneProgress = 0;
  let targetProgress = 0;
  let pointerX = 0;
  let pointerY = 0;
  const clock = new THREE.Clock();
  const onProgress = (event: Event) => { targetProgress = Number((event as CustomEvent<number>).detail ?? 0); };
  const onPointer = (event: PointerEvent) => { pointerX = (event.clientX / innerWidth - 0.5) * 2; pointerY = (event.clientY / innerHeight - 0.5) * 2; };
  const onResize = () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer?.setPixelRatio(Math.min(devicePixelRatio, innerWidth < 760 ? 1.1 : 1.5)); renderer?.setSize(innerWidth, innerHeight); };
  addEventListener("portfolio-progress", onProgress as EventListener);
  addEventListener("pointermove", onPointer, { passive: true });
  addEventListener("resize", onResize);

  const draw = () => {
    const time = clock.getElapsedTime();
    sceneProgress += (targetProgress - sceneProgress) * 0.055;
    for (let index = 0; index < position.count; index += 1) {
      const offset = index * 3;
      const ox = original[offset];
      const oy = original[offset + 1];
      position.setZ(index, Math.sin(ox * 0.72 + time * 0.28 + sceneProgress * 7) * 0.34 + Math.cos(oy * 1.35 - time * 0.19) * 0.12);
      position.setY(index, oy + Math.sin(ox * 0.32 + sceneProgress * Math.PI * 2) * 0.18);
    }
    position.needsUpdate = true;
    ribbon.rotation.y = sceneProgress * 0.7 + pointerX * 0.025;
    ribbon.rotation.x = -0.45 + Math.sin(sceneProgress * Math.PI * 2) * 0.12 + pointerY * 0.018;
    ribbon.position.y = Math.sin(sceneProgress * Math.PI * 3) * 0.28;
    ribbonMaterial.opacity = 0.1 + Math.sin(sceneProgress * Math.PI) * 0.12;
    pointCloud.rotation.y = time * 0.012 + sceneProgress * 0.5;
    pointCloud.rotation.x = pointerY * 0.025;
    pointCloud.position.x = pointerX * 0.08;
    renderer?.render(scene, camera);
    frame = requestAnimationFrame(draw);
  };
  draw();
  cleanupThree = () => {
    cancelAnimationFrame(frame);
    removeEventListener("portfolio-progress", onProgress as EventListener);
    removeEventListener("pointermove", onPointer);
    removeEventListener("resize", onResize);
    ribbonGeometry.dispose();
    ribbonMaterial.dispose();
    pointGeometry.dispose();
    pointMaterial.dispose();
    renderer?.dispose();
  };
};

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);
  reducedMotion.value = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reducedMotion.value && track.value) {
    trigger = ScrollTrigger.create({ trigger: track.value, start: "top top", end: "bottom bottom", scrub: 0.9, onUpdate: (self) => renderProgress(self.progress) });
    initThree();
  } else renderProgress(0);
  addEventListener("load", () => ScrollTrigger.refresh(), { once: true });
});

onBeforeUnmount(() => { trigger?.kill(); cleanupThree?.(); });
</script>

<template>
  <div class="cinematic-portfolio">
    <a class="skip-link" href="#accessible-portfolio">Skip motion experience</a>
    <header class="cinematic-header">
      <button class="cinematic-brand" type="button" @click="goTo(0)" aria-label="Return to opening"><strong>DC</strong><span>SOFTWARE ENGINEER<br />+ CREATIVE TECHNOLOGIST</span></button>
      <div class="cinematic-progress" aria-label="Narrative progress"><span>{{ progressLabel }}</span><i><b :style="{ transform: `scaleX(${Number(progressLabel) / 100})` }" /></i><span>100</span></div>
      <button class="cinematic-menu-toggle" type="button" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">{{ menuOpen ? "CLOSE" : "INDEX" }}</button>
    </header>

    <nav :class="['cinematic-index', { 'is-open': menuOpen }]" aria-label="Portfolio index">
      <button type="button" @click="goTo(0)"><span>01</span><strong>Opening</strong><small>Identity and position</small></button>
      <button type="button" @click="goTo(0.18)"><span>02</span><strong>Trajectory</strong><small>Professional experience</small></button>
      <button type="button" @click="goTo(0.41)"><span>03</span><strong>Systems</strong><small>Selected technical work</small></button>
      <button type="button" @click="goTo(0.66)"><span>04</span><strong>Visual archive</strong><small>Ten material studies</small></button>
      <button type="button" @click="goTo(0.93)"><span>05</span><strong>Agent</strong><small>Questions and administration</small></button>
    </nav>

    <main ref="track" class="cinematic-track">
      <section ref="stage" class="cinematic-stage" aria-label="Scroll-driven portfolio narrative">
        <canvas ref="canvas" class="kinetic-canvas" aria-hidden="true" />
        <div class="cinematic-noise" aria-hidden="true" /><div class="cinematic-grid" aria-hidden="true" />

        <article class="scene scene--hero">
          <div class="hero-fragments" aria-hidden="true"><figure><img src="/studio/interior-shadow.png" alt="" /></figure><figure><img src="/studio/lounge-mint.png" alt="" /></figure><figure><img src="/studio/kempu.png" alt="" /></figure></div>
          <p class="scene-kicker"><span>BUENOS AIRES · ARGENTINA</span><span>SELECTED PRACTICE / 2026</span></p>
          <h1><span>DIEGO</span><span>CA<em>N</em>O</span></h1>
          <p class="hero-thesis">I design software systems, intelligent products and physical ideas with one principle: <em>complexity must become legible.</em></p>
          <div class="scroll-cue"><span>SCROLL TO ENTER</span><i /></div>
        </article>

        <article class="scene scene--career">
          <div class="scene-marker"><span>02</span><i />PROFESSIONAL TRAJECTORY</div>
          <div class="career-rail" aria-hidden="true"><i v-for="(_, index) in experiences" :key="index" :class="{ active: index === activeExperience }" /></div>
          <Transition name="scene-copy" mode="out-in"><div :key="currentExperience.period" class="career-copy"><span>{{ currentExperience.period }} · {{ currentExperience.company }}</span><h2>{{ currentExperience.role }}</h2><p>{{ currentExperience.summary }}</p><ul><li v-for="item in currentExperience.focus" :key="item">{{ item }}</li></ul></div></Transition>
          <div class="career-ghost" aria-hidden="true">{{ String(activeExperience + 1).padStart(2, "0") }}</div>
          <p class="career-principle">Responsibility, constraints and continuity—not a decorative CV timeline.</p>
        </article>

        <article class="scene scene--systems">
          <div class="scene-marker"><span>03</span><i />SELECTED TECHNICAL SYSTEMS</div>
          <div class="system-depth" aria-hidden="true"><div v-for="(project, index) in projects" :key="project.id" :class="['system-slab', { active: index === activeProject }]" :style="{ '--slab-index': index - activeProject }"><span>{{ project.code }}</span><i /><i /><i /><b>{{ project.id }}</b></div></div>
          <Transition name="scene-copy" mode="out-in"><div :key="currentProject.id" class="system-copy"><span>{{ currentProject.id }} · {{ currentProject.field }}</span><h2>{{ currentProject.title }}</h2><p class="system-premise">{{ currentProject.premise }}</p><p>{{ currentProject.detail }}</p><div><span>OUTCOME</span><strong>{{ currentProject.outcome }}</strong></div><ul><li v-for="item in currentProject.stack" :key="item">{{ item }}</li></ul></div></Transition>
          <div class="system-counter"><span>{{ String(activeProject + 1).padStart(2, "0") }}</span><i /><span>{{ String(projects.length).padStart(2, "0") }}</span></div>
        </article>

        <article class="scene scene--gallery">
          <div class="scene-marker"><span>04</span><i />VISUAL / MATERIAL ARCHIVE</div>
          <div class="gallery-environment" aria-label="Ten visual works"><button v-for="(artwork, index) in artworks" :key="artwork.src" :class="['gallery-plane', { active: index === activeArtwork }]" :style="{ '--art-offset': index - activeArtwork }" type="button" :aria-label="`Show ${artwork.title}`" @click="activeArtwork = index"><img :src="artwork.src" :alt="artwork.title" /></button></div>
          <Transition name="scene-copy" mode="out-in"><div :key="currentArtwork.src" class="gallery-caption"><span>{{ String(activeArtwork + 1).padStart(2, "0") }} / {{ String(artworks.length).padStart(2, "0") }} · {{ currentArtwork.type }}</span><h2>{{ currentArtwork.title }}</h2><p>{{ currentArtwork.meta }}</p></div></Transition>
          <div class="gallery-filmstrip" aria-label="Visual archive index"><button v-for="(artwork, index) in artworks" :key="`${artwork.src}-thumb`" type="button" :class="{ active: index === activeArtwork }" @click="activeArtwork = index"><img :src="artwork.src" alt="" /><span>{{ String(index + 1).padStart(2, "0") }}</span></button></div>
        </article>

        <article class="scene scene--agent">
          <div class="scene-marker"><span>05</span><i />PROFESSIONAL AGENT</div>
          <div class="agent-heading"><span>EXPERIENCE · PROJECTS · AVAILABILITY · ADMINISTRATION</span><h2>The portfolio becomes<br /><em>a working interface.</em></h2><p>Ask about the work, prepare a meeting or draft an administrative follow-up. External actions remain reviewable and require explicit confirmation.</p></div>
          <div class="agent-stage"><ContactAssistant /></div>
        </article>
      </section>
    </main>

    <section id="accessible-portfolio" class="motion-fallback">
      <header><span>DIEGO CANO / ACCESSIBLE INDEX</span><h1>Software, AI and material practice.</h1></header>
      <div class="fallback-block"><h2>Experience</h2><article v-for="item in experiences" :key="item.period"><span>{{ item.period }} · {{ item.company }}</span><h3>{{ item.role }}</h3><p>{{ item.summary }}</p></article></div>
      <div class="fallback-block"><h2>Technical systems</h2><article v-for="item in projects" :key="item.id"><span>{{ item.id }} · {{ item.field }}</span><h3>{{ item.title }}</h3><p>{{ item.premise }}</p></article></div>
      <div class="fallback-block fallback-art"><h2>Visual archive</h2><figure v-for="item in artworks" :key="item.src"><img :src="item.src" :alt="item.title" /><figcaption>{{ item.title }} · {{ item.type }}</figcaption></figure></div>
      <ContactAssistant />
    </section>
  </div>
</template>
