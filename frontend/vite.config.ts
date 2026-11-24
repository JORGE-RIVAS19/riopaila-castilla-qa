/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El frontend NO llama al modelo: en desarrollo, /api y /media se reenvían al backend FastAPI.
const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/media": { target: API, changeOrigin: true }, // M3: páginas de manuales, gráficas e informes
    },
  },
  build: { chunkSizeWarningLimit: 1600 }, // mermaid se carga bajo demanda solo en /arquitectura
  test: { environment: "node" },
});
