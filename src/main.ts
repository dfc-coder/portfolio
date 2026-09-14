import { createApp } from "vue";
import App from "./App.vue";
import { mountHeroExperience } from "./experiences/hero";
import { mountTrajectoryExperience } from "./experiences/trajectory";
import { mountSystemsExperience } from "./experiences/systems";
import { mountVisualContinuity } from "./experiences/continuity";
import { mountGalleryGel } from "./experiences/gallery";
import { mountGalleryTransition } from "./experiences/gallery-transition";
import { narrativeRuntime, type NarrativeScene } from "./experiences/narrative-runtime";
import { mountScrollSyncController } from "./experiences/scroll";

import "./styles/theme.css";
import "./styles/base.css";
import "./styles/shell.css";
import "./graphics/stage-graphics.css";
import "./experiences/scroll.css";
import "./components/agent/agent.css";
import "./experiences/hero.css";
import "./experiences/trajectory.css";
import "./experiences/trajectory-layout.css";
import "./styles/trajectory-role-fit.css";
import "./experiences/systems.css";
import "./experiences/systems-project-balance.css";
import "./experiences/continuity.css";
import "./styles/chapter-bridges.css";
import "./experiences/gallery.css";
import "./experiences/gallery-clean.css";
import "./experiences/gallery-transition.css";
import "./styles/mobile-experience.css";
import "./components/narrative/narrative-progress-rail.css";
import "./styles/mobile-hero-layout.css";
import "./styles/mobile-trajectory-layout.css";
import "./styles/mobile-systems-layout.css";

let agentGraphicsModule: Promise<typeof import("./graphics/stageGraphics")> | null = null;

const loadAgentGraphics = () => {
  agentGraphicsModule ??= import("./graphics/stageGraphics");
  return agentGraphicsModule;
};

const mountAgentGraphicsLifecycle = (): (() => void) => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return () => undefined;
  }

  let disposed = false;
  let cleanup: (() => void) | null = null;

  const sync = (scene: NarrativeScene) => {
    if (scene !== "agent") {
      cleanup?.();
      cleanup = null;

      if (scene === "gallery") {
        void loadAgentGraphics();
      }
      return;
    }

    if (cleanup) return;

    void loadAgentGraphics().then(({ mountStageGraphics }) => {
      if (disposed || cleanup || narrativeRuntime.getState().scene !== "agent") return;
      cleanup = mountStageGraphics();
    });
  };

  const unsubscribe = narrativeRuntime.subscribe(({ scene }) => sync(scene));

  return () => {
    disposed = true;
    unsubscribe();
    cleanup?.();
    cleanup = null;
  };
};

document.documentElement.classList.add("creative-hero-pending");

createApp(App).mount("#app");

void document.fonts.ready.then(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("creative-hero-pending");
      mountScrollSyncController();
      mountAgentGraphicsLifecycle();
      mountVisualContinuity();
      mountHeroExperience();
      mountTrajectoryExperience();
      mountSystemsExperience();
      mountGalleryGel();
      mountGalleryTransition();
    });
  });
});
