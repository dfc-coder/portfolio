<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import * as THREE from "three";
import ContactAssistant from "./ContactAssistant.vue";

type Experience = {
  period: string;
  role: string;
  company: string;
  summary: string;
  focus: string[];
};

type Project = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
};

type Artwork = {
  src: string;
  title: string;
  type: string;
  meta: string;
};

type SceneName = "hero" | "career" | "systems" | "gallery" | "agent";

const experiences: Experience[] = [
  {
    period: "2025 — NOW",
    role: "AI Engineer",
    company: "aiRoss · Madrid / Remote",
    summary:
      "Private document-intelligence systems, structured extraction and production workflows where security, evidence and human review remain visible.",
    focus: ["Local LLMs", "Document AI", "Python", "Product architecture"],
  },
  {
    period: "2024 — 2025",
    role: "Independent AI Engineer",
    company: "Applied AI · Remote",
    summary:
      "Agentic systems, retrieval pipelines and natural-language interfaces designed around operational constraints instead of isolated model demonstrations.",
    focus: ["RAG", "Agents", "NL→SQL", "Evaluation"],
  },
  {
    period: "2023 — 2025",
    role: "Software Engineer",
    company: "FK Tech · Argentina",
    summary:
      "Full-stack products and integrations with an emphasis on maintainable architecture, secure APIs and delivery across the complete software lifecycle.",
    focus: ["TypeScript", "Backend", "Integrations", "Cloud"],
  },
];

const projects: Project[] = [
  {
    id: "01",
    code: "DOC—AI",
    field: "PRIVATE AI / BANKING",
    title: "Secure Document Extractor",
    premise:
      "Sensitive documents become structured financial data without leaving isolated infrastructure.",
    detail:
      "PDF and image documents are segmented, ranked by field and processed by local models. Typed validation and evidence links keep uncertainty reviewable instead of hiding it behind a confident answer.",
    stack: ["Python", "FastAPI", "Docling", "Local LLM", "Redis"],
    outcome: "Private by design · evidence-linked output",
  },
  {
    id: "02",
    code: "NL→SQL",
    field: "AGENTS / DATA ACCESS",
    title: "Natural Language to SQL",
    premise:
      "A conversational question reaches data without granting unrestricted database access.",
    detail:
      "A planner resolves intent, retrieves only relevant schema, applies business rules and rejects ambiguous or unsafe operations before generating a guarded query.",
    stack: ["Python", "Tool calling", "Schema RAG", "SQL policies", "Evaluation"],
    outcome: "Grounded questions · guarded execution",
  },
  {
    id: "03",
    code: "MCP—03",
    field: "FINTECH / AGENT TOOLS",
    title: "Financial MCP Server",
    premise:
      "Market data becomes explicit, reusable instruments rather than an opaque recommendation engine.",
    detail:
      "Each capability exposes a strict contract, identifiable source and predictable output so specialised agents can combine evidence without hiding how an interpretation was produced.",
    stack: ["MCP", "Python", "Market data", "Typed tools", "Agents"],
    outcome: "Signals organised as auditable tools",
  },
  {
    id: "04",
    code: "SEARCH",
    field: "SEMANTIC SEARCH / PRODUCT",
    title: "Intent-aware Shopping Assistant",
    premise:
      "Product discovery starts from a real need, not from exact keyword matching.",
    detail:
      "Incomplete language is converted into comparable attributes, hybrid retrieval candidates and explainable ranking signals evaluated independently from the conversational layer.",
    stack: ["TypeScript", "Embeddings", "Hybrid search", "Catalog API", "Metrics"],
    outcome: "Faster discovery · explainable relevance",
  },
];

