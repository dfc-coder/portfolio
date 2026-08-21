<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import AgentOS from "./AgentOS.vue";

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

type SceneName = "hero" | "chapter" | "career" | "systems" | "gallery" | "agent";

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
    id: "00",
    code: "REACT—AI",
    field: "AGENTIC AI / LOCAL-FIRST",
    title: "Reflective ReAct Agent",
    premise:
      "A general-purpose local assistant can reason, use tools and recover from execution failures without being tied to a specific domain.",
    detail:
      "A bounded ReAct loop combines injected tools, deterministic verification and triggered reflection. Local inference runs on Qwen through llama.cpp, with private retrieval and specialised embedding/reranking, while an AWS-compatible runtime provides the infrastructure needed to test the same agent as a real system.",
    stack: [
      "Python",
      "Qwen3.5 2B",
      "ReAct + Reflection",
      "llama.cpp",
      "OpenVINO",
      "LangChain",
      "AWS CDK / Lambda",
      "S3 Vectors",
      "Podman / Floci",
    ],
    outcome:
      "General-purpose local agent · controlled autonomous execution",
  },
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

const HERO_NODE = 0;
const CHAPTER_CAREER_NODE = 1;
const CAREER_START_NODE = CHAPTER_CAREER_NODE + 1;
const CHAPTER_SYSTEMS_NODE = CAREER_START_NODE + experiences.length;
const SYSTEMS_START_NODE = CHAPTER_SYSTEMS_NODE + 1;
const CHAPTER_GALLERY_NODE = SYSTEMS_START_NODE + projects.length;
const GALLERY_START_NODE = CHAPTER_GALLERY_NODE + 1;
const CHAPTER_AGENT_NODE = GALLERY_START_NODE + artworks.length;
const AGENT_NODE = CHAPTER_AGENT_NODE + 1;
const LAST_NODE = AGENT_NODE;
const STEP_HOLD_START = 0.2;
const STEP_HOLD_END = 0.8;
const SCENE_CROSSFADE_WIDTH = 0.46;

const chapters = [
  { key: "career", kicker: "CHAPTER 02 · THE RECORD", line: "First, the proof — where the practice was built." },
  { key: "systems", kicker: "CHAPTER 03 · THE EVIDENCE", line: "Roles condense into systems that shipped." },
  { key: "gallery", kicker: "CHAPTER 04 · A NOTE ON ORIGIN", line: "My first language was design — here the argument turns visual." },
  { key: "agent", kicker: "CHAPTER 05 · THE INTERFACE", line: "Enough archive. Ask the work a question." },
] as const;

const TELEPORT_NODE_DISTANCE = 1.5;

const track = ref<HTMLElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const activeExperience = ref(0);
const activeProject = ref(0);
const activeArtwork = ref(0);
const activeScene = ref<SceneName>("hero");
const menuOpen = ref(false);
const progressLabel = ref("00");
const reducedMotion = ref(false);
const introVisible = ref(true);
const teleport = ref<HTMLElement | null>(null);
const cursorDot = ref<HTMLElement | null>(null);
const cursorRing = ref<HTMLElement | null>(null);
const cursorState = ref<"idle" | "hover" | "press" | "text">("idle");
const cursorEnabled = ref(false);

const currentExperience = computed(() => experiences[activeExperience.value]);
const currentProject = computed(() => projects[activeProject.value]);
const currentArtwork = computed(() => artworks[activeArtwork.value]);

let trigger: ScrollTrigger | null = null;
let motionFrame = 0;
let introTimeline: gsap.core.Timeline | null = null;
let teleportTimeline: gsap.core.Timeline | null = null;
let targetProgress = 0;
let displayedProgress = 0;
let lastFrameTime = performance.now();
let systemCards: HTMLElement[] = [];
let artworkCards: HTMLElement[] = [];
let cursorFrame = 0;
let pointerX = 0;
let pointerY = 0;
let ringX = 0;
let ringY = 0;
let cursorSeen = false;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

