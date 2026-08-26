import { galleryItems } from "./gallery";
import { systemsProjects } from "./systems-projects";
import { experiences } from "./trajectory-data";

export type NarrativeModel = {
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

export const buildNarrativeModel = (
  experienceCount = experiences.length,
  systemCount = systemsProjects.length,
  artworkCount = galleryItems.length,
): NarrativeModel => {
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

export const narrativeModel = buildNarrativeModel();
