import { createApp } from "vue";
import App from "./App.vue";
import { mountVisualContinuity } from "./experiences/continuity";
import { mountSceneLifecycle } from "./experiences/scene-lifecycle";
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

document.documentElement.classList.add("creative-hero-pending");

createApp(App).mount("#app");

void document.fonts.ready.then(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("creative-hero-pending");
      mountScrollSyncController();
      mountVisualContinuity();
      mountSceneLifecycle();
    });
  });
});
