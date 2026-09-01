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

const compiler = await loadTsModule("src/graph/system-graph.ts");
const projectData = await loadTsModule("src/experiences/systems-projects.ts");

test("BDD: refactor preserves every approved Systems node position", () => {
  for (const project of projectData.systemsProjects) {
    const compiled = compiler.compileSystemGraph(project.graph);
    assert.deepEqual(
      compiled.nodes.map(({ id, x, y }) => ({ id, x, y })),
      project.graph.nodes.map(({ id, x, y }) => ({ id, x, y })),
      project.title,
    );
  }
});

test("BDD: refactor preserves every explicit approved edge path", () => {
  for (const project of projectData.systemsProjects) {
    const compiled = compiler.compileSystemGraph(project.graph);
    for (const edge of project.graph.edges.filter((item) => item.path)) {
      const rendered = compiled.edges.find(
        (item) => item.from === edge.from && item.to === edge.to,
      );
      assert.equal(rendered?.path, edge.path, `${project.title}: ${edge.from} -> ${edge.to}`);
    }
  }
});

test("BDD: automatic straight and orthogonal routes remain backward compatible", () => {
  const graph = {
    nodes: [
      { id: "a", label: "A", x: 10, y: 20, step: 0 },
      { id: "b", label: "B", x: 30, y: 20, step: 1 },
      { id: "c", label: "C", x: 50, y: 40, step: 2 },
    ],
    edges: [
      { from: "a", to: "b", step: 0 },
      { from: "b", to: "c", step: 1 },
    ],
  };

  const compiled = compiler.compileSystemGraph(graph);
  assert.equal(compiled.edges[0].path, "M 10 20 H 30");
  assert.equal(compiled.edges[1].path, "M 30 20 H 40 V 40 H 50");
});

test("BDD: edge labels keep the same midpoint placement", () => {
  const project = projectData.systemsProjects[0];
  const compiled = compiler.compileSystemGraph(project.graph);

  for (const edge of compiled.edges) {
    const from = project.graph.nodes.find((node) => node.id === edge.from);
    const to = project.graph.nodes.find((node) => node.id === edge.to);
    assert.ok(from && to);
    assert.equal(edge.labelX, (from.x + to.x) / 2);
    assert.equal(edge.labelY, (from.y + to.y) / 2);
  }
});

test("BDD: invalid graph references fail explicitly", () => {
  assert.throws(
    () => compiler.compileSystemGraph({
      nodes: [{ id: "a", label: "A", x: 10, y: 10, step: 0 }],
      edges: [{ from: "a", to: "missing", step: 0 }],
    }),
    /Unknown graph node/,
  );
});
