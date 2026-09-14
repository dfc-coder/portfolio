import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");
const absent = (path) => assert.rejects(access(resolve(root, path)));

const removedFrontendLayers = [
  "src/styles/cinematic.css",
  "src/styles/cinematic-motion.css",
  "src/styles/typography.css",
  "src/experiences/trajectory-bridge.css",
  "src/experiences/systems-motion.css",
  "src/design-system/tokens.css",
  "src/design-system/primitives.css",
  "src/design-system/templates.css",
];

const removedBackendFacades = [
  "server/app/calendar_gateway.py",
  "server/app/llama_client.py",
  "server/app/policies.py",
  "server/app/profile.py",
  "server/app/session.py",
  "server/app/settings.py",
  "server/app/slot_service.py",
  "server/app/api/schemas.py",
  "server/app/api/sse.py",
];

test("architecture: obsolete frontend layers stay removed", async () => {
  await Promise.all(removedFrontendLayers.map(absent));
  await access(resolve(root, "src/styles/theme.css"));
  await access(resolve(root, "src/styles/shell.css"));
  await access(resolve(root, "src/graphics/stageGraphics.ts"));
  await access(resolve(root, "src/graphics/stage-graphics.css"));
});

test("architecture: pnpm remains the only frontend package manager", async () => {
  const packageJson = JSON.parse(await read("package.json"));
  const workspace = await read("pnpm-workspace.yaml");

  await access(resolve(root, "pnpm-lock.yaml"));
  await absent("package-lock.json");
  assert.equal(packageJson.packageManager, "pnpm@11.22.0");
  assert.match(workspace, /allowBuilds:\s*\n\s*esbuild:\s*true/);
  assert.ok(packageJson.dependencies.gsap);
  assert.ok(packageJson.dependencies.three);
  assert.ok(packageJson.dependencies.vue);
});

