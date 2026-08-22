import {
  chapterState,
  clamp01,
  collectionPosition,
  motionForOffset,
} from "./systems-motion-contract";
import { narrativeModel } from "./narrative-model";
import { systemsProjects as projects } from "./systems-projects";

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

export const mountSystemsExperience = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const systemsScene = document.querySelector<HTMLElement>(".ref-scene--systems");
  if (!stage || !systemsScene) return () => undefined;

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

  if (!root || !intro || !header || !axis || entries.length !== projects.length) {
    return () => undefined;
  }

  document.documentElement.classList.add("systems-refined-ready");

  const {
    chapterSystemsNode,
    systemsStartNode,
    chapterGalleryNode,
    virtualLastNode: lastNode,
  } = narrativeModel;
  const projectCount = projects.length;

  let frame = 0;
  let pointerX = 0;
  let pointerY = 0;
  let pointerTargetX = 0;
  let pointerTargetY = 0;
  let lastFrameTime = performance.now();

  const onPointerMove = (event: PointerEvent) => {
    if (stage.dataset.systemsRefined !== "true") return;
    pointerTargetX = event.clientX / innerWidth - 0.5;
    pointerTargetY = event.clientY / innerHeight - 0.5;
  };

  const render = (time: number) => {
    const dt = Math.min(0.05, Math.max(0.001, (time - lastFrameTime) / 1000));
    lastFrameTime = time;

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

    pointerX = damp(pointerX, pointerTargetX, 10.5, dt);
    pointerY = damp(pointerY, pointerTargetY, 10.5, dt);
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
  };
};
