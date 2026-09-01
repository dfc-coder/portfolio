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

test("architecture: main mounts one shared WebGL stage and predictable CSS ownership", async () => {
  const main = await read("src/main.ts");
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

  assert.match(main, /mountStageGraphics\(\)/);
  assert.match(main, /mountScrollSyncController\(\)/);
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

test("architecture: one GSAP module owns ScrollTrigger registration", async () => {
  const motion = await read("src/motion/gsap.ts");
  const scroll = await read("src/experiences/scroll.ts");
  const hero = await read("src/experiences/hero.ts");
  const transition = await read("src/experiences/section-transition.ts");

  assert.match(motion, /import gsap from "gsap"/);
  assert.match(motion, /ScrollTrigger/);
  assert.match(motion, /gsap\.registerPlugin\(ScrollTrigger\)/);
  assert.match(scroll, /from "\.\.\/motion\/gsap"/);
  assert.match(hero, /from "\.\.\/motion\/gsap"/);
  assert.match(transition, /from "\.\.\/motion\/gsap"/);
  assert.doesNotMatch(scroll, /from "gsap(?:\/ScrollTrigger)?"/);
  assert.doesNotMatch(hero, /from "gsap"/);
});

test("architecture: GSAP ScrollTrigger is the single physical scroll owner", async () => {
  const component = await read("src/components/PortfolioExperience.vue");
  const scroll = await read("src/experiences/scroll.ts");
  const gallery = await read("src/experiences/gallery.ts");

  assert.doesNotMatch(component, /ScrollTrigger|addEventListener\("wheel"/);
  assert.doesNotMatch(gallery, /addEventListener\("wheel"|scrollToNode|WHEEL_EXIT_LOCK/);
  assert.match(scroll, /ScrollTrigger\.create/);
  assert.match(scroll, /mapPhysicalProgressToVirtualProgress/);
  assert.match(scroll, /narrativeRuntime\.publish/);
  assert.match(scroll, /gsap\.to\(scrollProxy/);
  assert.doesNotMatch(scroll, /requestAnimationFrame\(runSmoothScroll\)/);
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
  assert.match(systems, /requestAnimationFrame\(renderParallax\)/);
  assert.match(systems, /requestAnimationFrame\(renderPointer\)/);
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

test("architecture: persistent Three stage and isolated menu WebGL have separate lifecycles", async () => {
  const graphics = await read("src/graphics/stageGraphics.ts");
  const hero = await read("src/experiences/hero.ts");
  const transition = await read("src/experiences/section-transition.ts");
  const continuity = await read("src/experiences/continuity.css");

  assert.equal((graphics.match(/new THREE\.WebGLRenderer/g) ?? []).length, 1);
  assert.match(graphics, /const atmosphereFragment/);
  assert.match(graphics, /const agentVertex/);
  assert.match(graphics, /new THREE\.PlaneGeometry\(2\.2, 2\.2/);
  assert.match(graphics, /new THREE\.Mesh\(this\.agentGeometry, this\.agentMaterial\)/);
  assert.doesNotMatch(graphics, /new THREE\.Points/);
  assert.match(graphics, /new THREE\.PerspectiveCamera/);
  assert.match(graphics, /renderer\.render\(this\.atmosphereScene/);
  assert.match(graphics, /renderer\.render\(this\.agentScene/);
  assert.doesNotMatch(hero, /three|WebGLRenderer|ShaderMaterial/);

  assert.match(transition, /document\.createElement\("canvas"\)/);
  assert.match(transition, /document\.body\.append\(canvas\)/);
  assert.match(transition, /getContext\("webgl"/);
  assert.match(transition, /const fragmentShader/);
  assert.match(transition, /gsap\.timeline/);
  assert.doesNotMatch(transition, /requestAnimationFrame/);
  assert.match(continuity, /\.ref-navigation-transition\.is-active/);
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

test("architecture: Agent UI drives shared Three state and batches stream rendering", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const runtime = await read("src/components/agent/useAgentRuntime.ts");

  assert.match(os, /setAgentVisualPhase/);
  assert.match(os, /pulseAgentVisual/);
  assert.doesNotMatch(os, /AsciiFluidCanvas/);
  assert.match(runtime, /pendingText/);
  assert.match(runtime, /scheduleStreamFlush/);
  assert.match(runtime, /requestAnimationFrame\(flushStream\)/);
  assert.doesNotMatch(runtime, /localProvider|CORPUS|CorpusEntry|chunkify|Math\.random/);
});

test("architecture: Gallery remains isolated outside its active scene", async () => {
  const component = await read("src/components/PortfolioExperience.vue");
  const scrollCss = await read("src/experiences/scroll.css");
  const gallery = await read("src/experiences/gallery.ts");

  assert.match(component, /<img[^>]+draggable="false"/);
  assert.match(scrollCss, /\.ref-stage:not\(\[data-scene="gallery"\]\) \.ref-scene--gallery/);
  assert.match(gallery, /const openFocus = \(index: number\) => \{\s*if \(!galleryIsVisible\(\)\) return;/);
  assert.match(gallery, /const onPointerMove = \(event: PointerEvent\) => \{\s*if \(!galleryIsVisible\(\) \|\| isOpen\) return;/);
});

test("architecture: backend compatibility facades stay removed", async () => {
  await Promise.all(removedBackendFacades.map(absent));
  const router = await read("server/app/api/router.py");
  assert.match(router, /class ChatRequest\(BaseModel\)/);
  assert.match(router, /def encode_sse\(/);
});