type SystemProject = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
  architecture: string[];
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
    architecture: ["REQUEST", "ROUTER", "REACT LOOP", "TOOLS + VERIFY", "LOCAL MODEL"],
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
    architecture: ["DOCUMENT", "SEGMENT", "RANK", "EXTRACT", "EVIDENCE"],
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
    architecture: ["QUESTION", "INTENT", "SCHEMA", "POLICY", "GUARDED SQL"],
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
    architecture: ["AGENT", "TOOL CONTRACT", "MARKET DATA", "TYPED RESULT", "EVIDENCE"],
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
    architecture: ["NEED", "ATTRIBUTES", "HYBRID RETRIEVAL", "RANK", "EXPLAIN"],
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

const projectMarkup = (project: SystemProject, index: number) => `
  <article class="systems-project" data-index="${index}">
    <div class="systems-project__identity">
      <div class="systems-project__eyebrow">
        <span>${project.id}</span><i></i><b>${project.code}</b><em>${project.field}</em>
      </div>
      <h2>${project.title}</h2>
      <p class="systems-project__premise">${project.premise}</p>
    </div>

    <div class="systems-project__architecture" aria-hidden="true">
      <div class="systems-project__architecture-label"><span>SYSTEM</span><b>ARCHITECTURE / ${project.id}</b></div>
      <div class="systems-flow">
        ${project.architecture
          .map(
            (node, nodeIndex) => `
              <div class="systems-flow__node" style="--node-index:${nodeIndex}">
                <i></i><span>${String(nodeIndex + 1).padStart(2, "0")}</span><strong>${node}</strong>
              </div>
              ${
                nodeIndex < project.architecture.length - 1
                  ? `<div class="systems-flow__connector" style="--connector-index:${nodeIndex}"><i></i><span>→</span></div>`
                  : ""
              }`,
          )
          .join("")}
      </div>
    </div>

    <p class="systems-project__detail">${project.detail}</p>

    <div class="systems-project__implementation">
      <span>IMPLEMENTATION</span>
      <div>${project.stack.map((item, stackIndex) => `<b style="--stack-index:${stackIndex}">${item}</b>`).join("")}</div>
    </div>

    <div class="systems-project__outcome">
      <span>EVIDENCE / ${project.id}</span>
      <i></i>
      <strong>${project.outcome}</strong>
    </div>
  </article>
`;

