import {
  damp,
  frameDeltaSeconds,
  springStep,
  type SpringConfig,
  type SpringState,
} from "../motion/inertia";
import { narrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeState } from "./narrative-runtime";

const ENTRY_START_OFFSET = -0.76;
const ENTRY_END_OFFSET = 0.08;
const EXIT_START_OFFSET = 0.62;
const EXIT_END_OFFSET = 1.06;
const VISIBILITY_MARGIN = 0.10;
const POSITION_EPSILON = 0.03;
const VELOCITY_EPSILON = 0.08;

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const clamp01 = (value: number) => clamp(value, 0, 1);

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

type CardProfile = SpringConfig & {
  entryPhase: number;
  exitPhase: number;
  velocityLead: number;
};

type CardMotion = {
  card: HTMLElement;
  state: SpringState;
  profile: CardProfile;
  entryDistance: number;
  exitDistance: number;
};

const CARD_PROFILES: CardProfile[] = [
  { frequency: 1.42, damping: 0.80, maxVelocity: 138, entryPhase: 0.00, exitPhase: 0.12, velocityLead: -1.6 },
  { frequency: 1.02, damping: 0.90, maxVelocity: 96, entryPhase: 0.13, exitPhase: 0.02, velocityLead: 1.0 },
  { frequency: 1.28, damping: 0.84, maxVelocity: 118, entryPhase: 0.05, exitPhase: 0.16, velocityLead: -0.5 },
  { frequency: 1.62, damping: 0.76, maxVelocity: 148, entryPhase: 0.18, exitPhase: 0.07, velocityLead: -1.9 },
  { frequency: 1.12, damping: 0.88, maxVelocity: 104, entryPhase: 0.09, exitPhase: 0.20, velocityLead: 0.7 },
  { frequency: 1.34, damping: 0.82, maxVelocity: 124, entryPhase: 0.16, exitPhase: 0.04, velocityLead: -0.8 },
  { frequency: 0.96, damping: 0.92, maxVelocity: 90, entryPhase: 0.03, exitPhase: 0.18, velocityLead: 1.2 },
  { frequency: 1.54, damping: 0.78, maxVelocity: 142, entryPhase: 0.21, exitPhase: 0.10, velocityLead: -1.5 },
  { frequency: 1.18, damping: 0.86, maxVelocity: 108, entryPhase: 0.07, exitPhase: 0.22, velocityLead: 0.4 },
  { frequency: 1.48, damping: 0.79, maxVelocity: 134, entryPhase: 0.19, exitPhase: 0.00, velocityLead: -1.2 },
];

const profileFor = (index: number) =>
  CARD_PROFILES[index % CARD_PROFILES.length] ?? CARD_PROFILES[0];

export const mountGalleryTransition = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return () => undefined;
  }

  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const gallery = document.querySelector<HTMLElement>(".ref-scene--gallery");
  const galleryStage = gallery?.querySelector<HTMLElement>(".ref-gallery-stage");
  const cards = galleryStage
    ? Array.from(galleryStage.querySelectorAll<HTMLElement>(".ref-art-card"))
    : [];

  if (!stage || !gallery || !galleryStage || cards.length === 0) {
    return () => undefined;
  }

  const { galleryStartNode, physicalLastNode } = narrativeModel;
  let latestState = narrativeRuntime.getState();
  let latestPhysicalNode = latestState.physicalProgress * physicalLastNode;
  let previousPhysicalNode = latestPhysicalNode;
  let inputLastTime = performance.now();
  let motionLastTime = inputLastTime;
  let driveVelocity = 0;
  let motionFrame = 0;

  const motions: CardMotion[] = cards.map((card, index) => ({
    card,
    state: { value: 0, velocity: 0 },
    profile: profileFor(index),
    entryDistance: 80,
    exitDistance: 80,
  }));

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

  const targetFor = (motion: CardMotion, physicalNode: number, velocity: number) => {
    const entryShift = motion.profile.entryPhase * 0.16;
    const exitShift = motion.profile.exitPhase * 0.14;
    const enter = range(
      physicalNode,
      galleryStartNode + ENTRY_START_OFFSET + entryShift,
      galleryStartNode + ENTRY_END_OFFSET + entryShift,
    );
    const exit = range(
      physicalNode,
      galleryStartNode + EXIT_START_OFFSET + exitShift,
      galleryStartNode + EXIT_END_OFFSET + exitShift,
    );

    return (
      motion.entryDistance * (1 - enter) -
      motion.exitDistance * exit +
      velocity * motion.profile.velocityLead
    );
  };

  measureDistances();
  motions.forEach((motion) => {
    const target = targetFor(motion, latestPhysicalNode, 0);
    motion.state = { value: target, velocity: 0 };
    motion.card.style.translate = `0 ${target.toFixed(3)}vh`;
  });

  const updateVisibilityOwnership = (physicalNode: number) => {
    const transitionStart = galleryStartNode + ENTRY_START_OFFSET - VISIBILITY_MARGIN;
    const transitionEnd = galleryStartNode + EXIT_END_OFFSET + VISIBILITY_MARGIN;

    if (physicalNode >= transitionStart && physicalNode <= transitionEnd) {
      stage.dataset.galleryMotion = "true";
    } else {
      delete stage.dataset.galleryMotion;
    }
  };

  const renderMotion = (time: number) => {
    motionFrame = 0;
    const dt = frameDeltaSeconds(time, motionLastTime);
    motionLastTime = time;
    driveVelocity = damp(driveVelocity, 0, 5.6, dt);

    let maxPositionError = 0;
    let maxVelocity = 0;

    motions.forEach((motion) => {
      const target = targetFor(motion, latestPhysicalNode, driveVelocity);
      const next = springStep(motion.state, target, motion.profile, dt);
      motion.state = next;
      motion.card.style.translate = `0 ${next.value.toFixed(3)}vh`;
      maxPositionError = Math.max(maxPositionError, Math.abs(target - next.value));
      maxVelocity = Math.max(maxVelocity, Math.abs(next.velocity));
    });

    const settled =
      Math.abs(driveVelocity) < VELOCITY_EPSILON &&
      maxPositionError < POSITION_EPSILON &&
      maxVelocity < VELOCITY_EPSILON;

    if (!settled) {
      motionFrame = requestAnimationFrame(renderMotion);
    }
  };

  const requestMotionRender = () => {
    if (motionFrame) return;
    motionLastTime = performance.now();
    motionFrame = requestAnimationFrame(renderMotion);
  };

  const renderNarrative = (state: NarrativeState) => {
    latestState = state;
    const now = performance.now();
    const inputDt = frameDeltaSeconds(now, inputLastTime);
    const physicalNode = state.physicalProgress * physicalLastNode;
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
    requestMotionRender();
  };

  const onResize = () => {
    measureDistances();
    requestMotionRender();
  };

  addEventListener("resize", onResize, { passive: true });
  const unsubscribe = narrativeRuntime.subscribe(renderNarrative);

  return () => {
    unsubscribe();
    if (motionFrame) cancelAnimationFrame(motionFrame);
    removeEventListener("resize", onResize);
    delete stage.dataset.galleryMotion;
    motions.forEach((motion) => {
      motion.card.style.removeProperty("translate");
    });
  };
};
