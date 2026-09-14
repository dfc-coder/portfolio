import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("BDD: Agent and Three stay outside the initial frontend JS graph", async () => {
  const main = await read("src/main.ts");
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");

  assert.doesNotMatch(main, /mountStageGraphics|stageGraphics\.ts|AgentOS\.vue/);
  assert.match(
    portfolio,
    /defineAsyncComponent\(\(\) => import\("\.\/agent\/AgentOS\.vue"\)\)/,
  );
  assert.match(portfolio, /runtimeScenesForState/);
  assert.match(portfolio, /<AgentOS v-if="agentActive" \/>/);
  assert.doesNotMatch(portfolio, /import\s+AgentOS\s+from/);

  assert.match(
    lifecycle,
    /agent: async \(\) => \{[\s\S]*import\("\.\.\/graphics\/stageGraphics"\)/,
  );
  assert.match(
    lifecycle,
    /gallery: \(\) => \{[\s\S]*import\("\.\.\/components\/agent\/AgentOS\.vue"\)[\s\S]*import\("\.\.\/graphics\/stageGraphics"\)/,
  );
});
