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

test("BDD: default compilation preserves every approved Systems node position", () => {
  for (const project of projectData.systemsProjects) {
    const compiled = compiler.compileSystemGraph(project.graph);
    assert.equal(compiled.layout, "fixed");
    assert.deepEqual(
      compiled.nodes.map(({ id, x, y }) => ({ id, x, y })),
      project.graph.nodes.map(({ id, x, y }) => ({ id, x, y })),
      project.title,
    );
  }
});

test("BDD: default compilation preserves every explicit approved edge path", () => {
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

test("BDD: fixed straight and orthogonal routes remain backward compatible", () => {
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

test("BDD: fixed edge labels keep the approved midpoint placement", () => {
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

test("BDD: automatic engine compiles every shipped system for desktop and mobile", () => {
  for (const project of projectData.systemsProjects) {
    for (const profile of ["desktop", "mobile"]) {
      const compiled = compiler.compileSystemGraph(project.graph, {
        mode: "auto",
        profile,
      });

      assert.equal(compiled.nodes.length, project.graph.nodes.length, `${project.title} ${profile}`);
      assert.equal(compiled.edges.length, project.graph.edges.length, `${project.title} ${profile}`);
      assert.ok(["layered-lr", "layered-tb"].includes(compiled.layout));

      for (const node of compiled.nodes) {
        assert.ok(node.x >= 0 && node.x <= compiled.width, `${project.title}: ${node.id} x`);
        assert.ok(node.y >= 0 && node.y <= compiled.height, `${project.title}: ${node.id} y`);
      }

      for (const edge of compiled.edges) {
        assert.ok(edge.path.startsWith("M "), `${project.title}: ${edge.from} -> ${edge.to}`);
      }
    }
  }
});

test("BDD: automatic layout is deterministic", () => {
  for (const project of projectData.systemsProjects) {
    const first = compiler.compileSystemGraph(project.graph, {
      mode: "auto",
      profile: "desktop",
    });
    const second = compiler.compileSystemGraph(project.graph, {
      mode: "auto",
      profile: "desktop",
    });
    assert.deepEqual(first, second, project.title);
  }
});

test("BDD: mobile automatic layout prefers vertical composition", () => {
  const project = projectData.systemsProjects.find((item) => item.code === "SEARCH");
  assert.ok(project);

  const desktop = compiler.compileSystemGraph(project.graph, {
    mode: "auto",
    profile: "desktop",
  });
  const mobile = compiler.compileSystemGraph(project.graph, {
    mode: "auto",
    profile: "mobile",
  });

  assert.equal(desktop.layout, "layered-lr");
  assert.equal(mobile.layout, "layered-tb");
  assert.notDeepEqual(
    desktop.nodes.map(({ id, x, y }) => ({ id, x, y })),
    mobile.nodes.map(({ id, x, y }) => ({ id, x, y })),
  );
});

test("BDD: backward narrative relations become feedback edges in automatic mode", () => {
  const project = projectData.systemsProjects.find((item) => item.code === "REACT—AI");
  assert.ok(project);

  const compiled = compiler.compileSystemGraph(project.graph, {
    mode: "auto",
    profile: "desktop",
  });

  const feedback = compiled.edges.filter((edge) => edge.feedback);
  assert.deepEqual(
    feedback.map((edge) => `${edge.from}->${edge.to}`).sort(),
    ["model->reason", "reflect->reason"],
  );
});

test("BDD: invalid graph references fail explicitly in both modes", () => {
  const graph = {
    nodes: [{ id: "a", label: "A", x: 10, y: 10, step: 0 }],
    edges: [{ from: "a", to: "missing", step: 0 }],
  };

  assert.throws(() => compiler.compileSystemGraph(graph), /Unknown graph node/);
  assert.throws(
    () => compiler.compileSystemGraph(graph, { mode: "auto" }),
    /Unknown graph node/,
  );
});
