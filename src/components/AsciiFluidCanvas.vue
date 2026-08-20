<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { AsciiField, type FieldState, type Occluder } from "./agent/asciiField";

const props = withDefaults(
  defineProps<{
    state?: FieldState;
    occluders?: Occluder[];
    paused?: boolean;
  }>(),
  { state: "idle", occluders: () => [], paused: false },
);

const canvas = ref<HTMLCanvasElement | null>(null);
let field: AsciiField | null = null;

/** Normalised pointer, so the field reacts to the cursor crossing the aperture. */
const onPointerMove = (event: PointerEvent) => {
  const element = canvas.value;
  if (!element || !field) return;
  const rect = element.getBoundingClientRect();
  field.setPointer(
    (event.clientX - rect.left) / rect.width,
    (event.clientY - rect.top) / rect.height,
    true,
  );
};

const onPointerLeave = () => field?.setPointer(-1, -1, false);

const onVisibility = () => field?.setPaused(document.hidden || props.paused);

/** Exposed so the console can inject impulses at the exact bubble origin. */
const pulse = (x: number, y: number, strength = 1) => field?.pulse(x, y, strength);
defineExpose({ pulse });

onMounted(() => {
  if (!canvas.value) return;
  field = new AsciiField(canvas.value);
  field.setState(props.state);
  field.setOccluders(props.occluders);
  field.setPaused(props.paused);
  field.start();

  window.addEventListener("pointermove", onPointerMove, { passive: true });
  window.addEventListener("pointerleave", onPointerLeave, { passive: true });
  document.addEventListener("visibilitychange", onVisibility);
});

watch(() => props.state, (next) => field?.setState(next));
watch(() => props.occluders, (next) => field?.setOccluders(next), { deep: true });
watch(() => props.paused, (next) => field?.setPaused(next || document.hidden));

onBeforeUnmount(() => {
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerleave", onPointerLeave);
  document.removeEventListener("visibilitychange", onVisibility);
  field?.destroy();
  field = null;
});
</script>

<template>
  <canvas ref="canvas" class="ascii-fluid" aria-hidden="true" />
</template>
