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

test("BDD: speech energy is independent from general presence activity", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const stage = await read("src/graphics/stageGraphics.ts");

  assert.match(os, /pulseAgentSpeech/);
  assert.match(os, /speechChars/);
  assert.match(os, /const boundary =/);
  assert.match(os, /if \(!boundary && speechChars < 6\) return/);
  assert.match(stage, /speechTarget/);
  assert.match(stage, /speechResponse/);
  assert.match(stage, /pulseAgentSpeech/);
  assert.match(stage, /uSpeech/);
  assert.match(stage, /speechTarget \*= Math\.exp\(-7\.2 \* dt\)/);
  assert.doesNotMatch(os, /pulseAgentVisual\(strength\);\s*speechChars = 0/);
});

test("BDD: visual motion keeps continuous flow while presented words drive the shell", async () => {
  const stage = await read("src/graphics/stageGraphics.ts");
  const particles = await read("src/graphics/agent-particle-cloud.ts");
  const liquid = await read("src/graphics/agent-liquid-shader.ts");

  assert.match(stage, /AgentParticleCloud/);
  assert.match(stage, /this\.agentParticles\.update/);
  assert.match(stage, /this\.agentGroup\.add\(this\.agentParticles\.points\)/);
  assert.match(stage, /private agentTime = 0/);
  assert.match(stage, /this\.agentTime \+= dt \* phaseMotionRate/);

  assert.match(particles, /pointCount = 4096/);
  assert.match(particles, /new THREE\.Points/);
  assert.match(particles, /uniform float uSpeech/);
  assert.match(particles, /Continuous, low-energy circulation/);
  assert.match(particles, /speechPacket/);
  assert.match(particles, /uSpeech \* speaking/);

  assert.match(liquid, /The flow never freezes/);
  assert.match(liquid, /float fluidValue\(vec2 p/);
  assert.match(liquid, /float refractStrength/);
  assert.match(liquid, /float caustic/);
  assert.match(liquid, /vec3 shellEdge/);
  assert.match(liquid, /uniform float uSpeech/);
});

test("BDD: the interface remains restrained around the reactive orb", async () => {
  const os = await read("src/components/agent/AgentOS.vue");

  assert.match(os, /READY/);
  assert.match(os, /LISTENING/);
  assert.match(os, /THINKING/);
  assert.match(os, /SPEAKING/);
  assert.match(os, /const engageAgent = \(\) =>/);
  assert.match(os, /inputEl\.value\?\.focus\(\)/);
  assert.match(os, /@pointerenter="wakeAgent/);
  assert.doesNotMatch(os, /agent-presence__orbit|agent-presence__reticle|agent-session__state/);
});
