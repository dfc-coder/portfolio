import { mountHeroExperience } from "./hero";
import { narrativeRuntime, type NarrativeScene } from "./narrative-runtime";

type RuntimeScene = Exclude<NarrativeScene, "chapter">;
type Cleanup = () => void;
type RuntimeLoader = () => Promise<Cleanup>;
type Prefetch = () => void;

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
    const [{ mountGalleryGel }, { mountGalleryTransition }] = await Promise.all([
      import("./gallery"),
      import("./gallery-transition"),
    ]);
    const gelCleanup = mountGalleryGel();
    const transitionCleanup = mountGalleryTransition();

    return () => {
      transitionCleanup();
      gelCleanup();
    };
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
  systems: () => {
    void import("./gallery");
    void import("./gallery-transition");
  },
  gallery: () => {
    void import("../components/agent/AgentOS.vue");
    void import("../graphics/stageGraphics");
  },
  agent: noop,
} satisfies Record<RuntimeScene, Prefetch>;

const isRuntimeScene = (scene: NarrativeScene): scene is RuntimeScene =>
  scene !== "chapter";

/**
 * One explicit runtime owner for scene-specific work.
 * Chapter interstitials intentionally keep the current owner alive so exit
 * motion can finish; the handoff happens only when the next concrete scene wins.
 */
export const mountSceneLifecycle = () => {
  let activeScene: RuntimeScene | null = null;
  let cleanupActive: Cleanup = noop;
  let activationVersion = 0;
  let disposed = false;

  const activate = async (scene: NarrativeScene) => {
    if (!isRuntimeScene(scene) || scene === activeScene) return;

    const version = ++activationVersion;
    cleanupActive();
    cleanupActive = noop;
    activeScene = scene;
    prefetchers[scene]();

    const cleanup = await runtimeLoaders[scene]();
    if (disposed || version !== activationVersion || activeScene !== scene) {
      cleanup();
      return;
    }

    cleanupActive = cleanup;
  };

  const unsubscribe = narrativeRuntime.subscribe(({ scene }) => {
    void activate(scene);
  });

  return () => {
    disposed = true;
    activationVersion += 1;
    unsubscribe();
    cleanupActive();
    cleanupActive = noop;
    activeScene = null;
  };
};
