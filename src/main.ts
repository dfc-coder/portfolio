import { createApp } from "vue";
import App from "./App.vue";
import { mountHeroExperience } from "./experiences/hero";
import { mountTrajectoryExperience } from "./experiences/trajectory";
import { mountSystemsExperience } from "./experiences/systems";
import { mountVisualContinuity } from "./experiences/continuity";
import { mountGalleryGel } from "./experiences/gallery";
import { mountGalleryTransition } from "./experiences/gallery-transition";
import { mountScrollSyncController } from "./experiences/scroll";
import { mountStageGraphics } from "./graphics/stageGraphics";

import "./styles/theme.css";
import "./styles/base.css";
import "./styles/shell.css";
import "./graphics/stage-graphics.css";
import "./experiences/scroll.css";
import "./components/agent/agent.css";
import "./experiences/hero.css";
import "./experiences/trajectory.css";
import "./experiences/trajectory-layout.css";
import "./experiences/systems.css";
import "./experiences/systems-project-balance.css";
import "./experiences/continuity.css";
import "./styles/chapter-bridges.css";
import "./components/narrative/narrative-progress-rail.css";
import "./experiences/gallery.css";
import "./experiences/gallery-clean.css";
import "./experiences/gallery-transition.css";

document.documentElement.classList.add("creative-hero-pending");

createApp(App).mount("#app");

void document.fonts.ready.then(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("creative-hero-pending");
      mountStageGraphics();
      mountScrollSyncController();
      mountVisualContinuity();
      mountHeroExperience();
      mountTrajectoryExperience();
      mountSystemsExperience();
      mountGalleryGel();
      mountGalleryTransition();
    });
  });
});
