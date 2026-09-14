import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

test("architecture: chapter handoffs overlap outgoing and incoming runtimes", async () => {
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");

  assert.match(lifecycle, /const chapterRuntimePairs/);
  assert.match(lifecycle, /scenes:\s*\["hero",\s*"career"\]/);
  assert.match(lifecycle, /scenes:\s*\["career",\s*"systems"\]/);
  assert.match(lifecycle, /scenes:\s*\["systems",\s*"gallery"\]/);
  assert.match(lifecycle, /scenes:\s*\["gallery",\s*"agent"\]/);
  assert.match(lifecycle, /runtimeScenesForState/);
  assert.match(lifecycle, /new Map<RuntimeScene, Cleanup>/);
  assert.match(lifecycle, /new Map<RuntimeScene, Promise<void>>/);
});

test("architecture: outgoing cleanup waits until all desired runtimes are mounted", async () => {
  const lifecycle = await read("src/experiences/scene-lifecycle.ts");

  assert.match(
    lifecycle,
    /if \(\[\.\.\.desiredRuntimes\]\.some\(\(scene\) => !mountedRuntimes\.has\(scene\)\)\) return;/,
  );
  assert.match(lifecycle, /desiredRuntimes\.forEach\(\(scene\) => \{[\s\S]*ensureMounted\(scene\)/);
  assert.match(lifecycle, /if \(disposed \|\| !desiredRuntimes\.has\(scene\)\)/);
  assert.match(lifecycle, /cleanupObsoleteRuntimes\(version\)/);
  assert.doesNotMatch(lifecycle, /cleanupActive/);
});

test("architecture: Agent UI and Three canvas share the chapter handoff", async () => {
  const portfolio = await read("src/components/PortfolioExperience.vue");
  const graphicsCss = await read("src/graphics/stage-graphics.css");

  assert.match(portfolio, /runtimeScenesForState\(narrativeRuntime\.getState\(\)\)\.includes\("agent"\)/);
  assert.match(portfolio, /runtimeScenesForState\(state\)\.includes\("agent"\)/);
  assert.match(portfolio, /<AgentOS v-if="agentActive" \/>/);
  assert.match(graphicsCss, /opacity:\s*var\(--agent,\s*0\)/);
});

test("architecture: scroll variables are the final narrative visibility owner", async () => {
  const main = await read("src/main.ts");
  const visibility = await read("src/styles/narrative-visibility.css");

  const ownershipImport = 'import "./styles/narrative-visibility.css";';
  assert.ok(main.includes(ownershipImport));
  assert.ok(main.indexOf(ownershipImport) > main.indexOf('import "./styles/mobile-systems-layout.css";'));

  assert.match(
    visibility,
    /\.ref-stage > \.ref-scene--career\s*\{[\s\S]*opacity:\s*max\(var\(--career,\s*0\),\s*var\(--chapter-career,\s*0\)\)\s*!important/,
  );
  assert.match(visibility, /\.ref-stage > \.ref-scene--systems,/);
  assert.match(visibility, /opacity:\s*var\(--systems,\s*0\)\s*!important/);
  assert.match(
    visibility,
    /\.ref-scene--chapter\[data-chapter="systems"\][\s\S]*opacity:\s*var\(--chapter-systems,\s*0\)\s*!important/,
  );
  assert.match(visibility, /\.ref-scene--systems \.systems-intro\s*\{[\s\S]*display:\s*none\s*!important/);
  assert.match(visibility, /\.systems-project__identity[\s\S]*opacity:\s*var\(--title-focus,\s*0\)\s*!important/);
  assert.match(visibility, /\.systems-project__architecture[\s\S]*opacity:\s*var\(--graph-focus,\s*0\)\s*!important/);
  assert.match(visibility, /data-chapter="gallery"/);
  assert.match(visibility, /opacity:\s*var\(--chapter-gallery,\s*0\)\s*!important/);
});

test("performance: feature style variables stay on local owners", async () => {
  const scroll = await read("src/experiences/scroll.ts");
  const trajectory = await read("src/experiences/trajectory.ts");
  const systems = await read("src/experiences/systems.ts");
  const galleryTransition = await read("src/experiences/gallery-transition.ts");
  const galleryTransitionCss = await read("src/experiences/gallery-transition.css");
  const bridges = await read("src/styles/chapter-bridges.css");

  assert.doesNotMatch(trajectory, /stage\.style\.setProperty\("--trajectory-/);
  assert.match(trajectory, /root\.style\.setProperty\("--trajectory-timeline-progress"/);
  assert.match(trajectory, /root\.style\.setProperty\("--trajectory-content"/);
  assert.match(trajectory, /heroScene\.style\.setProperty\("--trajectory-hero-exit"/);
  assert.match(trajectory, /heroScene\.style\.setProperty\([\s\S]*"--trajectory-cue-handoff-opacity"/);

  assert.doesNotMatch(systems, /stage\.style\.setProperty\("--systems-/);
  assert.match(systems, /root\.style\.setProperty\("--systems-progress"/);
  assert.match(systems, /root\.style\.setProperty\("--systems-content"/);
  assert.match(systems, /root\.style\.setProperty\("--systems-axis-reveal"/);

  assert.doesNotMatch(galleryTransition, /stage\.style\.|stage\.dataset\.galleryMotion/);
  assert.match(galleryTransition, /gallery\.style\.setProperty\("--gallery-motion-opacity"/);
  assert.match(galleryTransition, /gallery\.dataset\.galleryMotion/);
  assert.match(
    galleryTransitionCss,
    /\.ref-scene--gallery\.ref-gallery-gel-ready\[data-gallery-motion="true"\]/,
  );

  assert.match(bridges, /--trajectory-cue-handoff-opacity/);
  assert.doesNotMatch(bridges, /--systems-gallery-handoff/);

  assert.match(scroll, /let previousHero = ""/);
  assert.match(scroll, /if \(nextHero !== previousHero\)/);
  assert.match(scroll, /let previousChapterGallery = ""/);
  assert.match(scroll, /if \(nextChapterGallery !== previousChapterGallery\)/);
});

test("performance: pointermove consumers are owned by active scenes", async () => {
  const [hero, systems, gallery, graphics, continuity] = await Promise.all([
    read("src/experiences/hero.ts"),
    read("src/experiences/systems.ts"),
    read("src/experiences/gallery.ts"),
    read("src/graphics/stageGraphics.ts"),
    read("src/experiences/continuity.ts"),
  ]);

  assert.match(hero, /narrativeRuntime\.subscribe\(syncPointerOwnership\)/);
  assert.match(hero, /setPointerActive\(state\.scene === "hero"\)/);
  assert.match(hero, /new ResizeObserver\(measure\)/);
  const heroPointer =
    hero.match(/const onHeroPointerMove = \(event: PointerEvent\) => \{[\s\S]*?\n  \};/)?.[0] ?? "";
  assert.doesNotMatch(heroPointer, /getBoundingClientRect/);

  assert.match(systems, /setPointerListenerActive\(runtimeState\.scene === "systems"\)/);
  assert.match(
    systems,
    /if \(active\) \{[\s\S]*addEventListener\("pointermove", onPointerMove/,
  );
  assert.match(systems, /pointerViewportWidth = Math\.max\(1, innerWidth\)/);
  assert.match(systems, /pointerViewportHeight = Math\.max\(1, innerHeight\)/);

  assert.match(gallery, /narrativeRuntime\.subscribe\(syncNarrative\)/);
  assert.match(gallery, /setPointerListenerActive\(galleryActive && !isOpen\)/);
  const galleryPointer =
    gallery.match(/const onPointerMove = \(event: PointerEvent\) => \{[\s\S]*?\n  \};/)?.[0] ?? "";
  assert.doesNotMatch(galleryPointer, /getBoundingClientRect|measureCards/);
  assert.match(gallery, /if \(active\) \{[\s\S]*measureCards\(\);[\s\S]*addEventListener\("pointermove"/);

  assert.match(graphics, /narrativeRuntime\.subscribe\(this\.onNarrative\)/);
  assert.match(graphics, /this\.setPointerActive\(state\.scene === "agent"\)/);
  assert.match(graphics, /const rect = this\.stageRect/);
  const graphicsPointer =
    graphics.match(/private onPointerMove = \(event: PointerEvent\): void => \{[\s\S]*?\n  \};/)?.[0] ?? "";
  assert.doesNotMatch(graphicsPointer, /getBoundingClientRect/);

  assert.match(continuity, /addEventListener\("pointermove", onPointerMove/);
});
