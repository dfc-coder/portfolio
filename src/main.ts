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
import "./experiences/continuity.css";
import "./styles/chapter-bridges.css";
import "./components/agent/agent.css";
import "./experiences/hero.css";
import "./experiences/trajectory.css";
import "./experiences/systems.css";
import "./experiences/gallery.css";
import "./components/narrative/narrative-progress-rail.css";
import "./styles/narrative-visibility.css";

createApp(App).mount("#app");

mountScrollSyncController();
mountVisualContinuity();
mountSceneLifecycle();
