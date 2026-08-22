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

/* Every project receives the same hold/travel interval. The first project no
   longer gets a longer implicit viewport than the rest of the collection. */
export const SYSTEMS_COLLECTION = {
  firstHoldEnd: 0.26,
  holdEnd: 0.26,
  travelEnd: 0.74,
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

export const motionForOffset = (offset: number): MotionState => {
  if (offset < 0) {
    const t = clamp01(-offset);
    return {
      title: 1 - range(t, 0.18, 0.46),
      graph: 1 - range(t, 0.62, 0.94),
      support: 1 - range(t, 0.28, 0.56),
      titleY: -30 * range(t, 0.06, 0.68),
      supportY: -10 * range(t, 0.12, 0.72),
      graphX: -1.1 * range(t, 0.18, 0.90),
      build: 1,
    };
  }

  const t = clamp01(1 - offset);
  return {
    title: range(t, 0.54, 0.82),
    graph: range(t, 0.20, 0.50),
    support: range(t, 0.62, 0.90),
    titleY: 30 * (1 - range(t, 0.34, 0.82)),
    supportY: 10 * (1 - range(t, 0.48, 0.90)),
    graphX: 1.8 * (1 - range(t, 0.14, 0.62)),
    build: range(t, 0.18, 0.88),
  };
};

export const chapterState = (
  node: number,
  chapterSystemsNode: number,
  chapterGalleryNode: number,
) => {
  const systemsDelta = node - chapterSystemsNode;
  const galleryDelta = node - chapterGalleryNode;

  const sectionIn = range(
    systemsDelta,
    SYSTEMS_TIMING.sectionIn[0],
    SYSTEMS_TIMING.sectionIn[1],
  );
  const sectionOut = range(galleryDelta, -0.08, 0.28);
  const introIn = range(
    systemsDelta,
    SYSTEMS_TIMING.introIn[0],
    SYSTEMS_TIMING.introIn[1],
  );
  const introOut = range(
    systemsDelta,
    SYSTEMS_TIMING.introOut[0],
    SYSTEMS_TIMING.introOut[1],
  );

  return {
    sectionVisibility: sectionIn * (1 - sectionOut),
    introIn,
    introOut,
    introVisibility: introIn * (1 - introOut),
    axisReveal: range(
      systemsDelta,
      SYSTEMS_TIMING.axisReveal[0],
      SYSTEMS_TIMING.axisReveal[1],
    ),
    headerReveal: range(
      systemsDelta,
      SYSTEMS_TIMING.headerReveal[0],
      SYSTEMS_TIMING.headerReveal[1],
    ),
    contentReveal: range(
      systemsDelta,
      SYSTEMS_TIMING.contentReveal[0],
      SYSTEMS_TIMING.contentReveal[1],
    ),
    initialGraphBuild: range(
      systemsDelta,
      SYSTEMS_TIMING.initialGraphBuild[0],
      SYSTEMS_TIMING.initialGraphBuild[1],
    ),
    tailOut: range(
      galleryDelta,
      SYSTEMS_TIMING.tailOut[0],
      SYSTEMS_TIMING.tailOut[1],
    ),
    galleryHandoff: range(
      galleryDelta,
      SYSTEMS_TIMING.galleryHandoff[0],
      SYSTEMS_TIMING.galleryHandoff[1],
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
