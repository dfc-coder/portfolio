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

test("BDD: architecture bridges project title ownership", () => {
  for (let step = 0; step <= 100; step += 1) {
    const progress = step / 100;
    const outgoing = motion.motionForOffset(-progress).graph;
    const incoming = motion.motionForOffset(1 - progress).graph;
    assert.ok(Math.max(outgoing, incoming) >= 0.95);
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

test("TDD: Systems has one CSS owner and keeps critical motion variables", async () => {
  const systems = await read("src/experiences/systems.css");
  assert.match(systems, /--title-presence/);
  assert.match(systems, /--graph-presence/);
  assert.match(systems, /--support-presence/);
  assert.match(systems, /--graph-build/);
  assert.match(systems, /position:\s*absolute/);
  assert.match(systems, /content:\s*"SYSTEM NOTE"/);
  assert.match(systems, /font-size:\s*12px/);
  assert.match(systems, /color:\s*rgba\(238, 234, 226, \.76\)/);
});

test("TDD: continuity cannot own Systems or Trajectory geometry", async () => {
  const css = await read("src/experiences/continuity.css");
  assert.doesNotMatch(css, /\.(systems|trajectory)-/);
  assert.match(css, /\.ref-global-pointer-light/);
  assert.match(css, /width:\s*min\(82rem,\s*118vw\)/i);
  assert.match(css, /height:\s*min\(58rem,\s*94vh\)/i);
  assert.match(css, /ellipse\s+at\s+center/i);
  assert.match(css, /transform:\s*translate3d\(/i);
  assert.match(css, /contain:\s*layout\s+paint\s+style/i);
});

test("TDD: cross-chapter handoff lives outside Systems", async () => {
  const systems = await read("src/experiences/systems.css");
  const bridges = await read("src/styles/chapter-bridges.css");
  assert.doesNotMatch(systems, /data-chapter="agent"/);
  assert.doesNotMatch(systems, /ref-scene--gallery/);
  assert.match(bridges, /systems-gallery-handoff/);
  assert.match(bridges, /data-chapter="agent"/);
});

test("TDD: main mounts canonical experience modules only", async () => {
  const main = await read("src/main.ts");
  assert.match(main, /experiences\/systems/);
  assert.match(main, /experiences\/continuity/);
  assert.doesNotMatch(main, /systems-motion\.css|-v\d|hotfix|integration-fix|cinematic-tuning/);
});
