import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/search": "http://127.0.0.1:8000",
      "/products": "http://127.0.0.1:8000",
      "/im": "http://127.0.0.1:8000",
      "/watches": "http://127.0.0.1:8000",
      "/notify": "http://127.0.0.1:8000",
      "/ai": "http://127.0.0.1:8000",
      "/autoreply": "http://127.0.0.1:8000",
      "/settings": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
