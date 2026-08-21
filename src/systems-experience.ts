type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  accent?: boolean;
};

type GraphEdge = {
  from: string;
  to: string;
  label?: string;
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
        { id: "request", label: "REQUEST", x: 7, y: 32 },
        { id: "router", label: "ROUTER", x: 24, y: 32 },
        { id: "reason", label: "REASON", x: 43, y: 17, accent: true },
        { id: "tools", label: "TOOLS", x: 64, y: 17 },
        { id: "verify", label: "VERIFY", x: 64, y: 47 },
        { id: "reflect", label: "REFLECT", x: 43, y: 47, accent: true },
        { id: "model", label: "LOCAL MODEL", x: 88, y: 32 },
      ],
      edges: [
        { from: "request", to: "router" },
        { from: "router", to: "reason", label: "PLAN" },
        { from: "reason", to: "tools" },
        { from: "tools", to: "verify", label: "RESULT" },
        { from: "verify", to: "reflect" },
        { from: "reflect", to: "reason", label: "RETRY" },
        { from: "verify", to: "model" },
        { from: "model", to: "reason" },
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
        { id: "document", label: "DOCUMENT", x: 7, y: 31 },
        { id: "segment", label: "SEGMENT", x: 27, y: 31 },
        { id: "rank", label: "RANK", x: 47, y: 17, accent: true },
        { id: "extract", label: "EXTRACT", x: 66, y: 31 },
        { id: "validate", label: "VALIDATE", x: 82, y: 17 },
        { id: "evidence", label: "EVIDENCE", x: 91, y: 46, accent: true },
        { id: "review", label: "REVIEW", x: 47, y: 47 },
      ],
      edges: [
        { from: "document", to: "segment" },
        { from: "segment", to: "rank" },
        { from: "rank", to: "extract", label: "FIELD" },
        { from: "segment", to: "review" },
        { from: "review", to: "extract", label: "UNCERTAIN" },
        { from: "extract", to: "validate" },
        { from: "validate", to: "evidence" },
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
        { id: "question", label: "QUESTION", x: 8, y: 32 },
        { id: "intent", label: "INTENT", x: 27, y: 32, accent: true },
        { id: "schema", label: "SCHEMA", x: 48, y: 17 },
        { id: "policy", label: "POLICY", x: 48, y: 47 },
        { id: "planner", label: "PLANNER", x: 69, y: 32 },
        { id: "sql", label: "GUARDED SQL", x: 90, y: 32, accent: true },
      ],
      edges: [
        { from: "question", to: "intent" },
        { from: "intent", to: "schema", label: "GROUND" },
        { from: "intent", to: "policy", label: "BOUND" },
        { from: "schema", to: "planner" },
        { from: "policy", to: "planner" },
        { from: "planner", to: "sql" },
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
        { id: "agent", label: "AGENT", x: 7, y: 32 },
        { id: "contract", label: "TOOL CONTRACT", x: 28, y: 32, accent: true },
        { id: "source-a", label: "QUOTE", x: 50, y: 14 },
        { id: "source-b", label: "HISTORY", x: 50, y: 32 },
        { id: "source-c", label: "SIGNALS", x: 50, y: 50 },
        { id: "typed", label: "TYPED RESULT", x: 73, y: 32 },
        { id: "evidence", label: "EVIDENCE", x: 91, y: 32, accent: true },
      ],
      edges: [
        { from: "agent", to: "contract" },
        { from: "contract", to: "source-a" },
        { from: "contract", to: "source-b" },
        { from: "contract", to: "source-c" },
        { from: "source-a", to: "typed" },
        { from: "source-b", to: "typed" },
        { from: "source-c", to: "typed" },
        { from: "typed", to: "evidence" },
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
        { id: "need", label: "NEED", x: 7, y: 32 },
        { id: "attributes", label: "ATTRIBUTES", x: 27, y: 32, accent: true },
        { id: "semantic", label: "SEMANTIC", x: 48, y: 17 },
        { id: "keyword", label: "KEYWORD", x: 48, y: 47 },
        { id: "rank", label: "RANK", x: 69, y: 32 },
        { id: "explain", label: "EXPLAIN", x: 90, y: 32, accent: true },
      ],
      edges: [
        { from: "need", to: "attributes" },
        { from: "attributes", to: "semantic", label: "EMBED" },
        { from: "attributes", to: "keyword", label: "MATCH" },
        { from: "semantic", to: "rank" },
        { from: "keyword", to: "rank" },
        { from: "rank", to: "explain" },
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
  const from = project.graph.nodes.find((node) => node.id === edge.from);
  const to = project.graph.nodes.find((node) => node.id === edge.to);
  if (!from || !to) return "";

  if (Math.abs(from.y - to.y) < 2) {
    return `M ${from.x} ${from.y} H ${to.x}`;
  }

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
            (edge, edgeIndex) => `
              <path class="systems-graph__edge systems-graph__edge--base"
                d="${edgePath(project, edge)}" pathLength="1" />
              <path class="systems-graph__edge systems-graph__edge--active"
                d="${edgePath(project, edge)}" pathLength="1"
                style="--edge-index:${edgeIndex}" />
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
                style="--node-index:${nodeIndex}">
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
      .map((edge, index) => {
        const from = project.graph.nodes.find((node) => node.id === edge.from);
        const to = project.graph.nodes.find((node) => node.id === edge.to);
        if (!from || !to || !edge.label) return "";
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        return `<span class="systems-graph__edge-label"
          style="left:${x}%;top:${y}%;--edge-label-index:${index}">${edge.label}</span>`;
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

    <div class="systems-project__evidence">
      <span>EVIDENCE / ${project.id}</span>
      <i></i>
      <strong>${project.outcome}</strong>
    </div>

    <p class="systems-project__detail">${project.detail}</p>

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

    <div class="systems-axis" aria-hidden="true">
      <i class="systems-axis__progress"></i>
    </div>

    <div class="systems-axis-items" aria-hidden="true">
      ${projects
        .map(
          (project, index) => `
            <div class="systems-axis-item" data-index="${index}">
              <span>${project.id}</span><i></i><b>${project.code}</b>
            </div>
          `,
        )
        .join("")}
    </div>

    <div class="systems-projects">
      ${projects.map(projectMarkup).join("")}
    </div>

    <div class="systems-counter" aria-hidden="true">
      <small>SYSTEM</small>
      <div><b class="systems-counter__current">01</b><i></i><span>${String(projects.length).padStart(2, "0")}</span></div>
    </div>
  </div>
`;

export const mountSystemsExperience = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const systemsScene = document.querySelector<HTMLElement>(".ref-scene--systems");
  if (!stage || !systemsScene) return () => undefined;
  if (systemsScene.querySelector(".systems-experience")) return () => undefined;

  systemsScene.insertAdjacentHTML("beforeend", markup());
  systemsScene.classList.add("systems-refined-mounted");
  document.documentElement.classList.add("systems-refined-ready");

  const root = systemsScene.querySelector<HTMLElement>(".systems-experience");
  const intro = systemsScene.querySelector<HTMLElement>(".systems-intro");
  const header = systemsScene.querySelector<HTMLElement>(".systems-header");
  const axis = systemsScene.querySelector<HTMLElement>(".systems-axis");
  const axisItems = Array.from(
    systemsScene.querySelectorAll<HTMLElement>(".systems-axis-item"),
  );
  const entries = Array.from(
    systemsScene.querySelectorAll<HTMLElement>(".systems-project"),
  );
  const counter = systemsScene.querySelector<HTMLElement>(".systems-counter");
  const counterCurrent =
    systemsScene.querySelector<HTMLElement>(".systems-counter__current");

  if (!root || !intro || !header || !axis || !counter || !counterCurrent) {
    root?.remove();
    systemsScene.classList.remove("systems-refined-mounted");
    document.documentElement.classList.remove("systems-refined-ready");
    return () => undefined;
  }

  const experienceCount =
    document.querySelectorAll(".trajectory-entry").length || 3;
  const projectCount = projects.length;
  const artworkCount =
    document.querySelectorAll(".ref-filmstrip button").length || 10;

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
    const progress =
      Number.parseFloat(stage.style.getPropertyValue("--progress")) || 0;
    const node = clamp01(progress) * lastNode;

    const sectionIn = range(
      node,
      chapterSystemsNode - 0.52,
      chapterSystemsNode - 0.04,
    );
    const sectionOut = range(
      node,
      chapterGalleryNode - 0.50,
      chapterGalleryNode + 0.14,
    );
    const sectionVisibility = sectionIn * (1 - sectionOut);

    const introIn = range(
      node,
      chapterSystemsNode - 0.34,
      chapterSystemsNode - 0.02,
    );
    const introOut = range(
      node,
      chapterSystemsNode + 0.34,
      chapterSystemsNode + 0.72,
    );
    const introVisibility = introIn * (1 - introOut);

    const axisReveal = range(
      node,
      chapterSystemsNode - 0.26,
      chapterSystemsNode + 0.10,
    );
    const headerReveal = range(
      node,
      chapterSystemsNode + 0.26,
      chapterSystemsNode + 0.66,
    );
    const contentReveal = range(
      node,
      chapterSystemsNode + 0.44,
      systemsStartNode - 0.02,
    );

    const projectPosition = collectionPosition(
      node,
      systemsStartNode,
      projectCount,
    );
    const projectProgress =
      projectCount > 1 ? projectPosition / (projectCount - 1) : 0;

    stage.dataset.systemsRefined =
      node > chapterSystemsNode - 0.58 &&
      node < chapterGalleryNode + 0.20
        ? "true"
        : "false";

    stage.style.setProperty(
      "--systems-editorial-visibility",
      sectionVisibility.toFixed(5),
    );
    stage.style.setProperty("--systems-axis-reveal", axisReveal.toFixed(5));
    stage.style.setProperty("--systems-intro-in", introIn.toFixed(5));
    stage.style.setProperty("--systems-intro-out", introOut.toFixed(5));
    stage.style.setProperty("--systems-content", contentReveal.toFixed(5));
    stage.style.setProperty("--systems-progress", projectProgress.toFixed(5));

    root.style.opacity = "1";

    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${
      ((1 - introIn) * 68 - introOut * 78).toFixed(2)
    }px, 0)`;

    header.style.opacity = headerReveal.toFixed(5);
    header.style.transform = `translate3d(0, ${
      (8 * (1 - headerReveal)).toFixed(2)
    }px, 0)`;

    axis.style.opacity = axisReveal.toFixed(5);
    counter.style.opacity = (contentReveal * 0.72).toFixed(5);

    pointerX += (pointerTargetX - pointerX) * 0.075;
    pointerY += (pointerTargetY - pointerY) * 0.075;
    root.style.setProperty("--systems-pointer-x", pointerX.toFixed(4));
    root.style.setProperty("--systems-pointer-y", pointerY.toFixed(4));

    axisItems.forEach((element, index) => {
      const offset = index - projectPosition;
      const focus = Math.exp(-(offset * offset) * 4.9);
      const distance = Math.abs(offset);

      element.style.visibility = distance < 2.25 ? "visible" : "hidden";
      element.style.opacity = (
        contentReveal * Math.max(0.08, focus)
      ).toFixed(5);
      element.style.transform = `translate3d(0, ${(offset * 11.5).toFixed(
        3,
      )}vh, 0)`;
      element.style.setProperty("--axis-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const offset = index - projectPosition;
      const distance = Math.abs(offset);
      const titleFocus = Math.exp(-(offset * offset) * 7.2);
      const graphFocus = Math.exp(-(offset * offset) * 5.0);
      const supportFocus = Math.exp(-(offset * offset) * 5.8);
      const outgoing = offset < 0;
      const titleTravel = offset * (outgoing ? 20 : 24);
      const supportTravel = offset * (outgoing ? 8 : 10);
      const graphTravel = offset * (outgoing ? 1.5 : -1.9);

      element.style.visibility = distance < 1.34 ? "visible" : "hidden";
      element.style.setProperty("--title-focus", titleFocus.toFixed(5));
      element.style.setProperty("--graph-focus", graphFocus.toFixed(5));
      element.style.setProperty("--support-focus", supportFocus.toFixed(5));
      element.style.setProperty("--system-offset", offset.toFixed(5));
      element.style.setProperty("--title-y", `${titleTravel.toFixed(3)}vh`);
      element.style.setProperty("--support-y", `${supportTravel.toFixed(3)}vh`);
      element.style.setProperty("--graph-x", `${graphTravel.toFixed(3)}vw`);
    });

    counterCurrent.textContent = String(
      Math.round(projectPosition) + 1,
    ).padStart(2, "0");

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
    ].forEach((property) => stage.style.removeProperty(property));
    systemsScene.classList.remove("systems-refined-mounted");
    document.documentElement.classList.remove("systems-refined-ready");
    root.remove();
  };
};
