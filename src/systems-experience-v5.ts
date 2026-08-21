import {
  chapterState,
  clamp01,
  collectionPosition,
  motionForOffset,
} from "./systems-motion-contract";
import {
  systemsProjects as projects,
  type GraphEdge,
  type SystemProject,
} from "./systems-projects";

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
  const axisItems = Array.from(
    systemsScene.querySelectorAll<HTMLElement>(".systems-axis-item"),
  );
  const entries = Array.from(
    systemsScene.querySelectorAll<HTMLElement>(".systems-project"),
  );
  const counter = systemsScene.querySelector<HTMLElement>(".systems-counter");
  const counterCurrent = systemsScene.querySelector<HTMLElement>(
    ".systems-counter__current",
  );

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
    const progress =
      Number.parseFloat(stage.style.getPropertyValue("--progress")) || 0;
    const node = clamp01(progress) * lastNode;
    const state = chapterState(node, chapterSystemsNode, chapterGalleryNode);

    const projectPosition = collectionPosition(
      node,
      systemsStartNode,
      projectCount,
    );
    const projectProgress =
      projectCount > 1 ? projectPosition / (projectCount - 1) : 0;

    stage.dataset.systemsRefined =
      node > chapterSystemsNode - 0.36 && node < chapterGalleryNode + 0.34
        ? "true"
        : "false";

    stage.style.setProperty(
      "--systems-editorial-visibility",
      state.sectionVisibility.toFixed(5),
    );
    stage.style.setProperty("--systems-axis-reveal", state.axisReveal.toFixed(5));
    stage.style.setProperty("--systems-intro-in", state.introIn.toFixed(5));
    stage.style.setProperty("--systems-intro-out", state.introOut.toFixed(5));
    stage.style.setProperty("--systems-content", state.contentReveal.toFixed(5));
    stage.style.setProperty("--systems-progress", projectProgress.toFixed(5));
    stage.style.setProperty(
      "--systems-gallery-handoff",
      state.galleryHandoff.toFixed(5),
    );

    root.style.opacity = "1";

    intro.style.opacity = state.introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${(
      (1 - state.introIn) * 60 -
      state.introOut * 86
    ).toFixed(2)}px, 0)`;

    header.style.opacity = state.headerReveal.toFixed(5);
    header.style.transform = `translate3d(0, ${(
      7 *
      (1 - state.headerReveal)
    ).toFixed(2)}px, 0)`;
    axis.style.opacity = state.axisReveal.toFixed(5);
    counter.style.opacity = (
      state.contentReveal *
      (1 - state.tailOut) *
      0.78
    ).toFixed(5);

    pointerX += (pointerTargetX - pointerX) * 0.075;
    pointerY += (pointerTargetY - pointerY) * 0.075;
    root.style.setProperty("--systems-pointer-x", pointerX.toFixed(4));
    root.style.setProperty("--systems-pointer-y", pointerY.toFixed(4));

    axisItems.forEach((element, index) => {
      const offset = index - projectPosition;
      const focus = Math.exp(-(offset * offset) * 5.2);
      element.style.visibility = "visible";
      element.style.opacity = (
        state.contentReveal *
        (0.34 + focus * 0.66) *
        (1 - state.tailOut * 0.72)
      ).toFixed(5);
      element.style.transform = "translate3d(0, -50%, 0)";
      element.style.setProperty("--axis-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const offset = index - projectPosition;
      const distance = Math.abs(offset);
      const motion = motionForOffset(offset);
      const isLast = index === projectCount - 1;
      const tail = isLast ? state.tailOut : 0;
      const firstProjectBuild = index === 0 ? state.initialGraphBuild : 1;

      const titlePresence = motion.title * (1 - tail);
      const graphPresence = motion.graph * (1 - tail * 0.82);
      const supportPresence = motion.support * (1 - tail * 0.94);
      const graphBuild = Math.min(motion.build, firstProjectBuild);
      const extraTailY = isLast ? -30 * tail : 0;

      element.style.visibility =
        distance < 1.08 || (isLast && tail < 1) ? "visible" : "hidden";
      element.style.setProperty("--title-presence", titlePresence.toFixed(5));
      element.style.setProperty("--graph-presence", graphPresence.toFixed(5));
      element.style.setProperty(
        "--support-presence",
        supportPresence.toFixed(5),
      );
      element.style.setProperty("--graph-build", graphBuild.toFixed(5));
      element.style.setProperty("--system-offset", offset.toFixed(5));
      element.style.setProperty(
        "--title-y",
        `${(motion.titleY + extraTailY).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--support-y",
        `${(motion.supportY + extraTailY * 0.28).toFixed(3)}vh`,
      );
      element.style.setProperty("--graph-x", `${motion.graphX.toFixed(3)}vw`);
    });

    counterCurrent.textContent = String(Math.round(projectPosition) + 1).padStart(
      2,
      "0",
    );

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
