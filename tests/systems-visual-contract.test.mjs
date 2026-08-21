import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = process.cwd();

const loadTsModule = async (relativePath) => {
  const source = await readFile(resolve(root, relativePath), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: relativePath,
  });

  const encoded = Buffer.from(outputText).toString("base64");
  return import(`data:text/javascript;base64,${encoded}`);
};

const motion = await loadTsModule("src/systems-motion-contract.ts");
const projectData = await loadTsModule("src/systems-projects.ts");

test("BDD: Given Career is leaving, when THE EVIDENCE becomes readable, then Career is no longer a competing protagonist", () => {
  const systemsDelta = 0.11;
  const introPresence = motion.range(
    systemsDelta,
    motion.SYSTEMS_TIMING.introIn[0],
    motion.SYSTEMS_TIMING.introIn[1],
  );
  const careerResidual = motion.priorChapterResidual(systemsDelta);

  assert.ok(introPresence >= 0.45, `intro should be readable, got ${introPresence}`);
  assert.ok(
    careerResidual < 0.01,
    `Career must be effectively gone before the intro owns the beat, got ${careerResidual}`,
  );
});

test("BDD: Given THE EVIDENCE is yielding, when project 00 becomes readable, then the chapter statement is no longer a competing protagonist", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;

  for (let step = 0; step <= 100; step += 1) {
    const systemsDelta =
      motion.SYSTEMS_TIMING.contentReveal[0] +
      ((motion.SYSTEMS_TIMING.contentReveal[1] - motion.SYSTEMS_TIMING.contentReveal[0]) * step) /
        100;
    const state = motion.chapterState(
      chapterSystemsNode + systemsDelta,
      chapterSystemsNode,
      chapterGalleryNode,
    );

    if (state.contentReveal >= 0.05) {
      assert.ok(
        state.introVisibility < 0.01,
        `chapter statement still competes when content is readable: intro=${state.introVisibility}, content=${state.contentReveal}`,
      );
    }
  }
});

test("BDD: Given THE EVIDENCE hands off to project 00, then there is no perceptible dead interval between chapter and system", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;
  let deadSamples = 0;
  let longestDeadRun = 0;

  for (let step = 0; step <= 120; step += 1) {
    const systemsDelta = 0.20 + step * 0.003;
    const state = motion.chapterState(
      chapterSystemsNode + systemsDelta,
      chapterSystemsNode,
      chapterGalleryNode,
    );
    const coverage = Math.max(state.introVisibility, state.contentReveal);

    if (coverage < 0.01) {
      deadSamples += 1;
      longestDeadRun = Math.max(longestDeadRun, deadSamples);
    } else {
      deadSamples = 0;
    }
  }

  assert.ok(
    longestDeadRun <= 7,
    `chapter-to-project dead interval is too wide: ${longestDeadRun} samples`,
  );
});

test("BDD: Given project 00 is the first dossier, then it owns an extended full-focus plateau before project 01 begins", () => {
  const startNode = 6;
  const endOfRequiredPlateau = startNode + motion.SYSTEMS_COLLECTION.firstHoldEnd - 0.01;
  const duringPlateau = motion.collectionPosition(endOfRequiredPlateau, startNode, 5);
  const afterPlateau = motion.collectionPosition(
    startNode + motion.SYSTEMS_COLLECTION.firstHoldEnd + 0.10,
    startNode,
    5,
  );

  assert.equal(duringPlateau, 0, "project 00 must remain fully focused through its first hold window");
  assert.ok(afterPlateau > 0, "project 01 transition should begin only after project 00 hold completes");
});

test("BDD: Given a project-to-project transition, when titles exchange ownership, then two title protagonists never coexist", () => {
  for (let step = 0; step <= 100; step += 1) {
    const progress = step / 100;
    const outgoing = motion.motionForOffset(-progress).title;
    const incoming = motion.motionForOffset(1 - progress).title;

    assert.ok(
      !(outgoing > 0.05 && incoming > 0.05),
      `title overlap at transition progress ${progress}: outgoing=${outgoing}, incoming=${incoming}`,
    );
  }
});

test("BDD: Given titles exchange ownership, when the viewport crosses the handoff, then architecture keeps the scene intentional", () => {
  for (let step = 0; step <= 100; step += 1) {
    const progress = step / 100;
    const outgoing = motion.motionForOffset(-progress).graph;
    const incoming = motion.motionForOffset(1 - progress).graph;

    assert.ok(
      Math.max(outgoing, incoming) >= 0.95,
      `architecture coverage dropped at ${progress}`,
    );
  }
});

