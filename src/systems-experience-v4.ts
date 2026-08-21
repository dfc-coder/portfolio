type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  step: number;
  accent?: boolean;
};

type GraphEdge = {
  from: string;
  to: string;
  step: number;
  label?: string;
  path?: string;
};

type SystemProject = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
};

const projects: SystemProject[] = [
  {
    id: "00",
    code: "REACT—AI",
    field: "AGENTIC AI / LOCAL-FIRST",
    title: "Reflective ReAct Agent",
    premise:
      "A general-purpose local assistant can reason, use tools and recover from execution failures without being tied to a specific domain.",
    detail:
      "A bounded ReAct loop combines injected tools, deterministic verification and triggered reflection. Local inference runs on Qwen through llama.cpp, with private retrieval and specialised embedding/reranking, while an AWS-compatible runtime provides the infrastructure needed to test the same agent as a real system.",
    stack: [
      "Python",
      "Qwen3.5 2B",
      "ReAct + Reflection",
      "llama.cpp",
      "OpenVINO",
      "LangChain",
      "AWS CDK / Lambda",
      "S3 Vectors",
      "Podman / Floci",
    ],
    outcome: "General-purpose local agent · controlled autonomous execution",
    graph: {
      nodes: [
        { id: "request", label: "REQUEST", x: 6, y: 32, step: 0 },
        { id: "router", label: "ROUTER", x: 20, y: 32, step: 1 },
        { id: "reason", label: "REASON", x: 42, y: 18, step: 2, accent: true },
        { id: "tools", label: "TOOLS", x: 64, y: 18, step: 3 },
        { id: "verify", label: "VERIFY", x: 64, y: 46, step: 4 },
        { id: "reflect", label: "REFLECT", x: 42, y: 46, step: 5, accent: true },
        { id: "model", label: "LOCAL MODEL", x: 88, y: 32, step: 6 },
      ],
      edges: [
        { from: "request", to: "router", step: 0 },
        { from: "router", to: "reason", step: 1, label: "PLAN", path: "M 20 32 H 31 V 18 H 42" },
        { from: "reason", to: "tools", step: 2 },
        { from: "tools", to: "verify", step: 3, label: "RESULT", path: "M 64 18 V 46" },
        { from: "verify", to: "reflect", step: 4 },
        { from: "reflect", to: "reason", step: 5, label: "RETRY", path: "M 42 46 V 18" },
        { from: "verify", to: "model", step: 6, path: "M 64 46 H 76 V 32 H 88" },
        { from: "model", to: "reason", step: 7, path: "M 88 32 H 78 V 9 H 42 V 18" },
      ],
    },
  },
  {
    id: "01",
    code: "DOC—AI",
    field: "PRIVATE AI / BANKING",
    title: "Secure Document Extractor",
    premise:
      "Sensitive documents become structured financial data without leaving isolated infrastructure.",
    detail:
      "PDF and image documents are segmented, ranked by field and processed by local models. Typed validation and evidence links keep uncertainty reviewable instead of hiding it behind a confident answer.",
    stack: ["Python", "FastAPI", "Docling", "Local LLM", "Redis"],
    outcome: "Private by design · evidence-linked output",
    graph: {
      nodes: [
        { id: "document", label: "DOCUMENT", x: 7, y: 18, step: 0 },
        { id: "segment", label: "SEGMENT", x: 25, y: 18, step: 1 },
        { id: "rank", label: "RANK", x: 43, y: 18, step: 2, accent: true },
        { id: "extract", label: "EXTRACT", x: 61, y: 18, step: 3 },
        { id: "validate", label: "VALIDATE", x: 79, y: 18, step: 4 },
        { id: "review", label: "REVIEW", x: 43, y: 49, step: 5 },
        { id: "evidence", label: "EVIDENCE", x: 82, y: 49, step: 6, accent: true },
      ],
      edges: [
        { from: "document", to: "segment", step: 0 },
        { from: "segment", to: "rank", step: 1 },
        { from: "rank", to: "extract", step: 2, label: "FIELD" },
        { from: "extract", to: "validate", step: 3 },
        { from: "segment", to: "review", step: 4, path: "M 25 18 V 49 H 43" },
        { from: "review", to: "extract", step: 5, label: "UNCERTAIN", path: "M 43 49 H 52 V 18 H 61" },
        { from: "validate", to: "evidence", step: 6, path: "M 79 18 H 82 V 49" },
      ],
    },
  },
  {
    id: "02",
    code: "NL→SQL",
    field: "AGENTS / DATA ACCESS",
    title: "Natural Language to SQL",
    premise:
      "A conversational question reaches data without granting unrestricted database access.",
    detail:
      "A planner resolves intent, retrieves only relevant schema, applies business rules and rejects ambiguous or unsafe operations before generating a guarded query.",
    stack: ["Python", "Tool calling", "Schema RAG", "SQL policies", "Evaluation"],
    outcome: "Grounded questions · guarded execution",
    graph: {
      nodes: [
        { id: "question", label: "QUESTION", x: 10, y: 10, step: 0 },
        { id: "intent", label: "INTENT", x: 35, y: 10, step: 1, accent: true },
        { id: "schema", label: "SCHEMA", x: 24, y: 32, step: 2 },
        { id: "policy", label: "POLICY", x: 47, y: 32, step: 3 },
        { id: "planner", label: "PLANNER", x: 35, y: 53, step: 4 },
        { id: "sql", label: "GUARDED SQL", x: 79, y: 53, step: 5, accent: true },
      ],
      edges: [
        { from: "question", to: "intent", step: 0 },
        { from: "intent", to: "schema", step: 1, label: "GROUND", path: "M 35 10 V 20 H 24 V 32" },
        { from: "intent", to: "policy", step: 2, label: "BOUND", path: "M 35 10 V 20 H 47 V 32" },
        { from: "schema", to: "planner", step: 3, path: "M 24 32 V 43 H 35 V 53" },
        { from: "policy", to: "planner", step: 4, path: "M 47 32 V 43 H 35 V 53" },
        { from: "planner", to: "sql", step: 5 },
      ],
    },
  },
  {
    id: "03",
    code: "MCP—03",
    field: "FINTECH / AGENT TOOLS",
    title: "Financial MCP Server",
    premise:
      "Market data becomes explicit, reusable instruments rather than an opaque recommendation engine.",
    detail:
      "Each capability exposes a strict contract, identifiable source and predictable output so specialised agents can combine evidence without hiding how an interpretation was produced.",
    stack: ["MCP", "Python", "Market data", "Typed tools", "Agents"],
    outcome: "Signals organised as auditable tools",
    graph: {
      nodes: [
        { id: "agent", label: "AGENT", x: 7, y: 32, step: 0 },
        { id: "contract", label: "TOOL CONTRACT", x: 28, y: 32, step: 1, accent: true },
        { id: "quote", label: "QUOTE", x: 53, y: 10, step: 2 },
        { id: "history", label: "HISTORY", x: 53, y: 32, step: 3 },
        { id: "signals", label: "SIGNALS", x: 53, y: 54, step: 4 },
        { id: "typed", label: "TYPED RESULT", x: 76, y: 32, step: 5 },
        { id: "evidence", label: "EVIDENCE", x: 92, y: 32, step: 6, accent: true },
      ],
      edges: [
        { from: "agent", to: "contract", step: 0 },
        { from: "contract", to: "quote", step: 1, path: "M 28 32 H 39 V 10 H 53" },
        { from: "contract", to: "history", step: 2 },
        { from: "contract", to: "signals", step: 3, path: "M 28 32 H 39 V 54 H 53" },
        { from: "quote", to: "typed", step: 4, path: "M 53 10 H 65 V 32 H 76" },
        { from: "history", to: "typed", step: 5 },
        { from: "signals", to: "typed", step: 6, path: "M 53 54 H 65 V 32 H 76" },
        { from: "typed", to: "evidence", step: 7 },
      ],
    },
  },
  {
    id: "04",
    code: "SEARCH",
    field: "SEMANTIC SEARCH / PRODUCT",
    title: "Intent-aware Shopping Assistant",
    premise:
      "Product discovery starts from a real need, not from exact keyword matching.",
    detail:
      "Incomplete language is converted into comparable attributes, hybrid retrieval candidates and explainable ranking signals evaluated independently from the conversational layer.",
    stack: ["TypeScript", "Embeddings", "Hybrid search", "Catalog API", "Metrics"],
    outcome: "Faster discovery · explainable relevance",
    graph: {
      nodes: [
        { id: "need", label: "NEED", x: 7, y: 32, step: 0 },
        { id: "attributes", label: "ATTRIBUTES", x: 23, y: 32, step: 1, accent: true },
        { id: "semantic", label: "SEMANTIC", x: 42, y: 13, step: 2 },
        { id: "keyword", label: "KEYWORD", x: 42, y: 51, step: 3 },
        { id: "vector", label: "VECTOR SET", x: 62, y: 13, step: 4 },
        { id: "lexical", label: "LEXICAL SET", x: 62, y: 51, step: 5 },
        { id: "rank", label: "RANK", x: 79, y: 32, step: 6 },
        { id: "explain", label: "EXPLAIN", x: 93, y: 32, step: 7, accent: true },
      ],
      edges: [
        { from: "need", to: "attributes", step: 0 },
        { from: "attributes", to: "semantic", step: 1, label: "EMBED", path: "M 23 32 H 31 V 13 H 42" },
        { from: "attributes", to: "keyword", step: 2, label: "MATCH", path: "M 23 32 H 31 V 51 H 42" },
        { from: "semantic", to: "vector", step: 3 },
        { from: "keyword", to: "lexical", step: 4 },
        { from: "vector", to: "rank", step: 5, path: "M 62 13 H 70 V 32 H 79" },
        { from: "lexical", to: "rank", step: 6, path: "M 62 51 H 70 V 32 H 79" },
        { from: "rank", to: "explain", step: 7 },
      ],
    },
  },
];

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