const markup = () => `
  <div class="systems-experience" aria-label="Selected technical systems">
    <div class="systems-intro" aria-hidden="true">
      <div class="systems-intro__kicker"><span>03</span><i></i><b>THE EVIDENCE</b></div>
      <p>Roles become systems.<br><em>Decisions become evidence.</em></p>
    </div>

    <div class="systems-header" aria-hidden="true">
      <div class="systems-header__label"><span>03</span><i></i><b>SELECTED TECHNICAL SYSTEMS</b></div>
      <div class="systems-header__meta"><span>${String(projects.length).padStart(2, "0")} SYSTEMS</span><span>BUILT / SHIPPED</span></div>
    </div>

    <div class="systems-register" aria-hidden="true">
      <span class="systems-register__label">SYSTEM REGISTER</span>
      <div class="systems-register__rail"><i class="systems-register__cursor"></i></div>
      ${projects
        .map(
          (project, index) => `
            <div class="systems-register__item" data-index="${index}">
              <span>${project.id}</span><i></i><b>${project.code}</b>
            </div>`,
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
  const register = systemsScene.querySelector<HTMLElement>(".systems-register");
  const registerCursor = systemsScene.querySelector<HTMLElement>(".systems-register__cursor");
  const registerItems = Array.from(
    systemsScene.querySelectorAll<HTMLElement>(".systems-register__item"),
  );
  const entries = Array.from(systemsScene.querySelectorAll<HTMLElement>(".systems-project"));
  const counter = systemsScene.querySelector<HTMLElement>(".systems-counter");
  const counterCurrent = systemsScene.querySelector<HTMLElement>(".systems-counter__current");

  if (!root || !intro || !header || !register || !registerCursor || !counter || !counterCurrent) {
    root?.remove();
    systemsScene.classList.remove("systems-refined-mounted");
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

    const sectionIn = range(node, chapterSystemsNode - 0.46, chapterSystemsNode - 0.04);
    const sectionOut = range(node, chapterGalleryNode - 0.50, chapterGalleryNode + 0.12);
    const sectionVisibility = sectionIn * (1 - sectionOut);

    const introIn = range(node, chapterSystemsNode - 0.20, chapterSystemsNode + 0.10);
    const introOut = range(node, chapterSystemsNode + 0.28, chapterSystemsNode + 0.68);
    const introVisibility = introIn * (1 - introOut);

    const contentReveal = range(node, chapterSystemsNode + 0.44, systemsStartNode - 0.06);
    const headerReveal = range(node, chapterSystemsNode + 0.34, chapterSystemsNode + 0.78);
    const projectPosition = collectionPosition(node, systemsStartNode, projectCount);
    const projectProgress = projectCount > 1 ? projectPosition / (projectCount - 1) : 0;

    stage.dataset.systemsRefined =
      node > chapterSystemsNode - 0.52 && node < chapterGalleryNode + 0.18 ? "true" : "false";
    stage.style.setProperty("--systems-editorial-visibility", sectionVisibility.toFixed(5));
    stage.style.setProperty("--systems-intro-in", introIn.toFixed(5));
    stage.style.setProperty("--systems-intro-out", introOut.toFixed(5));
    stage.style.setProperty("--systems-content", contentReveal.toFixed(5));
    stage.style.setProperty("--systems-progress", projectProgress.toFixed(5));

    root.style.opacity = "1";
    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(-50%, ${((1 - introIn) * 42 - introOut * 54).toFixed(2)}px, 0)`;

    header.style.opacity = (headerReveal * sectionVisibility).toFixed(5);
    header.style.transform = `translate3d(0, ${(8 * (1 - headerReveal)).toFixed(2)}px, 0)`;
    register.style.opacity = (contentReveal * sectionVisibility).toFixed(5);
    counter.style.opacity = (contentReveal * sectionVisibility * 0.82).toFixed(5);

    pointerX += (pointerTargetX - pointerX) * 0.08;
    pointerY += (pointerTargetY - pointerY) * 0.08;
    root.style.setProperty("--systems-pointer-x", pointerX.toFixed(4));
    root.style.setProperty("--systems-pointer-y", pointerY.toFixed(4));

    registerCursor.style.transform = `translate3d(0, ${(projectPosition * 34).toFixed(3)}px, 0)`;

    registerItems.forEach((element, index) => {
      const offset = index - projectPosition;
      const focus = Math.exp(-(offset * offset) * 4.4);
      element.style.setProperty("--register-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const offset = index - projectPosition;
      const distance = Math.abs(offset);
      const focus = Math.exp(-(offset * offset) * 3.8);
      const outgoingScale = offset < 0 ? 0.78 : 1;

      element.style.visibility = distance < 1.82 ? "visible" : "hidden";
      element.style.opacity = (contentReveal * Math.max(0.008, focus)).toFixed(5);
      element.style.setProperty("--system-focus", focus.toFixed(5));
      element.style.setProperty("--system-offset", offset.toFixed(5));
      element.style.setProperty("--title-y", `${(offset * 29 * outgoingScale).toFixed(3)}vh`);
      element.style.setProperty("--premise-y", `${(offset * 19 * outgoingScale).toFixed(3)}vh`);
      element.style.setProperty("--architecture-y", `${(offset * 12.5 * outgoingScale).toFixed(3)}vh`);
      element.style.setProperty("--detail-y", `${(offset * 9.2 * outgoingScale).toFixed(3)}vh`);
      element.style.setProperty("--implementation-y", `${(offset * 7.1 * outgoingScale).toFixed(3)}vh`);
      element.style.setProperty("--outcome-y", `${(offset * 5.4 * outgoingScale).toFixed(3)}vh`);
      element.style.setProperty(
        "--system-x",
        `${(offset < 0 ? offset * 0.34 : offset * -0.52).toFixed(3)}vw`,
      );
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
