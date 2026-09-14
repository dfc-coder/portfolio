import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("architecture: chapter handoffs overlap outgoing and incoming runtimes", async () => {
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");

  assert.match(lifecycle, /const chapterRuntimePairs/);
  assert.match(lifecycle, /scenes:\s*\["hero",\s*"career"\]/);
  assert.match(lifecycle, /scenes:\s*\["career",\s*"systems"\]/);
  assert.match(lifecycle, /scenes:\s*\["systems",\s*"gallery"\]/);
  assert.match(lifecycle, /scenes:\s*\["gallery",\s*"agent"\]/);
  assert.match(lifecycle, /runtimeScenesForState/);
  assert.match(lifecycle, /new Map<RuntimeScene, Cleanup>/);
  assert.match(lifecycle, /new Map<RuntimeScene, Promise<void>>/);
});

test("architecture: outgoing cleanup waits until all desired runtimes are mounted", async () => {
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");

  assert.match(
    lifecycle,
    /if \(\[\.\.\.desiredRuntimes\]\.some\(\(scene\) => !mountedRuntimes\.has\(scene\)\)\) return;/,
  );
  assert.match(lifecycle, /desiredRuntimes\.forEach\(\(scene\) => \{[\s\S]*ensureMounted\(scene\)/);
  assert.match(lifecycle, /if \(disposed \|\| !desiredRuntimes\.has\(scene\)\)/);
  assert.match(lifecycle, /cleanupObsoleteRuntimes\(version\)/);
  assert.doesNotMatch(lifecycle, /cleanupActive/);
});

test("architecture: Agent UI and Three canvas share the chapter handoff", async () => {
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const graphicsCss = await read("src/graphics/stage-graphics.css");

  assert.match(portfolio, /runtimeScenesForState\(narrativeRuntime\.getState\(\)\)\.includes\("agent"\)/);
  assert.match(portfolio, /runtimeScenesForState\(state\)\.includes\("agent"\)/);
  assert.match(portfolio, /<AgentOS v-if="agentActive" \/>/);
  assert.match(graphicsCss, /opacity:\s*var\(--agent,\s*0\)/);
});
