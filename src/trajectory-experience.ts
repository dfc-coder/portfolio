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

const splitCompany = (company: string) => {
  const [organization, ...rest] = company.split(" · ");
  return { organization, location: rest.join(" · ") || "Remote" };
};

const markup = () => `
  <div class="trajectory-experience" aria-label="Professional trajectory">
    <div class="trajectory-intro" aria-hidden="true">
      <div class="trajectory-intro__kicker"><span>02</span><i></i><b>THE RECORD</b></div>
      <p>First, the proof —<br>where the practice was built.</p>
    </div>

    <div class="trajectory-header" aria-hidden="true">
      <div class="trajectory-header__label"><span>02</span><i></i><b>PROFESSIONAL TRAJECTORY</b></div>
      <div class="trajectory-header__meta"><span>2023 — NOW</span><span>${String(experiences.length).padStart(2, "0")} ROLES</span></div>
    </div>

    <div class="trajectory-axis" aria-hidden="true"><i></i></div>

    <div class="trajectory-years" aria-hidden="true">
      ${experiences
        .map(
          (experience, index) => `
            <div class="trajectory-year" data-index="${index}">
              <span>${experience.period.slice(0, 4)}</span><i></i><b>${String(index + 1).padStart(2, "0")}</b>
            </div>`,
        )
        .join("")}
    </div>

    <div class="trajectory-entries">
      ${experiences
        .map((experience, index) => {
          const company = splitCompany(experience.company);
          return `
            <article class="trajectory-entry" data-index="${index}">
              <div class="trajectory-entry__eyebrow">
                <span>${String(index + 1).padStart(2, "0")}</span><i></i><b>${experience.period}</b>
              </div>
              <h2>${experience.role}</h2>
              <div class="trajectory-entry__context">
                <div><small>ORGANIZATION</small><strong>${company.organization}</strong></div>
                <div><small>CONTEXT</small><strong>${company.location}</strong></div>
              </div>
              <div class="trajectory-entry__statement"><i></i><p>${experience.summary}</p></div>
              <div class="trajectory-entry__focus">
                <span>FOCUS</span>
                <ul>${experience.focus
                  .map((item, tagIndex) => `<li style="--tag-index:${tagIndex}">${item}</li>`)
                  .join("")}</ul>
              </div>
            </article>`;
        })
        .join("")}
    </div>

    <div class="trajectory-counter" aria-hidden="true">
      <small>ROLE</small>
      <div class="trajectory-counter__row">
        <div class="trajectory-counter__viewport">
          <div class="trajectory-counter__track">
            ${experiences.map((_, index) => `<span>${String(index + 1).padStart(2, "0")}</span>`).join("")}
          </div>
        </div>
        <i></i><span>${String(experiences.length).padStart(2, "0")}</span>
      </div>
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

    /* The Hero cue keeps its elegant vertical travel, but it no longer bends
       across the viewport into the career axis. The chronology is introduced
       independently as a quiet editorial rule after the chapter beat. */
    const heroExit = range(node, 0.10, 0.86);
    const cueExit = range(node, 0.24, 1.08);
    const trajectoryIn = range(node, 0.26, 0.56);
    const trajectoryOut = range(node, chapterSystemsNode - 0.48, chapterSystemsNode + 0.16);
    const trajectoryVisibility = trajectoryIn * (1 - trajectoryOut);

    /* Give the chapter sentence a readable plateau instead of making it a
       passing frame when the user scrolls quickly. */
    const introIn = range(node, 0.58, 0.80);
    const introOut = range(node, 1.18, 1.48);
    const introVisibility = introIn * (1 - introOut);

    const axisReveal = range(node, 1.18, 1.62);
    const contentReveal = range(node, 1.32, 1.72);
    const heroShell = 1 - range(node, chapterSystemsNode - 0.62, chapterSystemsNode + 0.12);
    const experiencePosition = collectionPosition(node, careerStartNode, experiences.length);
    const timelineProgress = experiences.length > 1 ? experiencePosition / (experiences.length - 1) : 0;

    stage.dataset.trajectory = node > 0.12 && node < chapterSystemsNode + 0.18 ? "true" : "false";
    stage.style.setProperty("--trajectory-hero-exit", heroExit.toFixed(5));
    stage.style.setProperty("--trajectory-cue-exit", cueExit.toFixed(5));
    stage.style.setProperty("--trajectory-visibility", trajectoryVisibility.toFixed(5));
    stage.style.setProperty("--trajectory-intro", introVisibility.toFixed(5));
    stage.style.setProperty("--trajectory-axis-reveal", axisReveal.toFixed(5));
    stage.style.setProperty("--trajectory-content", contentReveal.toFixed(5));
    stage.style.setProperty("--trajectory-hero-shell", heroShell.toFixed(5));
    stage.style.setProperty("--trajectory-timeline-progress", timelineProgress.toFixed(5));

    root.style.opacity = trajectoryVisibility.toFixed(5);
    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${((1 - introIn) * 10 - introOut * 14).toFixed(2)}px, 0)`;

    header.style.opacity = (contentReveal * trajectoryVisibility).toFixed(5);
    header.style.transform = `translate3d(0, ${(6 * (1 - contentReveal)).toFixed(2)}px, 0)`;
    axis.style.opacity = (axisReveal * trajectoryVisibility).toFixed(5);

    yearNodes.forEach((element, index) => {
      const offset = index - experiencePosition;
      const focus = Math.exp(-(offset * offset) * 3.45);
      const y = offset * 14.2;
      element.style.transform = `translate3d(0, calc(-50% + ${y.toFixed(3)}vh), 0)`;
      element.style.opacity = (contentReveal * Math.max(0.09, focus)).toFixed(5);
      element.style.setProperty("--year-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const offset = index - experiencePosition;
      const distance = Math.abs(offset);
      const focus = Math.exp(-(offset * offset) * 3.55);
      const directionScale = offset < 0 ? 0.76 : 1;

      element.style.visibility = distance < 1.92 ? "visible" : "hidden";
      element.style.opacity = (contentReveal * Math.max(0.012, focus)).toFixed(5);
      element.style.setProperty("--entry-focus", focus.toFixed(5));
      element.style.setProperty("--entry-offset", offset.toFixed(5));
      element.style.setProperty("--role-y", `${(offset * 23 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--eyebrow-y", `${(offset * 14.5 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--context-y", `${(offset * 11.5 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--summary-y", `${(offset * 9.2 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--tags-y", `${(offset * 7.4 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--entry-x", `${(offset < 0 ? offset * 0.42 : offset * -0.62).toFixed(3)}vw`);
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
      "--trajectory-cue-exit",
      "--trajectory-visibility",
      "--trajectory-intro",
      "--trajectory-axis-reveal",
      "--trajectory-content",
      "--trajectory-hero-shell",
      "--trajectory-timeline-progress",
    ].forEach((property) => stage.style.removeProperty(property));
    root.remove();
  };
};
