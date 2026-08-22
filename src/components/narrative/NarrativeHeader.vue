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
  <div class="narrative-header" aria-hidden="true">
    <ChapterSignal
      :class="['narrative-header__label', `${props.variant}-header__label`]"
      :index="index"
      :label="label"
    />
    <div
      v-if="meta?.length"
      :class="['narrative-header__meta', `${props.variant}-header__meta`]"
    >
      <span v-for="item in meta" :key="item">{{ item }}</span>
    </div>
  </div>
</template>
