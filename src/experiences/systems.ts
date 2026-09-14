import {
  damp,
  frameDeltaSeconds,
  springStep,
  type SpringConfig,
  type SpringState,
} from "../motion/inertia";
import {
  chapterState,
  collectionPosition,
  motionForOffset,
} from "./systems-motion-contract";
import { narrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeState } from "./narrative-runtime";
import { systemsProjects as projects } from "./systems-projects";

const PARALLAX_SETTLE_EPSILON = 0.0004;
const VELOCITY_SETTLE_EPSILON = 0.0015;
const POINTER_SETTLE_EPSILON = 0.001;
const MOBILE_BREAKPOINT = "(max-width: 680px)";

type ProjectParts = {
  architecture: HTMLElement;
  detail: HTMLElement;
  evidence: HTMLElement;
  implementation: HTMLElement;
};

type MotionConfig = SpringConfig & {
  lead: number;
};

const PRIMARY_MOTION: MotionConfig = {
  frequency: 2.62,
  damping: 0.72,
  lead: 0.026,
  maxVelocity: 7.5,
};

const SECONDARY_MOTION: MotionConfig = {
  frequency: 1.58,
  damping: 0.86,
  lead: -0.020,
  maxVelocity: 5.5,
};

const TITLE_DEPTH = 0.72;
const GRAPH_DEPTH = 1.0;
const AXIS_DEPTH = 1.62;
const IMPLEMENTATION_DEPTH = 1.24;
const DETAIL_DEPTH = 1.0;
const EVIDENCE_DEPTH = 0.78;
const BUILD_DEPTH = 0.66;

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const positionAtDepth = (
  state: SpringState,
  target: number,
  depth: number,
) => target + (state.value - target) * depth;

const projectPartsFor = (element: HTMLElement): ProjectParts | null => {
  const architecture = element.querySelector<HTMLElement>(
    ".systems-project__architecture",
  );
  const detail = element.querySelector<HTMLElement>(".systems-project__detail");
  const evidence = element.querySelector<HTMLElement>(".systems-project__evidence");
  const implementation = element.querySelector<HTMLElement>(
    ".systems-project__implementation",
  );

  if (!architecture || !detail || !evidence || !implementation) return null;
  return { architecture, detail, evidence, implementation };
};

