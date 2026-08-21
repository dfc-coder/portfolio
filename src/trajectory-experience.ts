type Experience = {
  period: string;
  role: string;
  company: string;
  summary: string;
  focus: string[];
};

const experiences: Experience[] = [
  {
    period: "2025 — NOW",
    role: "AI Engineer",
    company: "aiRoss · Madrid / Remote",
    summary:
      "Private document-intelligence systems, structured extraction and production workflows where security, evidence and human review remain visible.",
    focus: ["Local LLMs", "Document AI", "Python", "Product architecture"],
  },
  {
    period: "2024 — 2025",
    role: "Independent AI Engineer",
    company: "Applied AI · Remote",
    summary:
      "Agentic systems, retrieval pipelines and natural-language interfaces designed around operational constraints instead of isolated model demonstrations.",
    focus: ["RAG", "Agents", "NL→SQL", "Evaluation"],
  },
  {
    period: "2023 — 2025",
    role: "Software Engineer",
    company: "FK Tech · Argentina",
    summary:
      "Full-stack products and integrations with an emphasis on maintainable architecture, secure APIs and delivery across the complete software lifecycle.",
    focus: ["TypeScript", "Backend", "Integrations", "Cloud"],
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

const markup = () => `
  <div class="trajectory-experience" aria-label="Professional trajectory">
    <div class="trajectory-intro" aria-hidden="true">
      <span>CHAPTER 02 · THE RECORD</span>
      <p>First, the proof —<br>where the practice was built.</p>
    </div>

    <div class="trajectory-header" aria-hidden="true">
      <span>02</span><i></i><b>THE RECORD</b>
    </div>

    <div class="trajectory-axis" aria-hidden="true"><i></i></div>

    <div class="trajectory-years" aria-hidden="true">
      ${experiences
        .map(
          (experience, index) => `
            <div class="trajectory-year" data-index="${index}">
              <span>${experience.period.slice(0, 4)}</span><i></i>
            </div>`,
        )
        .join("")}
    </div>

    <div class="trajectory-entries">
      ${experiences
        .map(
          (experience, index) => `
            <article class="trajectory-entry" data-index="${index}">
              <span class="trajectory-entry__meta">${experience.period} · ${experience.company}</span>
              <h2>${experience.role}</h2>
              <p>${experience.summary}</p>
              <ul>${experience.focus.map((item) => `<li>${item}</li>`).join("")}</ul>
            </article>`,
        )
        .join("")}
    </div>

    <div class="trajectory-counter" aria-hidden="true">
      <div class="trajectory-counter__viewport">
        <div class="trajectory-counter__track">
          ${experiences.map((_, index) => `<span>${String(index + 1).padStart(2, "0")}</span>`).join("")}
        </div>
      </div>
      <i></i><span>${String(experiences.length).padStart(2, "0")}</span>
    </div>
  </div>
`;

export const mountTrajectoryExperience = () => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const career = document.querySelector<HTMLElement>(".ref-scene--career");
  if (!stage || !career) return () => undefined;

  if (career.querySelector(".trajectory-experience")) return () => undefined;

  career.insertAdjacentHTML("beforeend", markup());

  const root = career.querySelector<HTMLElement>(".trajectory-experience");
  const intro = career.querySelector<HTMLElement>(".trajectory-intro");
  const header = career.querySelector<HTMLElement>(".trajectory-header");
  const axis = career.querySelector<HTMLElement>(".trajectory-axis");
  const yearNodes = Array.from(career.querySelectorAll<HTMLElement>(".trajectory-year"));
  const entries = Array.from(career.querySelectorAll<HTMLElement>(".trajectory-entry"));
  const counterTrack = career.querySelector<HTMLElement>(".trajectory-counter__track");

  if (!root || !intro || !header || !axis || !counterTrack) {
    root?.remove();
    return () => undefined;
  }

  /* Derive the same node map as the Vue narrative from the DOM, so this motion
     director stays aligned if project or artwork counts change later. */
  const projectCount = document.querySelectorAll(".ref-system-nav button").length || 5;
  const artworkCount = document.querySelectorAll(".ref-filmstrip button").length || 10;
  const careerStartNode = 2;
  const chapterSystemsNode = careerStartNode + experiences.length;
  const systemsStartNode = chapterSystemsNode + 1;
  const chapterGalleryNode = systemsStartNode + projectCount;
  const galleryStartNode = chapterGalleryNode + 1;
  const chapterAgentNode = galleryStartNode + artworkCount;
  const lastNode = chapterAgentNode + 1;

  let frame = 0;

  const render = () => {
    const progress = Number.parseFloat(stage.style.getPropertyValue("--progress")) || 0;
    const node = clamp01(progress) * lastNode;

    /* One protagonist per beat:
       1. the Hero evacuates completely;
       2. the chapter sentence occupies the quiet interval;
       3. only then does the timeline content come into focus.
       The background field survives, but Hero typography never ghosts behind
       Trajectory. Everything remains reversible because it is derived from one
       continuous scroll position. */
    const heroExit = range(node, 0.10, 0.84);
    const axisMorph = range(node, 0.28, 1.28);
    const trajectoryIn = range(node, 0.24, 0.54);
    const trajectoryOut = range(node, chapterSystemsNode - 0.48, chapterSystemsNode + 0.16);
    const trajectoryVisibility = trajectoryIn * (1 - trajectoryOut);
    const introIn = range(node, 0.60, 0.88);
    const introOut = range(node, 1.04, 1.32);
    const introVisibility = introIn * (1 - introOut);
    const contentReveal = range(node, 1.24, 1.68);
    const heroShell = 1 - range(node, chapterSystemsNode - 0.62, chapterSystemsNode + 0.12);
    const experiencePosition = collectionPosition(node, careerStartNode, experiences.length);

    stage.dataset.trajectory = node > 0.12 && node < chapterSystemsNode + 0.18 ? "true" : "false";
    stage.style.setProperty("--trajectory-hero-exit", heroExit.toFixed(5));
    stage.style.setProperty("--trajectory-axis-morph", axisMorph.toFixed(5));
    stage.style.setProperty("--trajectory-visibility", trajectoryVisibility.toFixed(5));
    stage.style.setProperty("--trajectory-intro", introVisibility.toFixed(5));
    stage.style.setProperty("--trajectory-content", contentReveal.toFixed(5));
    stage.style.setProperty("--trajectory-hero-shell", heroShell.toFixed(5));

    root.style.opacity = trajectoryVisibility.toFixed(5);

    /* The chapter sentence is a single editorial beat. It arrives after the
       Hero is almost gone and leaves before the role typography becomes the
       protagonist, removing the layered pile-up visible in the previous pass. */
    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${((1 - introIn) * 12 - introOut * 20).toFixed(2)}px, 0)`;

    header.style.opacity = (contentReveal * trajectoryVisibility).toFixed(5);
    header.style.transform = `translate3d(0, ${(8 * (1 - contentReveal)).toFixed(2)}px, 0)`;

    /* The cue and chronology overlap only as lines. Text never overlaps text.
       The destination axis starts low/central and settles on the left focal
       band while it lengthens. */
    const axisLeft = 50 - axisMorph * 36.5;
    const axisTop = 86 - axisMorph * 39.5;
    const axisHeight = 4 + axisMorph * 47;
    axis.style.left = `${axisLeft.toFixed(3)}%`;
    axis.style.top = `${axisTop.toFixed(3)}%`;
    axis.style.height = `${axisHeight.toFixed(3)}vh`;
    axis.style.opacity = (trajectoryVisibility * axisMorph).toFixed(5);

    yearNodes.forEach((element, index) => {
      const offset = index - experiencePosition;
      const focus = Math.exp(-(offset * offset) * 4.15);
      const y = offset * 15;
      element.style.transform = `translate3d(0, calc(-50% + ${y.toFixed(3)}vh), 0)`;
      element.style.opacity = (contentReveal * Math.max(0.12, focus)).toFixed(5);
      element.style.setProperty("--year-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const offset = index - experiencePosition;
      const distance = Math.abs(offset);
      const focus = Math.exp(-(offset * offset) * 4.6);
      const directionScale = offset < 0 ? 0.74 : 1;

      element.style.visibility = distance < 1.48 ? "visible" : "hidden";
      element.style.opacity = (contentReveal * Math.max(0.018, focus)).toFixed(5);
      element.style.setProperty("--entry-focus", focus.toFixed(5));
      element.style.setProperty("--role-y", `${(offset * 31 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--meta-y", `${(offset * 22 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--summary-y", `${(offset * 17 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--tags-y", `${(offset * 13.5 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--entry-x", `${(offset < 0 ? offset * 0.8 : offset * -1.2).toFixed(3)}vw`);
    });

    counterTrack.style.transform = `translate3d(0, ${(-experiencePosition).toFixed(5)}em, 0)`;

    frame = requestAnimationFrame(render);
  };

  frame = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(frame);
    delete stage.dataset.trajectory;
    [
      "--trajectory-hero-exit",
      "--trajectory-axis-morph",
      "--trajectory-visibility",
      "--trajectory-intro",
      "--trajectory-content",
      "--trajectory-hero-shell",
    ].forEach((property) => stage.style.removeProperty(property));
    root.remove();
  };
};