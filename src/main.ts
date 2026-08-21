import { createApp } from "vue";
import App from "./App.vue";
import { mountHeroExperience } from "./hero-experience";
import "./style.css";
import "./cinematic-refined.css";
import "./cinematic-tuning.css";
import "./scroll-sync-hotfix.css";
import "./type-system.css";
import "./gallery-editorial.css";
import "./micro-interactions.css";
import "./agent-os.css";
import "./hero-experience.css";

/* Keep the first paint quiet while Vue, the self-hosted display face and the
   legacy intro initialize. This prevents a one-frame Hero flash before the
   creative director has established its starting state. */
document.documentElement.classList.add("creative-hero-pending");

createApp(App).mount("#app");

/* The legacy Vue intro waits for nextTick + font readiness before it creates its
   timeline. Mount the creative director one frame after that initialization so
   it can cancel every legacy Hero tween once, instead of racing it and causing
   flashes or late property writes. */
void document.fonts.ready.then(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      mountHeroExperience();
    });
  });
});
