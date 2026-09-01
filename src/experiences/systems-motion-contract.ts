export type MotionState = {
  title: number;
  graph: number;
  support: number;
  titleY: number;
  supportY: number;
  graphX: number;
  build: number;
};

export const SYSTEMS_TIMING = {
  priorChapterOut: [-0.48, 0.16] as const,
  sectionIn: [-0.30, 0.02] as const,
  introIn: [0.02, 0.20] as const,
  introOut: [0.28, 0.44] as const,
  axisReveal: [0.40, 0.62] as const,
  headerReveal: [0.44, 0.66] as const,
  contentReveal: [0.58, 0.86] as const,
  initialGraphBuild: [0.66, 1.02] as const,
  tailOut: [-0.38, -0.02] as const,
  galleryHandoff: [0.02, 0.30] as const,
} as const;

export const MOBILE_SYSTEMS_TIMING = {
  priorChapterOut: [-0.42, 0.12] as const,
  sectionIn: [-0.26, 0.02] as const,
  introIn: [0.01, 0.17] as const,
  introOut: [0.24, 0.38] as const,
  axisReveal: [0.32, 0.50] as const,
  headerReveal: [0.34, 0.52] as const,
  contentReveal: [0.40, 0.66] as const,
  initialGraphBuild: [0.50, 0.82] as const,
  tailOut: [-0.32, -0.02] as const,
  galleryHandoff: [0.00, 0.22] as const,
} as const;

/* Spend more of each project interval travelling and less time snapping between
   fixed positions. This makes the handoff legible even on a quick wheel pass. */
export const SYSTEMS_COLLECTION = {
  firstHoldEnd: 0.16,
  holdEnd: 0.16,
  travelEnd: 0.90,
} as const;

export const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

export const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

export const collectionPosition = (
  nodePosition: number,
  startNode: number,
  count: number,
) => {
  const lastIndex = count - 1;
  const raw = Math.min(lastIndex, Math.max(0, nodePosition - startNode));
  if (raw >= lastIndex) return lastIndex;

  const index = Math.floor(raw);
  const local = raw - index;
  const holdEnd = SYSTEMS_COLLECTION.holdEnd;
  const travelEnd = SYSTEMS_COLLECTION.travelEnd;

  if (local <= holdEnd) return index;
  if (local >= travelEnd) return index + 1;
  return index + smoother((local - holdEnd) / (travelEnd - holdEnd));
};

export const motionForOffset = (
  offset: number,
  compact = false,
): MotionState => {
  if (compact) {
    if (offset < 0) {
      const t = clamp01(-offset);
      return {
        title: 1 - range(t, 0.20, 0.68),
        graph: 1 - range(t, 0.24, 0.70),
        support: 1 - range(t, 0.24, 0.72),
        titleY: -18 * range(t, 0.06, 0.82),
        supportY: -7 * range(t, 0.10, 0.86),
        graphX: -4 * range(t, 0.12, 0.90),
        build: 1,
      };
    }

    const t = clamp01(1 - offset);
    return {
      title: range(t, 0.40, 0.80),
      graph: range(t, 0.44, 0.82),
      support: range(t, 0.42, 0.84),
      titleY: 18 * (1 - range(t, 0.24, 0.82)),
      supportY: 7 * (1 - range(t, 0.30, 0.86)),
      graphX: 7 * (1 - range(t, 0.12, 0.90)),
      build: range(t, 0.08, 0.90),
    };
  }

  if (offset < 0) {
    const t = clamp01(-offset);
    return {
      // Outgoing content now spends longer fading and travelling out.
      title: 1 - range(t, 0.18, 0.58),
      graph: 1 - range(t, 0.24, 0.60),
      support: 1 - range(t, 0.24, 0.66),
      titleY: -32 * range(t, 0.05, 0.82),
      supportY: -11 * range(t, 0.08, 0.86),
      // Graph exits to the left, opposite to its incoming direction.
      graphX: -5.5 * range(t, 0.10, 0.92),
      build: 1,
    };
  }

  const t = clamp01(1 - offset);
  return {
    // Incoming content starts earlier but reaches full authority more slowly.
    title: range(t, 0.58, 0.90),
    graph: range(t, 0.60, 0.88),
    support: range(t, 0.56, 0.94),
    titleY: 32 * (1 - range(t, 0.26, 0.90)),
    supportY: 11 * (1 - range(t, 0.34, 0.94)),
    // Architecture enters clearly from the right instead of shadowing the
    // title's vertical travel. The longer range avoids a lateral snap.
    graphX: 10.5 * (1 - range(t, 0.10, 0.94)),
    build: range(t, 0.10, 0.96),
  };
};

export const chapterState = (
  node: number,
  chapterSystemsNode: number,
  chapterGalleryNode: number,
  compact = false,
) => {
  const timing = compact ? MOBILE_SYSTEMS_TIMING : SYSTEMS_TIMING;
  const systemsDelta = node - chapterSystemsNode;
  const galleryDelta = node - chapterGalleryNode;

  const sectionIn = range(
    systemsDelta,
    timing.sectionIn[0],
    timing.sectionIn[1],
  );
  const sectionOut = range(galleryDelta, -0.08, 0.28);
  const introIn = range(
    systemsDelta,
    timing.introIn[0],
    timing.introIn[1],
  );
  const introOut = range(
    systemsDelta,
    timing.introOut[0],
    timing.introOut[1],
  );

  return {
    sectionVisibility: sectionIn * (1 - sectionOut),
    introIn,
    introOut,
    introVisibility: introIn * (1 - introOut),
    axisReveal: range(
      systemsDelta,
      timing.axisReveal[0],
      timing.axisReveal[1],
    ),
    headerReveal: range(
      systemsDelta,
      timing.headerReveal[0],
      timing.headerReveal[1],
    ),
    contentReveal: range(
      systemsDelta,
      timing.contentReveal[0],
      timing.contentReveal[1],
    ),
    initialGraphBuild: range(
      systemsDelta,
      timing.initialGraphBuild[0],
      timing.initialGraphBuild[1],
    ),
    tailOut: range(
      galleryDelta,
      timing.tailOut[0],
      timing.tailOut[1],
    ),
    galleryHandoff: range(
      galleryDelta,
      timing.galleryHandoff[0],
      timing.galleryHandoff[1],
    ),
  };
};

export const priorChapterResidual = (systemsDelta: number) =>
  1 -
  range(
    systemsDelta,
    SYSTEMS_TIMING.priorChapterOut[0],
    SYSTEMS_TIMING.priorChapterOut[1],
  );