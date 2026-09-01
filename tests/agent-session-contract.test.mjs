import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("agent session lifetime matches the visible page conversation", async () => {
  const provider = await read("src/components/agent/businessAgentProvider.ts");

  assert.match(provider, /const SESSION_ID = `web-\$\{crypto\.randomUUID\(\)\}`;/);
  assert.doesNotMatch(provider, /sessionStorage|SESSION_KEY|getItem\(|setItem\(/);
  assert.equal((provider.match(/session_id: SESSION_ID/g) ?? []).length, 1);
});

test("BDD: the agent presence is carried by one reactive liquid surface", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const stage = await read("src/graphics/stageGraphics.ts");

  assert.match(os, /READY/);
  assert.match(os, /LISTENING/);
  assert.match(os, /THINKING/);
  assert.match(os, /SPEAKING/);
  assert.match(os, /const engageAgent = \(\) =>/);
  assert.match(os, /inputEl\.value\?\.focus\(\)/);
  assert.match(os, /@pointerenter="wakeAgent/);

  assert.match(stage, /new THREE\.PlaneGeometry\(2\.2, 2\.2/);
  assert.match(stage, /new THREE\.Mesh\(this\.agentGeometry, this\.agentMaterial\)/);
  assert.match(stage, /float fbm\(vec2 p\)/);
  assert.match(stage, /uniform float uMode/);
  assert.match(stage, /listenMembrane/);
  assert.match(stage, /voiceMembrane/);
  assert.match(stage, /THREE\.NormalBlending/);

  assert.doesNotMatch(stage, /THREE\.Points/);
  assert.doesNotMatch(stage, /pointCount\s*=\s*4096/);
  assert.doesNotMatch(stage, /createRing/);
  assert.doesNotMatch(os, /agent-presence__orbit|agent-presence__reticle|agent-session__state/);
});