const artworks: Artwork[] = [
  {
    src: "/studio/bench-detail.png",
    title: "Quiet Joinery",
    type: "Furniture system",
    meta: "Oak · leather · structural detail",
  },
  {
    src: "/studio/mortar.png",
    title: "Domestic Ritual",
    type: "Object design",
    meta: "Stone · timber · material contrast",
  },
  {
    src: "/studio/radios.png",
    title: "Portable Frequency",
    type: "Product language",
    meta: "CMF · retro-futurism · series",
  },
  {
    src: "/studio/bench.png",
    title: "Linear Rest",
    type: "Furniture design",
    meta: "Structure · proportion · restraint",
  },
  {
    src: "/studio/lounge-mint.png",
    title: "Soft Landscape",
    type: "Seating concept",
    meta: "Textile · tubular steel · comfort",
  },
  {
    src: "/studio/interior-shadow.png",
    title: "Shadow Room",
    type: "Spatial direction",
    meta: "Light · texture · atmosphere",
  },
  {
    src: "/studio/interior-blue.png",
    title: "Blue Alcove",
    type: "Interior visualisation",
    meta: "Materiality · composition · mood",
  },
  {
    src: "/studio/chairs.png",
    title: "Primary Structure",
    type: "Furniture family",
    meta: "Modularity · colour · assembly",
  },
  {
    src: "/studio/kempu.png",
    title: "Kempu",
    type: "Art direction",
    meta: "Campaign · typography · image",
  },
  {
    src: "/studio/magnolias.png",
    title: "Magnolias",
    type: "Visual identity",
    meta: "Editorial · type system · artwork",
  },
];

const track = ref<HTMLElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
const activeExperience = ref(0);
const activeProject = ref(0);
const activeArtwork = ref(0);
const activeScene = ref<SceneName>("hero");
const menuOpen = ref(false);
const progressLabel = ref("00");
const reducedMotion = ref(false);
const introVisible = ref(true);

const currentExperience = computed(() => experiences[activeExperience.value]);
const currentProject = computed(() => projects[activeProject.value]);
const currentArtwork = computed(() => artworks[activeArtwork.value]);

let trigger: ScrollTrigger | null = null;
let motionFrame = 0;
let threeFrame = 0;
let introTimeline: gsap.core.Timeline | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let cleanupThree: (() => void) | null = null;
let targetProgress = 0;
let displayedProgress = 0;
let visualProgress = 0;
let lastFrameTime = performance.now();
let systemCards: HTMLElement[] = [];
let artworkCards: HTMLElement[] = [];

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

const damp = (current: number, target: number, lambda: number, deltaSeconds: number) =>
  current + (target - current) * (1 - Math.exp(-lambda * deltaSeconds));

const sceneForProgress = (progress: number): SceneName => {
  if (progress < 0.125) return "hero";
  if (progress < 0.315) return "career";
  if (progress < 0.555) return "systems";
  if (progress < 0.885) return "gallery";
  return "agent";
};

const setActiveIndex = (position: number, current: number, length: number) => {
  const next = Math.min(length - 1, Math.max(0, Math.round(position)));
  return next === current ? current : next;
};

const sceneOpacities = (progress: number) => {
  const heroToCareer = range(progress, 0.105, 0.14);
  const careerToSystems = range(progress, 0.295, 0.33);
  const systemsToGallery = range(progress, 0.535, 0.57);
  const galleryToAgent = range(progress, 0.865, 0.9);

  return {
    hero: 1 - heroToCareer,
    career: heroToCareer * (1 - careerToSystems),
    systems: careerToSystems * (1 - systemsToGallery),
    gallery: systemsToGallery * (1 - galleryToAgent),
    agent: galleryToAgent,
  };
};

