import { createApp } from "vue";
import App from "./App.vue";
import { mountHeroExperience } from "./experiences/hero";
import { mountTrajectoryExperience } from "./experiences/trajectory";
import { mountSystemsExperience } from "./experiences/systems";
import { mountVisualContinuity } from "./experiences/continuity";
import { mountGalleryGel } from "./experiences/gallery";
import { mountScrollSyncController } from "./experiences/scroll";

import "./styles/base.css";
import "./styles/cinematic.css";
import "./styles/cinematic-motion.css";
import "./experiences/scroll.css";
import "./styles/typography.css";
import "./components/agent/agent.css";
import "./experiences/hero.css";
import "./experiences/trajectory.css";
import "./experiences/trajectory-bridge.css";
import "./experiences/systems.css";
import "./experiences/continuity.css";
import "./experiences/systems-motion.css";
import "./styles/chapter-bridges.css";
import "./experiences/gallery.css";

import "./design-system/tokens.css";
import "./design-system/primitives.css";
import "./design-system/templates.css";

document.documentElement.classList.add("creative-hero-pending");

createApp(App).mount("#app");

void document.fonts.ready.then(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("creative-hero-pending");
      mountScrollSyncController();
      mountVisualContinuity();
      mountHeroExperience();
      mountTrajectoryExperience();
      mountSystemsExperience();
      mountGalleryGel();
    });
  });
});
