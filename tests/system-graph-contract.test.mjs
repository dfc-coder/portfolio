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
    source = source
      .replaceAll(`"${from}"`, `"${to}"`)
      .replaceAll(`'${from}'`, `'${to}'`);
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

const modelUrl = await transpileToDataUrl("src/graph/model.ts");
const routingUrl = await transpileToDataUrl(
  "src/graph/routing.ts",
  new Map([["./model", modelUrl]]),
);
const layoutUrl = await transpileToDataUrl(
  "src/graph/layout.ts",
  new Map([
    ["./model", modelUrl],
    ["./routing", routingUrl],
  ]),
);
const compilerUrl = await transpileToDataUrl(
  "src/graph/system-graph.ts",
  new Map([
    ["./layout", layoutUrl],
    ["./model", modelUrl],
  ]),
);
const projectDataUrl = await transpileToDataUrl("src/experiences/systems-projects.ts");

const compiler = await import(compilerUrl);
const projectData = await import(projectDataUrl);

const overlaps = (left, right) =>
  Math.abs(left.x - right.x) * 2 < left.width + right.width &&
  Math.abs(left.y - right.y) * 2 < left.height + right.height;

const isOrthogonal = (points) =>
  points.every((point, index) => {
    if (index === 0) return true;
    const previous = points[index - 1];
    return point.x === previous.x || point.y === previous.y;
  });

const bounds = (nodes) => ({
  minX: Math.min(...nodes.map((node) => node.x - node.width / 2)),
  maxX: Math.max(...nodes.map((node) => node.x + node.width / 2)),
});