const damp = (current: number, target: number, lambda: number, deltaSeconds: number) =>
  current + (target - current) * (1 - Math.exp(-lambda * deltaSeconds));

const progressToNode = (progress: number) => clamp01(progress) * LAST_NODE;
const nodeToProgress = (node: number) => Math.min(LAST_NODE, Math.max(0, node)) / LAST_NODE;

const collectionPosition = (nodePosition: number, startNode: number, count: number) => {
  const lastIndex = count - 1;
  const raw = Math.min(lastIndex, Math.max(0, nodePosition - startNode));
  if (raw >= lastIndex) return lastIndex;

  const index = Math.floor(raw);
  const local = raw - index;

  if (local <= STEP_HOLD_START) return index;
  if (local >= STEP_HOLD_END) return index + 1;

  return index + smoother((local - STEP_HOLD_START) / (STEP_HOLD_END - STEP_HOLD_START));
};

const crossfadeAt = (nodePosition: number, boundary: number) =>
  range(
    nodePosition,
    boundary - SCENE_CROSSFADE_WIDTH / 2,
    boundary + SCENE_CROSSFADE_WIDTH / 2,
  );

const sceneForNode = (nodePosition: number): SceneName => {
  if (nodePosition < CHAPTER_CAREER_NODE - 0.5) return "hero";
  if (nodePosition < CAREER_START_NODE - 0.5) return "chapter";
  if (nodePosition < CHAPTER_SYSTEMS_NODE - 0.5) return "career";
  if (nodePosition < SYSTEMS_START_NODE - 0.5) return "chapter";
  if (nodePosition < CHAPTER_GALLERY_NODE - 0.5) return "systems";
  if (nodePosition < GALLERY_START_NODE - 0.5) return "chapter";
  if (nodePosition < CHAPTER_AGENT_NODE - 0.5) return "gallery";
  if (nodePosition < AGENT_NODE - 0.5) return "chapter";
  return "agent";
};

const sceneOpacities = (nodePosition: number) => {
  const heroToChapter = crossfadeAt(nodePosition, CHAPTER_CAREER_NODE - 0.5);
  const chapterToCareer = crossfadeAt(nodePosition, CAREER_START_NODE - 0.5);
  const careerToChapter = crossfadeAt(nodePosition, CHAPTER_SYSTEMS_NODE - 0.5);
  const chapterToSystems = crossfadeAt(nodePosition, SYSTEMS_START_NODE - 0.5);
  const systemsToChapter = crossfadeAt(nodePosition, CHAPTER_GALLERY_NODE - 0.5);
  const chapterToGallery = crossfadeAt(nodePosition, GALLERY_START_NODE - 0.5);
  const galleryToChapter = crossfadeAt(nodePosition, CHAPTER_AGENT_NODE - 0.5);
  const chapterToAgent = crossfadeAt(nodePosition, AGENT_NODE - 0.5);

  return {
    hero: 1 - heroToChapter,
    chapterCareer: heroToChapter * (1 - chapterToCareer),
    career: chapterToCareer * (1 - careerToChapter),
    chapterSystems: careerToChapter * (1 - chapterToSystems),
    systems: chapterToSystems * (1 - systemsToChapter),
    chapterGallery: systemsToChapter * (1 - chapterToGallery),
    gallery: chapterToGallery * (1 - galleryToChapter),
    chapterAgent: galleryToChapter * (1 - chapterToAgent),
    agent: chapterToAgent,
  };
};

