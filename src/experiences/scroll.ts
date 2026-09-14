import { transitionSectionNavigation } from "./continuity";
import { narrativeModel, type NarrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeScene } from "./narrative-runtime";

const SCROLL_STEP_VH = 56;
const SCENE_CROSSFADE_WIDTH = 0.34;
const MOBILE_SCENE_CROSSFADE_WIDTH = 0.22;
const MOBILE_BREAKPOINT = "(max-width: 680px)";
const GALLERY_EXIT_START = 0.72;
const GALLERY_EXIT_VIRTUAL_LEAD = 0.8;
const COMPOSITOR_VISIBILITY_EPSILON = 0.001;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

export const mapPhysicalProgressToVirtualProgress = (
  physicalProgress: number,
  model: NarrativeModel = narrativeModel,
) => {
  const physicalNode = clamp01(physicalProgress) * model.physicalLastNode;

  if (physicalNode <= model.galleryStartNode) {
    return clamp01(physicalNode / model.virtualLastNode);
  }

  if (physicalNode >= model.physicalChapterAgentNode) {
    const virtualNode =
      model.virtualChapterAgentNode +
      (physicalNode - model.physicalChapterAgentNode);
    return clamp01(virtualNode / model.virtualLastNode);
  }

  const galleryLocal =
    (physicalNode - model.galleryStartNode) /
    (model.physicalChapterAgentNode - model.galleryStartNode);

  if (galleryLocal <= GALLERY_EXIT_START) {
    return clamp01(model.galleryStartNode / model.virtualLastNode);
  }

  const exitProgress = smoother(
    (galleryLocal - GALLERY_EXIT_START) / (1 - GALLERY_EXIT_START),
  );
  const exitStartNode = model.virtualChapterAgentNode - GALLERY_EXIT_VIRTUAL_LEAD;
  const virtualNode =
    exitStartNode +
    (model.virtualChapterAgentNode - exitStartNode) * exitProgress;

  return clamp01(virtualNode / model.virtualLastNode);
};

const sceneForNode = (node: number, model: NarrativeModel): NarrativeScene => {
  if (node < 0.5) return "hero";
  if (node < model.careerStartNode - 0.5) return "chapter";
  if (node < model.chapterSystemsNode - 0.5) return "career";
  if (node < model.systemsStartNode - 0.5) return "chapter";
  if (node < model.chapterGalleryNode - 0.5) return "systems";
  if (node < model.galleryStartNode - 0.5) return "chapter";
  if (node < model.virtualChapterAgentNode - 0.5) return "gallery";
  if (node < model.virtualLastNode - 0.5) return "chapter";
  return "agent";
};

const crossfadeAt = (node: number, boundary: number, width: number) =>
  range(
    node,
    boundary - width / 2,
    boundary + width / 2,
  );

const sceneOpacities = (
  node: number,
  model: NarrativeModel,
  compact = false,
) => {
  const width = compact
    ? MOBILE_SCENE_CROSSFADE_WIDTH
    : SCENE_CROSSFADE_WIDTH;
  const heroToChapter = crossfadeAt(node, 0.5, width);
  const chapterToCareer = crossfadeAt(node, model.careerStartNode - 0.5, width);
  const careerToChapter = crossfadeAt(node, model.chapterSystemsNode - 0.5, width);
  const chapterToSystems = crossfadeAt(node, model.systemsStartNode - 0.5, width);
  const systemsToChapter = crossfadeAt(node, model.chapterGalleryNode - 0.5, width);
  const chapterToGallery = crossfadeAt(node, model.galleryStartNode - 0.5, width);
  const galleryToChapter = crossfadeAt(node, model.virtualChapterAgentNode - 0.5, width);
  const chapterToAgent = crossfadeAt(node, model.virtualLastNode - 0.5, width);

  return {
    hero: 1 - heroToChapter,
    chapterCareer: heroToChapter * (1 - chapterToCareer),
    career: chapterToCareer * (1 - careerToChapter),
    chapterSystems: careerToChapter * (1 - chapterToSystems),
    systems: chapterToSystems * (1 - systemsToChapter),
    chapterGallery: systemsToChapter * (1 - chapterToGallery),
    gallery: chapterToGallery * (1 - galleryToChapter),
    chapterAgent: galleryToChapter * (1 - chapterToAgent),
    agent: chapterToAgent,
  };
};

