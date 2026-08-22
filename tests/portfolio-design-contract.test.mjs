import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");
const absent = (path) => assert.rejects(access(resolve(root, path)));

const removedFrontendLayers = [
  "src/styles/cinematic.css",
  "src/styles/cinematic-motion.css",
  "src/styles/typography.css",
  "src/experiences/trajectory-bridge.css",
  "src/experiences/systems-motion.css",
  "src/design-system/tokens.css",
  "src/design-system/primitives.css",
  "src/design-system/templates.css",
  "pnpm-lock.yaml",
];

const removedBackendFacades = [
  "server/app/calendar_gateway.py",
  "server/app/llama_client.py",
  "server/app/policies.py",
  "server/app/profile.py",
  "server/app/session.py",
  "server/app/settings.py",
  "server/app/slot_service.py",
  "server/app/api/schemas.py",
  "server/app/api/sse.py",
];

test("architecture: obsolete frontend layers are removed instead of overridden", async () => {
  await Promise.all(removedFrontendLayers.map(absent));
  await access(resolve(root, "src/styles/theme.css"));
  await access(resolve(root, "src/styles/shell.css"));
});

test("architecture: main loads one predictable CSS ownership chain", async () => {
  const main = await read("src/main.ts");
  const ordered = [
    'import "./styles/theme.css"',
    'import "./styles/base.css"',
    'import "./styles/shell.css"',
    'import "./experiences/scroll.css"',
    'import "./components/agent/agent.css"',
    'import "./experiences/hero.css"',
    'import "./experiences/trajectory.css"',
    'import "./experiences/systems.css"',
    'import "./experiences/continuity.css"',
    'import "./styles/chapter-bridges.css"',
    'import "./experiences/gallery.css"',
  ];

  let previous = -1;
  for (const statement of ordered) {
    const index = main.indexOf(statement);
    assert.ok(index > previous, `${statement} must be present and ordered`);
    previous = index;
  }

  assert.doesNotMatch(main, /design-system|cinematic|typography|systems-motion|trajectory-bridge/);
});

test("architecture: theme is the only global semantic vocabulary", async () => {
  const theme = await read("src/styles/theme.css");
  const base = await read("src/styles/base.css");
  const shell = await read("src/styles/shell.css");

  for (const token of ["--color-ink", "--color-paper", "--color-accent", "--font-sans", "--font-mono", "--t-display"]) {
    assert.match(theme, new RegExp(token.replaceAll("-", "\\-")));
  }
  assert.doesNotMatch(base, /:root\s*\{/);
  assert.doesNotMatch(shell, /:root\s*\{/);
  assert.doesNotMatch(theme, /--ds-/);
});

test("architecture: continuity owns only cross-chapter pointer interaction", async () => {
  const css = await read("src/experiences/continuity.css");
  const runtime = await read("src/experiences/continuity.ts");
  const component = await read("src/components/PortfolioExperience.vue");

  assert.match(css, /\.ref-global-pointer-light\s*\{/);
  assert.match(css, /\.ref-cursor/);
  assert.doesNotMatch(css, /\.(trajectory|systems)-/);
  assert.match(runtime, /addEventListener\("pointermove"/);
  assert.match(runtime, /requestAnimationFrame\(render\)/);
  assert.doesNotMatch(component, /pointermove|cursorFrame|requestAnimationFrame|ref-cursor/);
});

test("architecture: PortfolioExperience is structure, not an animation director", async () => {
  const component = await read("src/components/PortfolioExperience.vue");

  assert.doesNotMatch(component, /ScrollTrigger|Flip|requestAnimationFrame|addEventListener/);
  assert.doesNotMatch(component, /ref-career-nav|ref-career-copy|ref-system-stack|ref-system-nav|ref-system-copy/);
  assert.doesNotMatch(component, /ref-filmstrip|ref-art-caption|ref-art-index/);
  assert.match(component, /<article class="ref-scene ref-scene--career"\s*\/>/);
  assert.match(component, /<article class="ref-scene ref-scene--systems"\s*\/>/);
});

test("architecture: physical scroll has one runtime owner", async () => {
  const component = await read("src/components/PortfolioExperience.vue");
  const scroll = await read("src/experiences/scroll.ts");
  const gallery = await read("src/experiences/gallery.ts");

  assert.doesNotMatch(component, /ScrollTrigger|addEventListener\("wheel"/);
  assert.doesNotMatch(gallery, /addEventListener\("wheel"|scrollToNode|WHEEL_EXIT_LOCK/);
  assert.match(scroll, /ScrollTrigger\.create/);
  assert.match(scroll, /mapPhysicalProgressToVirtualProgress/);
});

test("architecture: Systems motion is owned by systems.css", async () => {
  const systems = await read("src/experiences/systems.css");
  const bridges = await read("src/styles/chapter-bridges.css");

  assert.match(systems, /--graph-build/);
  assert.match(systems, /--title-presence/);
  assert.match(systems, /\.systems-project__detail::before/);
  assert.doesNotMatch(systems, /ref-scene--chapter\[data-chapter="agent"\]/);
  assert.match(bridges, /data-chapter="agent"/);
});

test("architecture: chapter handoffs have one shared owner", async () => {
  const bridges = await read("src/styles/chapter-bridges.css");
  assert.match(bridges, /trajectory-axis-reveal/);
  assert.match(bridges, /systems-gallery-handoff/);
  assert.match(bridges, /A NOTE ON ORIGIN/);
  assert.match(bridges, /THE INTERFACE/);
});

test("architecture: browser Agent has no fake corpus or fallback provider", async () => {
  const runtime = await read("src/components/agent/useAgentRuntime.ts");
  const os = await read("src/components/agent/AgentOS.vue");

  assert.doesNotMatch(runtime, /localProvider|CORPUS|CorpusEntry|chunkify|Math\.random/);
  assert.match(runtime, /useAgentRuntime\(provider: AgentProvider/);
  assert.match(os, /businessAgentProvider/);
});

test("architecture: Agent implementation remains colocated", async () => {
  for (const path of [
    "src/components/agent/AgentOS.vue",
    "src/components/agent/AsciiFluidCanvas.vue",
    "src/components/agent/asciiField.ts",
    "src/components/agent/businessAgentProvider.ts",
    "src/components/agent/useAgentRuntime.ts",
    "src/components/agent/agent.css",
  ]) {
    await access(resolve(root, path));
  }
});

test("architecture: backend compatibility facades and one-function API files are gone", async () => {
  await Promise.all(removedBackendFacades.map(absent));
  const router = await read("server/app/api/router.py");
  assert.match(router, /class ChatRequest\(BaseModel\)/);
  assert.match(router, /def encode_sse\(/);
});