const updateDepthObjects = (projectPosition: number, artworkPosition: number) => {
  systemCards.forEach((element, index) => {
    const offset = index - projectPosition;
    const distance = Math.abs(offset);
    const focus = Math.exp(-(offset * offset) * 3.4);
    const visible = distance < 1.55;

    element.style.visibility = visible ? "visible" : "hidden";
    element.style.transform = [
      `translate3d(${offset * -3.2}vw, ${offset * 2.1}vh, ${offset * -135}px)`,
      `rotateY(${offset * -5.5}deg)`,
      `rotateZ(${offset * -0.7}deg)`,
    ].join(" ");
    element.style.opacity = String(focus * 0.96 + (visible ? 0.025 : 0));
    element.style.filter = `brightness(${0.34 + focus * 0.66})`;
    element.style.zIndex = String(30 - Math.round(distance * 5));
    element.style.setProperty("--focus", focus.toFixed(4));
  });

  artworkCards.forEach((element, index) => {
    const offset = index - artworkPosition;
    const distance = Math.abs(offset);
    const focus = Math.exp(-(offset * offset) * 4.6);
    const visible = distance < 1.18;

    element.style.visibility = visible ? "visible" : "hidden";
    element.style.transform = [
      `translate3d(calc(-50% + ${offset * 15}vw), calc(-50% + ${offset * -0.6}vh), ${offset * -210}px)`,
      `rotateY(${offset * -5.8}deg)`,
      `rotateZ(${offset * 0.55}deg)`,
    ].join(" ");
    element.style.opacity = String(focus + (visible ? 0.025 : 0));
    element.style.filter = `grayscale(${1 - focus}) brightness(${0.38 + focus * 0.62})`;
    element.style.zIndex = String(40 - Math.round(distance * 6));
    element.style.pointerEvents =
      activeScene.value === "gallery" && distance < 0.48 ? "auto" : "none";
  });
};

const renderProgress = (progress: number) => {
  if (!stage.value) return;

  const opacity = sceneOpacities(progress);
  const experiencePosition =
    clamp01((progress - 0.14) / (0.295 - 0.14)) * (experiences.length - 1);
  const projectPosition =
    clamp01((progress - 0.33) / (0.535 - 0.33)) * (projects.length - 1);
  const artworkPosition =
    clamp01((progress - 0.57) / (0.865 - 0.57)) * (artworks.length - 1);

  activeScene.value = sceneForProgress(progress);
  stage.value.dataset.scene = activeScene.value;
  stage.value.style.setProperty("--progress", progress.toFixed(5));
  stage.value.style.setProperty("--hero", opacity.hero.toFixed(5));
  stage.value.style.setProperty("--career", opacity.career.toFixed(5));
  stage.value.style.setProperty("--systems", opacity.systems.toFixed(5));
  stage.value.style.setProperty("--gallery", opacity.gallery.toFixed(5));
  stage.value.style.setProperty("--agent", opacity.agent.toFixed(5));

  progressLabel.value = String(Math.round(progress * 100)).padStart(2, "0");
  activeExperience.value = setActiveIndex(
    experiencePosition,
    activeExperience.value,
    experiences.length,
  );
  activeProject.value = setActiveIndex(projectPosition, activeProject.value, projects.length);
  activeArtwork.value = setActiveIndex(artworkPosition, activeArtwork.value, artworks.length);

  updateDepthObjects(projectPosition, artworkPosition);
  visualProgress = progress;
};

const goTo = (progress: number) => {
  if (!track.value) return;
  const rect = track.value.getBoundingClientRect();
  const start = scrollY + rect.top;
  const distance = Math.max(1, track.value.offsetHeight - innerHeight);
  scrollTo({
    top: start + distance * progress,
    behavior: reducedMotion.value ? "auto" : "smooth",
  });
  menuOpen.value = false;
};

const goToExperience = (index: number) =>
  goTo(0.14 + (index / Math.max(1, experiences.length - 1)) * (0.295 - 0.14));

const goToProject = (index: number) =>
  goTo(0.33 + (index / Math.max(1, projects.length - 1)) * (0.535 - 0.33));

const goToArtwork = (index: number) =>
  goTo(0.57 + (index / Math.max(1, artworks.length - 1)) * (0.865 - 0.57));

const startMotionLoop = () => {
  const tick = (time: number) => {
    const deltaSeconds = Math.min(0.04, Math.max(0.001, (time - lastFrameTime) / 1000));
    lastFrameTime = time;
    displayedProgress = reducedMotion.value
      ? targetProgress
      : damp(displayedProgress, targetProgress, 17, deltaSeconds);
    renderProgress(displayedProgress);
    motionFrame = requestAnimationFrame(tick);
  };

  motionFrame = requestAnimationFrame(tick);
};

