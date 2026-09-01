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

test("BDD: network chunks are presented at a stable UI-controlled pace", async () => {
  const runtime = await read("src/components/agent/useAgentRuntime.ts");
  const os = await read("src/components/agent/AgentOS.vue");

  assert.match(runtime, /PRESENTATION_BASE_CPS/);
  assert.match(runtime, /PRESENTATION_MAX_BATCH/);
  assert.match(runtime, /presentationQueue \+= text/);
  assert.match(runtime, /requestAnimationFrame\(present\)/);
  assert.match(runtime, /await waitForPresentation\(\)/);
  assert.match(runtime, /hooks\.onPresent\?\.\(batch\)/);
  assert.doesNotMatch(runtime, /target\.text \+= pendingText/);
  assert.doesNotMatch(runtime, /scheduleStreamFlush/);

  assert.match(os, /onPresent: \(text\) =>/);
  assert.match(os, /pulsePresentedText\(text\)/);
  assert.match(os, /message\.streaming/);
  assert.match(os, /agent-msg__stream/);
  assert.match(os, /@scroll="handleLaneScroll"/);
});

test("BDD: visual motion follows presented output instead of accumulating arbitrary impulses", async () => {
  const stage = await read("src/graphics/stageGraphics.ts");

  assert.match(stage, /activityTarget = Math\.max\(agentSignal\.activityTarget, impulse\)/);
  assert.match(stage, /const phaseMotionRate/);
  assert.match(stage, /private agentTime = 0/);
  assert.match(stage, /this\.agentTime \+= dt \* phaseMotionRate/);
  assert.match(stage, /uTime\.value = this\.agentTime/);
  assert.match(stage, /excessActivity \* Math\.exp\(-7\.0 \* dt\)/);
  assert.doesNotMatch(stage, /activityTarget \+ impulse/);
});

test("BDD: the agent presence is carried by one reactive refractive liquid surface", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const stage = await read("src/graphics/stageGraphics.ts");
  const shader = await read("src/graphics/agent-liquid-shader.ts");

  assert.match(os, /READY/);
  assert.match(os, /LISTENING/);
  assert.match(os, /THINKING/);
  assert.match(os, /SPEAKING/);
  assert.match(os, /const engageAgent = \(\) =>/);
  assert.match(os, /inputEl\.value\?\.focus\(\)/);
  assert.match(os, /@pointerenter="wakeAgent/);

  assert.match(stage, /new THREE\.PlaneGeometry\(/);
  assert.match(stage, /new THREE\.Mesh\(this\.agentGeometry, this\.agentMaterial\)/);
  assert.match(stage, /agentLiquidFragment/);
  assert.match(stage, /agentLiquidVertex/);
  assert.match(stage, /THREE\.NormalBlending/);

  assert.match(shader, /float fluidValue\(vec2 p/);
  assert.match(shader, /float refractStrength/);
  assert.match(shader, /float caustic/);
  assert.match(shader, /float chroma/);
  assert.match(shader, /vec3 shellMid/);
  assert.match(shader, /uniform float uMode/);
  assert.match(shader, /listeningWave/);
  assert.match(shader, /speakingWave/);

  assert.doesNotMatch(stage, /THREE\.Points/);
  assert.doesNotMatch(stage, /pointCount\s*=\s*4096/);
  assert.doesNotMatch(stage, /createRing/);
  assert.doesNotMatch(shader, /diffuse\s*=|sphereRadius|lightDirection/);
  assert.doesNotMatch(os, /agent-presence__orbit|agent-presence__reticle|agent-session__state/);
});
