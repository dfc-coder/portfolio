import {
  damp,
  frameDeltaSeconds,
  springStep,
  type SpringConfig,
  type SpringState,
} from "../motion/inertia";
import { narrativeModel } from "./narrative-model";
import type { NarrativeState } from "./narrative-runtime";

const ENTRY_START_OFFSET = -0.76;
const ENTRY_END_OFFSET = 0.08;
const MOBILE_ENTRY_START_OFFSET = -1.04;
const MOBILE_ENTRY_END_OFFSET = -0.06;

// The outgoing archive needs materially more scroll distance than the incoming
// handoff. Mobile starts the exit slightly earlier so the Agent chapter never
// competes with a dense wall of artwork.
const EXIT_START_OFFSET = 0.48;
const EXIT_END_OFFSET = 1.30;
const EXIT_VISIBILITY_HOLD_OFFSET = 1.12;
const EXIT_VISIBILITY_END_OFFSET = 1.38;
const MOBILE_EXIT_START_OFFSET = 0.40;
const MOBILE_EXIT_END_OFFSET = 1.16;
const MOBILE_EXIT_VISIBILITY_HOLD_OFFSET = 0.98;
const MOBILE_EXIT_VISIBILITY_END_OFFSET = 1.24;

const MOBILE_BREAKPOINT = "(max-width: 680px)";
const VISIBILITY_MARGIN = 0.12;
const NODE_POSITION_EPSILON = 0.0004;
const NODE_VELOCITY_EPSILON = 0.0015;
const GOLDEN_RATIO_FRACTION = 0.61803398875;

