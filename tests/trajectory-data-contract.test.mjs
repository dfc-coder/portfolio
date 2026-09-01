import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

const loadTsModule = async (relativePath) => {
  const source = await read(relativePath);
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: relativePath,
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
};

const trajectory = await loadTsModule("src/experiences/trajectory-data.ts");

test("BDD: professional trajectory follows the CV current-first order and exact periods", () => {
  assert.deepEqual(
    trajectory.experiences.map(({ period, role }) => ({ period, role })),
    [
      { period: "JAN 2024 — NOW", role: "AI Engineer / Full-Stack Developer" },
      { period: "DEC 2025 — APR 2026", role: "AI Engineer" },
      { period: "JAN 2023 — SEP 2025", role: "Software Engineer" },
    ],
  );
});

test("BDD: freelance overlap and transition to primary activity remain explicit", () => {
  const [freelance] = trajectory.experiences;
  assert.match(freelance.summary, /parallel through Apr 2026/i);
  assert.match(freelance.summary, /primary professional activity from May 2026/i);
});

test("BDD: trajectory does not invent unsupported employer locations", () => {
  const serialized = JSON.stringify(trajectory.experiences);
  assert.doesNotMatch(serialized, /Madrid \/ Remote|FK Tech · Argentina|Applied AI · Remote/);
});
