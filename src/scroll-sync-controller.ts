import { ScrollTrigger } from "gsap/ScrollTrigger";

const FALLBACK_EXPERIENCE_COUNT = 3;
const FALLBACK_SYSTEM_COUNT = 5;
const FALLBACK_ARTWORK_COUNT = 10;
const SCROLL_STEP_VH = 36;
const MAX_INSTALL_ATTEMPTS = 120;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

type ScrollModel = {
  careerStartNode: number;
  systemsStartNode: number;
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
    systemsStartNode,
    galleryStartNode,
    virtualChapterAgentNode,
    virtualLastNode,
    physicalChapterAgentNode,
    physicalLastNode,
  };
};

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

  const galleryProgress =
    (physicalNode - model.galleryStartNode) /
    (model.physicalChapterAgentNode - model.galleryStartNode);
  const virtualNode =
    model.galleryStartNode +
    galleryProgress *
      (model.virtualChapterAgentNode - model.galleryStartNode);

  return clamp01(virtualNode / model.virtualLastNode);
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

  const syncProgressChrome = (physicalProgress: number) => {
    const progress = clamp01(physicalProgress);
    portfolio.style.setProperty("--physical-scroll-progress", progress.toFixed(5));
    progressCurrent?.setAttribute(
      "data-scroll-progress",
      String(Math.round(progress * 100)).padStart(2, "0"),
    );
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

  /* gallery-gel used to jump ten virtual artwork nodes on wheel. The physical
     controller compresses those nodes into one real scroll interval, so wheel
     input must remain native. stopImmediatePropagation blocks the legacy
     gallery handler without cancelling the browser's default scroll. */
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
    const physicalProgress = clamp01(self.progress);
    const virtualProgress = mapPhysicalProgressToVirtualProgress(
      physicalProgress,
      model,
    );

    syncProgressChrome(physicalProgress);
    if (!originalOnUpdate) return;

    const virtualView = new Proxy(self, {
      get(target, property) {
        if (property === "progress") return virtualProgress;
        const value = Reflect.get(target, property, target);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) as ScrollTrigger;

    originalOnUpdate(virtualView);
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
    ScrollTrigger.refresh();
  };

  syncProgressChrome(0);
  addEventListener("click", onNavigationClick, true);
  addEventListener("wheel", onWheelCapture, { capture: true, passive: false });
  installFrame = requestAnimationFrame(install);

  return () => {
    cancelAnimationFrame(installFrame);
    replacementTrigger?.kill();
    removeEventListener("click", onNavigationClick, true);
    removeEventListener("wheel", onWheelCapture, true);
    track.style.removeProperty("height");
    delete track.dataset.scrollSyncOwner;
    portfolio.style.removeProperty("--physical-scroll-progress");
    progressCurrent?.removeAttribute("data-scroll-progress");
  };
};
