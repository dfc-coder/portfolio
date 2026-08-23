import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { transitionSectionNavigation } from "./continuity";
import { narrativeModel, type NarrativeModel } from "./narrative-model";
import { narrativeRuntime, type NarrativeScene } from "./narrative-runtime";

const SCROLL_STEP_VH = 56;
const SCENE_CROSSFADE_WIDTH = 0.34;
const GALLERY_EXIT_START = 0.72;
const GALLERY_EXIT_VIRTUAL_LEAD = 0.8;
const WHEEL_GAIN = 1.08;
const SCROLL_RESPONSE = 15;
const MAX_FRAME_DT = 0.05;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

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

const crossfadeAt = (node: number, boundary: number) =>
  range(
    node,
    boundary - SCENE_CROSSFADE_WIDTH / 2,
    boundary + SCENE_CROSSFADE_WIDTH / 2,
  );

const sceneOpacities = (node: number, model: NarrativeModel) => {
  const heroToChapter = crossfadeAt(node, 0.5);
  const chapterToCareer = crossfadeAt(node, model.careerStartNode - 0.5);
  const careerToChapter = crossfadeAt(node, model.chapterSystemsNode - 0.5);
  const chapterToSystems = crossfadeAt(node, model.systemsStartNode - 0.5);
  const systemsToChapter = crossfadeAt(node, model.chapterGalleryNode - 0.5);
  const chapterToGallery = crossfadeAt(node, model.galleryStartNode - 0.5);
  const galleryToChapter = crossfadeAt(node, model.virtualChapterAgentNode - 0.5);
  const chapterToAgent = crossfadeAt(node, model.virtualLastNode - 0.5);

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

const wheelDeltaPixels = (event: WheelEvent) => {
  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 16;
  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * innerHeight;
  return event.deltaY;
};

const nestedScrollerCanConsume = (target: EventTarget | null, delta: number) => {
  const element = target instanceof Element ? target : null;
  const scroller = element?.closest<HTMLElement>(".agent-lane");
  if (!scroller) return false;

  if (delta < 0) return scroller.scrollTop > 0;
  return scroller.scrollTop + scroller.clientHeight < scroller.scrollHeight - 1;
};

export const mountScrollSyncController = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return () => undefined;
  }

  const track = document.querySelector<HTMLElement>(".ref-track");
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const portfolio = document.querySelector<HTMLElement>(".ref-portfolio");
  const progressCurrent = document.querySelector<HTMLElement>(
    ".ref-progress > span:first-child",
  );

  if (!track || !stage || !portfolio) return () => undefined;
  if (track.dataset.scrollSyncOwner === "physical") return () => undefined;

  // ScrollTrigger is the single source of truth for physical scroll progress.
  gsap.registerPlugin(ScrollTrigger);

  const model = narrativeModel;
  const trackHeightVh = 100 + model.physicalLastNode * SCROLL_STEP_VH;

  track.dataset.scrollSyncOwner = "physical";
  track.style.setProperty("height", `${trackHeightVh}vh`, "important");

  const applyState = (physicalProgress: number) => {
    const physical = clamp01(physicalProgress);
    const progress = mapPhysicalProgressToVirtualProgress(physical, model);
    const node = progress * model.virtualLastNode;
    const scene = sceneForNode(node, model);
    const opacity = sceneOpacities(node, model);

    portfolio.style.setProperty("--physical-scroll-progress", physical.toFixed(5));
    progressCurrent?.setAttribute(
      "data-scroll-progress",
      String(Math.round(physical * 100)).padStart(2, "0"),
    );

    stage.dataset.scene = scene;
    stage.style.setProperty("--progress", progress.toFixed(6));
    stage.style.setProperty("--scroll-director-progress", progress.toFixed(6));
    stage.style.setProperty("--hero", opacity.hero.toFixed(6));
    stage.style.setProperty("--career", opacity.career.toFixed(6));
    stage.style.setProperty("--systems", opacity.systems.toFixed(6));
    stage.style.setProperty("--gallery", opacity.gallery.toFixed(6));
    stage.style.setProperty("--agent", opacity.agent.toFixed(6));
    stage.style.setProperty("--chapter-career", opacity.chapterCareer.toFixed(6));
    stage.style.setProperty("--chapter-systems", opacity.chapterSystems.toFixed(6));
    stage.style.setProperty("--chapter-gallery", opacity.chapterGallery.toFixed(6));
    stage.style.setProperty("--chapter-agent", opacity.chapterAgent.toFixed(6));

    narrativeRuntime.publish({
      physicalProgress: physical,
      progress,
      node,
      scene,
    });
  };

  // This loop exists only while physical scrolling is settling. It is not a
  // second narrative clock: ScrollTrigger still observes the resulting scroll
  // position and publishes the canonical state above.
  let smoothFrame = 0;
  let currentScrollY = scrollY;
  let targetScrollY = scrollY;
  let lastFrameTime = performance.now();

  const maxScrollY = () =>
    Math.max(0, document.documentElement.scrollHeight - innerHeight);

  const stopSmoothScroll = () => {
    if (smoothFrame) cancelAnimationFrame(smoothFrame);
    smoothFrame = 0;
    currentScrollY = scrollY;
    targetScrollY = scrollY;
  };

  const runSmoothScroll = (time: number) => {
    const dt = Math.min(MAX_FRAME_DT, Math.max(0.001, (time - lastFrameTime) / 1000));
    lastFrameTime = time;
    currentScrollY = damp(currentScrollY, targetScrollY, SCROLL_RESPONSE, dt);

    if (Math.abs(targetScrollY - currentScrollY) < 0.25) {
      currentScrollY = targetScrollY;
      scrollTo(0, currentScrollY);
      smoothFrame = 0;
      return;
    }

    scrollTo(0, currentScrollY);
    smoothFrame = requestAnimationFrame(runSmoothScroll);
  };

  const smoothTo = (top: number) => {
    targetScrollY = clamp(top, 0, maxScrollY());
    if (!smoothFrame) {
      currentScrollY = scrollY;
      lastFrameTime = performance.now();
      smoothFrame = requestAnimationFrame(runSmoothScroll);
    }
  };

  const physicalNodeTop = (node: number) => {
    const rect = track.getBoundingClientRect();
    const start = scrollY + rect.top;
    const distance = Math.max(1, track.offsetHeight - innerHeight);
    const progress = clamp01(node / model.physicalLastNode);
    return {
      progress,
      top: start + distance * progress,
    };
  };

  const jumpToPhysicalNode = (node: number) => {
    stopSmoothScroll();
    const target = physicalNodeTop(node);
    scrollTo({ top: target.top, behavior: "auto" });
    applyState(target.progress);
    ScrollTrigger.update();
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
    stopSmoothScroll();
    const currentNode = trigger.progress * model.physicalLastNode;
    const direction = node >= currentNode ? 1 : -1;

    if (indexToggle?.getAttribute("aria-expanded") === "true") {
      indexToggle.click();
    }

    transitionSectionNavigation(() => jumpToPhysicalNode(node), direction);
  };

  const onWheel = (event: WheelEvent) => {
    if (event.ctrlKey || event.metaKey) return;

    if (document.documentElement.classList.contains("is-section-transitioning")) {
      event.preventDefault();
      return;
    }

    if (
      stage.dataset.scene === "gallery" &&
      document.querySelector(".ref-gallery-focus.is-open")
    ) {
      event.preventDefault();
      return;
    }

    const delta = wheelDeltaPixels(event);
    if (!delta || nestedScrollerCanConsume(event.target, delta)) return;

    event.preventDefault();
    const origin = smoothFrame ? targetScrollY : scrollY;
    smoothTo(origin + delta * WHEEL_GAIN);
  };

  const onNativeScroll = () => {
    if (smoothFrame) return;
    currentScrollY = scrollY;
    targetScrollY = scrollY;
  };

  const onNativeNavigation = (event: KeyboardEvent) => {
    if (
      ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(
        event.key,
      )
    ) {
      stopSmoothScroll();
    }
  };

  const trigger = ScrollTrigger.create({
    trigger: track,
    start: "top top",
    end: "bottom bottom",
    invalidateOnRefresh: true,
    onUpdate: (self) => applyState(self.progress),
    onRefresh: (self) => applyState(self.progress),
  });

  addEventListener("click", onNavigationClick, true);
  addEventListener("wheel", onWheel, { capture: true, passive: false });
  addEventListener("scroll", onNativeScroll, { passive: true });
  addEventListener("keydown", onNativeNavigation);
  addEventListener("pointerdown", stopSmoothScroll, { passive: true });

  applyState(trigger.progress);
  ScrollTrigger.refresh();

  return () => {
    trigger.kill();
    stopSmoothScroll();
    removeEventListener("click", onNavigationClick, true);
    removeEventListener("wheel", onWheel, true);
    removeEventListener("scroll", onNativeScroll);
    removeEventListener("keydown", onNativeNavigation);
    removeEventListener("pointerdown", stopSmoothScroll);
    track.style.removeProperty("height");
    delete track.dataset.scrollSyncOwner;
    portfolio.style.removeProperty("--physical-scroll-progress");
    progressCurrent?.removeAttribute("data-scroll-progress");
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
