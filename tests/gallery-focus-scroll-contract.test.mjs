import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("performance: Gallery focus never mutates the document scroll container", async () => {
  const gallery = await read("src/experiences/gallery.ts");

  assert.doesNotMatch(gallery, /document\.documentElement\.style\.overflow/);
  assert.doesNotMatch(gallery, /lockDocumentScroll|unlockDocumentScroll|rootOverflow/);
  assert.match(gallery, /focus\.addEventListener\("wheel", onFocusScrollIntent, \{ passive: false \}\)/);
  assert.match(gallery, /focus\.addEventListener\("touchmove", onFocusScrollIntent, \{ passive: false \}\)/);
  assert.match(gallery, /if \(isOpen\) event\.preventDefault\(\)/);
});

test("behavior: Gallery focus remains owned by the Gallery scene", async () => {
  const gallery = await read("src/experiences/gallery.ts");

  assert.match(gallery, /const galleryIsVisible = \(\) => galleryActive/);
  assert.match(gallery, /if \(!galleryIsVisible\(\)\) return;/);
  assert.match(gallery, /gallery\.classList\.add\("is-gallery-focus-open"\)/);
  assert.match(gallery, /focus\.classList\.add\("is-open"\)/);
  assert.match(gallery, /setPointerListenerActive\(galleryActive && !isOpen\)/);
});
