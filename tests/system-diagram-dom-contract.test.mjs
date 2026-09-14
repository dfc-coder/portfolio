import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("PR7: each System renders exactly one responsive graph variant", async () => {
  const diagram = await read("src/components/narrative/SystemDiagram.vue");
  const scene = await read("src/components/narrative/SystemsScene.vue");

  assert.equal((diagram.match(/<svg\b/g) ?? []).length, 1);
  assert.equal((diagram.match(/compileSystemGraph\(/g) ?? []).length, 1);
  assert.match(diagram, /compileSystemGraph\(props\.project\.graph, props\.mode\)/);
  assert.doesNotMatch(diagram, /v-for="variant in scenes"|systems-diagram__variant--desktop|systems-diagram__variant--mobile/);

  assert.match(scene, /matchMedia\(MOBILE_BREAKPOINT\)/);
  assert.match(scene, /compact\.value \? "mobile" : "desktop"/);
  assert.match(scene, /addEventListener\("change", onCompactChange\)/);
  assert.match(scene, /removeEventListener\("change", onCompactChange\)/);
  assert.match(scene, /<SystemDiagram :project="project" :mode="graphMode" \/>/);
});

test("PR7: project virtualization remains intentionally deferred", async () => {
  const scene = await read("src/components/narrative/SystemsScene.vue");

  assert.match(scene, /v-for="\(project, index\) in projects"/);
  assert.doesNotMatch(scene, /previousProject|activeProject|nextProject|visibleProjects/);
});
