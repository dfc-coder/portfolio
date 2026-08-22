<script setup lang="ts">
defineProps<{
  index: string;
  label: string;
}>();
</script>

<template>
  <div class="narrative-signal">
    <span>{{ index }}</span>
    <i aria-hidden="true" />
    <b>{{ label }}</b>
  </div>
</template>
