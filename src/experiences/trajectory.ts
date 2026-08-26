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

const PARALLAX_LAYERS = [
  "years",
  "eyebrow",
  "role",
  "context",
  "summary",
  "tags",
  "counter",
] as const;

type ParallaxLayer = (typeof PARALLAX_LAYERS)[number];

type LayerConfig = SpringConfig & {
  lead: number;
};

const PARALLAX_CONFIG: Record<ParallaxLayer, LayerConfig> = {
  years: { frequency: 1.15, damping: 0.88, lead: -0.038, maxVelocity: 5.0 },
  eyebrow: { frequency: 2.65, damping: 0.78, lead: 0.018, maxVelocity: 7.0 },
  role: { frequency: 3.15, damping: 0.70, lead: 0.034, maxVelocity: 8.0 },
  context: { frequency: 2.15, damping: 0.80, lead: 0.004, maxVelocity: 6.0 },
  summary: { frequency: 1.72, damping: 0.84, lead: -0.010, maxVelocity: 5.5 },
  tags: { frequency: 1.38, damping: 0.88, lead: -0.022, maxVelocity: 5.0 },
  counter: { frequency: 1.92, damping: 0.82, lead: -0.008, maxVelocity: 6.0 },
};

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

// Start revealing the next role earlier and let it acquire authority over a
// wider distance. The spring controls the inertia; this controls how abruptly
// the typography itself appears/disappears.
const entryPresence = (distance: number) =>
  smoother(clamp01((0.78 - distance) / 0.54));

const layerTravel = (offset: number, distance: number) =>
  offset * distance * (offset < 0 ? 0.82 : 1);

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
  const initialPosition = collectionPosition(
    narrativeRuntime.getState().node,
    careerStartNode,
    experiences.length,
  );

  let targetPosition = initialPosition;
  let driveVelocity = 0;
  let inputLastTime = performance.now();
  let latestContentReveal = 0;
  let motionFrame = 0;
  let motionLastTime = performance.now();

  const layerStates = Object.fromEntries(
    PARALLAX_LAYERS.map((layer) => [
      layer,
      { value: initialPosition, velocity: 0 } satisfies SpringState,
    ]),
  ) as Record<ParallaxLayer, SpringState>;

  const renderParallax = (time: number) => {
    motionFrame = 0;
    const dt = frameDeltaSeconds(time, motionLastTime);
    motionLastTime = time;
    driveVelocity = damp(driveVelocity, 0, 5.8, dt);

    let maxLag = 0;
    let maxVelocity = 0;

    PARALLAX_LAYERS.forEach((layer) => {
      const config = PARALLAX_CONFIG[layer];
      const drivenTarget = targetPosition + driveVelocity * config.lead;
      const next = springStep(layerStates[layer], drivenTarget, config, dt);
      layerStates[layer] = next;
      maxLag = Math.max(maxLag, Math.abs(drivenTarget - next.value));
      maxVelocity = Math.max(maxVelocity, Math.abs(next.velocity));
    });

    const settled =
      Math.abs(driveVelocity) < VELOCITY_SETTLE_EPSILON &&
      maxLag < PARALLAX_SETTLE_EPSILON &&
      maxVelocity < VELOCITY_SETTLE_EPSILON;

    if (settled) {
      PARALLAX_LAYERS.forEach((layer) => {
        layerStates[layer].value = targetPosition;
        layerStates[layer].velocity = 0;
      });
      driveVelocity = 0;
    }

    const timelineProgress =
      experiences.length > 1
        ? layerStates.years.value / (experiences.length - 1)
        : 0;
    stage.style.setProperty("--trajectory-timeline-progress", timelineProgress.toFixed(5));

    yearNodes.forEach((element, index) => {
      const offset = index - layerStates.years.value;
      const focus = Math.exp(-(offset * offset) * 3.45);
      const y = offset * 14.2;
      element.style.transform = `translate3d(0, calc(-50% + ${y.toFixed(3)}vh), 0)`;
      element.style.opacity = (latestContentReveal * Math.max(0.09, focus)).toFixed(5);
      element.style.setProperty("--year-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const roleOffset = index - layerStates.role.value;
      const eyebrowOffset = index - layerStates.eyebrow.value;
      const contextOffset = index - layerStates.context.value;
      const summaryOffset = index - layerStates.summary.value;
      const tagsOffset = index - layerStates.tags.value;
      const presence = entryPresence(Math.abs(roleOffset));
      const roleVelocity = layerStates.role.velocity;

      element.style.visibility = presence > 0.001 ? "visible" : "hidden";
      element.style.opacity = (latestContentReveal * presence).toFixed(5);
      element.style.setProperty("--entry-focus", presence.toFixed(5));
      element.style.setProperty("--entry-offset", roleOffset.toFixed(5));
      element.style.setProperty(
        "--role-y",
        `${(layerTravel(roleOffset, 6.25) - roleVelocity * 0.11).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--eyebrow-y",
        `${(layerTravel(eyebrowOffset, 4.45) - layerStates.eyebrow.velocity * 0.07).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--context-y",
        `${(layerTravel(contextOffset, 3.0) - layerStates.context.velocity * 0.045).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--summary-y",
        `${(layerTravel(summaryOffset, 2.25) - layerStates.summary.velocity * 0.032).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--tags-y",
        `${(layerTravel(tagsOffset, 1.7) - layerStates.tags.velocity * 0.024).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--entry-x",
        `${(
          (roleOffset < 0 ? roleOffset * 0.22 : roleOffset * -0.28) -
          roleVelocity * 0.018
        ).toFixed(3)}vw`,
      );
    });

    counterTrack.style.transform = `translate3d(0, ${(-layerStates.counter.value).toFixed(5)}em, 0)`;

    if (!settled) {
      motionFrame = requestAnimationFrame(renderParallax);
    }
  };

  const requestParallaxRender = () => {
    if (motionFrame) return;
    motionLastTime = performance.now();
    motionFrame = requestAnimationFrame(renderParallax);
  };

  const renderNarrative = (state: NarrativeState) => {
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

    const now = performance.now();
    const inputDt = frameDeltaSeconds(now, inputLastTime);
    const nextPosition = collectionPosition(node, careerStartNode, experiences.length);
    const rawVelocity = clamp((nextPosition - targetPosition) / inputDt, -5, 5);
    driveVelocity = damp(driveVelocity, rawVelocity, 14, inputDt);
    targetPosition = nextPosition;
    inputLastTime = now;
    latestContentReveal = contentReveal;

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

    root.style.opacity = trajectoryVisibility.toFixed(5);
    intro.style.opacity = introVisibility.toFixed(5);
    intro.style.transform = `translate3d(0, ${((1 - introIn) * 34 - introOut * 42).toFixed(2)}px, 0)`;

    header.style.opacity = (contentReveal * trajectoryVisibility).toFixed(5);
    header.style.transform = `translate3d(0, ${(10 * (1 - contentReveal)).toFixed(2)}px, 0)`;
    axis.style.opacity = (axisReveal * trajectoryVisibility).toFixed(5);

    requestParallaxRender();
  };

  const unsubscribe = narrativeRuntime.subscribe(renderNarrative);

  return () => {
    unsubscribe();
    if (motionFrame) cancelAnimationFrame(motionFrame);
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