const setActiveIndex = (position: number, current: number, length: number) => {
  const next = Math.min(length - 1, Math.max(0, Math.round(position)));
  return next === current ? current : next;
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
    /* Wider focus falloff than the other collections: neighbours must stay
       readable, because the depth only reads as depth if you can see the
       pieces receding behind the active one. */
    const focus = Math.exp(-(offset * offset) * 1.45);
    const visible = distance <= 2.4;
    const clamped = Math.min(distance, 3);

    /* The previous build rotated 4.8deg per step, which at this perspective is
       invisible — the scene was declared 3D but rendered flat. These values put
       the pieces on a real arc: they turn away from the viewer and recede on
       both sides, like objects on a turntable. */
    const depth = -clamped * 330;
    const sink = clamped * 2.4;
    /* Rotation is capped below 90deg: past that the plane faces away and
       backface-visibility would drop it out of the scene entirely. */
    const turn = Math.max(-1.85, Math.min(1.85, offset)) * -38;

    element.style.visibility = visible ? "visible" : "hidden";
    element.style.transform = [
      `translate3d(calc(-50% + ${offset * 17}vw), calc(-50% + ${sink}vh), ${depth}px)`,
      `rotateY(${turn.toFixed(2)}deg)`,
      `scale(${(1 - clamped * 0.05).toFixed(3)})`,
    ].join(" ");
    element.style.opacity = String(visible ? Math.max(0.05, 0.22 + focus * 0.78) : 0);
    /* Depth of field: everything off-centre softens and desaturates, so the eye
       is told which object is being presented. */
    const blur = distance > 0.55 ? Math.min(5, (distance - 0.55) * 2.6) : 0;
    element.style.filter = [
      `grayscale(${(1 - focus).toFixed(3)})`,
      `brightness(${(0.34 + focus * 0.66).toFixed(3)})`,
      `blur(${blur.toFixed(2)}px)`,
    ].join(" ");
    element.style.zIndex = String(40 - Math.round(distance * 7));
    element.style.pointerEvents =
      activeScene.value === "gallery" && distance < 0.5 ? "auto" : "none";
  });
};

const renderProgress = (progress: number) => {
  if (!stage.value) return;

  const nodePosition = progressToNode(progress);
  const opacity = sceneOpacities(nodePosition);
  const experiencePosition = collectionPosition(
    nodePosition,
    CAREER_START_NODE,
    experiences.length,
  );
  const projectPosition = collectionPosition(
    nodePosition,
    SYSTEMS_START_NODE,
    projects.length,
  );
  const artworkPosition = collectionPosition(
    nodePosition,
    GALLERY_START_NODE,
    artworks.length,
  );

  activeScene.value = sceneForNode(nodePosition);
  stage.value.dataset.scene = activeScene.value;
  stage.value.style.setProperty("--progress", progress.toFixed(5));
  stage.value.style.setProperty("--hero", opacity.hero.toFixed(5));
  stage.value.style.setProperty("--career", opacity.career.toFixed(5));
  stage.value.style.setProperty("--systems", opacity.systems.toFixed(5));
  stage.value.style.setProperty("--gallery", opacity.gallery.toFixed(5));
  stage.value.style.setProperty("--agent", opacity.agent.toFixed(5));
  stage.value.style.setProperty("--chapter-career", opacity.chapterCareer.toFixed(5));
  stage.value.style.setProperty("--chapter-systems", opacity.chapterSystems.toFixed(5));
  stage.value.style.setProperty("--chapter-gallery", opacity.chapterGallery.toFixed(5));
  stage.value.style.setProperty("--chapter-agent", opacity.chapterAgent.toFixed(5));

  progressLabel.value = String(Math.round(progress * 100)).padStart(2, "0");
  activeExperience.value = setActiveIndex(
    experiencePosition,
    activeExperience.value,
    experiences.length,
  );
  activeProject.value = setActiveIndex(projectPosition, activeProject.value, projects.length);
  activeArtwork.value = setActiveIndex(artworkPosition, activeArtwork.value, artworks.length);

  updateDepthObjects(projectPosition, artworkPosition);
};

