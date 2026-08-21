import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { galleryItems } from "./gallery";
import { systemsProjects } from "./systems-projects";
import { experiences } from "./trajectory";

const SCROLL_STEP_VH = 36;
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
  const careerStartNode = 2;
  const chapterSystemsNode = careerStartNode + experiences.length;
  const systemsStartNode = chapterSystemsNode + 1;
  const chapterGalleryNode = systemsStartNode + systemsProjects.length;
  const galleryStartNode = chapterGalleryNode + 1;
  const virtualChapterAgentNode = galleryStartNode + galleryItems.length;
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

  gsap.registerPlugin(ScrollTrigger);

  const model = buildScrollModel();
  const trackHeightVh = 100 + model.physicalLastNode * SCROLL_STEP_VH;

  track.dataset.scrollSyncOwner = "physical";
  track.style.setProperty("height", `${trackHeightVh}vh`, "important");

  const applyState = (physicalProgress: number) => {
    const physical = clamp01(physicalProgress);
    const progress = mapPhysicalProgressToVirtualProgress(physical, model);
    const node = progress * model.virtualLastNode;
    const opacity = sceneOpacities(node, model);

    portfolio.style.setProperty("--physical-scroll-progress", physical.toFixed(5));
    progressCurrent?.setAttribute(
      "data-scroll-progress",
      String(Math.round(physical * 100)).padStart(2, "0"),
    );

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
    const button = (event.target as Element | null)?.closest<HTMLButtonElement>("button") ?? null;
    if (!button) return;

    const node = navigationNodes.get(button);
    if (node === undefined) return;

    event.preventDefault();
    if (indexToggle?.getAttribute("aria-expanded") === "true") {
      indexToggle.click();
    }
    scrollToPhysicalNode(node);
  };

  const onWheelCapture = (event: WheelEvent) => {
    if (stage.dataset.scene !== "gallery") return;
    if (!document.querySelector(".ref-gallery-focus.is-open")) return;
    event.preventDefault();
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
  addEventListener("wheel", onWheelCapture, { capture: true, passive: false });
  applyState(trigger.progress);
  ScrollTrigger.refresh();

  return () => {
    trigger.kill();
    removeEventListener("click", onNavigationClick, true);
    removeEventListener("wheel", onWheelCapture, true);
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
