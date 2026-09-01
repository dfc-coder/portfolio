<script setup lang="ts">
import ChapterSignal from "./ChapterSignal.vue";
import NarrativeHeader from "./NarrativeHeader.vue";
import NarrativeProgressRail from "./NarrativeProgressRail.vue";
import { experiences } from "../../experiences/trajectory-data";

const splitCompany = (company: string) => {
  const [organization, ...rest] = company.split(" · ");
  return { organization, location: rest.join(" · ") || "Remote" };
};

const startYear = (period: string) => period.match(/\b\d{4}\b/)?.[0] ?? period.slice(0, 4);
const roleCount = String(experiences.length).padStart(2, "0");
const trajectoryRailItems = experiences.map((experience, index) => ({
  key: experience.period,
  label: startYear(experience.period),
  meta: String(index + 1).padStart(2, "0"),
}));
</script>

<template>
  <div class="trajectory-experience" aria-label="Professional trajectory">
    <div class="trajectory-intro" aria-hidden="true">
      <ChapterSignal class="trajectory-intro__kicker" index="02" label="THE RECORD" />
      <p>First, the proof —<br />where the practice was built.</p>
    </div>

    <NarrativeHeader
      class="trajectory-header"
      variant="trajectory"
      index="02"
      label="PROFESSIONAL TRAJECTORY"
      :meta="['2023 — NOW', `${roleCount} ROLES`]"
    />

    <NarrativeProgressRail
      class="trajectory-progress-rail"
      variant="trajectory"
      :items="trajectoryRailItems"
    />

    <div class="trajectory-static-chrome" aria-hidden="true">
      <div class="trajectory-static-chrome__context">
        <span>ORGANIZATION</span>
        <span>CONTEXT</span>
      </div>
      <span class="trajectory-static-chrome__focus">FOCUS</span>
    </div>

    <div class="trajectory-entries">
      <article
        v-for="(experience, index) in experiences"
        :key="`${experience.period}-${experience.role}`"
        class="trajectory-entry"
        :class="{ 'trajectory-entry--long-role': experience.role.length > 24 }"
        :data-index="index"
      >
        <div class="trajectory-entry__eyebrow">
          <span>{{ String(index + 1).padStart(2, "0") }}</span><i /><time>{{ experience.period }}</time>
        </div>
        <h3>{{ experience.role }}</h3>
        <dl class="trajectory-entry__context">
          <div>
            <dt>ORGANIZATION</dt>
            <dd>{{ splitCompany(experience.company).organization }}</dd>
          </div>
          <div>
            <dt>CONTEXT</dt>
            <dd>{{ splitCompany(experience.company).location }}</dd>
          </div>
        </dl>
        <div class="trajectory-entry__statement"><i /><p>{{ experience.summary }}</p></div>
        <section class="trajectory-entry__focus" aria-label="Role focus">
          <h4>FOCUS</h4>
          <ul>
            <li
              v-for="(item, tagIndex) in experience.focus"
              :key="item"
              :style="{ '--tag-index': tagIndex }"
            >
              {{ item }}
            </li>
          </ul>
        </section>
      </article>
    </div>

    <div class="trajectory-counter" aria-hidden="true">
      <span>ROLE</span>
      <div class="trajectory-counter__row">
        <div class="trajectory-counter__viewport">
          <div class="trajectory-counter__track">
            <span v-for="(_, index) in experiences" :key="index">{{ String(index + 1).padStart(2, "0") }}</span>
          </div>
        </div>
        <i /><span>{{ roleCount }}</span>
      </div>
    </div>
  </div>
</template>
