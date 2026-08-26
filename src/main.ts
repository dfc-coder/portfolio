import { createApp } from "vue";

import "./styles/theme.css";
import "./styles/base.css";

const MOBILE_QUERY = "(max-width: 820px)";

const mountDesktop = async () => {
  const [
    { default: App },
    { mountHeroExperience },
    { mountTrajectoryExperience },
    { mountSystemsExperience },
    { mountVisualContinuity },
    { mountGalleryGel },
    { mountScrollSyncController },
    { mountStageGraphics },
  ] = await Promise.all([
    import("./App.vue"),
    import("./experiences/hero"),
    import("./experiences/trajectory"),
    import("./experiences/systems"),
    import("./experiences/continuity"),
    import("./experiences/gallery"),
    import("./experiences/scroll"),
    import("./graphics/stageGraphics"),
    import("./styles/shell.css"),
    import("./graphics/stage-graphics.css"),
    import("./experiences/scroll.css"),
    import("./components/agent/agent.css"),
    import("./experiences/hero.css"),
    import("./experiences/trajectory.css"),
    import("./experiences/trajectory-layout.css"),
    import("./experiences/systems.css"),
    import("./experiences/continuity.css"),
    import("./styles/chapter-bridges.css"),
    import("./experiences/gallery.css"),
  ]);

  document.documentElement.classList.add("creative-hero-pending");
  createApp(App).mount("#app");

  await document.fonts.ready;
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
};

const mountMobile = async () => {
  const [{ default: MobilePortfolio }] = await Promise.all([
    import("./mobile/MobilePortfolio.vue"),
    import("./mobile/mobile.css"),
  ]);
  document.documentElement.classList.add("mobile-portfolio-ready");
  createApp(MobilePortfolio).mount("#app");
};

if (window.matchMedia(MOBILE_QUERY).matches) {
  void mountMobile();
} else {
  void mountDesktop();
}
