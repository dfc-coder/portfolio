import { ScrollTrigger } from "gsap/ScrollTrigger";

const FALLBACK_EXPERIENCE_COUNT = 3;
const FALLBACK_SYSTEM_COUNT = 5;
const FALLBACK_ARTWORK_COUNT = 10;
const SCROLL_STEP_VH = 36;
const MAX_INSTALL_ATTEMPTS = 120;
const SCENE_CROSSFADE_WIDTH = 0.46;
const GALLERY_EXIT_START = 0.72;
const GALLERY_EXIT_VIRTUAL_LEAD = 0.8;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const smoother = (value: number) => {
  const x = clamp01(value);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const range = (value: number, start: number, end: number) =>
  smoother((value - start) / (end - start));

type SceneName = "hero" | "chapter" | "career" | "systems" | "gallery" | "agent";

type ScrollModel = {
  careerStartNode: number;
  chapterSystemsNode: number;
  systemsStartNode: number;
  chapterGalleryNode: number;
  galleryStartNode: number;
  virtualChapterAgentNode: number;
  virtualLastNode: number;
  physicalChapterAgentNode: number;
  physicalLastNode: number;
};

const buildScrollModel = (): ScrollModel => {
  const experienceCount =
    document.querySelectorAll(".ref-career-nav button").length || FALLBACK_EXPERIENCE_COUNT;
  const systemCount =
    document.querySelectorAll(".ref-system-nav button").length || FALLBACK_SYSTEM_COUNT;
  const artworkCount =
    document.querySelectorAll(".ref-art-card").length || FALLBACK_ARTWORK_COUNT;

  const careerStartNode = 2;
  const chapterSystemsNode = careerStartNode + experienceCount;
  const systemsStartNode = chapterSystemsNode + 1;
  const chapterGalleryNode = systemsStartNode + systemCount;
  const galleryStartNode = chapterGalleryNode + 1;
  const virtualChapterAgentNode = galleryStartNode + artworkCount;
  const virtualLastNode = virtualChapterAgentNode + 1;
  const physicalChapterAgentNode = galleryStartNode + 1;
  const physicalLastNode = physicalChapterAgentNode + 1;

  return {
    careerStartNode,
    chapterSystemsNode,
    systemsStartNode,
    chapterGalleryNode,
    galleryStartNode,
    virtualChapterAgentNode,
    virtualLastNode,
    physicalChapterAgentNode,
    physicalLastNode,
  };
};

/**
 * Maps the real document position to the legacy virtual chapter model.
 *
 * The gallery no longer has ten physical scroll steps. While the gallery is on
 * screen its virtual progress is intentionally held still; only the final part
 * of the physical interval is used to reveal Chapter 05. This avoids the old
 * 10x progress acceleration that made the gallery/agent handoff and parallax
 * look detached from the scrollbar.
 */
export const mapPhysicalProgressToVirtualProgress = (
  physicalProgress: number,
  model: ScrollModel,
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

const sceneForNode = (node: number, model: ScrollModel): SceneName => {
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

const sceneOpacities = (node: number, model: ScrollModel) => {
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

  const model = buildScrollModel();
  const trackHeightVh = 100 + model.physicalLastNode * SCROLL_STEP_VH;

  track.dataset.scrollSyncOwner = "physical";
  track.style.setProperty("height", `${trackHeightVh}vh`, "important");

  let latestPhysicalProgress = 0;
  let latestVirtualProgress = 0;
  let authoritativeFrame = 0;

  const syncProgressChrome = (physicalProgress: number) => {
    const progress = clamp01(physicalProgress);
    portfolio.style.setProperty("--physical-scroll-progress", progress.toFixed(5));
    progressCurrent?.setAttribute(
      "data-scroll-progress",
      String(Math.round(progress * 100)).padStart(2, "0"),
    );
  };

  const applyAuthoritativeVisualState = () => {
    const progress = latestVirtualProgress;
    const node = progress * model.virtualLastNode;
    const opacity = sceneOpacities(node, model);

    stage.dataset.scene = sceneForNode(node, model);
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
  };

  const runAuthoritativeFrame = () => {
    /* Vue still owns internal active-item refs. It applies its damped progress
       first; this controller deliberately writes the exact scroll state after
       that frame and before the chapter-specific directors read --progress.
       All visible parallax therefore shares one, non-lagging clock. */
    applyAuthoritativeVisualState();
    authoritativeFrame = requestAnimationFrame(runAuthoritativeFrame);
  };

  const scrollToPhysicalNode = (node: number) => {
    const rect = track.getBoundingClientRect();
    const start = scrollY + rect.top;
    const distance = Math.max(1, track.offsetHeight - innerHeight);
    const progress = clamp01(node / model.physicalLastNode);
    scrollTo({ top: start + distance * progress, behavior: "smooth" });
  };

  const indexButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>(".ref-index > button"),
  );
  const careerButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>(".ref-career-nav button"),
  );
  const systemButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>(".ref-system-nav button"),
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
  careerButtons.forEach((button, index) =>
    navigationNodes.set(button, model.careerStartNode + index),
  );
  systemButtons.forEach((button, index) =>
    navigationNodes.set(button, model.systemsStartNode + index),
  );

  const onNavigationClick = (event: MouseEvent) => {
    const target = event.target as Element | null;
    const button = target?.closest<HTMLButtonElement>("button") ?? null;
    if (!button) return;

    const node = navigationNodes.get(button);
    if (node === undefined) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    if (indexToggle?.getAttribute("aria-expanded") === "true") {
      indexToggle.click();
    }

    scrollToPhysicalNode(node);
  };

  /* The gallery owns artwork selection through pointer/keyboard only. Native
     wheel movement must remain attached to the physical document. Blocking the
     legacy gallery wheel handler prevents a second, competing scroll clock. */
  const onWheelCapture = (event: WheelEvent) => {
    if (stage.dataset.scene !== "gallery") return;

    if (document.querySelector(".ref-gallery-focus.is-open")) {
      event.preventDefault();
    }
    event.stopImmediatePropagation();
  };

  let replacementTrigger: ScrollTrigger | null = null;
  let installFrame = 0;
  let installAttempts = 0;
  let originalOnUpdate: ((self: ScrollTrigger) => void) | undefined;

  const forwardProgress = (self: ScrollTrigger) => {
    latestPhysicalProgress = clamp01(self.progress);
    latestVirtualProgress = mapPhysicalProgressToVirtualProgress(
      latestPhysicalProgress,
      model,
    );

    syncProgressChrome(latestPhysicalProgress);

    if (originalOnUpdate) {
      const virtualView = new Proxy(self, {
        get(target, property) {
          if (property === "progress") return latestVirtualProgress;
          const value = Reflect.get(target, property, target);
          return typeof value === "function" ? value.bind(target) : value;
        },
      }) as ScrollTrigger;

      originalOnUpdate(virtualView);
    }

    /* ScrollTrigger may update between animation frames. Write immediately as
       well, eliminating the one-frame phase error visible during fast wheel or
       touchpad motion. */
    applyAuthoritativeVisualState();
  };

  const install = () => {
    const existing = ScrollTrigger.getAll().find(
      (candidate) => candidate.trigger === track,
    );

    if (!existing) {
      installAttempts += 1;
      if (installAttempts < MAX_INSTALL_ATTEMPTS) {
        installFrame = requestAnimationFrame(install);
      }
      return;
    }

    const callback = existing.vars.onUpdate;
    originalOnUpdate = typeof callback === "function" ? callback : undefined;
    existing.kill();

    replacementTrigger = ScrollTrigger.create({
      trigger: track,
      start: "top top",
      end: "bottom bottom",
      invalidateOnRefresh: true,
      onUpdate: forwardProgress,
    });

    forwardProgress(replacementTrigger);
    authoritativeFrame = requestAnimationFrame(runAuthoritativeFrame);
    ScrollTrigger.refresh();
  };

  syncProgressChrome(0);
  addEventListener("click", onNavigationClick, true);
  addEventListener("wheel", onWheelCapture, { capture: true, passive: false });
  installFrame = requestAnimationFrame(install);

  return () => {
    cancelAnimationFrame(installFrame);
    cancelAnimationFrame(authoritativeFrame);
    replacementTrigger?.kill();
    removeEventListener("click", onNavigationClick, true);
    removeEventListener("wheel", onWheelCapture, true);
    track.style.removeProperty("height");
    delete track.dataset.scrollSyncOwner;
    portfolio.style.removeProperty("--physical-scroll-progress");
    progressCurrent?.removeAttribute("data-scroll-progress");
    [
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
