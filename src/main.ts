import { createApp } from "vue";
import App from "./App.vue";
import { mountHeroExperience } from "./hero-experience";
import { mountTrajectoryExperience } from "./trajectory-experience";
import { mountSystemsExperience } from "./systems-experience-v5";
import { mountDesignSystemRuntime } from "./design-system/runtime";
import "./style.css";
import "./cinematic-refined.css";
import "./cinematic-tuning.css";
import "./scroll-sync-hotfix.css";
import "./type-system.css";
import "./gallery-editorial.css";
import "./micro-interactions.css";
import "./agent-os.css";
import "./hero-experience.css";
import "./trajectory-experience.css";
import "./trajectory-bridge.css";
import "./systems-experience-v3.css";
import "./systems-integration-fix.css";
import "./visual-continuity-v3.css";
import "./systems-experience-v5.css";
import "./design-system/tokens.css";
import "./design-system/primitives.css";
import "./design-system/templates.css";

/* Keep the first paint quiet while Vue, the self-hosted display face and the
   legacy intro initialize. This prevents a one-frame Hero flash before the
   creative director has established its starting state. */
document.documentElement.classList.add("creative-hero-pending");

createApp(App).mount("#app");

/* The legacy Vue intro waits for nextTick + font readiness before it creates its
   timeline. Mount the chapter directors first; the design-system runtime mounts
   last so repeated primitives own the final shared motion/output layer. */
void document.fonts.ready.then(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("creative-hero-pending");
      mountHeroExperience();
      mountTrajectoryExperience();
      mountSystemsExperience();
      mountDesignSystemRuntime();
    });
  });
});