test("BDD: Given project 00 enters after THE EVIDENCE, when its architecture appears, then the graph visibly builds instead of arriving complete", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;
  const [start, end] = motion.SYSTEMS_TIMING.initialGraphBuild;
  const mid = (start + end) / 2;

  const before = motion.chapterState(
    chapterSystemsNode + start,
    chapterSystemsNode,
    chapterGalleryNode,
  ).initialGraphBuild;
  const during = motion.chapterState(
    chapterSystemsNode + mid,
    chapterSystemsNode,
    chapterGalleryNode,
  ).initialGraphBuild;
  const after = motion.chapterState(
    chapterSystemsNode + end,
    chapterSystemsNode,
    chapterGalleryNode,
  ).initialGraphBuild;

  assert.ok(before <= 0.01, `build should start near zero, got ${before}`);
  assert.ok(during > 0.35 && during < 0.65, `build midpoint should be visible, got ${during}`);
  assert.ok(after >= 0.99, `build should finish, got ${after}`);
});

test("SDD: the five systems have five distinct architecture signatures", () => {
  const signatures = projectData.systemsProjects.map((project) => {
    const nodes = project.graph.nodes
      .map((node) => `${node.id}:${node.x},${node.y}`)
      .join("|");
    const edges = project.graph.edges
      .map((edge) => `${edge.from}>${edge.to}:${edge.path ?? "auto"}`)
      .join("|");
    return `${nodes}::${edges}`;
  });

  assert.equal(new Set(signatures).size, projectData.systemsProjects.length);
});

test("TDD regression: active CSS files contain real newlines and no escaped-newline corruption", async () => {
  for (const file of [
    "src/systems-experience-v5.css",
    "src/visual-continuity-v3.css",
  ]) {
    const css = await readFile(resolve(root, file), "utf8");
    assert.ok(css.split("\n").length > 40, `${file} must be a real multiline stylesheet`);
    assert.equal(css.includes("\\n"), false, `${file} contains literal \\n escapes`);
  }
});

test("TDD regression: shared visual continuity must never mutate Systems direct-child positioning", async () => {
  const css = await readFile(resolve(root, "src/visual-continuity-v3.css"), "utf8");

  assert.doesNotMatch(
    css,
    /\.systems-experience\s*>\s*\*\s*\{[^}]*position\s*:\s*relative/is,
  );
  assert.doesNotMatch(
    css,
    /\.trajectory-experience\s*>\s*\*\s*\{[^}]*position\s*:\s*relative/is,
  );
  assert.match(css, /\.systems-experience\s*\{[^}]*isolation\s*:\s*isolate/is);
});

test("TDD regression: critical Systems composition layers are explicitly absolute", async () => {
  const css = await readFile(resolve(root, "src/systems-experience-v5.css"), "utf8");

  for (const selector of [
    ".systems-intro",
    ".systems-header",
    ".systems-axis",
    ".systems-axis-items",
    ".systems-projects",
    ".systems-counter",
  ]) {
    assert.match(
      css,
      new RegExp(`${selector.replaceAll(".", "\\.")}[^}]*position\\s*:\\s*absolute\\s*!important`, "is"),
      `${selector} must remain absolutely positioned`,
    );
  }
});

test("TDD regression: main mounts only the clean V5 Systems director and V3 continuity styles", async () => {
  const main = await readFile(resolve(root, "src/main.ts"), "utf8");

  assert.match(main, /systems-experience-v5/);
  assert.match(main, /visual-continuity-v3\.css/);
  assert.match(main, /systems-experience-v5\.css/);
  assert.doesNotMatch(main, /systems-experience-v4\.css/);
  assert.doesNotMatch(main, /visual-continuity-v2\.css/);
});

test("TDD regression: supporting System Note copy is readable and structurally anchored", async () => {
  const css = await readFile(
    resolve(root, "src/systems-experience-v5.css"),
    "utf8",
  );

  assert.match(css, /content: "SYSTEM NOTE"/);
  assert.match(css, /font-size: 12px !important/);
  assert.match(css, /color: rgba\(238, 234, 226, \.76\) !important/);
  assert.match(css, /border-top: 1px solid/);
});
