import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("BDD: Agent and Three stay outside the initial frontend graph", async () => {
  const main = await read("src/main.ts");
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const agent = await read("src/components/agent/AgentOS.vue");
  const stageGraphics = await read("src/graphics/stageGraphics.ts");

  assert.doesNotMatch(main, /stageGraphics/);
  assert.doesNotMatch(main, /components\/agent/);
  assert.doesNotMatch(portfolio, /import\s+AgentOS\s+from/);

  assert.match(portfolio, /import\("\.\/agent\/AgentOS\.vue"\)/);
  assert.match(portfolio, /defineAsyncComponent/);
  assert.match(portfolio, /agentModulePromise/);
  assert.match(portfolio, /agentModulePromise = null/);
  assert.match(portfolio, /scene === "gallery"/);
  assert.match(portfolio, /scene === "agent"/);
  assert.match(portfolio, /<AsyncAgentOS v-if="agentActive" \/>/);

  assert.match(agent, /import \{ mountStageGraphics \} from "\.\.\/\.\.\/graphics\/stageGraphics"/);
  assert.match(agent, /disposeStageGraphics = mountStageGraphics\(\)/);
  assert.match(agent, /disposeStageGraphics\?\.\(\)/);
  assert.match(agent, /<style src="\.\/agent\.css"><\/style>/);
  assert.match(agent, /<style src="\.\.\/\.\.\/graphics\/stage-graphics\.css"><\/style>/);

  assert.match(stageGraphics, /import \* as THREE from "three"/);
});
