import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, Vite serves the app and proxies API calls to FastAPI on :8000.
const api = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/search": api,
      "/funds": api,
      "/meta": api,
      "/health": api,
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
