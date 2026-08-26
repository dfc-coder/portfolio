<script setup lang="ts">
import ChapterSignal from "./ChapterSignal.vue";

const props = defineProps<{
  index: string;
  label: string;
  meta?: readonly string[];
  variant: "trajectory" | "systems";
}>();
</script>

<template>
  <header class="narrative-header">
    <h2 class="narrative-header__heading">
      <ChapterSignal
        :class="['narrative-header__label', `${props.variant}-header__label`]"
        :index="index"
        :label="label"
      />
    </h2>
    <div
      v-if="meta?.length"
      :class="['narrative-header__meta', `${props.variant}-header__meta`]"
      aria-label="Section metadata"
    >
      <span v-for="item in meta" :key="item">{{ item }}</span>
    </div>
  </header>
</template>
