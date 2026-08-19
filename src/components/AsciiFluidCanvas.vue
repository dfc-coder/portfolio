<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{ active?: boolean }>();
const canvas = ref<HTMLCanvasElement | null>(null);
let frame = 0;
let start = performance.now();
let reducedMotion = false;

const draw = (time: number) => {
  const element = canvas.value;
  if (!element) return;

  const ctx = element.getContext("2d");
  if (!ctx) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  const rect = element.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));

  if (element.width !== width || element.height !== height) {
    element.width = width;
    element.height = height;
  }

  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;
  const elapsed = reducedMotion ? 0.65 : (time - start) / 1000;
  const energy = props.active ? 1.25 : 1;
  const chars = ".,:;+*#%@";
  const columns = Math.max(42, Math.floor(w / 12));
  const rows = Math.max(26, Math.floor(h / 15));
  const stepX = w / columns;
  const stepY = h / rows;

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `${Math.max(8, stepY * 0.68)}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;

  for (let row = 0; row <= rows; row += 1) {
    const ny = row / rows;
    for (let col = 0; col <= columns; col += 1) {
      const nx = col / columns;
      const x = nx * w;
      const y = ny * h;
      const cx = nx - 0.5;
      const cy = ny - 0.47;

      const radius = Math.sqrt(cx * cx * 1.5 + cy * cy * 2.15);
      const angle = Math.atan2(cy, cx);
      const wave =
        Math.sin(angle * 3.2 + elapsed * 0.7) * 0.055 +
        Math.sin(nx * 10.5 - elapsed * 0.45) * 0.03 +
        Math.cos(ny * 9 + elapsed * 0.35) * 0.025;
      const target = 0.27 + wave * energy;
      const ring = Math.exp(-Math.pow((radius - target) * 10.5, 2));
      const halo = Math.exp(-Math.pow((radius - 0.39) * 6.2, 2)) * 0.42;
      const turbulence =
        (Math.sin(nx * 23 + ny * 13 + elapsed) + Math.cos(nx * 9 - ny * 21 - elapsed * 0.6)) *
        0.06;
      const density = Math.max(0, Math.min(1, ring + halo + turbulence - radius * 0.25));

      if (density < 0.08) continue;

      const driftX = Math.sin(angle * 2 + elapsed * 0.55 + radius * 11) * stepX * 0.75 * density;
      const driftY = Math.cos(angle * 3 - elapsed * 0.4 + radius * 8) * stepY * 0.55 * density;
      const charIndex = Math.min(chars.length - 1, Math.floor(density * chars.length));
      const alpha = Math.min(0.95, 0.15 + density * 0.85);

      ctx.fillStyle = `rgba(236, 230, 213, ${alpha})`;
      ctx.fillText(chars[charIndex], x + driftX, y + driftY);
    }
  }

  ctx.restore();
  frame = requestAnimationFrame(draw);
};

onMounted(() => {
  reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  start = performance.now();
  frame = requestAnimationFrame(draw);
});

watch(
  () => props.active,
  () => {
    if (!reducedMotion) start = performance.now() - 450;
  },
);

onBeforeUnmount(() => cancelAnimationFrame(frame));
</script>

<template>
  <canvas ref="canvas" class="ascii-fluid" aria-hidden="true" />
</template>