test("SDD: portfolio scene contract is orthogonal-only", async () => {
  const model = await read("src/graph/model.ts");
  assert.doesNotMatch(model, /kind:\s*['"]curve['"]/);

  const renderer = await read("src/components/narrative/SystemDiagram.vue");
  assert.doesNotMatch(renderer, /path\.kind\s*===\s*["']curve["']/);
});

test("BDD: Systems data contains semantics only and no manual geometry or animation steps", async () => {
  const source = await read("src/experiences/systems-projects.ts");
  assert.doesNotMatch(source, /\b(?:x|y|path|step|accent)\s*:/);

  for (const project of projectData.systemsProjects) {
    assert.equal(project.graph.kind, "graph");
    assert.ok(project.graph.nodes.every((node) => !("x" in node) && !("y" in node) && !("step" in node)));
    assert.ok(project.graph.edges.every((edge) => !("path" in edge) && !("step" in edge)));
  }
});

test("BDD: every shipped System compiles with orthogonal paths on desktop and mobile", () => {
  assert.equal(projectData.systemsProjects.length, 7);

  for (const project of projectData.systemsProjects) {
    for (const profile of ["desktop", "mobile"]) {
      const scene = compiler.compileSystemGraph(project.graph, profile);
      assert.equal(scene.nodes.length, project.graph.nodes.length, `${project.title} ${profile} nodes`);
      assert.equal(scene.edges.length, project.graph.edges.length, `${project.title} ${profile} edges`);

      for (const node of scene.nodes) {
        assert.ok(Number.isFinite(node.x) && Number.isFinite(node.y), `${project.title}: ${node.id}`);
        assert.ok(node.x - node.width / 2 >= 0 && node.x + node.width / 2 <= scene.width, `${project.title}: ${node.id} x`);
      }

      for (let left = 0; left < scene.nodes.length; left += 1) {
        for (let right = left + 1; right < scene.nodes.length; right += 1) {
          assert.equal(overlaps(scene.nodes[left], scene.nodes[right]), false, `${project.title}: overlapping nodes`);
        }
      }

      for (const edge of scene.edges) {
        assert.equal(edge.path.kind, "polyline", `${project.title}: ${edge.from} -> ${edge.to} kind`);
        assert.ok(edge.path.points.length >= 2, `${project.title}: ${edge.from} -> ${edge.to}`);
        assert.ok(isOrthogonal(edge.path.points), `${project.title}: ${edge.from} -> ${edge.to} must be orthogonal`);
      }
    }
  }
});

test("BDD: desktop Systems use a wide left-to-right reading direction", () => {
  for (const project of projectData.systemsProjects) {
    const scene = compiler.compileSystemGraph(project.graph, "desktop");
    assert.notEqual(scene.layout, "layered-tb", `${project.title} must not collapse into a vertical tower`);
    const used = bounds(scene.nodes);
    assert.ok(used.maxX - used.minX >= scene.width * 0.6, `${project.title} uses too little horizontal space`);
  }
});

test("BDD: Reflective ReAct keeps its forward spine readable and feedback external", () => {
  const project = projectData.systemsProjects.find((item) => item.code === "REACT—AI");
  assert.ok(project);

  const scene = compiler.compileSystemGraph(project.graph, "desktop");
  assert.equal(scene.topology, "cycle");
  assert.equal(scene.layout, "cycle");

  const byId = new Map(scene.nodes.map((node) => [node.id, node]));
  const request = byId.get("request");
  const router = byId.get("router");
  const reason = byId.get("reason");
  const tools = byId.get("tools");
  const verify = byId.get("verify");
  const reflect = byId.get("reflect");
  const model = byId.get("model");
  assert.ok(request && router && reason && tools && verify && reflect && model);

  assert.ok(request.x < router.x && router.x < reason.x && reason.x < tools.x && tools.x < verify.x);
  assert.ok(verify.x < reflect.x && reflect.x === model.x, "return nodes should share the final rank");
  assert.equal(reason.y, tools.y);
  assert.equal(tools.y, verify.y);
  assert.ok(reflect.y < model.y, "feedback sources must remain visually distinct");

  assert.deepEqual(
    scene.edges.filter((edge) => edge.kind === "feedback").map((edge) => `${edge.from}->${edge.to}`).sort(),
    ["model->reason", "reflect->reason"],
  );
  assert.ok(scene.edges.every((edge) => isOrthogonal(edge.path.points)));
});

test("BDD: branch and join systems stay horizontally layered", () => {
  const expected = new Set(["DOC—AI", "NL→SQL", "MCP—03", "SEARCH", "VOICE—ACP"]);
  for (const code of expected) {
    const project = projectData.systemsProjects.find((item) => item.code === code);
    assert.ok(project, code);
    const scene = compiler.compileSystemGraph(project.graph, "desktop");
    assert.equal(scene.topology, "branch-join", code);
    assert.equal(scene.layout, "layered-lr", code);
  }
});

test("BDD: responsive scenes preserve semantics but use different geometry", () => {
  for (const project of projectData.systemsProjects) {
    const desktop = compiler.compileSystemGraph(project.graph, "desktop");
    const mobile = compiler.compileSystemGraph(project.graph, "mobile");

    assert.deepEqual(
      desktop.nodes.map((node) => node.id).sort(),
      mobile.nodes.map((node) => node.id).sort(),
      project.title,
    );
    assert.deepEqual(
      desktop.edges.map((edge) => `${edge.kind}:${edge.from}->${edge.to}`).sort(),
      mobile.edges.map((edge) => `${edge.kind}:${edge.from}->${edge.to}`).sort(),
      project.title,
    );
  }
});

test("BDD: layout is deterministic for every System and profile", () => {
  for (const project of projectData.systemsProjects) {
    for (const profile of ["desktop", "mobile"]) {
      assert.deepEqual(
        compiler.compileSystemGraph(project.graph, profile),
        compiler.compileSystemGraph(project.graph, profile),
        `${project.title} ${profile}`,
      );
    }
  }
});

test("BDD: invalid graph references fail explicitly", () => {
  assert.throws(
    () => compiler.compileSystemGraph({
      kind: "graph",
      nodes: [{ id: "a", label: "A" }],
      edges: [{ from: "a", to: "missing" }],
    }),
    /Unknown node/,
  );
});