const goTo = (progress: number) => {
  if (!track.value) return;
  const rect = track.value.getBoundingClientRect();
  const start = scrollY + rect.top;
  const distance = Math.max(1, track.value.offsetHeight - innerHeight);
  const top = start + distance * clamp01(progress);
  menuOpen.value = false;

  if (reducedMotion.value) {
    scrollTo({ top, behavior: "auto" });
    return;
  }

  const currentNode = progressToNode(displayedProgress);
  const targetNode = progressToNode(clamp01(progress));

  if (Math.abs(targetNode - currentNode) <= TELEPORT_NODE_DISTANCE || !teleport.value) {
    scrollTo({ top, behavior: "smooth" });
    return;
  }

  const cover = teleport.value;
  teleportTimeline?.kill();
  teleportTimeline = gsap.timeline({
    onComplete: () => gsap.set(cover, { visibility: "hidden" }),
  });
  teleportTimeline
    .set(cover, { visibility: "visible" })
    .fromTo(
      cover,
      { clipPath: "inset(0% 0% 100% 0%)" },
      { clipPath: "inset(0% 0% 0% 0%)", duration: 0.3, ease: "expo.in" },
    )
    .add(() => {
      scrollTo({ top, behavior: "auto" });
      const progressAtTarget = clamp01(progress);
      targetProgress = progressAtTarget;
      displayedProgress = progressAtTarget;
      renderProgress(progressAtTarget);
    })
    .to(cover, {
      clipPath: "inset(100% 0% 0% 0%)",
      duration: 0.44,
      ease: "expo.out",
      delay: 0.08,
    });
};

const goToNode = (node: number) => goTo(nodeToProgress(node));
const goToExperience = (index: number) => goToNode(CAREER_START_NODE + index);
const goToProject = (index: number) => goToNode(SYSTEMS_START_NODE + index);
const goToArtwork = (index: number) => goToNode(GALLERY_START_NODE + index);

