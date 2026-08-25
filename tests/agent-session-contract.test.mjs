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
  assert.equal((provider.match(/session_id: SESSION_ID/g) ?? []).length, 2);
});
