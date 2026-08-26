import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("mobile uses the existing fallback and skips cinematic runtime", async () => {
  const main = await read("src/main.ts");
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const mobile = await read("src/styles/mobile.css");

  assert.match(main, /const MOBILE_QUERY = "\(max-width: 820px\)";/);
  assert.match(main, /if \(!mobileExperience\)/);
  assert.match(main, /mountStageGraphics\(\)/);
  assert.match(portfolio, /id="ref-fallback"/);
  assert.match(portfolio, /id="mobile-agent"/);
  assert.match(portfolio, /<AgentOS \/>/);
  assert.match(mobile, /html\.mobile-experience \.ref-track[\s\S]*display: none !important;/);
  assert.match(mobile, /html\.mobile-experience \.ref-fallback[\s\S]*display: block !important;/);
  assert.doesNotMatch(portfolio, /MobilePortfolio/);
});