const initThree = () => {
  if (!canvas.value) return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.1, 30);
  camera.position.z = 7;

  try {
    renderer = new THREE.WebGLRenderer({
      canvas: canvas.value,
      alpha: true,
      antialias: innerWidth > 760,
      powerPreference: "high-performance",
    });
  } catch {
    canvas.value.style.display = "none";
    return;
  }

  renderer.setPixelRatio(Math.min(devicePixelRatio, innerWidth < 760 ? 1 : 1.35));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const lineCount = 130;
  const lineGeometry = new THREE.BufferGeometry();
  const linePositions = new Float32Array(lineCount * 3);
  const lineBase = new Float32Array(lineCount * 3);

  for (let index = 0; index < lineCount; index += 1) {
    const t = index / (lineCount - 1);
    const offset = index * 3;
    lineBase[offset] = -5.4 + t * 10.8;
    lineBase[offset + 1] = Math.sin(t * Math.PI * 2) * 0.5;
    lineBase[offset + 2] = Math.cos(t * Math.PI * 2) * 0.25;
    linePositions[offset] = lineBase[offset];
    linePositions[offset + 1] = lineBase[offset + 1];
    linePositions[offset + 2] = lineBase[offset + 2];
  }

  lineGeometry.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
  const lineMaterial = new THREE.LineBasicMaterial({
    color: 0xc9c3b8,
    transparent: true,
    opacity: 0.16,
  });
  const line = new THREE.Line(lineGeometry, lineMaterial);
  line.rotation.z = -0.14;
  line.position.y = 0.25;
  scene.add(line);

  const pointCount = innerWidth < 760 ? 70 : 130;
  const pointGeometry = new THREE.BufferGeometry();
  const points = new Float32Array(pointCount * 3);

  for (let index = 0; index < pointCount; index += 1) {
    points[index * 3] = (Math.random() - 0.5) * 10;
    points[index * 3 + 1] = (Math.random() - 0.5) * 5.8;
    points[index * 3 + 2] = (Math.random() - 0.5) * 3;
  }

  pointGeometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
  const pointMaterial = new THREE.PointsMaterial({
    color: 0xe7e1d7,
    size: 0.015,
    transparent: true,
    opacity: 0.2,
    depthWrite: false,
  });
  const pointCloud = new THREE.Points(pointGeometry, pointMaterial);
  scene.add(pointCloud);

  let sceneProgress = 0;
  let pointerX = 0;
  let pointerY = 0;
  const clock = new THREE.Clock();

  const onPointer = (event: PointerEvent) => {
    pointerX = (event.clientX / innerWidth - 0.5) * 2;
    pointerY = (event.clientY / innerHeight - 0.5) * 2;
  };

  const onResize = () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer?.setPixelRatio(Math.min(devicePixelRatio, innerWidth < 760 ? 1 : 1.35));
    renderer?.setSize(innerWidth, innerHeight);
    ScrollTrigger.refresh();
  };

  addEventListener("pointermove", onPointer, { passive: true });
  addEventListener("resize", onResize);

  const draw = () => {
    const time = clock.getElapsedTime();
    sceneProgress += (visualProgress - sceneProgress) * 0.065;
    const attribute = lineGeometry.attributes.position as THREE.BufferAttribute;

    for (let index = 0; index < lineCount; index += 1) {
      const offset = index * 3;
      const x = lineBase[offset];
      const y = lineBase[offset + 1];
      attribute.setY(
        index,
        y + Math.sin(x * 0.75 + time * 0.3 + sceneProgress * 8) * 0.22,
      );
      attribute.setZ(index, Math.cos(x * 0.52 - time * 0.22) * 0.14);
    }

    attribute.needsUpdate = true;
    line.rotation.y = sceneProgress * 0.42 + pointerX * 0.018;
    line.position.y = 0.25 + Math.sin(sceneProgress * Math.PI * 2) * 0.18;
    lineMaterial.opacity = activeScene.value === "agent" ? 0 : 0.08 + (1 - sceneProgress) * 0.06;
    pointCloud.rotation.y = time * 0.009 + sceneProgress * 0.28;
    pointCloud.position.x = pointerX * 0.05;
    pointCloud.position.y = pointerY * -0.04;

    renderer?.render(scene, camera);
    threeFrame = requestAnimationFrame(draw);
  };

  draw();

  cleanupThree = () => {
    cancelAnimationFrame(threeFrame);
    removeEventListener("pointermove", onPointer);
    removeEventListener("resize", onResize);
    lineGeometry.dispose();
    lineMaterial.dispose();
    pointGeometry.dispose();
    pointMaterial.dispose();
    renderer?.dispose();
  };
};

