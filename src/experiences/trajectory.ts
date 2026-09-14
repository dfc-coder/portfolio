import {
  damp,
  frameDeltaSeconds,
  springStep,
  type SpringConfig,
  type SpringState,
} from "../motion/inertia";
import { narrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeState } from "./narrative-runtime";
import { experiences } from "./trajectory-data";

const COLLECTION_HOLD_END = 0.16;
const COLLECTION_TRAVEL_END = 0.90;
const PARALLAX_SETTLE_EPSILON = 0.0004;
const VELOCITY_SETTLE_EPSILON = 0.0015;
const MOBILE_BREAKPOINT = "(max-width: 680px)";

type MotionConfig = SpringConfig & {
  lead: number;
};

const PRIMARY_MOTION: MotionConfig = {
  frequency: 3.0,
  damping: 0.72,
  lead: 0.030,
  maxVelocity: 8.0,
};

const SECONDARY_MOTION: MotionConfig = {
  frequency: 1.72,
  damping: 0.84,
  lead: -0.010,
  maxVelocity: 5.5,
};

const YEARS_DEPTH = 1.38;
const EYEBROW_DEPTH = 0.58;
const CONTEXT_DEPTH = 0.86;
const SUMMARY_DEPTH = 1.0;
const TAGS_DEPTH = 1.16;
const COUNTER_DEPTH = 0.88;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

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

// Desktop keeps the broad, layered handoff. On mobile the viewport cannot carry
// two large role titles at equal authority, so the visibility envelope narrows
// while the underlying spring/inertia remains intact.
const entryPresence = (distance: number, compact: boolean) =>
  compact
    ? smoother(clamp01((0.60 - distance) / 0.30))
    : smoother(clamp01((0.78 - distance) / 0.54));

const layerTravel = (offset: number, distance: number) =>
  offset * distance * (offset < 0 ? 0.82 : 1);

const positionAtDepth = (
  state: SpringState,
  target: number,
  depth: number,
) => target + (state.value - target) * depth;

