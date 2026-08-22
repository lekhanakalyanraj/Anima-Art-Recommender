import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI backend so the app can fetch same-origin in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // expose on the local network (0.0.0.0) so other devices can reach it
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // locally-served artwork images (Indian art) live under /media on the API
      "/media": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