const collectionPosition = (nodePosition: number, startNode: number, count: number) => {
  const lastIndex = count - 1;
  const raw = Math.min(lastIndex, Math.max(0, nodePosition - startNode));
  if (raw >= lastIndex) return lastIndex;

  const index = Math.floor(raw);
  const local = raw - index;
  if (local <= 0.2) return index;
  if (local >= 0.8) return index + 1;
  return index + smoother((local - 0.2) / 0.6);
};

const edgePath = (project: SystemProject, edge: GraphEdge) => {
  if (edge.path) return edge.path;

  const from = project.graph.nodes.find((node) => node.id === edge.from);
  const to = project.graph.nodes.find((node) => node.id === edge.to);
  if (!from || !to) return "";

  if (Math.abs(from.y - to.y) < 2) return `M ${from.x} ${from.y} H ${to.x}`;

  const midX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} H ${midX} V ${to.y} H ${to.x}`;
};

const graphMarkup = (project: SystemProject) => `
  <div class="systems-graph-field">
    <span class="systems-graph-field__index">ARCH / ${project.id}</span>
    <span class="systems-graph-field__mode">${project.code}</span>
    <div class="systems-graph-field__crosshair" aria-hidden="true"></div>
    <svg class="systems-graph" viewBox="0 0 100 64" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <g class="systems-graph__edges">
        ${project.graph.edges
          .map(
            (edge) => `
              <path class="systems-graph__edge systems-graph__edge--base"
                d="${edgePath(project, edge)}" pathLength="1" />
              <path class="systems-graph__edge systems-graph__edge--active"
                d="${edgePath(project, edge)}" pathLength="1"
                style="--edge-step:${edge.step}" />
            `,
          )
          .join("")}
      </g>
      <g class="systems-graph__nodes">
        ${project.graph.nodes
          .map(
            (node, nodeIndex) => `
              <g class="systems-graph__node${node.accent ? " is-accent" : ""}"
                transform="translate(${node.x} ${node.y})"
                style="--node-step:${node.step}">
                <circle r="1.05"></circle>
                <circle class="systems-graph__node-halo" r="3.25"></circle>
                <text x="2.4" y=".8">${String(nodeIndex + 1).padStart(2, "0")}</text>
                <text class="systems-graph__node-label" x="2.4" y="4.2">${node.label}</text>
              </g>
            `,
          )
          .join("")}
      </g>
    </svg>
    ${project.graph.edges
      .filter((edge) => edge.label)
      .map((edge) => {
        const from = project.graph.nodes.find((node) => node.id === edge.from);
        const to = project.graph.nodes.find((node) => node.id === edge.to);
        if (!from || !to || !edge.label) return "";
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        return `<span class="systems-graph__edge-label"
          style="left:${x}%;top:${y}%;--edge-step:${edge.step}">${edge.label}</span>`;
      })
      .join("")}
  </div>