const runIntro = () => {
  if (reducedMotion.value) {
    introVisible.value = false;
    return;
  }

  document.documentElement.classList.add("is-refined-intro");
  gsap.set(".ref-hero__media figure, .ref-hero__title span, .ref-hero__meta, .ref-hero__thesis, .ref-scroll-cue, .ref-header", {
    opacity: 0,
  });

  introTimeline = gsap
    .timeline({
      defaults: { ease: "power3.out" },
      onComplete: () => {
        introVisible.value = false;
        document.documentElement.classList.remove("is-refined-intro");
      },
    })
    .from(".ref-intro__title span", {
      yPercent: 112,
      duration: 0.76,
      stagger: 0.07,
    })
    .from(
      ".ref-intro__media figure",
      {
        opacity: 0,
        scale: 1.08,
        y: 22,
        duration: 0.82,
        stagger: 0.08,
      },
      "-=0.55",
    )
    .from(
      ".ref-intro__meta span",
      { opacity: 0, y: 9, duration: 0.42, stagger: 0.06 },
      "-=0.55",
    )
    .to(".ref-intro__line i", { scaleX: 1, duration: 0.8, ease: "expo.inOut" }, "-=0.45")
    .to(
      ".ref-intro__title, .ref-intro__media, .ref-intro__meta, .ref-intro__line",
      { opacity: 0, duration: 0.42, ease: "power2.in" },
      "+=0.18",
    )
    .to(
      ".ref-intro__panel--top",
      { yPercent: -101, duration: 0.86, ease: "expo.inOut" },
      "<",
    )
    .to(
      ".ref-intro__panel--bottom",
      { yPercent: 101, duration: 0.86, ease: "expo.inOut" },
      "<",
    )
    .to(
      ".ref-hero__media figure",
      { opacity: 1, scale: 1, y: 0, duration: 0.92, stagger: 0.07 },
      "-=0.72",
    )
    .to(
      ".ref-hero__title span",
      { opacity: 1, yPercent: 0, duration: 0.82, stagger: 0.07 },
      "-=0.86",
    )
    .to(
      ".ref-hero__meta, .ref-hero__thesis, .ref-scroll-cue, .ref-header",
      { opacity: 1, y: 0, duration: 0.56, stagger: 0.06 },
      "-=0.52",
    );
};

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);

  reducedMotion.value = matchMedia("(prefers-reduced-motion: reduce)").matches;
  systemCards = Array.from(document.querySelectorAll<HTMLElement>(".ref-system-card"));
  artworkCards = Array.from(document.querySelectorAll<HTMLElement>(".ref-art-card"));

  renderProgress(0);

  if (!reducedMotion.value && track.value) {
    trigger = ScrollTrigger.create({
      trigger: track.value,
      start: "top top",
      end: "bottom bottom",
      onUpdate: (self) => {
        targetProgress = self.progress;
      },
      invalidateOnRefresh: true,
    });
    initThree();
    startMotionLoop();
  }

  runIntro();
  addEventListener("load", () => ScrollTrigger.refresh(), { once: true });
});

onBeforeUnmount(() => {
  trigger?.kill();
  introTimeline?.kill();
  cancelAnimationFrame(motionFrame);
  cleanupThree?.();
  document.documentElement.classList.remove("is-refined-intro");
});
</script>

