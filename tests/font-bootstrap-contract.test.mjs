import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("performance: fonts never block global application bootstrap", async () => {
  const main = await read("src/main.ts");

  const appMount = main.indexOf('createApp(App).mount("#app")');
  const scrollMount = main.indexOf("mountScrollSyncController()");
  const continuityMount = main.indexOf("mountVisualContinuity()");
  const lifecycleMount = main.indexOf("mountSceneLifecycle()");

  assert.ok(appMount >= 0);
  assert.ok(scrollMount > appMount);
  assert.ok(continuityMount > appMount);
  assert.ok(lifecycleMount > appMount);
  assert.doesNotMatch(main, /document\.fonts\.ready/);
  assert.doesNotMatch(main, /requestAnimationFrame/);
  assert.doesNotMatch(main, /creative-hero-pending/);
});

test("performance: Hero alone owns the font gate required by its intro", async () => {
  const hero = await read("src/experiences/hero.ts");

  assert.match(hero, /const HERO_INTRO_FONTS = \[/);
  assert.match(hero, /document\.fonts\.check\(font\)/);
  assert.match(hero, /document\.fonts\.load\(font\)/);
  assert.match(hero, /export const mountHeroExperience = async \(\) =>/);
  assert.match(hero, /classList\.add\("creative-hero-pending"\)/);
  assert.match(hero, /await waitForHeroIntroFonts\(\)/);
  assert.match(hero, /paused:\s*true/);
  assert.match(
    hero,
    /classList\.remove\("creative-hero-pending"\);[\s\S]*timeline\.play\(0\)/,
  );

  for (const font of [
    '800 1em "Syne"',
    '700 1em "Syne"',
    '500 1em "Instrument Sans"',
    '400 1em "Instrument Sans"',
    'italic 400 1em "Instrument Serif"',
  ]) {
    assert.ok(hero.includes(font), `Hero must explicitly own ${font}`);
  }
});
