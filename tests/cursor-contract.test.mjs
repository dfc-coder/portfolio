import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("cursor keeps native fallback until the custom cursor has a valid position", async () => {
  const runtime = await read("src/experiences/continuity.ts");

  const appendAt = runtime.indexOf("portfolio.append(cursor, ring)");
  const showAt = runtime.indexOf("const showCursor = () =>");
  const nativeHideAt = runtime.indexOf('portfolio.classList.add("has-cursor")');

  assert.ok(appendAt >= 0);
  assert.ok(showAt > appendAt);
  assert.ok(nativeHideAt > showAt);
  assert.match(runtime, /onPointerMove[\s\S]*showCursor\(\)/);
  assert.match(runtime, /hideCursor[\s\S]*classList\.remove\("has-cursor"\)/);
  assert.doesNotMatch(runtime, /requestAnimationFrame|setTimeout|setInterval/);
});

test("cursor point inverts its backdrop above the peach hover lens", async () => {
  const css = await read("src/experiences/continuity.css");

  assert.match(css, /\.ref-cursor\s*\{[^}]*z-index:\s*2001/is);
  assert.match(css, /\.ref-cursor-ring\s*\{[^}]*z-index:\s*2000/is);
  assert.match(css, /mix-blend-mode:\s*difference/);
  assert.match(css, /backdrop-filter:\s*invert\(1\)\s+contrast\(1\.3\)/);
  assert.match(css, /\.ref-cursor-ring\[data-state="hover"\][\s\S]*background:\s*rgba\(249, 157, 127, \.085\)/);
});
