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

const graphCore = await loadTsModule("src/graph/system-graph.ts");
const projectData = await loadTsModule("src/experiences/systems-projects.ts");

test("BDD: every System keeps the same semantics in desktop and mobile layouts", () => {
  for (const project of projectData.systemsProjects) {
    const desktop = graphCore.compileSystemGraph(project.graph, "desktop");
    const mobile = graphCore.compileSystemGraph(project.graph, "mobile");

    assert.equal(desktop.nodes.length, project.graph.nodes.length);
    assert.equal(desktop.edges.length, project.graph.edges.length);
    assert.equal(mobile.nodes.length, project.graph.nodes.length);
    assert.equal(mobile.edges.length, project.graph.edges.length);
    assert.deepEqual(
      desktop.edges.map(({ from, to, label, kind }) => ({ from, to, label, kind })),
      mobile.edges.map(({ from, to, label, kind }) => ({ from, to, label, kind })),
    );
  }
});

test("BDD: compiled System diagrams stay inside the canonical viewBox", () => {
  for (const project of projectData.systemsProjects) {
    for (const profile of ["desktop", "mobile"]) {
      const compiled = graphCore.compileSystemGraph(project.graph, profile);
      assert.equal(compiled.width, 100);
      assert.equal(compiled.height, 64);
      for (const node of compiled.nodes) {
        assert.ok(node.x >= 0 && node.x <= compiled.width, `${project.id}/${profile}/${node.id} x`);
        assert.ok(node.y >= 0 && node.y <= compiled.height, `${project.id}/${profile}/${node.id} y`);
      }
    }
  }
});

test("BDD: mobile reorganizes complex architecture instead of scaling desktop coordinates", () => {
  const project = projectData.systemsProjects[0];
  const desktop = graphCore.compileSystemGraph(project.graph, "desktop");
  const mobile = graphCore.compileSystemGraph(project.graph, "mobile");
  const desktopPositions = desktop.nodes.map(({ id, x, y }) => `${id}:${x},${y}`).join("|");
  const mobilePositions = mobile.nodes.map(({ id, x, y }) => `${id}:${x},${y}`).join("|");

  assert.notEqual(mobilePositions, desktopPositions);
});

test("BDD: ReAct return relationships are explicit feedback edges", () => {
  const react = projectData.systemsProjects[0];
  const feedback = react.graph.edges.filter((edge) => edge.kind === "feedback");

  assert.deepEqual(
    feedback.map((edge) => `${edge.from}>${edge.to}`),
    ["reflect>reason", "model>reason"],
  );
  assert.doesNotThrow(() => graphCore.compileSystemGraph(react.graph, "desktop"));
  assert.doesNotThrow(() => graphCore.compileSystemGraph(react.graph, "mobile"));
});

test("SDD: System project data describes topology, not drawing coordinates", async () => {
  const source = await read("src/experiences/systems-projects.ts");
  assert.doesNotMatch(source, /\b[xy]:\s*\d/);
  assert.doesNotMatch(source, /\bpath:\s*["']/);
});

test("SDD: all five Systems remain semantically distinct", () => {
  const signatures = projectData.systemsProjects.map((project) => {
    const nodes = project.graph.nodes.map((node) => node.id).join("|");
    const edges = project.graph.edges
      .map((edge) => `${edge.from}>${edge.to}:${edge.kind ?? "default"}`)
      .join("|");
    return `${nodes}::${edges}`;
  });

  assert.equal(new Set(signatures).size, projectData.systemsProjects.length);
});
