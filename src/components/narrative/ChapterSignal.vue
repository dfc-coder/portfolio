<script setup lang="ts">
defineProps<{
  index: string;
  label: string;
}>();
</script>

<template>
  <span class="narrative-signal">
    <span class="narrative-signal__index">{{ index }}</span>
    <i aria-hidden="true" />
    <span class="narrative-signal__label">{{ label }}</span>
  </span>
</template>
