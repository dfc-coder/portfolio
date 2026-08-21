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

createApp(App).mount("#app");

requestAnimationFrame(() => {
  mountHeroExperience();
});
