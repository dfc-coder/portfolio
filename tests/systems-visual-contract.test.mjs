import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

const loadTsModule = async (relativePath) => {
  const source = await read(relativePath);
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: relativePath,
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
};

const motion = await loadTsModule("src/experiences/systems-motion-contract.ts");
const projectData = await loadTsModule("src/experiences/systems-projects.ts");

test("BDD: Career is gone before THE EVIDENCE is readable", () => {
  const systemsDelta = 0.11;
  const introPresence = motion.range(systemsDelta, ...motion.SYSTEMS_TIMING.introIn);
  const careerResidual = motion.priorChapterResidual(systemsDelta);
  assert.ok(introPresence >= 0.45);
  assert.ok(careerResidual < 0.01);
});

test("BDD: intro and persistent project chrome never compete", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;

  for (let step = 0; step <= 100; step += 1) {
    const systemsDelta = 0.02 + step * 0.0042;
    const state = motion.chapterState(chapterSystemsNode + systemsDelta, chapterSystemsNode, chapterGalleryNode);
    if (state.introVisibility >= 0.35) {
      assert.ok(state.axisReveal < 0.01);
      assert.ok(state.headerReveal < 0.01);
    }
  }
});

test("BDD: project 00 cannot compete with THE EVIDENCE statement", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;
  const [start, end] = motion.SYSTEMS_TIMING.contentReveal;

  for (let step = 0; step <= 100; step += 1) {
    const systemsDelta = start + ((end - start) * step) / 100;
    const state = motion.chapterState(chapterSystemsNode + systemsDelta, chapterSystemsNode, chapterGalleryNode);
    if (state.contentReveal >= 0.05) assert.ok(state.introVisibility < 0.01);
  }
});

test("BDD: chapter-to-project handoff has no meaningful dead interval", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;
  let deadSamples = 0;
  let longestDeadRun = 0;

  for (let step = 0; step <= 150; step += 1) {
    const state = motion.chapterState(chapterSystemsNode + 0.20 + step * 0.003, chapterSystemsNode, chapterGalleryNode);
    const coverage = Math.max(state.introVisibility, state.axisReveal, state.headerReveal, state.contentReveal);
    if (coverage < 0.01) {
      deadSamples += 1;
      longestDeadRun = Math.max(longestDeadRun, deadSamples);
    } else {
      deadSamples = 0;
    }
  }

  assert.ok(longestDeadRun <= 2);
});

test("BDD: every System project uses the same focus cadence", () => {
  const startNode = 6;
  assert.equal(motion.SYSTEMS_COLLECTION.firstHoldEnd, motion.SYSTEMS_COLLECTION.holdEnd);

  const during = motion.collectionPosition(startNode + motion.SYSTEMS_COLLECTION.holdEnd - 0.01, startNode, 5);
  const after = motion.collectionPosition(startNode + motion.SYSTEMS_COLLECTION.holdEnd + 0.10, startNode, 5);
  assert.equal(during, 0);
  assert.ok(after > 0);
});

test("BDD: two System titles never become simultaneous protagonists", () => {
  for (let step = 0; step <= 100; step += 1) {
    const progress = step / 100;
    const outgoing = motion.motionForOffset(-progress).title;
    const incoming = motion.motionForOffset(1 - progress).title;
    assert.ok(!(outgoing > 0.05 && incoming > 0.05));
  }
});

test("BDD: two architecture graphs never become simultaneous protagonists", () => {
  for (let step = 0; step <= 100; step += 1) {
    const progress = step / 100;
    const outgoing = motion.motionForOffset(-progress).graph;
    const incoming = motion.motionForOffset(1 - progress).graph;
    assert.ok(!(outgoing > 0.05 && incoming > 0.05));
  }
});

test("BDD: project 00 graph visibly builds", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;
  const [start, end] = motion.SYSTEMS_TIMING.initialGraphBuild;
  const mid = (start + end) / 2;

  const before = motion.chapterState(chapterSystemsNode + start, chapterSystemsNode, chapterGalleryNode).initialGraphBuild;
  const during = motion.chapterState(chapterSystemsNode + mid, chapterSystemsNode, chapterGalleryNode).initialGraphBuild;
  const after = motion.chapterState(chapterSystemsNode + end, chapterSystemsNode, chapterGalleryNode).initialGraphBuild;

  assert.ok(before <= 0.01);
  assert.ok(during > 0.35 && during < 0.65);
  assert.ok(after >= 0.99);
});

test("SDD: all five Systems expose distinct architecture signatures", () => {
  const signatures = projectData.systemsProjects.map((project) => {
    const nodes = project.graph.nodes.map((node) => `${node.id}:${node.x},${node.y}`).join("|");
    const edges = project.graph.edges.map((edge) => `${edge.from}>${edge.to}:${edge.path ?? "auto"}`).join("|");
    return `${nodes}::${edges}`;
  });
  assert.equal(new Set(signatures).size, projectData.systemsProjects.length);
});

test("SDD: Trajectory and Systems rails share one physical register", async () => {
  const bridges = await read("src/styles/chapter-bridges.css");
  const trajectoryScene = await read("src/components/narrative/TrajectoryScene.vue");
  const systemsScene = await read("src/components/narrative/SystemsScene.vue");

  assert.match(bridges, /\.narrative-rail\s*\{[^}]*left:\s*var\(--narrative-rail-x,\s*11\.5%\)[^}]*top:\s*28%[^}]*height:\s*48vh/is);
  assert.match(trajectoryScene, /trajectory-axis narrative-rail/);
  assert.match(systemsScene, /systems-axis narrative-rail/);
  assert.match(systemsScene, /systems-axis-items narrative-rail/);
});