export const mountSystemsExperience = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const compactQuery = matchMedia(MOBILE_BREAKPOINT);
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
  const projectParts = entries.map(projectPartsFor);

  if (
    !root ||
    !intro ||
    !header ||
    !axis ||
    entries.length !== projects.length ||
    projectParts.some((parts) => parts === null)
  ) {
    return () => undefined;
  }

  const resolvedProjectParts = projectParts as ProjectParts[];
  document.documentElement.classList.add("systems-refined-ready");

  const {
    chapterSystemsNode,
    systemsStartNode,
    chapterGalleryNode,
  } = narrativeModel;
  const projectCount = projects.length;
  const initialRuntimeState = narrativeRuntime.getState();
  const initialProjectPosition = collectionPosition(
    initialRuntimeState.node,
    systemsStartNode,
    projectCount,
  );

  let latestState = initialRuntimeState;
  let latestChapterState = chapterState(
    initialRuntimeState.node,
    chapterSystemsNode,
    chapterGalleryNode,
    compactQuery.matches,
  );
  let targetProjectPosition = initialProjectPosition;
  let driveVelocity = 0;
  let inputLastTime = performance.now();
  let primaryMotionState: SpringState = {
    value: initialProjectPosition,
    velocity: 0,
  };
  let secondaryMotionState: SpringState = {
    value: initialProjectPosition,
    velocity: 0,
  };

  let motionFrame = 0;
  let motionLastTime = performance.now();
  let parallaxPending = false;
  let pointerPending = false;
  let pointerX = 0;
  let pointerY = 0;
  let pointerTargetX = 0;
  let pointerTargetY = 0;

  const syncMotionToTarget = () => {
    primaryMotionState = { value: targetProjectPosition, velocity: 0 };
    secondaryMotionState = { value: targetProjectPosition, velocity: 0 };
    driveVelocity = 0;
  };

  const stopMotion = () => {
    if (motionFrame) {
      cancelAnimationFrame(motionFrame);
      motionFrame = 0;
    }
    parallaxPending = false;
    pointerPending = false;
  };

  const renderParallax = (dt: number) => {
    driveVelocity = damp(driveVelocity, 0, 6.8, dt);

    const compact = compactQuery.matches;
    const leadScale = compact ? 0.70 : 1;
    const motionScale = compact ? 0.66 : 1;

    const primaryTarget =
      targetProjectPosition + driveVelocity * PRIMARY_MOTION.lead * leadScale;
    const secondaryTarget =
      targetProjectPosition + driveVelocity * SECONDARY_MOTION.lead * leadScale;

    primaryMotionState = springStep(
      primaryMotionState,
      primaryTarget,
      PRIMARY_MOTION,
      dt,
    );
    secondaryMotionState = springStep(
      secondaryMotionState,
      secondaryTarget,
      SECONDARY_MOTION,
      dt,
    );

    const maxLag = Math.max(
      Math.abs(primaryTarget - primaryMotionState.value),
      Math.abs(secondaryTarget - secondaryMotionState.value),
    );
    const maxVelocity = Math.max(
      Math.abs(primaryMotionState.velocity),
      Math.abs(secondaryMotionState.velocity),
    );
    const settled =
      Math.abs(driveVelocity) < VELOCITY_SETTLE_EPSILON &&
      maxLag < PARALLAX_SETTLE_EPSILON &&
      maxVelocity < VELOCITY_SETTLE_EPSILON;

    if (settled) {
      syncMotionToTarget();
    }

    const titlePosition = positionAtDepth(
      primaryMotionState,
      targetProjectPosition,
      TITLE_DEPTH,
    );
    const graphPosition = positionAtDepth(
      primaryMotionState,
      targetProjectPosition,
      GRAPH_DEPTH,
    );
    const axisPosition = positionAtDepth(
      primaryMotionState,
      targetProjectPosition,
      AXIS_DEPTH,
    );
    const implementationPosition = positionAtDepth(
      secondaryMotionState,
      targetProjectPosition,
      IMPLEMENTATION_DEPTH,
    );
    const detailPosition = positionAtDepth(
      secondaryMotionState,
      targetProjectPosition,
      DETAIL_DEPTH,
    );
    const evidencePosition = positionAtDepth(
      secondaryMotionState,
      targetProjectPosition,
      EVIDENCE_DEPTH,
    );
    const buildPosition = positionAtDepth(
      secondaryMotionState,
      targetProjectPosition,
      BUILD_DEPTH,
    );

    const titleVelocity = primaryMotionState.velocity * TITLE_DEPTH;
    const graphVelocity = primaryMotionState.velocity * GRAPH_DEPTH;
    const axisVelocity = primaryMotionState.velocity * AXIS_DEPTH;
    const detailVelocity = secondaryMotionState.velocity * DETAIL_DEPTH;
    const evidenceVelocity = secondaryMotionState.velocity * EVIDENCE_DEPTH;
    const implementationVelocity =
      secondaryMotionState.velocity * IMPLEMENTATION_DEPTH;

    const projectProgress =
      projectCount > 1 ? axisPosition / (projectCount - 1) : 0;
    stage.style.setProperty("--systems-progress", projectProgress.toFixed(5));

    axisItems.forEach((element, index) => {
      const offset = index - axisPosition;
      const focus = Math.exp(-(offset * offset) * 5.2);
      const inertialY = clamp(
        -axisVelocity * (compact ? 1.35 : 2.4),
        compact ? -3.5 : -6,
        compact ? 3.5 : 6,
      );
      element.style.visibility = "visible";
      element.style.opacity = (
        latestChapterState.contentReveal *
        (0.34 + focus * 0.66) *
        (1 - latestChapterState.tailOut * 0.72)
      ).toFixed(5);
      element.style.transform = `translate3d(0, calc(-50% + ${inertialY.toFixed(2)}px), 0)`;
      element.style.setProperty("--axis-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const parts = resolvedProjectParts[index];
      if (!parts) return;

      const titleOffset = index - titlePosition;
      const graphOffset = index - graphPosition;
      const detailOffset = index - detailPosition;
      const evidenceOffset = index - evidencePosition;
      const implementationOffset = index - implementationPosition;
      const buildOffset = index - buildPosition;

      const titleMotion = motionForOffset(titleOffset, compact);
      const graphMotion = motionForOffset(graphOffset, compact);
      const detailMotion = motionForOffset(detailOffset, compact);
      const evidenceMotion = motionForOffset(evidenceOffset, compact);
      const implementationMotion = motionForOffset(implementationOffset, compact);
      const buildMotion = motionForOffset(buildOffset, compact);

      const isLast = index === projectCount - 1;
      const tail = isLast ? latestChapterState.tailOut : 0;
      const firstProjectBuild = index === 0 ? latestChapterState.initialGraphBuild : 1;

      const titlePresence = titleMotion.title * (1 - tail);
      const graphPresence = graphMotion.graph * (1 - tail * 0.82);
      const detailPresence = detailMotion.support * (1 - tail * 0.94);
      const evidencePresence = evidenceMotion.support * (1 - tail * 0.91);
      const implementationPresence =
        implementationMotion.support * (1 - tail * 0.96);
      const supportPresence = Math.max(
        detailPresence,
        evidencePresence,
        implementationPresence,
      );
      const graphBuild = Math.min(buildMotion.build, firstProjectBuild);
      const extraTailY = isLast ? (compact ? -20 : -30) * tail : 0;
      const graphY =
        clamp(graphOffset, -1, 1) * (compact ? 1.35 : 2.15) -
        graphVelocity * (compact ? 0.10 : 0.16);
      const graphX =
        graphMotion.graphX - graphVelocity * (compact ? 0.016 : 0.026);
      const visibleDistance = Math.min(
        Math.abs(titleOffset),
        Math.abs(graphOffset),
        Math.abs(detailOffset),
        Math.abs(evidenceOffset),
        Math.abs(implementationOffset),
      );

      element.style.visibility =
        visibleDistance < 1.15 || (isLast && tail < 1) ? "visible" : "hidden";
      element.style.setProperty("--title-presence", titlePresence.toFixed(5));
      element.style.setProperty("--graph-presence", graphPresence.toFixed(5));
      element.style.setProperty("--support-presence", supportPresence.toFixed(5));
      element.style.setProperty("--title-focus", titleMotion.title.toFixed(5));
      element.style.setProperty("--graph-focus", graphMotion.graph.toFixed(5));
      element.style.setProperty("--support-focus", supportPresence.toFixed(5));
      element.style.setProperty("--graph-build", graphBuild.toFixed(5));
      element.style.setProperty("--system-offset", titleOffset.toFixed(5));
      element.style.setProperty(
        "--title-y",
        `${(
          titleMotion.titleY +
          extraTailY -
          titleVelocity * 0.18 * motionScale
        ).toFixed(3)}vh`,
      );

      parts.architecture.style.transform = `translate3d(${graphX.toFixed(3)}vw, ${graphY.toFixed(3)}vh, 0)`;
      parts.detail.style.opacity = (
        latestChapterState.contentReveal * detailPresence
      ).toFixed(5);
      parts.detail.style.transform = `translate3d(0, ${(
        detailMotion.supportY * 0.46 +
        extraTailY * 0.22 -
        detailVelocity * 0.09 * motionScale
      ).toFixed(3)}vh, 0)`;
      parts.evidence.style.opacity = (
        latestChapterState.contentReveal * evidencePresence
      ).toFixed(5);
      parts.evidence.style.transform = `translate3d(0, ${(
        evidenceMotion.supportY * 0.72 +
        extraTailY * 0.18 -
        evidenceVelocity * 0.075 * motionScale
      ).toFixed(3)}vh, 0)`;
      parts.implementation.style.opacity = (
        latestChapterState.contentReveal * implementationPresence
      ).toFixed(5);
      parts.implementation.style.transform = `translate3d(0, ${(
        implementationMotion.supportY * 0.34 +
        extraTailY * 0.13 -
        implementationVelocity * 0.055 * motionScale
      ).toFixed(3)}vh, 0)`;
    });

    parallaxPending = !settled;
  };

  const renderPointer = (dt: number) => {
    pointerX = damp(pointerX, pointerTargetX, 12, dt);
    pointerY = damp(pointerY, pointerTargetY, 12, dt);
    root.style.setProperty("--systems-pointer-x", pointerX.toFixed(4));
    root.style.setProperty("--systems-pointer-y", pointerY.toFixed(4));

    pointerPending =
      Math.abs(pointerX - pointerTargetX) > POINTER_SETTLE_EPSILON ||
      Math.abs(pointerY - pointerTargetY) > POINTER_SETTLE_EPSILON;
  };

  const renderMotion = (time: number) => {
    motionFrame = 0;
    if (latestState.scene !== "systems") return;

    const dt = frameDeltaSeconds(time, motionLastTime);
    motionLastTime = time;

    if (parallaxPending) renderParallax(dt);
    if (pointerPending) renderPointer(dt);

    if (parallaxPending || pointerPending) {
      motionFrame = requestAnimationFrame(renderMotion);
    }
  };

  const requestMotionRender = () => {
    if (motionFrame || latestState.scene !== "systems") return;
    motionLastTime = performance.now();
    motionFrame = requestAnimationFrame(renderMotion);
  };

  const onPointerMove = (event: PointerEvent) => {
    if (latestState.scene !== "systems") return;
    pointerTargetX = event.clientX / innerWidth - 0.5;
    pointerTargetY = event.clientY / innerHeight - 0.5;
    pointerPending = true;
    requestMotionRender();
  };

  const renderNarrative = (runtimeState: NarrativeState) => {
    latestState = runtimeState;
    const node = runtimeState.node;
    latestChapterState = chapterState(
      node,
      chapterSystemsNode,
      chapterGalleryNode,
      compactQuery.matches,
    );

    const now = performance.now();
    const nextPosition = collectionPosition(node, systemsStartNode, projectCount);

    if (runtimeState.scene === "systems") {
      const inputDt = frameDeltaSeconds(now, inputLastTime);
      const rawVelocity = clamp(
        (nextPosition - targetProjectPosition) / inputDt,
        -7,
        7,
      );
      driveVelocity = damp(driveVelocity, rawVelocity, 18, inputDt);
      targetProjectPosition = nextPosition;
      parallaxPending = true;
    } else {
      targetProjectPosition = nextPosition;
      syncMotionToTarget();
      stopMotion();
    }

    inputLastTime = now;

    stage.dataset.systemsRefined =
      node > chapterSystemsNode - 0.36 && node < chapterGalleryNode + 0.34
        ? "true"
        : "false";

    stage.style.setProperty(
      "--systems-editorial-visibility",
      latestChapterState.sectionVisibility.toFixed(5),
    );
    stage.style.setProperty(
      "--systems-axis-reveal",
      latestChapterState.axisReveal.toFixed(5),
    );
    stage.style.setProperty(
      "--systems-intro-in",
      latestChapterState.introIn.toFixed(5),
    );
    stage.style.setProperty(
      "--systems-intro-out",
      latestChapterState.introOut.toFixed(5),
    );
    stage.style.setProperty(
      "--systems-content",
      latestChapterState.contentReveal.toFixed(5),
    );
    stage.style.setProperty(
      "--systems-tail-out",
      latestChapterState.tailOut.toFixed(5),
    );
    stage.style.setProperty(
      "--systems-gallery-handoff",
      latestChapterState.galleryHandoff.toFixed(5),
    );

    root.style.opacity = "1";

    intro.style.opacity = latestChapterState.introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${(
      (1 - latestChapterState.introIn) * 60 -
      latestChapterState.introOut * 86
    ).toFixed(2)}px, 0)`;

    header.style.opacity = latestChapterState.headerReveal.toFixed(5);
    header.style.transform = `translate3d(0, ${(
      7 *
      (1 - latestChapterState.headerReveal)
    ).toFixed(2)}px, 0)`;
    axis.style.opacity = latestChapterState.axisReveal.toFixed(5);

    requestMotionRender();
  };

  const onCompactChange = () => {
    latestChapterState = chapterState(
      latestState.node,
      chapterSystemsNode,
      chapterGalleryNode,
      compactQuery.matches,
    );
    if (latestState.scene !== "systems") return;
    parallaxPending = true;
    requestMotionRender();
  };

  compactQuery.addEventListener("change", onCompactChange);
  addEventListener("pointermove", onPointerMove, { passive: true });
  const unsubscribe = narrativeRuntime.subscribe(renderNarrative);

  return () => {
    unsubscribe();
    compactQuery.removeEventListener("change", onCompactChange);
    stopMotion();
    removeEventListener("pointermove", onPointerMove);
    resolvedProjectParts.forEach((parts) => {
      parts.architecture.style.removeProperty("transform");
      parts.detail.style.removeProperty("opacity");
      parts.detail.style.removeProperty("transform");
      parts.evidence.style.removeProperty("opacity");
      parts.evidence.style.removeProperty("transform");
      parts.implementation.style.removeProperty("opacity");
      parts.implementation.style.removeProperty("transform");
    });
    root.style.removeProperty("--systems-pointer-x");
    root.style.removeProperty("--systems-pointer-y");
    delete stage.dataset.systemsRefined;
    [
      "--systems-editorial-visibility",
      "--systems-axis-reveal",
      "--systems-intro-in",
      "--systems-intro-out",
      "--systems-content",
      "--systems-progress",
      "--systems-tail-out",
      "--systems-gallery-handoff",
    ].forEach((property) => stage.style.removeProperty(property));
    document.documentElement.classList.remove("systems-refined-ready");
  };
};
