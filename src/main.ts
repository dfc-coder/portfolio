import { createApp } from "vue";
import App from "./App.vue";
import { mountHeroExperience } from "./experiences/hero";
import { mountTrajectoryExperience } from "./experiences/trajectory";
import { mountSystemsExperience } from "./experiences/systems";
import { mountVisualContinuity } from "./experiences/continuity";
import { mountGalleryGel } from "./experiences/gallery";
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
import "./experiences/continuity.css";
import "./styles/chapter-bridges.css";
import "./experiences/gallery.css";
import "./styles/mobile.css";

const MOBILE_QUERY = "(max-width: 820px)";
const mobileExperience = window.matchMedia(MOBILE_QUERY).matches;

document.documentElement.classList.add(
  mobileExperience ? "mobile-experience" : "desktop-experience",
);

if (!mobileExperience) {
  document.documentElement.classList.add("creative-hero-pending");
}

createApp(App).mount("#app");

if (!mobileExperience) {
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
      });
    });
  });
}