`;

const projectMarkup = (project: SystemProject, index: number) => `
  <article class="systems-project" data-index="${index}">
    <div class="systems-project__identity">
      <div class="systems-project__eyebrow">
        <span>${project.id}</span><i></i><b>${project.code}</b>
      </div>
      <span class="systems-project__field">${project.field}</span>
      <h2>${project.title}</h2>
      <p class="systems-project__premise">${project.premise}</p>
    </div>

    <div class="systems-project__architecture">
      <div class="systems-project__architecture-heading">
        <span>SYSTEM ARCHITECTURE</span><i></i><b>${project.id} / ${String(projects.length).padStart(2, "0")}</b>
      </div>
      ${graphMarkup(project)}
    </div>

    <p class="systems-project__detail">${project.detail}</p>

    <div class="systems-project__evidence">
      <span>EVIDENCE / ${project.id}</span>
      <i></i>
      <strong>${project.outcome}</strong>
    </div>

    <div class="systems-project__implementation">
      <span>IMPLEMENTATION</span>
      <div>${project.stack
        .map(
          (item, stackIndex) =>
            `<b style="--stack-index:${stackIndex}">${item}</b>`,
        )
        .join("")}</div>
    </div>
  </article>
`;

const markup = () => `
  <div class="systems-experience" aria-label="Selected technical systems">
    <div class="systems-intro" aria-hidden="true">
      <div class="systems-intro__kicker"><span>03</span><i></i><b>THE EVIDENCE</b></div>
      <p>The work becomes evidence —<br><em>systems designed, built and shipped.</em></p>
    </div>

    <div class="systems-header" aria-hidden="true">
      <div class="systems-header__label"><span>03</span><i></i><b>SELECTED TECHNICAL SYSTEMS</b></div>
      <div class="systems-header__meta"><span>${String(projects.length).padStart(2, "0")} SYSTEMS</span><span>BUILT / SHIPPED</span></div>
    </div>

    <div class="systems-axis" aria-hidden="true"><i class="systems-axis__progress"></i></div>

    <div class="systems-axis-items" aria-hidden="true">
      ${projects
        .map(
          (project, index) => `
            <div class="systems-axis-item" data-index="${index}"
              style="--axis-slot:${projects.length > 1 ? index / (projects.length - 1) : 0}">
              <span>${project.id}</span><i></i><b>${project.code}</b>
            </div>
          `,
        )
        .join("")}
    </div>

    <div class="systems-projects">${projects.map(projectMarkup).join("")}</div>

    <div class="systems-counter" aria-hidden="true">
      <small>SYSTEM</small>
      <div><b class="systems-counter__current">01</b><i></i><span>${String(projects.length).padStart(2, "0")}</span></div>
    </div>
  </div>
