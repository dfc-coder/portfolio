<script setup lang="ts">
import ChapterSignal from "./ChapterSignal.vue";
import { experiences } from "../../experiences/trajectory-data";

const splitCompany = (company: string) => {
  const [organization, ...rest] = company.split(" · ");
  return { organization, location: rest.join(" · ") || "Remote" };
};

const roleCount = String(experiences.length).padStart(2, "0");
</script>

<template>
  <div class="trajectory-experience" aria-label="Professional trajectory">
    <h2 class="sr-only">Professional trajectory</h2>

    <div class="trajectory-intro" aria-hidden="true">
      <ChapterSignal class="trajectory-intro__kicker" index="02" label="THE RECORD" />
      <p>First, the proof —<br />where the practice was built.</p>
    </div>

    <div class="trajectory-axis narrative-rail" aria-hidden="true"><i /></div>

    <div class="trajectory-years" aria-hidden="true">
      <div
        v-for="(experience, index) in experiences"
        :key="experience.period"
        class="trajectory-year"
        :data-index="index"
      >
        <span>{{ experience.period.slice(0, 4) }}</span><i /><b>{{ String(index + 1).padStart(2, "0") }}</b>
      </div>
    </div>

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
