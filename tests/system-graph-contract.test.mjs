import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = process.cwd();
const read = (path) => readFile(resolve(root, path), "utf8");

const transpileToDataUrl = async (relativePath, replacements = new Map()) => {
  let source = await read(relativePath);
  for (const [from, to] of replacements) {
    source = source.replaceAll(`"${from}"`, `"${to}"`);
  }

  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: relativePath,
  });
  return `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
};

const diagramCoreUrl = await transpileToDataUrl("src/graph/diagram-core.ts");
const compilerUrl = await transpileToDataUrl(
  "src/graph/system-graph.ts",
  new Map([["./diagram-core", diagramCoreUrl]]),
);
const projectDataUrl = await transpileToDataUrl("src/experiences/systems-projects.ts");

const compiler = await import(compilerUrl);
const projectData = await import(projectDataUrl);

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

test("BDD: automatic engine compiles every shipped system for desktop and mobile", () => {
  const allowed = ["serpentine", "layered-lr", "layered-tb", "fanout"];

  for (const project of projectData.systemsProjects) {
    for (const profile of ["desktop", "mobile"]) {
      const compiled = compiler.compileSystemGraph(project.graph, { mode: "auto", profile });
      assert.equal(compiled.nodes.length, project.graph.nodes.length, `${project.title} ${profile}`);
      assert.equal(compiled.edges.length, project.graph.edges.length, `${project.title} ${profile}`);
      assert.ok(allowed.includes(compiled.layout), `${project.title}: ${compiled.layout}`);
      assert.equal(compiled.width, profile === "desktop" ? 720 : 336);

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
    const first = compiler.compileSystemGraph(project.graph, { mode: "auto", profile: "desktop" });
    const second = compiler.compileSystemGraph(project.graph, { mode: "auto", profile: "desktop" });
    assert.deepEqual(first, second, project.title);
  }
});

test("BDD: ReAct follows the blog layered composition and keeps return edges outside the main flow", () => {
  const project = projectData.systemsProjects.find((item) => item.code === "REACT—AI");
  assert.ok(project);

  const compiled = compiler.compileSystemGraph(project.graph, { mode: "auto", profile: "desktop" });
  assert.equal(compiled.layout, "layered-tb");
  assert.equal(compiled.width, 720);

  const request = compiled.nodes.find((node) => node.id === "request");
  const router = compiled.nodes.find((node) => node.id === "router");
  const reason = compiled.nodes.find((node) => node.id === "reason");
  const tools = compiled.nodes.find((node) => node.id === "tools");
  const verify = compiled.nodes.find((node) => node.id === "verify");
  const reflect = compiled.nodes.find((node) => node.id === "reflect");
  const model = compiled.nodes.find((node) => node.id === "model");
  assert.ok(request && router && reason && tools && verify && reflect && model);

  assert.ok(request.y < router.y);
  assert.ok(router.y < reason.y);
  assert.ok(reason.y < tools.y);
  assert.ok(tools.y < verify.y);
  assert.equal(reflect.y, model.y);
  assert.ok(verify.y < reflect.y);

  const feedback = compiled.edges.filter((edge) => edge.feedback);
  assert.deepEqual(
    feedback.map((edge) => `${edge.from}->${edge.to}`).sort(),
    ["model->reason", "reflect->reason"],
  );
  assert.ok(feedback.every((edge) => edge.labelX < reason.x));
});

test("BDD: branching systems use blog-style layered TB when six ranks do not fit LR", () => {
  const project = projectData.systemsProjects.find((item) => item.code === "SEARCH");
  assert.ok(project);

  const desktop = compiler.compileSystemGraph(project.graph, { mode: "auto", profile: "desktop" });
  const mobile = compiler.compileSystemGraph(project.graph, { mode: "auto", profile: "mobile" });
  assert.equal(desktop.layout, "layered-tb");
  assert.equal(mobile.layout, "layered-tb");
  assert.equal(desktop.width, 720);
  assert.equal(mobile.width, 336);
  assert.notDeepEqual(
    desktop.nodes.map(({ id, x, y }) => ({ id, x, y })),
    mobile.nodes.map(({ id, x, y }) => ({ id, x, y })),
  );
});

test("BDD: compact three-rank branching graph may use layered LR on desktop", () => {
  const graph = {
    nodes: [
      { id: "in", label: "IN", x: 0, y: 0, step: 0 },
      { id: "left", label: "LEFT", x: 0, y: 0, step: 1 },
      { id: "right", label: "RIGHT", x: 0, y: 0, step: 2 },
      { id: "out", label: "OUT", x: 0, y: 0, step: 3 },
    ],
    edges: [
      { from: "in", to: "left", step: 0 },
      { from: "in", to: "right", step: 1 },
      { from: "left", to: "out", step: 2 },
      { from: "right", to: "out", step: 3 },
    ],
  };

  const compiled = compiler.compileSystemGraph(graph, { mode: "auto", profile: "desktop" });
  assert.equal(compiled.layout, "layered-lr");
});

test("BDD: simple chains use the blog serpentine layout instead of a horizontal strip", () => {
  const graph = {
    nodes: Array.from({ length: 7 }, (_, index) => ({
      id: `n${index}`,
      label: `N${index}`,
      x: index * 10,
      y: 20,
      step: index,
    })),
    edges: Array.from({ length: 6 }, (_, index) => ({
      from: `n${index}`,
      to: `n${index + 1}`,
      step: index,
    })),
  };

  const compiled = compiler.compileSystemGraph(graph, { mode: "auto", profile: "desktop" });
  assert.equal(compiled.layout, "serpentine");
  assert.ok(new Set(compiled.nodes.map((node) => node.y)).size > 1);
});

test("BDD: invalid graph references fail explicitly in both modes", () => {
  const graph = {
    nodes: [{ id: "a", label: "A", x: 10, y: 10, step: 0 }],
    edges: [{ from: "a", to: "missing", step: 0 }],
  };

  assert.throws(() => compiler.compileSystemGraph(graph), /Unknown graph node/);
  assert.throws(() => compiler.compileSystemGraph(graph, { mode: "auto" }), /Unknown graph node/);
});
