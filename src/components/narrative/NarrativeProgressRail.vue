<script setup lang="ts">
type RailItem = {
  key: string;
  label: string;
  meta?: string;
};

const props = defineProps<{
  items: RailItem[];
  variant: "trajectory" | "systems";
}>();

const axisClass = props.variant === "trajectory" ? "trajectory-axis" : "systems-axis";
const itemsClass = props.variant === "trajectory" ? "trajectory-years" : "systems-axis-items";
const itemClass = props.variant === "trajectory" ? "trajectory-year" : "systems-axis-item";
</script>

<template>
  <div
    class="narrative-progress-rail narrative-rail"
    :class="axisClass"
    aria-hidden="true"
  >
    <i class="narrative-progress-rail__progress" />
    <div class="narrative-progress-rail__items" :class="itemsClass">
      <div
        v-for="(item, index) in items"
        :key="item.key"
        class="narrative-progress-rail__item"
        :class="itemClass"
        :data-index="index"
        :style="{ '--rail-slot': items.length > 1 ? index / (items.length - 1) : 0 }"
      >
        <i />
        <b>{{ item.label }}</b>
        <span v-if="item.meta" class="narrative-progress-rail__meta">{{ item.meta }}</span>
      </div>
    </div>
  </div>
</template>
