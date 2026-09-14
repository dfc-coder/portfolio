import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("performance: desktop keeps the authored header blur while mobile disables it", async () => {
  const shell = await read("src/styles/shell.css");
  const mobileStart = shell.indexOf("@media (max-width: 680px)");
  const reducedMotionStart = shell.indexOf("@media (prefers-reduced-motion: reduce)", mobileStart);

  assert.ok(mobileStart > 0, "mobile shell breakpoint must exist");
  assert.ok(reducedMotionStart > mobileStart, "mobile shell block must precede reduced motion");

  const desktopShell = shell.slice(0, mobileStart);
  const mobileShell = shell.slice(mobileStart, reducedMotionStart);

  assert.match(
    desktopShell,
    /\.ref-header\s*\{[\s\S]*?background:\s*rgba\(9,\s*9,\s*8,\s*\.68\);[\s\S]*?backdrop-filter:\s*blur\(16px\)\s+saturate\(1\.1\);[\s\S]*?\}/,
  );
  assert.match(
    mobileShell,
    /\.ref-header\s*\{[\s\S]*?background:\s*rgba\(9,\s*9,\s*8,\s*\.94\);[\s\S]*?-webkit-backdrop-filter:\s*none;[\s\S]*?backdrop-filter:\s*none;[\s\S]*?\}/,
  );
});

test("performance: grain stays unchanged until profiling justifies a static texture", async () => {
  const shell = await read("src/styles/shell.css");

  assert.match(shell, /\.ref-grain\s*\{[\s\S]*?mix-blend-mode:\s*soft-light;/);
  assert.match(shell, /feTurbulence/);
  assert.doesNotMatch(shell, /deviceMemory|hardwareConcurrency|low-end-device|data-low-end/);
});
