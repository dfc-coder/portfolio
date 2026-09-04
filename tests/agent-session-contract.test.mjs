import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("agent remains stateless while round-tripping full tool context", async () => {
  const provider = await read("src/components/agent/businessAgentProvider.ts");
  const runtime = await read("src/components/agent/useAgentRuntime.ts");

  assert.doesNotMatch(provider, /SESSION_ID|session_id|sessionStorage|SESSION_KEY/);
  assert.match(provider, /JSON\.stringify\(\{ message: question, context \}\)/);
  assert.match(provider, /frame\.event === "context"/);
  assert.match(runtime, /const context = shallowRef<AgentContextMessage\[]>\(\[\]\)/);
  assert.match(runtime, /provider\.ask\(question, context\.value\)/);
  assert.match(runtime, /context\.value = event\.messages/);
  assert.doesNotMatch(provider, /history: history\.map/);
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

test("BDD: speech, interaction, pointer and state are independent visual signals", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const controller = await read("src/graphics/agent-visual-controller.ts");
  const stage = await read("src/graphics/stageGraphics.ts");

  assert.match(os, /pulseAgentSpeech/);
  assert.match(os, /pulseAgentInteraction/);
  assert.match(os, /speechChars/);
  assert.match(os, /const boundary =/);
  assert.match(os, /if \(!boundary && speechChars < 6\) return/);

  assert.match(controller, /activityTarget/);
  assert.match(controller, /speechTarget/);
  assert.match(controller, /interactionTarget/);
  assert.match(controller, /pointerForceTarget/);
  assert.match(controller, /const speechResponse/);
  assert.match(controller, /state\.phase !== "speaking"/);
  assert.match(controller, /updateAgentVisual/);

  assert.match(stage, /updateAgentVisual\(dt\)/);
  assert.match(stage, /setVisualPointer/);
  assert.match(stage, /pulseAgentInteraction/);
  assert.doesNotMatch(stage, /interface AgentSignalState/);
});

test("BDD: thinking is a distinct upper atomic halo pose", async () => {
  const controller = await read("src/graphics/agent-visual-controller.ts");
  const particles = await read("src/graphics/agent-particle-cloud.ts");
  const stage = await read("src/graphics/stageGraphics.ts");

  assert.match(controller, /thinkingBlend/);
  assert.match(controller, /state\.phase === "thinking" \? 1 : 0/);
  assert.match(controller, /"thinking"\) return "focused"/);

  assert.match(particles, /THINKING POSE/);
  assert.match(particles, /haloParticle/);
  assert.match(particles, /haloA/);
  assert.match(particles, /haloB/);
  assert.match(particles, /haloC/);
  assert.match(particles, /haloTarget/);
  assert.match(particles, /coreTarget/);
  assert.match(particles, /mix\(sphere, thinkingTarget, uThinkingBlend\)/);
  assert.match(particles, /uTime \* \(1\.45 \+ aLayer/);

  assert.match(stage, /signals\.thinkingBlend/);
  assert.match(stage, /this\.agentMesh\.position\.y = -signals\.thinkingBlend/);
});

test("BDD: listening visibly attends to the cursor with layered inertia", async () => {
  const controller = await read("src/graphics/agent-visual-controller.ts");
  const particles = await read("src/graphics/agent-particle-cloud.ts");
  const stage = await read("src/graphics/stageGraphics.ts");

  assert.match(stage, /agentScreenCenter/);
  assert.match(stage, /distanceToOrb/);
  assert.match(stage, /localX/);
  assert.match(stage, /localY/);
  assert.match(stage, /setVisualPointer\(localX, localY/);

  assert.match(controller, /pointerFastX/);
  assert.match(controller, /pointerSlowX/);
  assert.match(controller, /pointerDx/);
  assert.match(controller, /pointerDy/);
  assert.match(controller, /pointerTargetX/);
  assert.match(controller, /10\.5/);
  assert.match(controller, /3\.2/);

  assert.match(particles, /uPointerForce/);
  assert.match(particles, /uPointerVelocity/);
  assert.match(particles, /uPointerSlow/);
  assert.match(particles, /uPointerDelta/);
  assert.match(particles, /toPointer/);
  assert.match(particles, /broadField/);
  assert.match(particles, /vec2 drag/);
  assert.match(particles, /vec2 curl/);
  assert.match(particles, /pressureWave/);
  assert.match(particles, /basePresenceScale = 1\.20/);
});

test("BDD: speaking keeps continuous life while presented words drive stronger emission", async () => {
  const particles = await read("src/graphics/agent-particle-cloud.ts");
  const liquid = await read("src/graphics/agent-liquid-shader.ts");

  assert.match(particles, /pointCount = 4096/);
  assert.match(particles, /new THREE\.Points/);
  assert.match(particles, /CONTINUOUS LIFE/);
  assert.match(particles, /SPEAKING/);
  assert.match(particles, /speechPacket/);
  assert.match(particles, /speechAmplitude/);
  assert.match(particles, /p\.x \+= speechAmplitude/);
  assert.match(particles, /speechScale/);

  assert.match(liquid, /The flow never freezes/);
  assert.match(liquid, /float fluidValue\(vec2 p/);
  assert.match(liquid, /uniform float uSpeech/);
});

test("BDD: state-derived tone gives the same agent different movement character", async () => {
  const controller = await read("src/graphics/agent-visual-controller.ts");
  const particles = await read("src/graphics/agent-particle-cloud.ts");

  for (const tone of ["calm", "curious", "focused", "confident", "uncertain"]) {
    assert.match(controller, new RegExp(`"${tone}"`));
  }

  assert.match(controller, /phaseTone/);
  assert.match(controller, /toneMode/);
  assert.match(particles, /curious/);
  assert.match(particles, /focused/);
  assert.match(particles, /confident/);
  assert.match(particles, /uncertain/);
});

test("BDD: the interface remains restrained around the expressive orb", async () => {
  const os = await read("src/components/agent/AgentOS.vue");

  assert.match(os, /READY/);
  assert.match(os, /LISTENING/);
  assert.match(os, /WORKING/);
  assert.match(os, /SPEAKING/);
  assert.match(os, /EXECUTION/);
  assert.match(os, /const engageAgent = \(\) =>/);
  assert.match(os, /pulseAgentInteraction\(0\.82\)/);
  assert.match(os, /inputEl\.value\?\.focus\(\)/);
  assert.match(os, /@pointerenter="wakeAgent/);
  assert.doesNotMatch(os, /agent-presence__orbit|agent-presence__reticle|agent-session__state/);
});
