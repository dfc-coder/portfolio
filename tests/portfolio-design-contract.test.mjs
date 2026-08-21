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

const motion = await loadTsModule("src/systems-motion-contract.ts");
const projects = await loadTsModule("src/systems-projects.ts");

/* --------------------------------------------------------------------------
   BDD — narrative ownership remains correct after the visual-system refactor.
   -------------------------------------------------------------------------- */

test("BDD: THE EVIDENCE owns a clean chapter beat before structural instructions appear", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;

  for (let step = 0; step <= 100; step += 1) {
    const delta = 0.02 + step * 0.0042;
    const state = motion.chapterState(
      chapterSystemsNode + delta,
      chapterSystemsNode,
      chapterGalleryNode,
    );

    if (state.introVisibility >= 0.35) {
      assert.ok(state.axisReveal < 0.01, `register leaked into chapter beat at ${delta}`);
      assert.ok(state.headerReveal < 0.01, `section header leaked into chapter beat at ${delta}`);
    }
  }
});

test("BDD: project 00 cannot become readable while THE EVIDENCE is still a competing protagonist", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;

  for (let step = 0; step <= 100; step += 1) {
    const delta =
      motion.SYSTEMS_TIMING.contentReveal[0] +
      ((motion.SYSTEMS_TIMING.contentReveal[1] - motion.SYSTEMS_TIMING.contentReveal[0]) * step) / 100;
    const state = motion.chapterState(
      chapterSystemsNode + delta,
      chapterSystemsNode,
      chapterGalleryNode,
    );

    if (state.contentReveal >= 0.05) {
      assert.ok(state.introVisibility < 0.01, `intro=${state.introVisibility}, content=${state.contentReveal}`);
    }
  }
});

test("BDD: the chapter-to-project handoff always keeps an intentional visual layer", () => {
  const chapterSystemsNode = 5;
  const chapterGalleryNode = 11;
  let run = 0;
  let longestRun = 0;

  for (let step = 0; step <= 150; step += 1) {
    const delta = 0.20 + step * 0.003;
    const state = motion.chapterState(
      chapterSystemsNode + delta,
      chapterSystemsNode,
      chapterGalleryNode,
    );
    const coverage = Math.max(
      state.introVisibility,
      state.axisReveal,
      state.headerReveal,
      state.contentReveal,
    );

    if (coverage < 0.01) {
      run += 1;
      longestRun = Math.max(longestRun, run);
    } else {
      run = 0;
    }
  }

  assert.ok(longestRun <= 2, `structural dead interval too wide: ${longestRun}`);
});

test("BDD: project titles exchange ownership without two simultaneous protagonists", () => {
  for (let step = 0; step <= 100; step += 1) {
    const p = step / 100;
    const outgoing = motion.motionForOffset(-p).title;
    const incoming = motion.motionForOffset(1 - p).title;
    assert.ok(!(outgoing > 0.05 && incoming > 0.05), `title overlap at ${p}`);
  }
});

test("SDD: each technical system keeps a distinct architecture topology", () => {
  const signatures = projects.systemsProjects.map((project) => {
    const nodes = project.graph.nodes.map((node) => `${node.id}:${node.x},${node.y}`).join("|");
    const edges = project.graph.edges.map((edge) => `${edge.from}>${edge.to}:${edge.path ?? "auto"}`).join("|");
    return `${nodes}::${edges}`;
  });
  assert.equal(new Set(signatures).size, projects.systemsProjects.length);
});

/* --------------------------------------------------------------------------
   SDD/TDD — same meaning => same primitive => same source of truth.
   -------------------------------------------------------------------------- */

test("SDD: design-system token layer owns shared signal, register, chapter and ambient geometry", async () => {
  const css = await read("src/design-system/tokens.css");
  for (const token of [
    "--ds-signal-rule",
    "--ds-register-left",
    "--ds-register-top",
    "--ds-register-height",
    "--ds-register-node",
    "--ds-chapter-top",
    "--ds-chapter-width",
    "--ds-ambient-width",
    "--ds-ambient-height",
  ]) {
    assert.match(css, new RegExp(token.replaceAll("-", "\\-")));
  }
});

test("TDD: Editorial Signal is one shared primitive across chapter, header and item contexts", async () => {
  const css = await read("src/design-system/primitives.css");
  for (const selector of [
    ".trajectory-intro__kicker",
    ".systems-intro__kicker",
    ".trajectory-header__label",
    ".systems-header__label",
    ".trajectory-entry__eyebrow",
    ".systems-project__eyebrow",
  ]) {
    assert.match(css, new RegExp(selector.replaceAll(".", "\\.")));
  }
  assert.match(css, /grid-template-columns:\s*auto var\(--ds-signal-rule\) auto/);
  assert.match(css, /letter-spacing:\s*var\(--ds-signal-track\)/);
});

