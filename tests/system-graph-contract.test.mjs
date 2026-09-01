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

const byCode = (code) => {
  const project = projectData.systemsProjects.find((item) => item.code === code);
  assert.ok(project, code);
  return project;
};

const expectedSpines = new Map([
  ["REACT—AI", ["request", "router", "reason", "tools", "verify", "reflect"]],
  ["DOC—AI", ["document", "segment", "rank", "extract", "validate", "evidence"]],
  ["NL→SQL", ["question", "intent", "schema", "planner", "sql"]],
  ["MCP—03", ["agent", "contract", "quote", "typed", "evidence"]],
  ["SEARCH", ["need", "attributes", "semantic", "vector", "rank", "explain"]],
  ["TRACE—RUST", ["ingest", "validate", "normalize", "sqlite", "viewer"]],
  ["VOICE—ACP", ["mic", "vad", "stt", "acp", "agent", "tts", "speaker"]],
]);

test("SDD: portfolio scene contract is directional and orthogonal-only", async () => {
  const model = await read("src/graph/model.ts");
  assert.doesNotMatch(model, /kind:\s*['"]curve['"]/);
  assert.match(model, /kind:\s*'flow'/);

  const renderer = await read("src/components/narrative/SystemDiagram.vue");
  assert.doesNotMatch(renderer, /path\.kind\s*===\s*["']curve["']/);
  assert.match(renderer, /marker-end/);
  assert.match(renderer, /edge\.role\s*===\s*["']spine["']/);
});

test("BDD: Systems are flow definitions with semantics only", async () => {
  const source = await read("src/experiences/systems-projects.ts");
  assert.doesNotMatch(source, /\b(?:x|y|path|step|accent)\s*:/);

  for (const project of projectData.systemsProjects) {
    assert.equal(project.graph.kind, "flow");
    assert.ok(project.graph.nodes.every((node) => !("x" in node) && !("y" in node) && !("step" in node)));
    assert.ok(project.graph.edges.every((edge) => !("path" in edge) && !("step" in edge)));
  }
});

test("BDD: every shipped System compiles as a directed orthogonal flow", () => {
  assert.equal(projectData.systemsProjects.length, 7);

  for (const project of projectData.systemsProjects) {
    for (const profile of ["desktop", "mobile"]) {
      const scene = compiler.compileSystemGraph(project.graph, profile);
      assert.equal(scene.kind, "flow", `${project.title} ${profile}`);
      assert.equal(scene.layout, profile === "desktop" ? "flow-lr" : "flow-tb");
      assert.equal(scene.nodes.length, project.graph.nodes.length, `${project.title} ${profile} nodes`);
      assert.equal(scene.edges.length, project.graph.edges.length, `${project.title} ${profile} edges`);
      assert.ok(scene.spine.length >= 2, `${project.title} requires a readable main spine`);

      for (const node of scene.nodes) {
        assert.ok(Number.isFinite(node.x) && Number.isFinite(node.y), `${project.title}: ${node.id}`);
        assert.ok(node.x - node.width / 2 >= 0 && node.x + node.width / 2 <= scene.width, `${project.title}: ${node.id} x`);
        assert.ok(node.y - node.height / 2 >= 0 && node.y + node.height / 2 <= scene.height, `${project.title}: ${node.id} y`);
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
        assert.ok(["spine", "branch", "feedback"].includes(edge.role), `${project.title}: edge role`);
      }
    }
  }
});

test("BDD: each System exposes a deterministic main narrative spine", () => {
  for (const [code, expected] of expectedSpines) {
    const scene = compiler.compileSystemGraph(byCode(code).graph, "desktop");
    assert.deepEqual(scene.spine, expected, code);

    const byId = new Map(scene.nodes.map((node) => [node.id, node]));
    const spineNodes = expected.map((id) => byId.get(id));
    assert.ok(spineNodes.every(Boolean), code);
    assert.ok(spineNodes.every((node, index) => index === 0 || spineNodes[index - 1].x < node.x), `${code}: spine must read left to right`);
    assert.ok(spineNodes.every((node) => node.y === spineNodes[0].y), `${code}: spine must stay on one visual axis`);

    const spineEdges = scene.edges.filter((edge) => edge.role === "spine");
    assert.equal(spineEdges.length, expected.length - 1, `${code}: spine edge count`);
  }
});

test("BDD: side branches leave the spine and remain visually secondary", () => {
  const expectations = new Map([
    ["DOC—AI", ["review"]],
    ["NL→SQL", ["policy"]],
    ["MCP—03", ["history", "signals"]],
    ["SEARCH", ["keyword", "lexical"]],
    ["TRACE—RUST", ["search", "export"]],
    ["VOICE—ACP", ["cancel"]],
  ]);

  for (const [code, branchIds] of expectations) {
    const scene = compiler.compileSystemGraph(byCode(code).graph, "desktop");
    const byId = new Map(scene.nodes.map((node) => [node.id, node]));
    const spineY = byId.get(scene.spine[0]).y;
    for (const id of branchIds) {
      assert.notEqual(byId.get(id).y, spineY, `${code}: ${id} must leave the main spine`);
    }
    assert.ok(scene.edges.some((edge) => edge.role === "branch"), `${code}: branch edges`);
  }
});

test("BDD: Reflective ReAct reads as a forward flow with external feedback", () => {
  const scene = compiler.compileSystemGraph(byCode("REACT—AI").graph, "desktop");
  assert.equal(scene.topology, "feedback");
  assert.deepEqual(scene.spine, ["request", "router", "reason", "tools", "verify", "reflect"]);

  const byId = new Map(scene.nodes.map((node) => [node.id, node]));
  assert.notEqual(byId.get("model").y, byId.get("verify").y, "LOCAL MODEL is a side branch");
  assert.deepEqual(
    scene.edges.filter((edge) => edge.role === "feedback").map((edge) => `${edge.from}->${edge.to}`).sort(),
    ["model->reason", "reflect->reason"],
  );
  assert.ok(scene.edges.filter((edge) => edge.role === "feedback").every((edge) => isOrthogonal(edge.path.points)));
});

test("BDD: input and output roles are present in the rendered flow", () => {
  for (const project of projectData.systemsProjects) {
    const scene = compiler.compileSystemGraph(project.graph, "desktop");
    assert.ok(scene.nodes.some((node) => node.role === "input"), `${project.title}: input`);
    assert.ok(scene.nodes.some((node) => node.role === "output"), `${project.title}: output`);
  }
});

test("BDD: responsive flow scenes preserve semantics but use different geometry", () => {
  for (const project of projectData.systemsProjects) {
    const desktop = compiler.compileSystemGraph(project.graph, "desktop");
    const mobile = compiler.compileSystemGraph(project.graph, "mobile");

    assert.deepEqual(desktop.spine, mobile.spine, project.title);
    assert.deepEqual(
      desktop.nodes.map((node) => node.id).sort(),
      mobile.nodes.map((node) => node.id).sort(),
      project.title,
    );
    assert.deepEqual(
      desktop.edges.map((edge) => `${edge.role}:${edge.from}->${edge.to}`).sort(),
      mobile.edges.map((edge) => `${edge.role}:${edge.from}->${edge.to}`).sort(),
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

test("BDD: invalid flow references fail explicitly", () => {
  assert.throws(
    () => compiler.compileSystemGraph({
      kind: "flow",
      nodes: [{ id: "a", label: "A" }],
      edges: [{ from: "a", to: "missing" }],
    }),
    /Unknown node/,
  );
});
