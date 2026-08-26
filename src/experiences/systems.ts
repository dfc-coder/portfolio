import { damp, frameDeltaSeconds } from "../motion/inertia";
import {
  chapterState,
  collectionPosition,
  motionForOffset,
} from "./systems-motion-contract";
import { narrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeState } from "./narrative-runtime";
import { systemsProjects as projects } from "./systems-projects";

const PARALLAX_SETTLE_EPSILON = 0.00045;

const PARALLAX_LAYERS = [
  "axis",
  "implementation",
  "detail",
  "evidence",
  "build",
  "graph",
  "title",
] as const;

type ParallaxLayer = (typeof PARALLAX_LAYERS)[number];

const PARALLAX_RESPONSE: Record<ParallaxLayer, number> = {
  axis: 5.0,
  implementation: 5.8,
  detail: 6.8,
  evidence: 7.8,
  build: 7.2,
  graph: 9.4,
  title: 12.4,
};

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
  );
  let targetProjectPosition = initialProjectPosition;

  const layerPositions: Record<ParallaxLayer, number> = {
    axis: initialProjectPosition,
    implementation: initialProjectPosition,
    detail: initialProjectPosition,
    evidence: initialProjectPosition,
    build: initialProjectPosition,
    graph: initialProjectPosition,
    title: initialProjectPosition,
  };

  let parallaxFrame = 0;
  let parallaxLastTime = performance.now();
  let pointerFrame = 0;
  let pointerX = 0;
  let pointerY = 0;
  let pointerTargetX = 0;
  let pointerTargetY = 0;
  let pointerLastTime = performance.now();

  const renderPointer = (time: number) => {
    pointerFrame = 0;
    if (latestState.scene !== "systems") return;

    const dt = frameDeltaSeconds(time, pointerLastTime);
    pointerLastTime = time;
    pointerX = damp(pointerX, pointerTargetX, 12, dt);
    pointerY = damp(pointerY, pointerTargetY, 12, dt);
    root.style.setProperty("--systems-pointer-x", pointerX.toFixed(4));
    root.style.setProperty("--systems-pointer-y", pointerY.toFixed(4));

    if (
      Math.abs(pointerX - pointerTargetX) > 0.001 ||
      Math.abs(pointerY - pointerTargetY) > 0.001
    ) {
      pointerFrame = requestAnimationFrame(renderPointer);
    }
  };

  const requestPointerRender = () => {
    if (pointerFrame || latestState.scene !== "systems") return;
    pointerLastTime = performance.now();
    pointerFrame = requestAnimationFrame(renderPointer);
  };

  const renderParallax = (time: number) => {
    parallaxFrame = 0;
    const dt = frameDeltaSeconds(time, parallaxLastTime);
    parallaxLastTime = time;
    let maxLag = 0;

    PARALLAX_LAYERS.forEach((layer) => {
      layerPositions[layer] = damp(
        layerPositions[layer],
        targetProjectPosition,
        PARALLAX_RESPONSE[layer],
        dt,
      );
      maxLag = Math.max(
        maxLag,
        Math.abs(targetProjectPosition - layerPositions[layer]),
      );
    });

    const projectProgress =
      projectCount > 1 ? layerPositions.axis / (projectCount - 1) : 0;
    stage.style.setProperty("--systems-progress", projectProgress.toFixed(5));

    axisItems.forEach((element, index) => {
      const offset = index - layerPositions.axis;
      const focus = Math.exp(-(offset * offset) * 5.2);
      element.style.visibility = "visible";
      element.style.opacity = (
        latestChapterState.contentReveal *
        (0.34 + focus * 0.66) *
        (1 - latestChapterState.tailOut * 0.72)
      ).toFixed(5);
      element.style.transform = "translate3d(0, -50%, 0)";
      element.style.setProperty("--axis-focus", focus.toFixed(5));
    });

    entries.forEach((element, index) => {
      const titleOffset = index - layerPositions.title;
      const graphOffset = index - layerPositions.graph;
      const detailOffset = index - layerPositions.detail;
      const evidenceOffset = index - layerPositions.evidence;
      const implementationOffset = index - layerPositions.implementation;
      const buildOffset = index - layerPositions.build;

      const titleMotion = motionForOffset(titleOffset);
      const graphMotion = motionForOffset(graphOffset);
      const detailMotion = motionForOffset(detailOffset);
      const evidenceMotion = motionForOffset(evidenceOffset);
      const implementationMotion = motionForOffset(implementationOffset);
      const buildMotion = motionForOffset(buildOffset);

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
      const extraTailY = isLast ? -30 * tail : 0;
      const graphY = Math.max(-1, Math.min(1, graphOffset)) * 1.7;
      const visibleDistance = Math.min(
        Math.abs(titleOffset),
        Math.abs(graphOffset),
        Math.abs(detailOffset),
        Math.abs(evidenceOffset),
        Math.abs(implementationOffset),
      );

      element.style.visibility =
        visibleDistance < 1.12 || (isLast && tail < 1) ? "visible" : "hidden";
      element.style.setProperty("--title-presence", titlePresence.toFixed(5));
      element.style.setProperty("--graph-presence", graphPresence.toFixed(5));
      element.style.setProperty("--support-presence", supportPresence.toFixed(5));
      element.style.setProperty("--detail-presence", detailPresence.toFixed(5));
      element.style.setProperty("--evidence-presence", evidencePresence.toFixed(5));
      element.style.setProperty(
        "--implementation-presence",
        implementationPresence.toFixed(5),
      );
      element.style.setProperty("--title-focus", titleMotion.title.toFixed(5));
      element.style.setProperty("--graph-focus", graphMotion.graph.toFixed(5));
      element.style.setProperty("--support-focus", supportPresence.toFixed(5));
      element.style.setProperty("--graph-build", graphBuild.toFixed(5));
      element.style.setProperty("--system-offset", titleOffset.toFixed(5));
      element.style.setProperty(
        "--title-y",
        `${(titleMotion.titleY + extraTailY).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--detail-y",
        `${(detailMotion.supportY + extraTailY * 0.22).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--evidence-y",
        `${(evidenceMotion.supportY + extraTailY * 0.18).toFixed(3)}vh`,
      );
      element.style.setProperty(
        "--implementation-y",
        `${(implementationMotion.supportY + extraTailY * 0.13).toFixed(3)}vh`,
      );
      element.style.setProperty("--graph-x", `${graphMotion.graphX.toFixed(3)}vw`);
      element.style.setProperty("--graph-y", `${graphY.toFixed(3)}vh`);
    });

    if (maxLag > PARALLAX_SETTLE_EPSILON) {
      parallaxFrame = requestAnimationFrame(renderParallax);
    }
  };

  const requestParallaxRender = () => {
    if (parallaxFrame) return;
    parallaxLastTime = performance.now();
    parallaxFrame = requestAnimationFrame(renderParallax);
  };

  const onPointerMove = (event: PointerEvent) => {
    if (latestState.scene !== "systems") return;
    pointerTargetX = event.clientX / innerWidth - 0.5;
    pointerTargetY = event.clientY / innerHeight - 0.5;
    requestPointerRender();
  };

  const renderNarrative = (runtimeState: NarrativeState) => {
    latestState = runtimeState;
    const node = runtimeState.node;
    latestChapterState = chapterState(
      node,
      chapterSystemsNode,
      chapterGalleryNode,
    );
    targetProjectPosition = collectionPosition(
      node,
      systemsStartNode,
      projectCount,
    );

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

    requestParallaxRender();
  };

  addEventListener("pointermove", onPointerMove, { passive: true });
  const unsubscribe = narrativeRuntime.subscribe(renderNarrative);

  return () => {
    unsubscribe();
    if (parallaxFrame) cancelAnimationFrame(parallaxFrame);
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    removeEventListener("pointermove", onPointerMove);
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
      "--systems-pointer-x",
      "--systems-pointer-y",
    ].forEach((property) => stage.style.removeProperty(property));
    document.documentElement.classList.remove("systems-refined-ready");
  };
};