test("TDD: Systems template chrome is persistent and project content stays semantic", async () => {
  const scene = await read("src/components/narrative/SystemsScene.vue");
  const systems = await read("src/experiences/systems.css");
  const chromeStart = scene.indexOf('<div class="systems-static-chrome"');
  const chromeEnd = scene.indexOf('<div class="systems-projects">', chromeStart);
  const chrome = scene.slice(chromeStart, chromeEnd);

  assert.ok(chromeStart >= 0 && chromeEnd > chromeStart);
  assert.match(chrome, /systems-static-chrome__architecture[\s\S]*SYSTEM ARCHITECTURE/);
  assert.match(chrome, /systems-static-chrome__detail[\s\S]*SYSTEM NOTE/);
  assert.match(chrome, /systems-static-chrome__evidence[\s\S]*EVIDENCE/);
  assert.match(chrome, /systems-static-chrome__implementation[\s\S]*IMPLEMENTATION/);
  assert.match(scene, /<h4 class="sr-only">System architecture<\/h4>/);
  assert.match(scene, /<h4 class="sr-only">System note<\/h4>/);
  assert.match(scene, /<h4 class="sr-only">Evidence<\/h4>/);
  assert.match(scene, /<h4 class="sr-only">Implementation<\/h4>/);
  assert.match(systems, /\.systems-static-chrome\s*\{/);
  assert.match(systems, /--systems-tail-out/);
});

test("TDD: Systems runtime is event-driven by narrative state", async () => {
  const runtime = await read("src/experiences/systems.ts");

  assert.match(runtime, /narrativeRuntime\.subscribe\(renderNarrative\)/);
  assert.doesNotMatch(runtime, /getPropertyValue\("--progress"\)/);
  assert.doesNotMatch(runtime, /requestAnimationFrame\(renderNarrative\)/);
  assert.match(runtime, /requestAnimationFrame\(renderPointer\)/);
});

test("TDD: global atmosphere and pointer response are WebGL-owned", async () => {
  const graphics = await read("src/graphics/stageGraphics.ts");
  const continuity = await read("src/experiences/continuity.ts");
  const continuityCss = await read("src/experiences/continuity.css");

  assert.match(graphics, /const atmosphereFragment/);
  assert.match(graphics, /uPointer/);
  assert.match(graphics, /uVelocity/);
  assert.match(graphics, /uTurbulence/);
  assert.match(graphics, /new THREE\.WebGLRenderer/);
  assert.match(graphics, /this\.pointer\.lerp/);
  assert.doesNotMatch(continuity, /targetVelocityX|lightAngle|positionLight/);
  assert.doesNotMatch(continuityCss, /ref-global-pointer-light/);
});

test("TDD: WebGL renderer adapts work to scene and interaction", async () => {
  const graphics = await read("src/graphics/stageGraphics.ts");

  assert.match(graphics, /if \(this\.scene === "agent"\) return 60/);
  assert.match(graphics, /return 24/);
  assert.match(graphics, /pointerHotUntil/);
  assert.match(graphics, /document\.hidden/);
  assert.match(graphics, /setPixelRatio\(/);
  assert.match(graphics, /dprCap/);
});

test("TDD: menu transition is isolated WebGL driven by the shared GSAP runtime", async () => {
  const graphics = await read("src/graphics/stageGraphics.ts");
  const transition = await read("src/experiences/section-transition.ts");

  assert.equal((graphics.match(/new THREE\.WebGLRenderer/g) ?? []).length, 1);
  assert.doesNotMatch(graphics, /transitionFragment|transitionScene|setStageTransition/);
  assert.match(transition, /getContext\("webgl"/);
  assert.match(transition, /const fragmentShader/);
  assert.match(transition, /gsap\.timeline/);
  assert.match(transition, /document\.body\.append\(canvas\)/);
  assert.doesNotMatch(transition, /requestAnimationFrame/);
});

test("TDD: section title and narrative rails use fixed cross-section registers", async () => {
  const shell = await read("src/styles/shell.css");
  const bridges = await read("src/styles/chapter-bridges.css");
  const portfolio = await read("src/components/PortfolioExperience.vue");

  assert.match(shell, /One fixed register for every visible section title/);
  assert.match(portfolio, /class="ref-section-chrome"/);
  assert.match(portfolio, /v-for="\(\[key, index, label\]\) in sectionTitles"/);
  assert.match(shell, /\.ref-section-marker\s*\{[^}]*left:\s*var\(--shell-gutter\)[^}]*top:\s*92px/is);
  assert.match(shell, /\.ref-section-marker \.narrative-signal\s*\{[^}]*grid-template-columns:\s*auto\s+42px\s+auto/is);
  assert.match(bridges, /\.narrative-rail\s*\{[^}]*left:\s*var\(--narrative-rail-x,\s*11\.5%\)/is);
});

test("TDD: main mounts canonical experience modules only", async () => {
  const main = await read("src/main.ts");
  assert.match(main, /mountStageGraphics/);
  assert.match(main, /experiences\/systems/);
  assert.match(main, /experiences\/continuity/);
  assert.doesNotMatch(main, /systems-motion\.css|-v\d|hotfix|integration-fix|cinematic-tuning/);
});
