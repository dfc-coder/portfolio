<script setup lang="ts">
import ChapterSignal from "./ChapterSignal.vue";
import NarrativeHeader from "./NarrativeHeader.vue";
import NarrativeProgressRail from "./NarrativeProgressRail.vue";
import SystemDiagram from "./SystemDiagram.vue";
import { systemsProjects as projects } from "../../experiences/systems-projects";

const systemCount = String(projects.length).padStart(2, "0");
const systemRailItems = projects.map((project) => ({
  key: project.id,
  label: project.code,
}));
</script>

<template>
  <div class="systems-experience" aria-label="Selected technical systems">
    <div class="systems-intro" aria-hidden="true">
      <ChapterSignal class="systems-intro__kicker" index="03" label="THE EVIDENCE" />
      <p>The work becomes evidence —<br /><em>systems designed, built and shipped.</em></p>
    </div>

    <NarrativeHeader
      class="systems-header"
      variant="systems"
      index="03"
      label="SELECTED TECHNICAL SYSTEMS"
      :meta="[`${systemCount} SYSTEMS`, 'BUILT / SHIPPED']"
    />

    <NarrativeProgressRail
      class="systems-progress-rail"
      variant="systems"
      :items="systemRailItems"
    />

    <div class="systems-static-chrome" aria-hidden="true">
      <div class="systems-static-chrome__architecture">
        <span>SYSTEM ARCHITECTURE</span><i />
      </div>
      <div class="systems-static-chrome__detail"><span>SYSTEM NOTE</span></div>
      <div class="systems-static-chrome__evidence"><span>EVIDENCE</span><i /></div>
      <div class="systems-static-chrome__implementation"><span>IMPLEMENTATION</span></div>
    </div>

    <div class="systems-projects">
      <article
        v-for="(project, index) in projects"
        :key="project.id"
        class="systems-project"
        :data-index="index"
        :data-project="project.id"
      >
        <div class="systems-project__identity">
          <h3>{{ project.title }}</h3>
          <p class="systems-project__premise">{{ project.premise }}</p>
        </div>

        <section class="systems-project__architecture">
          <h4 class="sr-only">System architecture</h4>

          <div class="systems-graph-field">
            <div class="systems-graph-field__crosshair" aria-hidden="true" />
            <SystemDiagram :project="project" />
          </div>
        </section>

        <section class="systems-project__detail">
          <h4 class="sr-only">System note</h4>
          <p>{{ project.detail }}</p>
        </section>

        <section class="systems-project__evidence">
          <h4 class="sr-only">Evidence</h4>
          <p>{{ project.outcome }}</p>
        </section>

        <section class="systems-project__implementation">
          <h4 class="sr-only">Implementation</h4>
          <ul>
            <li
              v-for="(item, stackIndex) in project.stack"
              :key="item"
              :style="{ '--stack-index': stackIndex }"
            >
              {{ item }}
            </li>
          </ul>
        </section>
      </article>
    </div>
  </div>
</template>