<template>
  <div class="ref-portfolio">
    <a class="ref-skip" href="#ref-fallback">Skip motion experience</a>

    <div v-if="introVisible" class="ref-intro" aria-hidden="true">
      <div class="ref-intro__panel ref-intro__panel--top" />
      <div class="ref-intro__panel ref-intro__panel--bottom" />
      <div class="ref-intro__media">
        <figure><img src="/studio/interior-shadow.png" alt="" /></figure>
        <figure><img src="/studio/lounge-mint.png" alt="" /></figure>
        <figure><img src="/studio/kempu.png" alt="" /></figure>
      </div>
      <div class="ref-intro__meta">
        <span>BUENOS AIRES · ARGENTINA</span>
        <span>SELECTED PRACTICE / 2026</span>
      </div>
      <h1 class="ref-intro__title"><span>DIEGO</span><span>CA<em>N</em>O</span></h1>
      <div class="ref-intro__line"><i /></div>
    </div>

    <header class="ref-header">
      <button type="button" class="ref-brand" aria-label="Return to opening" @click="goTo(0)">
        <strong>DC</strong><span>SOFTWARE ENGINEER<br />+ CREATIVE TECHNOLOGIST</span>
      </button>
      <div class="ref-progress"><span>{{ progressLabel }}</span><i><b :style="{ transform: `scaleX(${Number(progressLabel) / 100})` }" /></i><span>100</span></div>
      <button type="button" class="ref-index-toggle" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">{{ menuOpen ? "CLOSE" : "INDEX" }}</button>
    </header>

    <nav :class="['ref-index', { 'is-open': menuOpen }]" aria-label="Portfolio index">
      <button type="button" @click="goTo(0)"><span>01</span><strong>Opening</strong></button>
      <button type="button" @click="goTo(0.16)"><span>02</span><strong>Trajectory</strong></button>
      <button type="button" @click="goTo(0.36)"><span>03</span><strong>Systems</strong></button>
      <button type="button" @click="goTo(0.6)"><span>04</span><strong>Visual archive</strong></button>
      <button type="button" @click="goTo(0.92)"><span>05</span><strong>Agent</strong></button>
    </nav>

    <main ref="track" class="ref-track">
      <section ref="stage" class="ref-stage" data-scene="hero" aria-label="Scroll-driven portfolio narrative">
        <canvas ref="canvas" class="ref-canvas" aria-hidden="true" />
        <div class="ref-grain" aria-hidden="true" />

        <article class="ref-scene ref-scene--hero">
          <div class="ref-hero__media" aria-hidden="true">
            <figure><img src="/studio/interior-shadow.png" alt="" /></figure>
            <figure><img src="/studio/lounge-mint.png" alt="" /></figure>
            <figure><img src="/studio/kempu.png" alt="" /></figure>
          </div>
          <p class="ref-hero__meta"><span>BUENOS AIRES · ARGENTINA</span><span>SELECTED PRACTICE / 2026</span></p>
          <h1 class="ref-hero__title"><span>DIEGO</span><span>CA<em>N</em>O</span></h1>
          <p class="ref-hero__thesis">I design software systems, intelligent products and physical ideas with one principle: <em>complexity must become legible.</em></p>
          <div class="ref-scroll-cue"><span>SCROLL TO ENTER</span><i /></div>
        </article>

        <article class="ref-scene ref-scene--career">
          <div class="ref-marker"><span>02</span><i />PROFESSIONAL TRAJECTORY</div>
          <div class="ref-career-nav" aria-label="Professional experience index">
            <button v-for="(_, index) in experiences" :key="index" type="button" :class="{ active: index === activeExperience }" :aria-label="`Show experience ${index + 1}`" @click="goToExperience(index)" />
          </div>
          <Transition name="ref-copy" mode="out-in">
            <div :key="currentExperience.period" class="ref-career-copy">
              <span>{{ currentExperience.period }} · {{ currentExperience.company }}</span>
              <h2>{{ currentExperience.role }}</h2>
              <p>{{ currentExperience.summary }}</p>
              <ul><li v-for="item in currentExperience.focus" :key="item">{{ item }}</li></ul>
            </div>
          </Transition>
          <div class="ref-career-number" aria-hidden="true">{{ String(activeExperience + 1).padStart(2, "0") }}</div>
        </article>

        <article class="ref-scene ref-scene--systems">
          <div class="ref-marker"><span>03</span><i />SELECTED TECHNICAL SYSTEMS</div>
          <div class="ref-system-stack" aria-hidden="true">
            <div v-for="(project, index) in projects" :key="project.id" :class="['ref-system-card', { active: index === activeProject }]">
              <div class="ref-system-card__grid" />
              <span>{{ project.code }}</span><b>{{ project.id }}</b><i /><i /><i />
            </div>
          </div>
          <Transition name="ref-copy" mode="out-in">
            <div :key="currentProject.id" class="ref-system-copy">
              <span>{{ currentProject.id }} · {{ currentProject.field }}</span>
              <h2>{{ currentProject.title }}</h2>
              <p class="ref-system-premise">{{ currentProject.premise }}</p>
              <p>{{ currentProject.detail }}</p>
              <div><span>OUTCOME</span><strong>{{ currentProject.outcome }}</strong></div>
              <ul><li v-for="item in currentProject.stack" :key="item">{{ item }}</li></ul>
            </div>
          </Transition>
          <div class="ref-system-nav" aria-label="Technical project index">
            <button v-for="(_, index) in projects" :key="index" type="button" :class="{ active: index === activeProject }" :aria-label="`Show project ${index + 1}`" @click="goToProject(index)">{{ String(index + 1).padStart(2, "0") }}</button>
          </div>
        </article>

        <article class="ref-scene ref-scene--gallery">
          <div class="ref-marker"><span>04</span><i />VISUAL / MATERIAL ARCHIVE</div>
          <div class="ref-gallery-stage" aria-label="Ten visual works">
            <button v-for="(artwork, index) in artworks" :key="artwork.src" :class="['ref-art-card', { active: index === activeArtwork }]" type="button" :aria-label="`Show ${artwork.title}`" @click="goToArtwork(index)"><img :src="artwork.src" :alt="artwork.title" /></button>
          </div>
          <Transition name="ref-copy" mode="out-in">
            <div :key="currentArtwork.src" class="ref-art-caption">
              <span>{{ String(activeArtwork + 1).padStart(2, "0") }} / {{ String(artworks.length).padStart(2, "0") }} · {{ currentArtwork.type }}</span>
              <h2>{{ currentArtwork.title }}</h2>
              <p>{{ currentArtwork.meta }}</p>
            </div>
          </Transition>
          <div class="ref-filmstrip" aria-label="Visual archive index">
            <button v-for="(artwork, index) in artworks" :key="`${artwork.src}-thumb`" type="button" :class="{ active: index === activeArtwork }" :aria-label="`Go to ${artwork.title}`" @click="goToArtwork(index)"><img :src="artwork.src" alt="" /><span>{{ String(index + 1).padStart(2, "0") }}</span></button>
          </div>
        </article>

        <article class="ref-scene ref-scene--agent">
          <div class="ref-marker"><span>05</span><i />PROFESSIONAL AGENT</div>
          <div class="ref-agent-heading"><span>EXPERIENCE · PROJECTS · AVAILABILITY</span><h2>A useful interface,<br /><em>not a decoration.</em></h2><p>Ask about the work or prepare a reviewable meeting request. Every visible control performs an action.</p></div>
          <div class="ref-agent-stage"><ContactAssistant /></div>
        </article>
      </section>
    </main>

    <section id="ref-fallback" class="ref-fallback">
      <header><span>DIEGO CANO / ACCESSIBLE INDEX</span><h1>Software, AI and material practice.</h1></header>
      <div><h2>Experience</h2><article v-for="item in experiences" :key="item.period"><span>{{ item.period }} · {{ item.company }}</span><h3>{{ item.role }}</h3><p>{{ item.summary }}</p></article></div>
      <div><h2>Technical systems</h2><article v-for="item in projects" :key="item.id"><span>{{ item.id }} · {{ item.field }}</span><h3>{{ item.title }}</h3><p>{{ item.premise }}</p></article></div>
      <div class="ref-fallback-art"><h2>Visual archive</h2><figure v-for="item in artworks" :key="item.src"><img :src="item.src" :alt="item.title" /><figcaption>{{ item.title }} · {{ item.type }}</figcaption></figure></div>
      <ContactAssistant />
    </section>
  </div>
</template>
