import { mountHeroExperience } from "./hero";
import { narrativeModel } from "./narrative-model";
import {
  narrativeRuntime,
  type NarrativeScene,
  type NarrativeState,
} from "./narrative-runtime";

type RuntimeScene = Exclude<NarrativeScene, "chapter">;
type Cleanup = () => void;
type RuntimeLoader = () => Promise<Cleanup>;
type Prefetch = () => void;

type ChapterRuntimePair = {
  endNode: number;
  scenes: readonly [RuntimeScene, RuntimeScene];
};

const noop = () => undefined;

const runtimeLoaders = {
  hero: async () => mountHeroExperience(),
  career: async () => {
    const { mountTrajectoryExperience } = await import("./trajectory");
    return mountTrajectoryExperience();
  },
  systems: async () => {
    const { mountSystemsExperience } = await import("./systems");
    return mountSystemsExperience();
  },
  gallery: async () => {
    const { mountGalleryExperience } = await import("./gallery");
    return mountGalleryExperience();
  },
  agent: async () => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return noop;
    const { mountStageGraphics } = await import("../graphics/stageGraphics");
    return mountStageGraphics();
  },
} satisfies Record<RuntimeScene, RuntimeLoader>;

const prefetchers = {
  hero: () => void import("./trajectory"),
  career: () => void import("./systems"),
  systems: () => void import("./gallery"),
  gallery: () => {
    void import("../components/agent/AgentOS.vue");
    void import("../graphics/stageGraphics");
  },
  agent: noop,
} satisfies Record<RuntimeScene, Prefetch>;

const chapterRuntimePairs: readonly ChapterRuntimePair[] = [
  {
    endNode: narrativeModel.careerStartNode - 0.5,
    scenes: ["hero", "career"],
  },
  {
    endNode: narrativeModel.systemsStartNode - 0.5,
    scenes: ["career", "systems"],
  },
  {
    endNode: narrativeModel.galleryStartNode - 0.5,
    scenes: ["systems", "gallery"],
  },
  {
    endNode: narrativeModel.virtualLastNode - 0.5,
    scenes: ["gallery", "agent"],
  },
];

/**
 * Concrete scenes own one runtime. Chapter handoffs intentionally own the
 * outgoing + incoming pair so the incoming runtime can prepare before it is
 * visually authoritative and the outgoing runtime survives until that mount
 * has completed.
 */
export const runtimeScenesForState = (
  state: Pick<NarrativeState, "node" | "scene">,
): readonly RuntimeScene[] => {
  if (state.scene !== "chapter") return [state.scene];

  return (
    chapterRuntimePairs.find(({ endNode }) => state.node < endNode)?.scenes ??
    chapterRuntimePairs[chapterRuntimePairs.length - 1]!.scenes
  );
};

/**
 * One explicit owner for scene-specific runtime lifecycles.
 *
 * Handoffs are atomic: missing incoming runtimes mount first. Obsolete outgoing
 * runtimes are cleaned only after every currently desired runtime is ready.
 * This preserves lazy chunks without exposing import latency as a blank frame.
 */
export const mountSceneLifecycle = () => {
  const mountedRuntimes = new Map<RuntimeScene, Cleanup>();
  const loadingRuntimes = new Map<RuntimeScene, Promise<void>>();
  let desiredRuntimes = new Set<RuntimeScene>();
  let activationVersion = 0;
  let disposed = false;

  const cleanupObsoleteRuntimes = (version = activationVersion) => {
    if (version !== activationVersion) return;
    if ([...desiredRuntimes].some((scene) => !mountedRuntimes.has(scene))) return;

    mountedRuntimes.forEach((cleanup, scene) => {
      if (desiredRuntimes.has(scene)) return;
      cleanup();
      mountedRuntimes.delete(scene);
    });
  };

  const ensureMounted = (scene: RuntimeScene): Promise<void> => {
    if (mountedRuntimes.has(scene)) return Promise.resolve();

    const pending = loadingRuntimes.get(scene);
    if (pending) return pending;

    const load = runtimeLoaders[scene]()
      .then((cleanup) => {
        if (disposed || !desiredRuntimes.has(scene)) {
          cleanup();
          return;
        }
        mountedRuntimes.set(scene, cleanup);
      })
      .finally(() => {
        loadingRuntimes.delete(scene);
        cleanupObsoleteRuntimes();
      });

    loadingRuntimes.set(scene, load);
    return load;
  };

  const sync = (state: NarrativeState) => {
    const version = ++activationVersion;
    const scene = state.scene;
    desiredRuntimes = new Set(runtimeScenesForState(state));

    // A stable scene downloads only its next likely runtime. Chapter states are
    // already mounting their incoming runtime, so extra prefetch would be noise.
    if (scene !== "chapter") prefetchers[scene]();

    desiredRuntimes.forEach((scene) => {
      void ensureMounted(scene);
    });

    cleanupObsoleteRuntimes(version);
  };

  const unsubscribe = narrativeRuntime.subscribe(sync);

  return () => {
    disposed = true;
    activationVersion += 1;
    unsubscribe();
    desiredRuntimes.clear();
    mountedRuntimes.forEach((cleanup) => cleanup());
    mountedRuntimes.clear();
  };
};