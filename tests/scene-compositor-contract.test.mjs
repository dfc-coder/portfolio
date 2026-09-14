import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("performance: scene will-change is scoped to visible or transitioning roots", async () => {
  const shell = await read("src/styles/shell.css");
  const scroll = await read("src/experiences/scroll.ts");

  assert.doesNotMatch(
    shell,
    /\.ref-scene\s*\{[^}]*will-change/s,
    "base scene styles must not permanently promote every scene",
  );
  assert.match(
    shell,
    /\.ref-scene\[data-scroll-compositor="true"\][\s\S]*will-change:\s*transform,\s*opacity/,
  );
  assert.match(
    shell,
    /\.ref-scene--gallery\[data-gallery-motion="true"\]/,
    "Gallery keeps its compositor hint only during the extended physical handoff",
  );
  assert.doesNotMatch(
    shell,
    /will-change:[^;]*filter/,
    "scene compositor hints must not reserve a filter layer",
  );

  assert.match(scroll, /const COMPOSITOR_VISIBILITY_EPSILON = 0\.001/);
  assert.match(scroll, /const sceneElements = \{/);
  assert.match(scroll, /element\.dataset\.scrollCompositor = "true"/);
  assert.match(scroll, /delete element\.dataset\.scrollCompositor/);
  assert.match(scroll, /updateCompositorOwnership\(opacity\)/);
  assert.match(
    scroll,
    /visible\(Math\.max\(opacity\.chapterCareer, opacity\.career\)\)/,
    "Trajectory remains promoted through its chapter-to-career ownership overlap",
  );
});