const onKeydown = (event: KeyboardEvent) => {
  const target = event.target as HTMLElement | null;
  if (
    target &&
    (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
  ) {
    return;
  }

  if (
    introVisible.value &&
    ["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].includes(event.key)
  ) {
    event.preventDefault();
    return;
  }

  if (activeScene.value !== "gallery") return;

  if (event.key === "ArrowRight") {
    event.preventDefault();
    goToArtwork(Math.min(artworks.length - 1, activeArtwork.value + 1));
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    goToArtwork(Math.max(0, activeArtwork.value - 1));
  } else if (event.key === "Home") {
    event.preventDefault();
    goToArtwork(0);
  } else if (event.key === "End") {
    event.preventDefault();
    goToArtwork(artworks.length - 1);
  }
};

const preventIntroScroll = (event: Event) => {
  if (introVisible.value) event.preventDefault();
};

const CURSOR_INTERACTIVE = "button, a, input, textarea, select, [data-cursor]";

const cursorStateFor = (element: Element | null): "idle" | "hover" | "text" => {
  if (!element) return "idle";
  const tag = element.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" ? "text" : "hover";
};

const onCursorMove = (event: PointerEvent) => {
  pointerX = event.clientX;
  pointerY = event.clientY;

  /* Gallery parallax: the whole arc turns a few degrees toward the cursor.
     Small numbers on purpose — it should feel like the room has depth, not
     like the scene is chasing the mouse. */
  if (activeScene.value === "gallery") {
    const stageElement = document.querySelector<HTMLElement>(".ref-gallery-stage");
    if (stageElement) {
      const nx = pointerX / window.innerWidth - 0.5;
      const ny = pointerY / window.innerHeight - 0.5;
      stageElement.style.setProperty("--tilt-y", `${(nx * 7).toFixed(2)}deg`);
      stageElement.style.setProperty("--tilt-x", `${(ny * -4.5).toFixed(2)}deg`);
    }
  }

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
  const interactive = (event.target as Element | null)?.closest?.(CURSOR_INTERACTIVE) ?? null;
  cursorState.value = cursorStateFor(interactive);
};

const onCursorDown = () => {
  if (cursorState.value !== "text") cursorState.value = "press";
};

const onCursorUp = (event: PointerEvent) => {
  const interactive = (event.target as Element | null)?.closest?.(CURSOR_INTERACTIVE) ?? null;
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

const startMotionLoop = () => {
  const tick = (time: number) => {
    const deltaSeconds = Math.min(0.04, Math.max(0.001, (time - lastFrameTime) / 1000));
    lastFrameTime = time;
    displayedProgress = reducedMotion.value
      ? targetProgress
      : damp(displayedProgress, targetProgress, 22, deltaSeconds);
    renderProgress(displayedProgress);
    motionFrame = requestAnimationFrame(tick);
  };

  motionFrame = requestAnimationFrame(tick);
};

const firstGlyphRect = (element: HTMLElement): DOMRect => {
  const textNode = Array.from(element.childNodes).find(
    (node) => node.nodeType === Node.TEXT_NODE && Boolean(node.textContent?.trim()),
  );
  if (!textNode?.textContent) return element.getBoundingClientRect();

  const firstIndex = textNode.textContent.search(/\S/);
  if (firstIndex < 0) return element.getBoundingClientRect();

  const glyph = document.createRange();
  glyph.setStart(textNode, firstIndex);
  glyph.setEnd(textNode, firstIndex + 1);
  return glyph.getBoundingClientRect();
};

const morphTransform = (source: DOMRect, target: DOMRect) => ({
  x: target.left + target.width / 2 - (source.left + source.width / 2),
  y: target.top + target.height / 2 - (source.top + source.height / 2),
  scaleX: target.width / Math.max(1, source.width),
  scaleY: target.height / Math.max(1, source.height),
});

const runIntro = () => {
  if (reducedMotion.value) {
    introVisible.value = false;
    return;
  }

  document.documentElement.classList.add("is-refined-intro");

  const markElement = document.querySelector<HTMLElement>(".ref-intro__mark");
  const heroWords = Array.from(
    document.querySelectorAll<HTMLElement>(".ref-hero__title span i"),
  );

  if (!markElement || heroWords.length < 2) {
    introVisible.value = false;
    document.documentElement.classList.remove("is-refined-intro");
    return;
  }

  /* The intro initials are transient clones. Keeping DIEGO/CANO as the real
     Hero DOM means their final layout remains the single source of truth. */
  markElement.innerHTML =
    '<span data-intro-glyph="D">D</span><span data-intro-glyph="C">C</span>';
  const introGlyphs = Array.from(
    markElement.querySelectorAll<HTMLElement>("[data-intro-glyph]"),
  );

  if (introGlyphs.length < 2) return;

  gsap.set(".ref-hero__meta, .ref-hero__thesis, .ref-scroll-cue, .ref-header", {
    opacity: 0,
  });
  gsap.set(heroWords, {
    opacity: 0,
    clipPath: "inset(0% 100% 0% 0%)",
    willChange: "clip-path, opacity",
  });
  gsap.set(introGlyphs, {
    display: "inline-block",
    transformOrigin: "50% 50%",
    willChange: "transform, opacity",
  });

  /* Measure the actual first glyphs of DIEGO and CANO. This is intentionally
     done against the final Hero typography rather than the small header logo. */
  const targetRects = [firstGlyphRect(heroWords[0]), firstGlyphRect(heroWords[1])];
  const sourceRects = introGlyphs.map((glyph) => glyph.getBoundingClientRect());
  const transforms = [
    morphTransform(sourceRects[0], targetRects[0]),
    morphTransform(sourceRects[1], targetRects[1]),
  ];

  introTimeline = gsap
    .timeline({
      defaults: { ease: "power3.out" },
      onComplete: () => {
        gsap.set(heroWords, { clearProps: "opacity,clipPath,willChange" });
        introVisible.value = false;
        document.documentElement.classList.remove("is-refined-intro");
      },
    })
    .from(markElement, {
      opacity: 0,
      scale: 0.9,
      letterSpacing: "0.05em",
      duration: 0.82,
      ease: "expo.out",
    })
    .from(
      ".ref-intro__statement span",
      { yPercent: 115, duration: 0.62, stagger: 0.055 },
      "-=0.44",
    )
    .from(
      ".ref-intro__meta span",
      { opacity: 0, y: 8, duration: 0.42, stagger: 0.05 },
      "-=0.42",
    )
    .addLabel("handoff", "+=0.14")
    .to(
      ".ref-intro__panel--top",
      { yPercent: -101, duration: 1.28, ease: "power4.inOut" },
      "handoff",
    )
    .to(
      ".ref-intro__panel--bottom",
      { yPercent: 101, duration: 1.28, ease: "power4.inOut" },
      "handoff",
    )
    .to(
      ".ref-intro__statement, .ref-intro__meta",
      { opacity: 0, y: -8, duration: 0.34, ease: "power2.in" },
      "handoff",
    )
    .to(
      introGlyphs[0],
      { ...transforms[0], duration: 1.18, ease: "power4.inOut" },
      "handoff+=0.08",
    )
    .to(
      introGlyphs[1],
      { ...transforms[1], duration: 1.18, ease: "power4.inOut" },
      "handoff+=0.08",
    )
    .to(
      heroWords,
      {
        opacity: 1,
        clipPath: "inset(0% 0% 0% 0%)",
        duration: 0.5,
        stagger: 0.055,
        ease: "power2.out",
      },
      "handoff+=1.02",
    )
    .to(
      introGlyphs,
      { opacity: 0, duration: 0.22, ease: "power1.out" },
      "handoff+=1.18",
    )
    .to(
      ".ref-hero__meta, .ref-hero__thesis, .ref-scroll-cue",
      { opacity: 1, y: 0, duration: 0.52, stagger: 0.055 },
      "handoff+=1.22",
    )
    .to(".ref-header", { opacity: 1, duration: 0.42 }, "handoff+=1.32")
    .set(".ref-intro", { display: "none" }, "handoff+=1.58");
};

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);

  reducedMotion.value = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* FLIP-style geometry must be measured only after the actual fonts settle;
     otherwise the target glyph boxes can change during the handoff. */
  await document.fonts.ready;

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
    startMotionLoop();
  }

  addEventListener("wheel", preventIntroScroll, { passive: false });
  addEventListener("touchmove", preventIntroScroll, { passive: false });
  addEventListener("keydown", onKeydown);
  runIntro();
  addEventListener("load", () => ScrollTrigger.refresh(), { once: true });

  cursorEnabled.value = matchMedia("(pointer: fine)").matches && !reducedMotion.value;
  if (cursorEnabled.value) {
    await nextTick();
    addEventListener("pointermove", onCursorMove, { passive: true });
    addEventListener("pointerover", onCursorOver, { passive: true });
    addEventListener("pointerdown", onCursorDown, { passive: true });
    addEventListener("pointerup", onCursorUp, { passive: true });
    document.documentElement.addEventListener("pointerout", onCursorLeaveWindow);
    startCursorLoop();
  }
});