test("architecture: bootstrap keeps global owners and scene runtimes are lazy", async () => {
  const main = await read("src/main.ts");
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const ordered = [
    'import "./styles/theme.css"',
    'import "./styles/base.css"',
    'import "./styles/shell.css"',
    'import "./graphics/stage-graphics.css"',
    'import "./experiences/scroll.css"',
    'import "./components/agent/agent.css"',
    'import "./experiences/hero.css"',
    'import "./experiences/trajectory.css"',
    'import "./experiences/systems.css"',
    'import "./experiences/continuity.css"',
    'import "./styles/chapter-bridges.css"',
    'import "./experiences/gallery.css"',
  ];

  let previous = -1;
  for (const statement of ordered) {
    const index = main.indexOf(statement);
    assert.ok(index > previous, `${statement} must be present and ordered`);
    previous = index;
  }

  assert.match(main, /mountScrollSyncController\(\)/);
  assert.match(main, /mountVisualContinuity\(\)/);
  assert.match(main, /mountSceneLifecycle\(\)/);
  assert.doesNotMatch(
    main,
    /mountTrajectoryExperience|mountSystemsExperience|mountGalleryGel|mountGalleryTransition|mountStageGraphics/,
  );
  assert.doesNotMatch(
    main,
    /from "\.\/experiences\/(trajectory|systems|gallery|gallery-transition)"/,
  );

  assert.match(lifecycle, /const runtimeLoaders = \{/);
  assert.match(lifecycle, /const prefetchers = \{/);
  assert.match(lifecycle, /career: async \(\) => \{[\s\S]*import\("\.\/trajectory"\)/);
  assert.match(lifecycle, /systems: async \(\) => \{[\s\S]*import\("\.\/systems"\)/);
  assert.match(lifecycle, /gallery: async \(\) => \{[\s\S]*import\("\.\/gallery"\)[\s\S]*import\("\.\/gallery-transition"\)/);
  assert.match(lifecycle, /agent: async \(\) => \{[\s\S]*import\("\.\.\/graphics\/stageGraphics"\)/);
  assert.match(lifecycle, /runtimeLoaders\[scene\]\(\)/);
  assert.match(lifecycle, /prefetchers\[scene\]\(\)/);
  assert.match(lifecycle, /activationVersion/);
  assert.match(lifecycle, /scene !== "chapter"/);
  assert.doesNotMatch(lifecycle, /switch\s*\(/);

  assert.match(portfolio, /defineAsyncComponent\(\(\) => import\("\.\/agent\/AgentOS\.vue"\)\)/);
  assert.match(portfolio, /<AgentOS v-if="agentActive" \/>/);
  assert.match(portfolio, /from "\.\.\/experiences\/gallery-data"/);
  assert.doesNotMatch(portfolio, /import AgentOS from/);
  assert.doesNotMatch(main, /design-system|cinematic|systems-motion|trajectory-bridge/);
});

test("semantics: visual narrative keeps one h1 and stable chapter headings", async () => {
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const header = await read("src/components/narrative/NarrativeHeader.vue");
  const trajectory = await read("src/components/narrative/TrajectoryScene.vue");
  const systems = await read("src/components/narrative/SystemsScene.vue");
  const agent = await read("src/components/agent/AgentOS.vue");
  const fallback = portfolio.slice(portfolio.indexOf('<section id="ref-fallback"'));

  assert.equal((portfolio.match(/<h1\b/g) ?? []).length, 1);
  assert.match(portfolio, /<h1 class="ref-hero__title"/);
  assert.match(header, /<h2 class="narrative-header__heading"/);
  assert.match(trajectory, /<NarrativeHeader[\s\S]*class="trajectory-header"/);
  assert.match(systems, /<NarrativeHeader[\s\S]*class="systems-header"/);
  assert.match(trajectory, /<h3>\{\{ experience\.role \}\}<\/h3>/);
  assert.match(systems, /<h3>\{\{ project\.title \}\}<\/h3>/);
  assert.match(portfolio, /<h2 class="ref-marker">[\s\S]*VISUAL \/ MATERIAL ARCHIVE/);
  assert.match(agent, /<h2 class="ref-marker">[\s\S]*THE INTERFACE/);
  assert.doesNotMatch(fallback, /<h1\b/);
});

test("architecture: runtime anchor headers cannot be removed by visual refactors", async () => {
  const trajectoryScene = await read("src/components/narrative/TrajectoryScene.vue");
  const systemsScene = await read("src/components/narrative/SystemsScene.vue");
  const trajectoryRuntime = await read("src/experiences/trajectory.ts");
  const systemsRuntime = await read("src/experiences/systems.ts");

  assert.match(trajectoryScene, /class="trajectory-header"/);
  assert.match(systemsScene, /class="systems-header"/);
  assert.match(trajectoryRuntime, /querySelector<HTMLElement>\("\.trajectory-header"\)/);
  assert.match(systemsRuntime, /querySelector<HTMLElement>\("\.systems-header"\)/);
});

test("architecture: GSAP remains isolated from the native scroll runtime", async () => {
  const motion = await read("src/motion/gsap.ts");
  const scroll = await read("src/experiences/scroll.ts");
  const hero = await read("src/experiences/hero.ts");
  const transition = await read("src/experiences/section-transition.ts");

  assert.match(motion, /import gsap from "gsap"/);
  assert.match(motion, /export \{ gsap \}/);
  assert.doesNotMatch(motion, /ScrollTrigger|registerPlugin/);
  assert.doesNotMatch(scroll, /motion\/gsap|ScrollTrigger|gsap\./);
  assert.match(hero, /from "\.\.\/motion\/gsap"/);
  assert.match(transition, /from "\.\.\/motion\/gsap"/);
  assert.doesNotMatch(hero, /from "gsap"/);
});

test("architecture: native scroll is the single physical scroll owner", async () => {
  const component = await read("src/components/PortfolioExperience.vue");
  const scroll = await read("src/experiences/scroll.ts");
  const gallery = await read("src/experiences/gallery.ts");

  assert.doesNotMatch(component, /ScrollTrigger|addEventListener\("wheel"/);
  assert.doesNotMatch(gallery, /addEventListener\("wheel"|scrollToNode|WHEEL_EXIT_LOCK/);
  assert.match(scroll, /addEventListener\("scroll", onNativeScroll, \{ passive: true \}\)/);
  assert.match(scroll, /requestAnimationFrame\(flushScroll\)/);
  assert.match(scroll, /if \(scrollFrame !== 0\) return;/);
  assert.match(scroll, /physicalProgressAt/);
  assert.match(scroll, /mapPhysicalProgressToVirtualProgress/);
  assert.match(scroll, /narrativeRuntime\.publish/);
  assert.match(scroll, /window\.scrollTo\(\{/);
  assert.match(scroll, /transitionSectionNavigation\(\(\) => jumpToPhysicalNode\(node\), direction\)/);
  assert.doesNotMatch(scroll, /ScrollTrigger|gsap\.to|scrollProxy|scrollTween/);
  assert.doesNotMatch(scroll, /addEventListener\("wheel"|WHEEL_GAIN|wheelDeltaPixels|nestedScrollerCanConsume/);
});

test("architecture: narrative runtime skips irrelevant publications", async () => {
  const runtime = await read("src/experiences/narrative-runtime.ts");

  assert.match(runtime, /NARRATIVE_EPSILON = 0\.0001/);
  assert.match(runtime, /const nearlyEqual/);
  assert.match(runtime, /next\.scene === state\.scene/);
  assert.match(runtime, /nearlyEqual\(next\.physicalProgress, state\.physicalProgress\)/);
  assert.match(runtime, /nearlyEqual\(next\.progress, state\.progress\)/);
  assert.match(runtime, /if \([\s\S]*?\) \{\s*return;\s*\}/);
  assert.match(runtime, /listeners\.forEach\(\(listener\) => listener\(state\)\)/);
});

test("architecture: narrative consumers subscribe instead of polling CSS every frame", async () => {
  const trajectory = await read("src/experiences/trajectory.ts");
  const systems = await read("src/experiences/systems.ts");

  for (const runtime of [trajectory, systems]) {
    assert.match(runtime, /narrativeRuntime\.subscribe/);
    assert.doesNotMatch(runtime, /getPropertyValue\("--progress"\)/);
    assert.doesNotMatch(runtime, /insertAdjacentHTML|innerHTML|const markup|Markup\s*=/);
    assert.doesNotMatch(runtime, /requestAnimationFrame\(renderNarrative\)/);
  }

  assert.match(trajectory, /requestAnimationFrame\(renderParallax\)/);
  assert.match(systems, /requestAnimationFrame\(renderMotion\)/);
  assert.doesNotMatch(systems, /requestAnimationFrame\(renderParallax\)/);
  assert.doesNotMatch(systems, /requestAnimationFrame\(renderPointer\)/);
});

test("architecture: mobile refinement is isolated from desktop ownership", async () => {
  const main = await read("src/main.ts");
  const mobile = await read("src/styles/mobile-experience.css");
  const trajectory = await read("src/experiences/trajectory.ts");
  const systemsMotion = await read("src/experiences/systems-motion-contract.ts");
  const galleryTransition = await read("src/experiences/gallery-transition.ts");
  const scroll = await read("src/experiences/scroll.ts");

  const mobileImport = 'import "./styles/mobile-experience.css"';
  const galleryTransitionImport = 'import "./experiences/gallery-transition.css"';

  assert.match(main, /import "\.\/styles\/mobile-experience\.css"/);
  assert.ok(main.indexOf(mobileImport) > main.indexOf(galleryTransitionImport));
  assert.match(mobile, /@media \(max-width: 680px\)/);
  assert.match(mobile, /--narrative-rail-x:\s*8\.5%/);
  assert.match(mobile, /\.narrative-header__meta\s*\{[^}]*display:\s*none\s*!important/is);
  assert.match(mobile, /\.systems-project__detail,[\s\S]*display:\s*none\s*!important/);
  assert.match(mobile, /\.agent-core\s*\{[^}]*64vw/is);
  assert.match(trajectory, /entryPresence\(Math\.abs\(roleOffset\), compact\)/);
  assert.match(systemsMotion, /MOBILE_SYSTEMS_TIMING/);
  assert.match(galleryTransition, /MOBILE_ENTRY_START_OFFSET = -1\.04/);
  assert.match(scroll, /MOBILE_SCENE_CROSSFADE_WIDTH = 0\.22/);
});

test("architecture: Agent-only Three renderer sleeps and menu WebGL stays isolated", async () => {
  const main = await read("src/main.ts");
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const graphics = await read("src/graphics/stageGraphics.ts");
  const controller = await read("src/graphics/agent-visual-controller.ts");
  const agent = await read("src/components/agent/AgentOS.vue");
  const agentShader = await read("src/graphics/agent-liquid-shader.ts");
  const hero = await read("src/experiences/hero.ts");
  const transition = await read("src/experiences/section-transition.ts");
  const continuity = await read("src/experiences/continuity.css");

  assert.equal((graphics.match(/new THREE\.WebGLRenderer/g) ?? []).length, 1);
  assert.match(graphics, /agent-liquid-shader/);
  assert.match(graphics, /agentLiquidVertex/);
  assert.match(graphics, /agentLiquidFragment/);
  assert.match(graphics, /new THREE\.PlaneGeometry\(/);
  assert.match(graphics, /new THREE\.Mesh\(this\.agentGeometry, this\.agentMaterial\)/);
  assert.doesNotMatch(graphics, /new THREE\.Points/);
  assert.match(graphics, /new THREE\.PerspectiveCamera/);
  assert.match(graphics, /renderer\.render\(this\.agentScene/);
  assert.match(graphics, /requestAnimationFrame\(this\.render\)/);
  assert.match(graphics, /agentVisualNeedsFrame\(\)/);
  assert.doesNotMatch(graphics, /atmosphereFragment|transitionFragment|setStageTransition/);
  assert.doesNotMatch(graphics, /setTimeout|targetFps|\.schedule\(/);
  assert.match(graphics, /narrativeRuntime\.subscribe\(this\.onNarrative\)/);
  assert.match(graphics, /this\.setPointerActive\(state\.scene === "agent"\)/);

  assert.match(controller, /bindAgentVisualWake/);
  assert.match(controller, /agentVisualNeedsFrame/);
  assert.match(controller, /requestVisualFrame\(\)/);
  assert.match(agent, /from "\.\.\/\.\.\/graphics\/agent-visual-controller"/);
  assert.doesNotMatch(agent, /graphics\/stageGraphics/);

  assert.match(lifecycle, /import\("\.\.\/graphics\/stageGraphics"\)/);
  assert.match(lifecycle, /gallery: \(\) => \{[\s\S]*AgentOS\.vue[\s\S]*stageGraphics/);
  assert.doesNotMatch(main, /graphics\/stageGraphics|mountStageGraphics/);
  assert.match(portfolio, /defineAsyncComponent\(\(\) => import\("\.\/agent\/AgentOS\.vue"\)\)/);
  assert.match(portfolio, /<AgentOS v-if="agentActive" \/>/);

  assert.match(agentShader, /fluidValue/);
  assert.match(agentShader, /refractStrength/);
  assert.match(agentShader, /caustic/);
  assert.match(agentShader, /shellEdge/);
  assert.doesNotMatch(hero, /three|WebGLRenderer|ShaderMaterial/);

  assert.match(transition, /document\.createElement\("canvas"\)/);
  assert.match(transition, /document\.body\.append\(canvas\)/);
  assert.match(transition, /getContext\("webgl"/);
  assert.match(transition, /const fragmentShader/);
  assert.match(transition, /gsap\.timeline/);
  assert.doesNotMatch(transition, /requestAnimationFrame/);
  assert.match(continuity, /\.ref-navigation-transition\.is-active/);
  assert.match(continuity, /html\.is-section-transitioning\s*\{[^}]*overflow:\s*hidden/is);
});

test("architecture: section titles share one register without changing component ownership", async () => {
  const bridges = await read("src/styles/chapter-bridges.css");
  const trajectory = await read("src/components/narrative/TrajectoryScene.vue");
  const systems = await read("src/components/narrative/SystemsScene.vue");
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const agent = await read("src/components/agent/AgentOS.vue");

  assert.match(bridges, /Persistent section chrome/);
  assert.match(bridges, /\.narrative-header,[\s\S]*\.ref-scene--gallery > \.ref-marker,[\s\S]*\.ref-scene--agent \.ref-marker/);
  assert.match(bridges, /left:\s*var\(--shell-gutter,\s*22px\)\s*!important/);
  assert.match(bridges, /top:\s*22px\s*!important/);
  assert.match(trajectory, /class="trajectory-header"/);
  assert.match(systems, /class="systems-header"/);
  assert.match(portfolio, /<h2 class="ref-marker">[\s\S]*VISUAL \/ MATERIAL ARCHIVE/);
  assert.match(agent, /<h2 class="ref-marker">[\s\S]*THE INTERFACE/);
});

test("architecture: CSS owns only static surface texture and small UI motion", async () => {
  const graphicsCss = await read("src/graphics/stage-graphics.css");
  const shell = await read("src/styles/shell.css");
  const continuity = await read("src/experiences/continuity.css");

  assert.match(shell, /\.ref-grain\s*\{/);
  assert.match(graphicsCss, /repeating-linear-gradient/);
  assert.match(graphicsCss, /radial-gradient/);
  assert.doesNotMatch(graphicsCss, /has-webgl-transition|is-transitioning/);
  assert.doesNotMatch(continuity, /ref-global-pointer-light/);
  assert.match(continuity, /\.ref-cursor/);
});

test("architecture: continuity no longer owns an animation loop", async () => {
  const runtime = await read("src/experiences/continuity.ts");
  const component = await read("src/components/PortfolioExperience.vue");

  assert.match(runtime, /mountSectionTransition/);
  assert.match(runtime, /addEventListener\("pointermove"/);
  assert.doesNotMatch(runtime, /requestAnimationFrame/);
  assert.doesNotMatch(component, /pointermove|cursorFrame|requestAnimationFrame|ref-cursor/);
});

test("architecture: Agent UI decouples network chunks from presentation and visual energy", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const runtime = await read("src/components/agent/useAgentRuntime.ts");

  assert.match(os, /setAgentVisualPhase/);
  assert.match(os, /pulseAgentVisual/);
  assert.match(os, /onPresent: \(text\) =>/);
  assert.doesNotMatch(os, /AsciiFluidCanvas/);
  assert.match(runtime, /presentationQueue/);
  assert.match(runtime, /PRESENTATION_BASE_CPS/);
  assert.match(runtime, /requestAnimationFrame\(present\)/);
  assert.match(runtime, /waitForPresentation/);
  assert.doesNotMatch(runtime, /pendingText|scheduleStreamFlush|flushStream/);
  assert.doesNotMatch(runtime, /localProvider|CORPUS|CorpusEntry|chunkify|Math\.random/);
});

test("architecture: Gallery remains isolated outside its active scene", async () => {
  const component = await read("src/components/PortfolioExperience.vue");
  const scrollCss = await read("src/experiences/scroll.css");
  const gallery = await read("src/experiences/gallery.ts");

  assert.match(component, /<img[^>]+draggable="false"/);
  assert.match(scrollCss, /\.ref-stage:not\(\[data-scene="gallery"\]\) \.ref-scene--gallery/);
  assert.match(gallery, /const openFocus = \(index: number\) => \{\s*if \(!galleryIsVisible\(\)\) return;/);
  assert.match(gallery, /lockDocumentScroll\(\)/);
  assert.match(gallery, /unlockDocumentScroll\(\)/);
  assert.match(gallery, /narrativeRuntime\.subscribe\(syncNarrative\)/);
  assert.match(gallery, /setPointerListenerActive\(galleryActive && !isOpen\)/);
  assert.match(
    gallery,
    /if \(active\) \{[\s\S]*measureCards\(\);[\s\S]*addEventListener\("pointermove", onPointerMove/,
  );
});

test("architecture: backend compatibility facades stay removed", async () => {
  await Promise.all(removedBackendFacades.map(absent));
  const router = await read("server/app/api/router.py");
  assert.match(router, /class ChatRequest\(BaseModel\)/);
  assert.match(router, /def encode_sse\(/);
});