export const mountScrollSyncController = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return () => undefined;
  }

  const compactQuery = matchMedia(MOBILE_BREAKPOINT);
  const track = document.querySelector<HTMLElement>(".ref-track");
  const stage = document.querySelector<HTMLElement>(".ref-stage");

  if (!track || !stage) return () => undefined;
  if (track.dataset.scrollSyncOwner === "physical") return () => undefined;

  const sceneElements = {
    hero: stage.querySelector<HTMLElement>(".ref-scene--hero"),
    chapterCareer: stage.querySelector<HTMLElement>(
      '.ref-scene--chapter[data-chapter="career"]',
    ),
    career: stage.querySelector<HTMLElement>(".ref-scene--career"),
    chapterSystems: stage.querySelector<HTMLElement>(
      '.ref-scene--chapter[data-chapter="systems"]',
    ),
    systems: stage.querySelector<HTMLElement>(".ref-scene--systems"),
    chapterGallery: stage.querySelector<HTMLElement>(
      '.ref-scene--chapter[data-chapter="gallery"]',
    ),
    gallery: stage.querySelector<HTMLElement>(".ref-scene--gallery"),
    chapterAgent: stage.querySelector<HTMLElement>(
      '.ref-scene--chapter[data-chapter="agent"]',
    ),
    agent: stage.querySelector<HTMLElement>(".ref-scene--agent"),
  };

  const setCompositorActive = (
    element: HTMLElement | null,
    active: boolean,
  ) => {
    if (!element) return;

    if (active) {
      if (element.dataset.scrollCompositor !== "true") {
        element.dataset.scrollCompositor = "true";
      }
      return;
    }

    if (element.dataset.scrollCompositor !== undefined) {
      delete element.dataset.scrollCompositor;
    }
  };

  const updateCompositorOwnership = (
    opacity: ReturnType<typeof sceneOpacities>,
  ) => {
    const visible = (value: number) => value > COMPOSITOR_VISIBILITY_EPSILON;

    setCompositorActive(sceneElements.hero, visible(opacity.hero));
    setCompositorActive(
      sceneElements.chapterCareer,
      visible(opacity.chapterCareer),
    );
    setCompositorActive(
      sceneElements.career,
      visible(Math.max(opacity.chapterCareer, opacity.career)),
    );
    setCompositorActive(
      sceneElements.chapterSystems,
      visible(opacity.chapterSystems),
    );
    setCompositorActive(sceneElements.systems, visible(opacity.systems));
    setCompositorActive(
      sceneElements.chapterGallery,
      visible(opacity.chapterGallery),
    );
    setCompositorActive(sceneElements.gallery, visible(opacity.gallery));
    setCompositorActive(
      sceneElements.chapterAgent,
      visible(opacity.chapterAgent),
    );
    setCompositorActive(sceneElements.agent, visible(opacity.agent));
  };

  const model = narrativeModel;
  const trackHeightVh = 100 + model.physicalLastNode * SCROLL_STEP_VH;

  track.dataset.scrollSyncOwner = "physical";
  track.style.setProperty("height", `${trackHeightVh}vh`, "important");

  let trackStart = 0;
  let scrollDistance = 1;
  let latestScrollY = scrollY;
  let scrollFrame = 0;

  let previousScene = "";
  let previousProgress = "";
  let previousHero = "";
  let previousCareer = "";
  let previousSystems = "";
  let previousGallery = "";
  let previousAgent = "";
  let previousChapterCareer = "";
  let previousChapterSystems = "";
  let previousChapterGallery = "";
  let previousChapterAgent = "";

  const measure = () => {
    const rect = track.getBoundingClientRect();
    trackStart = scrollY + rect.top;
    scrollDistance = Math.max(1, track.offsetHeight - innerHeight);
  };

  const physicalProgressAt = (scrollPosition: number) =>
    clamp01((scrollPosition - trackStart) / scrollDistance);

  const applyState = (physicalProgress: number) => {
    const physical = clamp01(physicalProgress);
    const progress = mapPhysicalProgressToVirtualProgress(physical, model);
    const node = progress * model.virtualLastNode;
    const scene = sceneForNode(node, model);
    const opacity = sceneOpacities(node, model, compactQuery.matches);

    if (scene !== previousScene) {
      stage.dataset.scene = scene;
      previousScene = scene;
    }

    updateCompositorOwnership(opacity);

    const nextProgress = progress.toFixed(6);
    if (nextProgress !== previousProgress) {
      stage.style.setProperty("--progress", nextProgress);
      stage.style.setProperty("--scroll-director-progress", nextProgress);
      previousProgress = nextProgress;
    }

    const nextHero = opacity.hero.toFixed(6);
    if (nextHero !== previousHero) {
      stage.style.setProperty("--hero", nextHero);
      previousHero = nextHero;
    }

    const nextCareer = opacity.career.toFixed(6);
    if (nextCareer !== previousCareer) {
      stage.style.setProperty("--career", nextCareer);
      previousCareer = nextCareer;
    }

    const nextSystems = opacity.systems.toFixed(6);
    if (nextSystems !== previousSystems) {
      stage.style.setProperty("--systems", nextSystems);
      previousSystems = nextSystems;
    }

    const nextGallery = opacity.gallery.toFixed(6);
    if (nextGallery !== previousGallery) {
      stage.style.setProperty("--gallery", nextGallery);
      previousGallery = nextGallery;
    }

    const nextAgent = opacity.agent.toFixed(6);
    if (nextAgent !== previousAgent) {
      stage.style.setProperty("--agent", nextAgent);
      previousAgent = nextAgent;
    }

    const nextChapterCareer = opacity.chapterCareer.toFixed(6);
    if (nextChapterCareer !== previousChapterCareer) {
      stage.style.setProperty("--chapter-career", nextChapterCareer);
      previousChapterCareer = nextChapterCareer;
    }

    const nextChapterSystems = opacity.chapterSystems.toFixed(6);
    if (nextChapterSystems !== previousChapterSystems) {
      stage.style.setProperty("--chapter-systems", nextChapterSystems);
      previousChapterSystems = nextChapterSystems;
    }

    const nextChapterGallery = opacity.chapterGallery.toFixed(6);
    if (nextChapterGallery !== previousChapterGallery) {
      stage.style.setProperty("--chapter-gallery", nextChapterGallery);
      previousChapterGallery = nextChapterGallery;
    }

    const nextChapterAgent = opacity.chapterAgent.toFixed(6);
    if (nextChapterAgent !== previousChapterAgent) {
      stage.style.setProperty("--chapter-agent", nextChapterAgent);
      previousChapterAgent = nextChapterAgent;
    }

    narrativeRuntime.publish({
      physicalProgress: physical,
      progress,
      node,
      scene,
    });
  };

  const flushScroll = () => {
    scrollFrame = 0;
    applyState(physicalProgressAt(latestScrollY));
  };

  const scheduleScrollUpdate = () => {
    if (scrollFrame !== 0) return;
    scrollFrame = requestAnimationFrame(flushScroll);
  };

  const onNativeScroll = () => {
    latestScrollY = scrollY;
    scheduleScrollUpdate();
  };

  const physicalNodeTop = (node: number) => {
    const progress = clamp01(node / model.physicalLastNode);
    const maxScrollY = Math.max(0, document.documentElement.scrollHeight - innerHeight);
    return Math.min(maxScrollY, trackStart + scrollDistance * progress);
  };

  const jumpToPhysicalNode = (node: number) => {
    measure();
    window.scrollTo({
      top: physicalNodeTop(node),
      behavior: "auto",
    });
  };

  const indexButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>(".ref-index > button"),
  );
  const brand = document.querySelector<HTMLButtonElement>(".ref-brand");
  const indexToggle = document.querySelector<HTMLButtonElement>(".ref-index-toggle");

  const navigationNodes = new Map<HTMLButtonElement, number>();
  if (brand) navigationNodes.set(brand, 0);

  const indexNodes = [
    0,
    model.careerStartNode,
    model.systemsStartNode,
    model.galleryStartNode,
    model.physicalLastNode,
  ];

  indexButtons.forEach((button, index) => {
    const node = indexNodes[index];
    if (node !== undefined) navigationNodes.set(button, node);
  });

  const onNavigationClick = (event: MouseEvent) => {
    const button =
      (event.target as Element | null)?.closest<HTMLButtonElement>("button") ?? null;
    if (!button) return;

    const node = navigationNodes.get(button);
    if (node === undefined) return;

    event.preventDefault();
    const currentNode = physicalProgressAt(scrollY) * model.physicalLastNode;
    const direction = node >= currentNode ? 1 : -1;

    if (indexToggle?.getAttribute("aria-expanded") === "true") {
      indexToggle.click();
    }

    transitionSectionNavigation(() => jumpToPhysicalNode(node), direction);
  };

  const remeasureAndSchedule = () => {
    measure();
    latestScrollY = scrollY;
    scheduleScrollUpdate();
  };

  compactQuery.addEventListener("change", remeasureAndSchedule);
  addEventListener("click", onNavigationClick, true);
  addEventListener("scroll", onNativeScroll, { passive: true });
  addEventListener("resize", remeasureAndSchedule, { passive: true });

  remeasureAndSchedule();

  return () => {
    if (scrollFrame !== 0) cancelAnimationFrame(scrollFrame);
    compactQuery.removeEventListener("change", remeasureAndSchedule);
    removeEventListener("click", onNavigationClick, true);
    removeEventListener("scroll", onNativeScroll);
    removeEventListener("resize", remeasureAndSchedule);
    track.style.removeProperty("height");
    delete track.dataset.scrollSyncOwner;
    Object.values(sceneElements).forEach((element) => {
      if (element) delete element.dataset.scrollCompositor;
    });
    [
      "--progress",
      "--scroll-director-progress",
      "--hero",
      "--career",
      "--systems",
      "--gallery",
      "--agent",
      "--chapter-career",
      "--chapter-systems",
      "--chapter-gallery",
      "--chapter-agent",
    ].forEach((property) => stage.style.removeProperty(property));
  };
};