onBeforeUnmount(() => {
  trigger?.kill();
  introTimeline?.kill();
  teleportTimeline?.kill();
  cancelAnimationFrame(motionFrame);
  cancelAnimationFrame(cursorFrame);
  removeEventListener("keydown", onKeydown);
  removeEventListener("wheel", preventIntroScroll);
  removeEventListener("touchmove", preventIntroScroll);
  removeEventListener("pointermove", onCursorMove);
  removeEventListener("pointerover", onCursorOver);
  removeEventListener("pointerdown", onCursorDown);
  removeEventListener("pointerup", onCursorUp);
  document.documentElement.removeEventListener("pointerout", onCursorLeaveWindow);
  document.documentElement.classList.remove("is-refined-intro");
});
</script>

<template>
  <div :class="['ref-portfolio', { 'is-intro': introVisible, 'has-cursor': cursorEnabled }]">
    <div ref="teleport" class="ref-teleport" aria-hidden="true" />
    <div v-if="cursorEnabled" ref="cursorDot" class="ref-cursor" :data-state="cursorState" aria-hidden="true" />
    <div v-if="cursorEnabled" ref="cursorRing" class="ref-cursor-ring" :data-state="cursorState" aria-hidden="true" />
    <a class="ref-skip" href="#ref-fallback">Skip motion experience</a>

    <div v-if="introVisible" class="ref-intro" aria-hidden="true">
      <div class="ref-intro__panel ref-intro__panel--top" />
      <div class="ref-intro__panel ref-intro__panel--bottom" />
      <div class="ref-intro__meta">
        <span>DIEGO CANO / PORTFOLIO 2026</span>
        <span>BUENOS AIRES · GMT−3</span>
      </div>
      <div class="ref-intro__mark">DC</div>
      <p class="ref-intro__statement">
        <span>SOFTWARE</span>
        <span>INTELLIGENCE</span>
        <span>OBJECTS</span>
      </p>
    </div>

    <header class="ref-header">
      <button type="button" class="ref-brand" aria-label="Return to opening" @click="goToNode(HERO_NODE)">
        <strong>DC</strong><span>SOFTWARE ENGINEER<br />+ CREATIVE TECHNOLOGIST</span>
      </button>
      <div class="ref-progress"><span>{{ progressLabel }}</span><i><b
            :style="{ transform: `scaleX(${Number(progressLabel) / 100})` }" /></i><span>100</span></div>
      <button type="button" class="ref-index-toggle" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">{{ menuOpen
        ? "CLOSE" : "MENU" }}</button>
    </header>

    <nav :class="['ref-index', { 'is-open': menuOpen }]" aria-label="Portfolio index">
      <button type="button" @click="goToNode(HERO_NODE)"><span>01</span><strong>Opening</strong></button>
      <button type="button" @click="goToNode(CAREER_START_NODE)"><span>02</span><strong>Trajectory</strong></button>
      <button type="button" @click="goToNode(SYSTEMS_START_NODE)"><span>03</span><strong>Systems</strong></button>
      <button type="button" @click="goToNode(GALLERY_START_NODE)"><span>04</span><strong>Visual
          archive</strong></button>
      <button type="button" @click="goToNode(AGENT_NODE)"><span>05</span><strong>Agent</strong></button>
    </nav>

    <main ref="track" class="ref-track">
      <section ref="stage" class="ref-stage" data-scene="hero" aria-label="Scroll-driven portfolio narrative">
        <div class="ref-grain" aria-hidden="true" />

        <article class="ref-scene ref-scene--hero">
          <p class="ref-hero__meta"><span>BUENOS AIRES · ARGENTINA</span><span>SELECTED PRACTICE / 2026</span></p>
          <h1 class="ref-hero__title"><span><i>DIEGO</i></span><span><i>CANO</i></span></h1>
          <p class="ref-hero__thesis">I design software systems, intelligent products and physical ideas with one
            principle: <em>complexity must become legible.</em></p>
          <div class="ref-scroll-cue"><span>SCROLL TO ENTER</span><i /></div>
        </article>

        <article class="ref-scene ref-scene--career">
          <div class="ref-marker"><span>02</span><i />PROFESSIONAL TRAJECTORY</div>
          <div class="ref-career-nav" aria-label="Professional experience index">
            <button v-for="(_, index) in experiences" :key="index" type="button"
              :class="{ active: index === activeExperience }" :aria-label="`Show experience ${index + 1}`"
              @click="goToExperience(index)" />
          </div>
          <Transition name="ref-copy" mode="out-in">
            <div :key="currentExperience.period" class="ref-career-copy">
              <span>{{ currentExperience.period }} · {{ currentExperience.company }}</span>
              <h2>{{ currentExperience.role }}</h2>
              <p>{{ currentExperience.summary }}</p>
              <ul>
                <li v-for="item in currentExperience.focus" :key="item">{{ item }}</li>
              </ul>
            </div>
          </Transition>
          <div class="ref-career-number" aria-hidden="true">{{ String(activeExperience + 1).padStart(2, "0") }}</div>
        </article>

        <article class="ref-scene ref-scene--systems">
          <div class="ref-marker"><span>03</span><i />SELECTED TECHNICAL SYSTEMS</div>
          <div class="ref-system-stack" aria-hidden="true">
            <div v-for="(project, index) in projects" :key="project.id"
              :class="['ref-system-card', { active: index === activeProject }]">
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
              <ul>
                <li v-for="item in currentProject.stack" :key="item">{{ item }}</li>
              </ul>
            </div>
          </Transition>
          <div class="ref-system-nav" aria-label="Technical project index">
            <button v-for="(_, index) in projects" :key="index" type="button"
              :class="{ active: index === activeProject }" :aria-label="`Show project ${index + 1}`"
              @click="goToProject(index)">{{ String(index + 1).padStart(2, "0") }}</button>
          </div>
        </article>

        <article class="ref-scene ref-scene--gallery">
          <div class="ref-marker"><span>04</span><i />VISUAL / MATERIAL ARCHIVE</div>
          <div class="ref-gallery-stage" aria-label="Ten visual works">
            <button v-for="(artwork, index) in artworks" :key="artwork.src"
              :class="['ref-art-card', { active: index === activeArtwork }]" type="button"
              :aria-label="`Show ${artwork.title}`" @click="goToArtwork(index)"><img :src="artwork.src"
                :alt="artwork.title" /></button>
          </div>
          <Transition name="ref-copy" mode="out-in">
            <div :key="currentArtwork.src" class="ref-art-caption">
              <span>{{ String(activeArtwork + 1).padStart(2, "0") }} / {{ String(artworks.length).padStart(2, "0") }} ·
                {{ currentArtwork.type }}</span>
              <h2>{{ currentArtwork.title }}</h2>
              <p>{{ currentArtwork.meta }}</p>
            </div>
          </Transition>
          <div class="ref-filmstrip" aria-label="Visual archive index">
            <button v-for="(artwork, index) in artworks" :key="`${artwork.src}-thumb`" type="button"
              :class="{ active: index === activeArtwork }" :aria-label="`Go to ${artwork.title}`"
              @click="goToArtwork(index)"><img :src="artwork.src" alt="" /><span>{{ String(index + 1).padStart(2, "0")
                }}</span></button>
          </div>
          <div class="ref-art-index" aria-hidden="true">{{ String(activeArtwork + 1).padStart(2, "0") }}</div>
        </article>

        <article class="ref-scene ref-scene--agent">
          <AgentOS />
        </article>

        <article v-for="chapter in chapters" :key="chapter.key" class="ref-scene ref-scene--chapter"
          :data-chapter="chapter.key" :aria-label="chapter.kicker">
          <div class="ref-chapter">
            <i />
            <span>{{ chapter.kicker }}</span>
            <p>{{ chapter.line }}</p>
          </div>
        </article>
      </section>
    </main>

    <section id="ref-fallback" class="ref-fallback">
      <header><span>DIEGO CANO / ACCESSIBLE INDEX</span>
        <h1>Software, AI and material practice.</h1>
      </header>
      <div>
        <h2>Experience</h2>
        <article v-for="item in experiences" :key="item.period"><span>{{ item.period }} · {{ item.company }}</span>
          <h3>{{ item.role }}</h3>
          <p>{{ item.summary }}</p>
        </article>
      </div>
      <div>
        <h2>Technical systems</h2>
        <article v-for="item in projects" :key="item.id"><span>{{ item.id }} · {{ item.field }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.premise }}</p>
        </article>
      </div>
      <div>
        <h2>A note on origin</h2>
        <p>My first language was design — objects, proportion, material honesty. That eye never left the engineering; it
          only changed medium. What follows is the other half of the practice, where the argument is visual.</p>
      </div>
      <div class="ref-fallback-art">
        <h2>Visual archive</h2>
        <figure v-for="item in artworks" :key="item.src"><img :src="item.src" :alt="item.title" />
          <figcaption>{{ item.title }} · {{ item.type }}</figcaption>
        </figure>
      </div>
    </section>
  </div>
</template>
