<script setup lang="ts">
type RailItem = {
  key: string;
  label: string;
  meta?: string;
};

defineProps<{
  items: RailItem[];
}>();
</script>

<template>
  <div class="narrative-progress-rail narrative-rail" aria-hidden="true">
    <i class="narrative-progress-rail__progress" />
    <div class="narrative-progress-rail__items">
      <div
        v-for="(item, index) in items"
        :key="item.key"
        class="narrative-progress-rail__item"
        :data-index="index"
        :style="{ '--rail-slot': items.length > 1 ? index / (items.length - 1) : 0 }"
      >
        <i />
        <b>{{ item.label }}</b>
        <span v-if="item.meta">{{ item.meta }}</span>
      </div>
    </div>
  </div>
</template>
