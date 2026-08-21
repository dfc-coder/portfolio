import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

const forbiddenOwnership = /\b(position|inset|top|right|bottom|left|z-index|transform|translate|opacity|animation|transition|filter)\s*:/i;

/* --------------------------------------------------------------------------
   DESIGN SYSTEM V2 — golden-baseline guardrails.

   The design system may define semantic tokens and opt-in classes, but it may
   not take layout/motion ownership from an approved chapter. Migration happens
   one primitive at a time after visual parity is demonstrated.
   -------------------------------------------------------------------------- */

test("SDD: the token layer defines the shared semantic vocabulary", async () => {
  const css = await read("src/design-system/tokens.css");
  for (const token of [
    "--ds-paper",
    "--ds-body",
    "--ds-muted",
    "--ds-accent",
    "--ds-signal-rule",
    "--ds-register-node",
    "--ds-statement-size",
  ]) {
    assert.match(css, new RegExp(token.replaceAll("-", "\\-")));
  }
});

test("TDD regression: shared design-system CSS never targets chapter implementation selectors", async () => {
  for (const file of [
    "src/design-system/primitives.css",
    "src/design-system/templates.css",
  ]) {
    const css = await read(file);
    assert.doesNotMatch(css, /\.(trajectory|systems|ref)-/i, `${file} must stay opt-in`);
    assert.match(css, /\.ds-/i, `${file} must expose semantic ds-* classes`);
  }
});

test("TDD regression: shared primitives cannot own layout, visibility or motion", async () => {
  for (const file of [
    "src/design-system/primitives.css",
    "src/design-system/templates.css",
  ]) {
    const css = await read(file);
    assert.doesNotMatch(css, forbiddenOwnership, `${file} attempted to own chapter geometry/motion`);
    assert.doesNotMatch(css, /!important/i, `${file} must never win by force`);
  }
});

test("TDD: the design system has no runtime animation owner", async () => {
  await assert.rejects(access(resolve(root, "src/design-system/runtime.ts")));
  const main = await read("src/main.ts");
  assert.doesNotMatch(main, /mountDesignSystemRuntime|design-system\/runtime/);
  assert.match(main, /mountVisualContinuity\(\)/);
});

test("TDD: static design-system layers load only after approved chapter styles", async () => {
  const main = await read("src/main.ts");
  const systems = main.indexOf('import "./systems-experience-v5.css"');
  const tokens = main.indexOf('import "./design-system/tokens.css"');
  const primitives = main.indexOf('import "./design-system/primitives.css"');
  const templates = main.indexOf('import "./design-system/templates.css"');

  assert.ok(systems >= 0 && systems < tokens && tokens < primitives && primitives < templates);
});

test("BDD golden baseline: Record and Evidence keep the approved shared chapter grammar", async () => {
  const css = await read("src/visual-continuity-v3.css");
  assert.match(css, /\.trajectory-intro,\s*\n\.systems-intro\s*\{/);
  assert.match(css, /\.trajectory-intro__kicker,\s*\n\.systems-intro__kicker\s*\{/);
  assert.match(css, /\.trajectory-intro p,\s*\n\.systems-intro p\s*\{/);
  assert.match(css, /font-size:\s*clamp\(2\.35rem, 3\.55vw, 4\.15rem\)/);
});

test("BDD golden baseline: pointer field and rail continuity remain owned by the approved continuity layer", async () => {
  const css = await read("src/visual-continuity-v3.css");
  assert.match(css, /\.ref-global-pointer-light\s*\{/);
  assert.match(css, /ellipse 54rem 38rem/);
  assert.match(css, /\.trajectory-axis,\s*\n\.systems-axis\s*\{/);
});

test("TDD regression: Trajectory keeps focus-driven title hierarchy", async () => {
  const css = await read("src/trajectory-experience.css");
  assert.match(
    css,
    /\.trajectory-entry h2\s*\{[^}]*color:\s*rgba\(238, 234, 226, calc\(\.10 \+ var\(--entry-focus\) \* \.90\)\)/is,
  );

  const primitives = await read("src/design-system/primitives.css");
  const templates = await read("src/design-system/templates.css");
  assert.doesNotMatch(primitives, /trajectory-entry h2/i);
  assert.doesNotMatch(templates, /trajectory-entry h2/i);
});

test("TDD regression: Trajectory director remains the owner of year movement", async () => {
  const director = await read("src/trajectory-experience.ts");
  assert.match(director, /element\.style\.transform = `translate3d\(0, calc\(-50% \+ \$\{y\.toFixed\(3\)\}vh\), 0\)`/);

  for (const file of [
    "src/design-system/primitives.css",
    "src/design-system/templates.css",
  ]) {
    const css = await read(file);
    assert.doesNotMatch(css, /trajectory-year/i);
  }
});