const GLOBAL_MOTION: SpringConfig & { lead: number } = {
  frequency: 1.28,
  damping: 0.84,
  maxVelocity: 6.5,
  lead: 0.018,
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const clamp01 = (value: number) => clamp(value, 0, 1);

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

const fract = (value: number) => value - Math.floor(value);
const entryPhaseFor = (index: number) => fract(index * GOLDEN_RATIO_FRACTION);
const exitPhaseFor = (index: number) =>
  fract(0.55 + index * (1 - GOLDEN_RATIO_FRACTION));

const inertiaFor = (index: number, phase: number, velocity: number) => {
  const direction = index % 2 === 0 ? -1 : 1;
  return velocity * direction * (0.52 + phase * 0.58);
};

type CardMotion = {
  card: HTMLElement;
  entryDistance: number;
  exitDistance: number;
  entryPhase: number;
  exitPhase: number;
};

export type GalleryTransitionMotion = {
  onNarrative: (state: NarrativeState) => void;
  onResize: () => void;
  render: (dt: number) => boolean;
  destroy: () => void;
};

export const createGalleryTransitionMotion = (
  gallery: HTMLElement,
  galleryStage: HTMLElement,
  cards: HTMLElement[],
): GalleryTransitionMotion => {
  const compactQuery = matchMedia(MOBILE_BREAKPOINT);
  const { galleryStartNode, physicalLastNode } = narrativeModel;
  const initialState = narrativeModel.physicalLastNode
    ? 0
    : 0;
  let latestPhysicalNode = initialState;
  let previousPhysicalNode = latestPhysicalNode;
  let inputLastTime = performance.now();
  let driveVelocity = 0;
  let globalMotionState: SpringState = {
    value: latestPhysicalNode,
    velocity: 0,
  };
  let motionPending = false;
  let galleryMotionActive = false;
  let previousGalleryMotionOpacity = "";

  const motions: CardMotion[] = cards.map((card, index) => ({
    card,
    entryDistance: 80,
    exitDistance: 80,
    entryPhase: entryPhaseFor(index),
    exitPhase: exitPhaseFor(index),
  }));

  const timing = () => {
    const compact = compactQuery.matches;
    return {
      entryStart: compact ? MOBILE_ENTRY_START_OFFSET : ENTRY_START_OFFSET,
      entryEnd: compact ? MOBILE_ENTRY_END_OFFSET : ENTRY_END_OFFSET,
      exitStart: compact ? MOBILE_EXIT_START_OFFSET : EXIT_START_OFFSET,
      exitEnd: compact ? MOBILE_EXIT_END_OFFSET : EXIT_END_OFFSET,
      exitHold: compact
        ? MOBILE_EXIT_VISIBILITY_HOLD_OFFSET
        : EXIT_VISIBILITY_HOLD_OFFSET,
      exitVisibilityEnd: compact
        ? MOBILE_EXIT_VISIBILITY_END_OFFSET
        : EXIT_VISIBILITY_END_OFFSET,
      entryPhaseScale: compact ? 0.025 : 0.034,
      exitPhaseScale: compact ? 0.040 : 0.053,
    };
  };

  const measureDistances = () => {
    const viewportHeight = Math.max(1, gallery.clientHeight || innerHeight);
    const stageTop = galleryStage.offsetTop;

    motions.forEach((motion) => {
      const cardTop = stageTop + motion.card.offsetTop;
      const cardBottom = cardTop + motion.card.offsetHeight;
      const margin = Math.max(24, motion.card.offsetHeight * 0.18);

      motion.entryDistance = clamp(
        ((viewportHeight - cardTop + margin) / viewportHeight) * 100,
        48,
        118,
      );
      motion.exitDistance = clamp(
        ((cardBottom + margin) / viewportHeight) * 100,
        48,
        118,
      );
    });
  };

  const targetFor = (
    motion: CardMotion,
    index: number,
    physicalNode: number,
    velocity: number,
  ) => {
    const values = timing();
    const entryShift = motion.entryPhase * values.entryPhaseScale;
    const exitShift = motion.exitPhase * values.exitPhaseScale;
    const enter = range(
      physicalNode,
      galleryStartNode + values.entryStart + entryShift,
      galleryStartNode + values.entryEnd + entryShift,
    );
    const exit = range(
      physicalNode,
      galleryStartNode + values.exitStart + exitShift,
      galleryStartNode + values.exitEnd + exitShift,
    );

    return (
      motion.entryDistance * (1 - enter) -
      motion.exitDistance * exit +
      inertiaFor(index, motion.entryPhase, velocity)
    );
  };

  const transitionOpacityFor = (physicalNode: number) => {
    const values = timing();
    const compact = compactQuery.matches;
    const entryOpacity = range(
      physicalNode,
      galleryStartNode + values.entryStart - 0.04,
      galleryStartNode + (compact ? -0.42 : -0.22),
    );
    const exitOpacity =
      1 -
      range(
        physicalNode,
        galleryStartNode + values.exitHold,
        galleryStartNode + values.exitVisibilityEnd,
      );
    return entryOpacity * exitOpacity;
  };

  const renderCards = (physicalNode: number, velocity: number) => {
    motions.forEach((motion, index) => {
      const target = targetFor(motion, index, physicalNode, velocity);
      motion.card.style.translate = `0 ${target.toFixed(3)}vh`;
    });
  };

  const updateVisibilityOwnership = (physicalNode: number) => {
    const values = timing();
    const transitionStart =
      galleryStartNode + values.entryStart - VISIBILITY_MARGIN;
    const transitionEnd =
      galleryStartNode + values.exitVisibilityEnd + VISIBILITY_MARGIN;
    const active = physicalNode >= transitionStart && physicalNode <= transitionEnd;

    if (active) {
      if (!galleryMotionActive) {
        gallery.dataset.galleryMotion = "true";
        galleryMotionActive = true;
      }

      const nextOpacity = transitionOpacityFor(physicalNode).toFixed(5);
      if (nextOpacity !== previousGalleryMotionOpacity) {
        gallery.style.setProperty("--gallery-motion-opacity", nextOpacity);
        previousGalleryMotionOpacity = nextOpacity;
      }
      return;
    }

    if (galleryMotionActive) {
      delete gallery.dataset.galleryMotion;
      galleryMotionActive = false;
    }
    if (previousGalleryMotionOpacity !== "") {
      gallery.style.removeProperty("--gallery-motion-opacity");
      previousGalleryMotionOpacity = "";
    }
  };

  const setInitialPhysicalNode = (state: NarrativeState) => {
    latestPhysicalNode = state.physicalProgress * physicalLastNode;
    previousPhysicalNode = latestPhysicalNode;
    globalMotionState = { value: latestPhysicalNode, velocity: 0 };
    measureDistances();
    renderCards(latestPhysicalNode, 0);
    updateVisibilityOwnership(latestPhysicalNode);
  };

  const onNarrative = (state: NarrativeState) => {
    const now = performance.now();
    const physicalNode = state.physicalProgress * physicalLastNode;

    if (!motionPending && globalMotionState.value === 0 && latestPhysicalNode === 0) {
      setInitialPhysicalNode(state);
      inputLastTime = now;
      return;
    }

    const inputDt = frameDeltaSeconds(now, inputLastTime);
    const rawVelocity = clamp(
      (physicalNode - previousPhysicalNode) / inputDt,
      -5.5,
      5.5,
    );

    driveVelocity = damp(driveVelocity, rawVelocity, 14, inputDt);
    previousPhysicalNode = physicalNode;
    latestPhysicalNode = physicalNode;
    inputLastTime = now;
    updateVisibilityOwnership(physicalNode);
    motionPending = true;
  };

  const onResize = () => {
    measureDistances();
    updateVisibilityOwnership(latestPhysicalNode);
    motionPending = true;
  };

  const render = (dt: number) => {
    if (!motionPending) return false;

    driveVelocity = damp(driveVelocity, 0, 5.2, dt);
    const targetNode = latestPhysicalNode + driveVelocity * GLOBAL_MOTION.lead;
    globalMotionState = springStep(
      globalMotionState,
      targetNode,
      GLOBAL_MOTION,
      dt,
    );

    renderCards(globalMotionState.value, globalMotionState.velocity);

    const settled =
      Math.abs(driveVelocity) < NODE_VELOCITY_EPSILON &&
      Math.abs(targetNode - globalMotionState.value) < NODE_POSITION_EPSILON &&
      Math.abs(globalMotionState.velocity) < NODE_VELOCITY_EPSILON;

    if (settled) {
      driveVelocity = 0;
      globalMotionState = { value: latestPhysicalNode, velocity: 0 };
      renderCards(latestPhysicalNode, 0);
      motionPending = false;
    }

    return motionPending;
  };

  const onCompactChange = () => onResize();
  compactQuery.addEventListener("change", onCompactChange);

  return {
    onNarrative,
    onResize,
    render,
    destroy: () => {
      compactQuery.removeEventListener("change", onCompactChange);
      delete gallery.dataset.galleryMotion;
      gallery.style.removeProperty("--gallery-motion-opacity");
      motions.forEach((motion) => {
        motion.card.style.removeProperty("translate");
      });
    },
  };
};