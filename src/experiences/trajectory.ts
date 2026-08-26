import { narrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeState } from "./narrative-runtime";
import { experiences } from "./trajectory-data";

const COLLECTION_HOLD_END = 0.26;
const COLLECTION_TRAVEL_END = 0.74;

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
  if (local <= COLLECTION_HOLD_END) return index;
  if (local >= COLLECTION_TRAVEL_END) return index + 1;
  return index + smoother(
    (local - COLLECTION_HOLD_END) /
      (COLLECTION_TRAVEL_END - COLLECTION_HOLD_END),
  );
};

const entryPresence = (distance: number) =>
  smoother(clamp01((0.5 - distance) / 0.2));

export const mountTrajectoryExperience = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const career = document.querySelector<HTMLElement>(".ref-scene--career");
  if (!stage || !career) return () => undefined;

  const root = career.querySelector<HTMLElement>(".trajectory-experience");
  const intro = career.querySelector<HTMLElement>(".trajectory-intro");
  const header = career.querySelector<HTMLElement>(".trajectory-header");
  const axis = career.querySelector<HTMLElement>(".trajectory-axis");
  const yearNodes = Array.from(career.querySelectorAll<HTMLElement>(".trajectory-year"));
  const entries = Array.from(career.querySelectorAll<HTMLElement>(".trajectory-entry"));
  const counterTrack = career.querySelector<HTMLElement>(".trajectory-counter__track");

  if (!root || !intro || !header || !axis || !counterTrack) {
    return () => undefined;
  }

  const { careerStartNode, chapterSystemsNode } = narrativeModel;

  const render = (state: NarrativeState) => {
    const node = state.node;

    const heroExit = range(node, 0.10, 0.86);
    const cueExit = range(node, 0.24, 1.06);
    const cueHandoff = range(node, 0.60, 0.78);

    const trajectoryIn = range(node, 0.26, 0.56);
    const trajectoryOut = range(node, chapterSystemsNode - 0.48, chapterSystemsNode + 0.16);
    const trajectoryVisibility = trajectoryIn * (1 - trajectoryOut);

    const introIn = range(node, 0.56, 0.82);
    const introOut = range(node, 1.16, 1.48);
    const introVisibility = introIn * (1 - introOut);

    const axisReveal = range(node, 1.18, 1.52);
    const contentReveal = range(node, 1.34, 1.74);
    const heroShell = 1 - range(node, chapterSystemsNode - 0.62, chapterSystemsNode + 0.12);
    const experiencePosition = collectionPosition(node, careerStartNode, experiences.length);
    const timelineProgress = experiences.length > 1 ? experiencePosition / (experiences.length - 1) : 0;

    stage.dataset.trajectory = node > 0.12 && node < chapterSystemsNode + 0.18 ? "true" : "false";
    stage.style.setProperty("--trajectory-hero-exit", heroExit.toFixed(5));
    stage.style.setProperty("--trajectory-cue-exit", cueExit.toFixed(5));
    stage.style.setProperty(
      "--trajectory-cue-handoff-opacity",
      ((1 - cueExit) * (1 - cueHandoff)).toFixed(5),
    );
    stage.style.setProperty("--trajectory-visibility", trajectoryVisibility.toFixed(5));
    stage.style.setProperty("--trajectory-intro", introVisibility.toFixed(5));
    stage.style.setProperty("--trajectory-intro-in", introIn.toFixed(5));
    stage.style.setProperty("--trajectory-intro-out", introOut.toFixed(5));
    stage.style.setProperty("--trajectory-axis-reveal", axisReveal.toFixed(5));
    stage.style.setProperty("--trajectory-content", contentReveal.toFixed(5));
    stage.style.setProperty("--trajectory-hero-shell", heroShell.toFixed(5));
    stage.style.setProperty("--trajectory-timeline-progress", timelineProgress.toFixed(5));

    root.style.opacity = trajectoryVisibility.toFixed(5);
    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${((1 - introIn) * 34 - introOut * 42).toFixed(2)}px, 0)`;

    header.style.opacity = (contentReveal * trajectoryVisibility).toFixed(5);
    header.style.transform = `translate3d(0, ${(10 * (1 - contentReveal)).toFixed(2)}px, 0)`;
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
      const presence = entryPresence(distance);
      const directionScale = offset < 0 ? 0.82 : 1;

      element.style.visibility = presence > 0.001 ? "visible" : "hidden";
      element.style.opacity = (contentReveal * presence).toFixed(5);
      element.style.setProperty("--entry-focus", presence.toFixed(5));
      element.style.setProperty("--entry-offset", offset.toFixed(5));
      element.style.setProperty("--role-y", `${(offset * 5.2 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--eyebrow-y", `${(offset * 3.4 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--context-y", `${(offset * 2.2 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--summary-y", `${(offset * 1.8 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--tags-y", `${(offset * 1.4 * directionScale).toFixed(3)}vh`);
      element.style.setProperty("--entry-x", `${(offset < 0 ? offset * 0.18 : offset * -0.24).toFixed(3)}vw`);
    });

    counterTrack.style.transform = `translate3d(0, ${(-experiencePosition).toFixed(5)}em, 0)`;
  };

  const unsubscribe = narrativeRuntime.subscribe(render);

  return () => {
    unsubscribe();
    delete stage.dataset.trajectory;
    [
      "--trajectory-hero-exit",
      "--trajectory-cue-exit",
      "--trajectory-cue-handoff-opacity",
      "--trajectory-visibility",
      "--trajectory-intro",
      "--trajectory-intro-in",
      "--trajectory-intro-out",
      "--trajectory-axis-reveal",
      "--trajectory-content",
      "--trajectory-hero-shell",
      "--trajectory-timeline-progress",
    ].forEach((property) => stage.style.removeProperty(property));
  };
};