export const mountTrajectoryExperience = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const compactQuery = matchMedia(MOBILE_BREAKPOINT);
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const heroScene = document.querySelector<HTMLElement>(".ref-scene--hero");
  const career = document.querySelector<HTMLElement>(".ref-scene--career");
  if (!stage || !heroScene || !career) return () => undefined;

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
  const initialRuntimeState = narrativeRuntime.getState();
  const initialPosition = collectionPosition(
    initialRuntimeState.node,
    careerStartNode,
    experiences.length,
  );

  let latestState = initialRuntimeState;
  let targetPosition = initialPosition;
  let driveVelocity = 0;
  let inputLastTime = performance.now();
  let latestContentReveal = 0;
  let motionFrame = 0;
  let motionLastTime = performance.now();
  let primaryMotionState: SpringState = { value: initialPosition, velocity: 0 };
  let secondaryMotionState: SpringState = { value: initialPosition, velocity: 0 };

  let previousTrajectoryActive = "";
  let previousHeroExit = "";
  let previousCueExit = "";
  let previousCueHandoffOpacity = "";
  let previousIntroIn = "";
  let previousIntroOut = "";
  let previousAxisReveal = "";
  let previousContent = "";
  let previousTimelineProgress = "";

  const syncMotionToTarget = () => {
    primaryMotionState = { value: targetPosition, velocity: 0 };
    secondaryMotionState = { value: targetPosition, velocity: 0 };
    driveVelocity = 0;
  };

  const stopMotion = () => {
    if (!motionFrame) return;
    cancelAnimationFrame(motionFrame);
    motionFrame = 0;
  };

  const renderParallax = (time: number) => {
    motionFrame = 0;
    if (latestState.scene !== "career") return;

    const dt = frameDeltaSeconds(time, motionLastTime);
    motionLastTime = time;
    driveVelocity = damp(driveVelocity, 0, 5.8, dt);

    const compact = compactQuery.matches;
    const travelScale = compact ? 0.62 : 1;
    const velocityScale = compact ? 0.52 : 1;
    const leadScale = compact ? 0.66 : 1;

    const primaryTarget =
      targetPosition + driveVelocity * PRIMARY_MOTION.lead * leadScale;
    const secondaryTarget =
      targetPosition + driveVelocity * SECONDARY_MOTION.lead * leadScale;

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

    const rolePosition = primaryMotionState.value;
    const yearsPosition = positionAtDepth(
      primaryMotionState,
      targetPosition,
      YEARS_DEPTH,
    );
    const eyebrowPosition = positionAtDepth(
      secondaryMotionState,
      targetPosition,
      EYEBROW_DEPTH,
    );
    const contextPosition = positionAtDepth(
      secondaryMotionState,
      targetPosition,
      CONTEXT_DEPTH,
    );
    const summaryPosition = positionAtDepth(
      secondaryMotionState,
      targetPosition,
      SUMMARY_DEPTH,
    );
    const tagsPosition = positionAtDepth(
      secondaryMotionState,
      targetPosition,
      TAGS_DEPTH,
    );
    const counterPosition = positionAtDepth(
      secondaryMotionState,
      targetPosition,
      COUNTER_DEPTH,
    );

    const roleVelocity = primaryMotionState.velocity;
    const eyebrowVelocity = secondaryMotionState.velocity * EYEBROW_DEPTH;
    const contextVelocity = secondaryMotionState.velocity * CONTEXT_DEPTH;
    const summaryVelocity = secondaryMotionState.velocity * SUMMARY_DEPTH;
    const tagsVelocity = secondaryMotionState.velocity * TAGS_DEPTH;

    const timelineProgress =
      experiences.length > 1 ? yearsPosition / (experiences.length - 1) : 0;
    const nextTimelineProgress = timelineProgress.toFixed(5);
    if (nextTimelineProgress !== previousTimelineProgress) {
      root.style.setProperty("--trajectory-timeline-progress", nextTimelineProgress);
      previousTimelineProgress = nextTimelineProgress;
    }

    yearNodes.forEach((element, index) => {
      const offset = index - yearsPosition;
      const focus = Math.exp(-(offset * offset) * 3.45);
      const y = offset * (compact ? 10.2 : 14.2);
      element.style.transform = `translate3d(0, calc(-50% + ${y.toFixed(3)}vh), 0)`;
      element.style.opacity = (latestContentReveal * Math.max(0.09, focus)).toFixed(5);
      element.style.setProperty("--year-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const roleOffset = index - rolePosition;
      const eyebrowOffset = index - eyebrowPosition;
      const contextOffset = index - contextPosition;
      const summaryOffset = index - summaryPosition;
      const tagsOffset = index - tagsPosition;
      const presence = entryPresence(Math.abs(roleOffset), compact);

      element.style.visibility = presence > 0.001 ? "visible" : "hidden";
      element.style.opacity = (latestContentReveal * presence).toFixed(5);
      element.style.setProperty("--entry-focus", presence.toFixed(5));
      element.style.setProperty("--entry-offset", roleOffset.toFixed(5));
      element.style.setProperty(
        "--role-y",
        `${(
          layerTravel(roleOffset, 6.25 * travelScale) -
          roleVelocity * 0.11 * velocityScale
        ).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--eyebrow-y",
        `${(
          layerTravel(eyebrowOffset, 4.45 * travelScale) -
          eyebrowVelocity * 0.07 * velocityScale
        ).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--context-y",
        `${(
          layerTravel(contextOffset, 3.0 * travelScale) -
          contextVelocity * 0.045 * velocityScale
        ).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--summary-y",
        `${(
          layerTravel(summaryOffset, 2.25 * travelScale) -
          summaryVelocity * 0.032 * velocityScale
        ).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--tags-y",
        `${(
          layerTravel(tagsOffset, 1.7 * travelScale) -
          tagsVelocity * 0.024 * velocityScale
        ).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--entry-x",
        `${(
          ((roleOffset < 0 ? roleOffset * 0.22 : roleOffset * -0.28) -
            roleVelocity * 0.018) *
          (compact ? 0.44 : 1)
        ).toFixed(3)}vw`,
      );
    });

    counterTrack.style.transform = `translate3d(0, ${(-counterPosition).toFixed(5)}em, 0)`;

    if (!settled) {
      motionFrame = requestAnimationFrame(renderParallax);
    }
  };

  const requestParallaxRender = () => {
    if (motionFrame || latestState.scene !== "career") return;
    motionLastTime = performance.now();
    motionFrame = requestAnimationFrame(renderParallax);
  };

  const renderNarrative = (state: NarrativeState) => {
    latestState = state;
    const node = state.node;

    const heroExit = range(node, 0.10, 0.86);
    const cueExit = range(node, 0.24, 1.06);

    const trajectoryIn = range(node, 0.26, 0.56);
    const trajectoryOut = range(node, chapterSystemsNode - 0.48, chapterSystemsNode + 0.16);
    const trajectoryVisibility = trajectoryIn * (1 - trajectoryOut);

    const introIn = range(node, 0.56, 0.82);
    const introOut = range(node, 1.06, 1.32);
    const introVisibility = introIn * (1 - introOut);

    const axisReveal = range(node, 1.18, 1.52);
    const contentReveal = range(node, 1.34, 1.74);

    const now = performance.now();
    const nextPosition = collectionPosition(node, careerStartNode, experiences.length);

    if (state.scene === "career") {
      const inputDt = frameDeltaSeconds(now, inputLastTime);
      const rawVelocity = clamp((nextPosition - targetPosition) / inputDt, -5, 5);
      driveVelocity = damp(driveVelocity, rawVelocity, 14, inputDt);
      targetPosition = nextPosition;
    } else {
      targetPosition = nextPosition;
      syncMotionToTarget();
      stopMotion();
    }

    inputLastTime = now;
    latestContentReveal = contentReveal;

    const nextTrajectoryActive =
      node > 0.12 && node < chapterSystemsNode + 0.18 ? "true" : "false";
    if (nextTrajectoryActive !== previousTrajectoryActive) {
      stage.dataset.trajectory = nextTrajectoryActive;
      previousTrajectoryActive = nextTrajectoryActive;
    }

    const nextHeroExit = heroExit.toFixed(5);
    if (nextHeroExit !== previousHeroExit) {
      heroScene.style.setProperty("--trajectory-hero-exit", nextHeroExit);
      previousHeroExit = nextHeroExit;
    }

    const nextCueExit = cueExit.toFixed(5);
    if (nextCueExit !== previousCueExit) {
      heroScene.style.setProperty("--trajectory-cue-exit", nextCueExit);
      previousCueExit = nextCueExit;
    }

    const nextCueHandoffOpacity = (
      (1 - axisReveal) *
      (1 - cueExit * 0.35)
    ).toFixed(5);
    if (nextCueHandoffOpacity !== previousCueHandoffOpacity) {
      heroScene.style.setProperty(
        "--trajectory-cue-handoff-opacity",
        nextCueHandoffOpacity,
      );
      previousCueHandoffOpacity = nextCueHandoffOpacity;
    }

    const nextIntroIn = introIn.toFixed(5);
    if (nextIntroIn !== previousIntroIn) {
      root.style.setProperty("--trajectory-intro-in", nextIntroIn);
      previousIntroIn = nextIntroIn;
    }

    const nextIntroOut = introOut.toFixed(5);
    if (nextIntroOut !== previousIntroOut) {
      root.style.setProperty("--trajectory-intro-out", nextIntroOut);
      previousIntroOut = nextIntroOut;
    }

    const nextAxisReveal = axisReveal.toFixed(5);
    if (nextAxisReveal !== previousAxisReveal) {
      root.style.setProperty("--trajectory-axis-reveal", nextAxisReveal);
      previousAxisReveal = nextAxisReveal;
    }

    const nextContent = contentReveal.toFixed(5);
    if (nextContent !== previousContent) {
      root.style.setProperty("--trajectory-content", nextContent);
      previousContent = nextContent;
    }

    root.style.opacity = trajectoryVisibility.toFixed(5);
    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${((1 - introIn) * 34 - introOut * 42).toFixed(2)}px, 0)`;

    header.style.opacity = (contentReveal * trajectoryVisibility).toFixed(5);
    header.style.transform = `translate3d(0, ${(10 * (1 - contentReveal)).toFixed(2)}px, 0)`;
    axis.style.opacity = (axisReveal * trajectoryVisibility).toFixed(5);

    requestParallaxRender();
  };

  const onCompactChange = () => requestParallaxRender();
  compactQuery.addEventListener("change", onCompactChange);
  const unsubscribe = narrativeRuntime.subscribe(renderNarrative);

  return () => {
    unsubscribe();
    compactQuery.removeEventListener("change", onCompactChange);
    stopMotion();
    delete stage.dataset.trajectory;
    [
      "--trajectory-hero-exit",
      "--trajectory-cue-exit",
      "--trajectory-cue-handoff-opacity",
    ].forEach((property) => heroScene.style.removeProperty(property));
    [
      "--trajectory-intro-in",
      "--trajectory-intro-out",
      "--trajectory-axis-reveal",
      "--trajectory-content",
      "--trajectory-timeline-progress",
    ].forEach((property) => root.style.removeProperty(property));
  };
};
