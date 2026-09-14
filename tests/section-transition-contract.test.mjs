import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("architecture: StageGraphics does not own section transitions", async () => {
  const graphics = await read("src/graphics/stageGraphics.ts");

  assert.doesNotMatch(graphics, /setStageTransition/);
  assert.doesNotMatch(graphics, /transitionScene|transitionMaterial|transitionFragment/);
  assert.doesNotMatch(graphics, /uTransition|transitionTexture/);
});

test("architecture: section transition WebGL is lazy and single-owner", async () => {
  const transition = await read("src/experiences/section-transition.ts");
  const mountStart = transition.indexOf("export const mountSectionTransition");
  const createRendererStart = transition.indexOf("const createTransitionRenderer");

  assert.ok(createRendererStart >= 0);
  assert.ok(mountStart > createRendererStart);
  assert.match(transition, /const MAX_TRANSITION_PIXELS = 1_250_000/);
  assert.match(transition, /let renderer: TransitionRenderer \| null = null/);
  assert.match(transition, /const ensureRenderer = \(\) =>/);
  assert.match(transition, /renderer = createTransitionRenderer\(\)/);
  assert.match(transition, /const currentRenderer = ensureRenderer\(\)/);
  assert.match(transition, /if \(!currentRenderer\) \{\s*commit\(\);\s*return;\s*\}/);
  assert.doesNotMatch(transition, /requestAnimationFrame/);

  const mountBody = transition.slice(mountStart);
  const ensureRendererCall = mountBody.indexOf("const currentRenderer = ensureRenderer()");
  const getContextCall = mountBody.indexOf('getContext("webgl"');

  assert.ok(ensureRendererCall >= 0);
  assert.equal(getContextCall, -1);
});

test("architecture: section transition renderer is reused and destroyed deterministically", async () => {
  const transition = await read("src/experiences/section-transition.ts");

  assert.match(transition, /if \(renderer\) return renderer/);
  assert.match(transition, /let rendererUnavailable = false/);
  assert.match(transition, /rendererUnavailable = renderer === null/);
  assert.match(transition, /removeEventListener\("resize", resize\)/);
  assert.match(transition, /gl\.deleteBuffer\(buffer\)/);
  assert.match(transition, /gl\.deleteProgram\(program\)/);
  assert.match(transition, /canvas\.remove\(\)/);
  assert.match(transition, /renderer\?\.destroy\(\)/);
  assert.match(transition, /renderer = null/);
});