test("TDD: Record and Evidence instantiate one Chapter Bridge template", async () => {
  const css = await read("src/design-system/templates.css");
  assert.match(css, /\.trajectory-intro,\s*\n\.systems-intro\s*\{/);
  assert.match(css, /left:\s*var\(--ds-chapter-left\)/);
  assert.match(css, /top:\s*var\(--ds-chapter-top\)/);
  assert.match(css, /width:\s*var\(--ds-chapter-width\)/);
  assert.match(css, /font-size:\s*var\(--ds-statement-size\)/);
});

test("TDD: Trajectory and Systems use the same register geometry and one active-node grammar", async () => {
  const css = await read("src/design-system/primitives.css");
  assert.match(css, /\.trajectory-axis,\s*\n\.systems-axis\s*\{/);
  assert.match(css, /left:\s*var\(--ds-register-left\)/);
  assert.match(css, /top:\s*var\(--ds-register-top\)/);
  assert.match(css, /height:\s*var\(--ds-register-height\)/);
  assert.match(css, /\.trajectory-axis::after,\s*\n\.systems-axis::after\s*\{[^}]*content:\s*none/is);
  assert.match(css, /\.trajectory-year > i,\s*\n\.systems-axis-item > i\s*\{/);
});

test("TDD: both registers expose populated inactive states instead of hiding navigation context", async () => {
  const css = await read("src/design-system/primitives.css");
  assert.match(css, /\.trajectory-year\s*\{[^}]*opacity:\s*calc\(var\(--trajectory-content[^}]*\.34/is);
  assert.match(css, /\.systems-axis-item\s*\{[^}]*opacity:\s*calc\(var\(--systems-content[^}]*\.34/is);
});

test("TDD: section headers use one shared instruction template", async () => {
  const css = await read("src/design-system/templates.css");
  assert.match(css, /\.trajectory-header,\s*\n\.systems-header\s*\{/);
  assert.match(css, /left:\s*22px/);
  assert.match(css, /right:\s*22px/);
  assert.match(css, /top:\s*22px/);
});

test("TDD: pointer lighting has one global owner and chapter-local spotlights are prohibited", async () => {
  const css = await read("src/design-system/templates.css");
  assert.match(css, /\.ref-global-pointer-light\s*\{/);
  assert.match(css, /ellipse var\(--ds-ambient-width\) var\(--ds-ambient-height\)/);
  assert.match(css, /\.trajectory-experience::after,\s*\n\.systems-experience::after\s*\{[^}]*content:\s*none/is);
});

test("TDD: the design-system runtime owns identical Chapter Bridge travel", async () => {
  const runtime = await read("src/design-system/runtime.ts");
  assert.match(runtime, /const y = \(1 - enter\) \* 42 - exit \* 58/g);
  const occurrences = runtime.match(/const y = \(1 - enter\) \* 42 - exit \* 58/g) ?? [];
  assert.equal(occurrences.length, 2);
});

test("TDD: main loads the design system after chapter styles and mounts its runtime last", async () => {
  const main = await read("src/main.ts");
  const systemsCss = main.indexOf('import "./systems-experience-v5.css"');
  const tokens = main.indexOf('import "./design-system/tokens.css"');
  const primitives = main.indexOf('import "./design-system/primitives.css"');
  const templates = main.indexOf('import "./design-system/templates.css"');
  assert.ok(systemsCss >= 0 && systemsCss < tokens && tokens < primitives && primitives < templates);

  const systemsMount = main.indexOf("mountSystemsExperience();");
  const designMount = main.indexOf("mountDesignSystemRuntime();");
  assert.ok(systemsMount >= 0 && systemsMount < designMount);
  assert.doesNotMatch(main, /mountVisualContinuity\(\)/);
});

test("TDD: legacy continuity layer no longer duplicates shared primitives", async () => {
  const css = await read("src/visual-continuity-v3.css");
  assert.doesNotMatch(css, /\.ref-global-pointer-light/);
  assert.doesNotMatch(css, /\.trajectory-intro__kicker/);
  assert.doesNotMatch(css, /\.systems-intro__kicker/);
  assert.doesNotMatch(css, /\.trajectory-axis/);
  assert.doesNotMatch(css, /\.systems-axis/);
});
