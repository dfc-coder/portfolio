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

test("BDD: the interface behaves as an active virtual presence", async () => {
  const os = await read("src/components/agent/AgentOS.vue");
  const presence = await read("src/components/agent/agent-presence.css");

  assert.match(os, /ONLINE/);
  assert.match(os, /LISTENING/);
  assert.match(os, /REASONING/);
  assert.match(os, /SPEAKING/);
  assert.match(os, /const engageAgent = \(\) =>/);
  assert.match(os, /inputEl\.value\?\.focus\(\)/);
  assert.match(os, /@pointerenter="wakeAgent/);
  assert.match(os, /Conversation context active/);
  assert.match(os, /NEW SESSION/);
  assert.match(os, /DC \/ AGENT/);

  assert.match(presence, /data-state="listening"/);
  assert.match(presence, /data-state="thinking"/);
  assert.match(presence, /data-state="speaking"/);
  assert.match(presence, /agent-presence__orbit/);
  assert.match(presence, /agent-session__state/);
});