`;

type MotionState = {
  title: number;
  graph: number;
  support: number;
  titleY: number;
  supportY: number;
  graphX: number;
  build: number;
};

const motionForOffset = (offset: number): MotionState => {
  if (offset < 0) {
    const t = clamp01(-offset);
    return {
      title: 1 - range(t, 0.18, 0.46),
      graph: 1 - range(t, 0.62, 0.94),
      support: 1 - range(t, 0.28, 0.56),
      titleY: -30 * range(t, 0.06, 0.68),
      supportY: -10 * range(t, 0.12, 0.72),
      graphX: -1.1 * range(t, 0.18, 0.90),
      build: 1,
    };
  }

  const t = clamp01(1 - offset);
  return {
    title: range(t, 0.54, 0.82),
    graph: range(t, 0.20, 0.50),
    support: range(t, 0.62, 0.90),
    titleY: 30 * (1 - range(t, 0.34, 0.82)),
    supportY: 10 * (1 - range(t, 0.48, 0.90)),
    graphX: 1.8 * (1 - range(t, 0.14, 0.62)),
    build: range(t, 0.18, 0.88),
  };
};

export const mountSystemsExperience = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const systemsScene = document.querySelector<HTMLElement>(".ref-scene--systems");
  if (!stage || !systemsScene) return () => undefined;
  if (systemsScene.querySelector(".systems-experience")) return () => undefined;

  systemsScene.insertAdjacentHTML("beforeend", markup());
  document.documentElement.classList.add("systems-refined-ready");

  const root = systemsScene.querySelector<HTMLElement>(".systems-experience");
  const intro = systemsScene.querySelector<HTMLElement>(".systems-intro");
  const header = systemsScene.querySelector<HTMLElement>(".systems-header");
  const axis = systemsScene.querySelector<HTMLElement>(".systems-axis");
  const axisItems = Array.from(systemsScene.querySelectorAll<HTMLElement>(".systems-axis-item"));
  const entries = Array.from(systemsScene.querySelectorAll<HTMLElement>(".systems-project"));
  const counter = systemsScene.querySelector<HTMLElement>(".systems-counter");
  const counterCurrent = systemsScene.querySelector<HTMLElement>(".systems-counter__current");

  if (!root || !intro || !header || !axis || !counter || !counterCurrent) {
    root?.remove();
    document.documentElement.classList.remove("systems-refined-ready");
    return () => undefined;
  }

  const experienceCount = document.querySelectorAll(".trajectory-entry").length || 3;
  const projectCount = projects.length;
  const artworkCount = document.querySelectorAll(".ref-filmstrip button").length || 10;

  const careerStartNode = 2;
  const chapterSystemsNode = careerStartNode + experienceCount;
  const systemsStartNode = chapterSystemsNode + 1;
  const chapterGalleryNode = systemsStartNode + projectCount;
  const galleryStartNode = chapterGalleryNode + 1;
  const chapterAgentNode = galleryStartNode + artworkCount;
  const lastNode = chapterAgentNode + 1;

  let frame = 0;
  let pointerX = 0;
  let pointerY = 0;
  let pointerTargetX = 0;
  let pointerTargetY = 0;

  const onPointerMove = (event: PointerEvent) => {
    if (stage.dataset.systemsRefined !== "true") return;
    pointerTargetX = event.clientX / innerWidth - 0.5;
    pointerTargetY = event.clientY / innerHeight - 0.5;
  };

  const render = () => {
    const progress = Number.parseFloat(stage.style.getPropertyValue("--progress")) || 0;
    const node = clamp01(progress) * lastNode;

    const sectionIn = range(node, chapterSystemsNode - 0.50, chapterSystemsNode - 0.06);
    const sectionOut = range(node, chapterGalleryNode - 0.08, chapterGalleryNode + 0.28);
    const sectionVisibility = sectionIn * (1 - sectionOut);

    /* Intro owns the chapter beat completely. The first project does not start
       until the statement has cleared its spatial anchor. */
    const introIn = range(node, chapterSystemsNode - 0.34, chapterSystemsNode - 0.04);
    const introOut = range(node, chapterSystemsNode + 0.10, chapterSystemsNode + 0.38);
    const introVisibility = introIn * (1 - introOut);

    const axisReveal = range(node, chapterSystemsNode - 0.20, chapterSystemsNode + 0.18);
    const headerReveal = range(node, chapterSystemsNode + 0.24, chapterSystemsNode + 0.54);
    const contentReveal = range(node, chapterSystemsNode + 0.46, chapterSystemsNode + 0.86);

    const projectPosition = collectionPosition(node, systemsStartNode, projectCount);
    const projectProgress = projectCount > 1 ? projectPosition / (projectCount - 1) : 0;

    /* The last project physically leaves before Chapter 04 is allowed to enter. */
    const tailOut = range(node, chapterGalleryNode - 0.38, chapterGalleryNode - 0.02);
    const galleryHandoff = range(node, chapterGalleryNode - 0.01, chapterGalleryNode + 0.30);

    stage.dataset.systemsRefined =
      node > chapterSystemsNode - 0.58 && node < chapterGalleryNode + 0.34
        ? "true"
        : "false";

    stage.style.setProperty("--systems-editorial-visibility", sectionVisibility.toFixed(5));
    stage.style.setProperty("--systems-axis-reveal", axisReveal.toFixed(5));
    stage.style.setProperty("--systems-intro-in", introIn.toFixed(5));
    stage.style.setProperty("--systems-intro-out", introOut.toFixed(5));
    stage.style.setProperty("--systems-content", contentReveal.toFixed(5));
    stage.style.setProperty("--systems-progress", projectProgress.toFixed(5));
    stage.style.setProperty("--systems-gallery-handoff", galleryHandoff.toFixed(5));

    root.style.opacity = "1";

    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${((1 - introIn) * 62 - introOut * 82).toFixed(2)}px, 0)`;

    header.style.opacity = headerReveal.toFixed(5);
    header.style.transform = `translate3d(0, ${(7 * (1 - headerReveal)).toFixed(2)}px, 0)`;
    axis.style.opacity = axisReveal.toFixed(5);
    counter.style.opacity = (contentReveal * (1 - tailOut) * 0.78).toFixed(5);

    pointerX += (pointerTargetX - pointerX) * 0.075;
    pointerY += (pointerTargetY - pointerY) * 0.075;
    root.style.setProperty("--systems-pointer-x", pointerX.toFixed(4));
    root.style.setProperty("--systems-pointer-y", pointerY.toFixed(4));

    axisItems.forEach((element, index) => {
      const offset = index - projectPosition;
      const focus = Math.exp(-(offset * offset) * 5.2);
      element.style.visibility = "visible";
      element.style.opacity = (contentReveal * (0.34 + focus * 0.66) * (1 - tailOut * 0.72)).toFixed(5);
      element.style.transform = "translate3d(0, -50%, 0)";
      element.style.setProperty("--axis-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const offset = index - projectPosition;
      const distance = Math.abs(offset);
      const motion = motionForOffset(offset);
      const isLast = index === projectCount - 1;
      const tail = isLast ? tailOut : 0;

      const titlePresence = motion.title * (1 - tail);
      const graphPresence = motion.graph * (1 - tail * 0.82);
      const supportPresence = motion.support * (1 - tail * 0.94);
      const extraTailY = isLast ? -30 * tail : 0;

      element.style.visibility = distance < 1.08 || (isLast && tail < 1) ? "visible" : "hidden";
      element.style.setProperty("--title-presence", titlePresence.toFixed(5));
      element.style.setProperty("--graph-presence", graphPresence.toFixed(5));
      element.style.setProperty("--support-presence", supportPresence.toFixed(5));
      element.style.setProperty("--graph-build", motion.build.toFixed(5));
      element.style.setProperty("--system-offset", offset.toFixed(5));
      element.style.setProperty("--title-y", `${(motion.titleY + extraTailY).toFixed(3)}vh`);
      element.style.setProperty("--support-y", `${(motion.supportY + extraTailY * 0.28).toFixed(3)}vh`);
      element.style.setProperty("--graph-x", `${motion.graphX.toFixed(3)}vw`);
    });

    counterCurrent.textContent = String(Math.round(projectPosition) + 1).padStart(2, "0");
    frame = requestAnimationFrame(render);
  };

  addEventListener("pointermove", onPointerMove, { passive: true });
  frame = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(frame);
    removeEventListener("pointermove", onPointerMove);
    delete stage.dataset.systemsRefined;
    [
      "--systems-editorial-visibility",
      "--systems-axis-reveal",
      "--systems-intro-in",
      "--systems-intro-out",
      "--systems-content",
      "--systems-progress",
      "--systems-gallery-handoff",
    ].forEach((property) => stage.style.removeProperty(property));
    document.documentElement.classList.remove("systems-refined-ready");
    root.remove();
  };
};
