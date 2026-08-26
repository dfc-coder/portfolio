import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("/three/")) return "three";
          if (id.includes("/gsap/")) return "gsap";
          if (id.includes("/vue/") || id.includes("/@vue/")) return "vue";
          return "vendor";
        },
      },
    },
  },
});
