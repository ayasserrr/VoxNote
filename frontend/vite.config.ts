import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the React app runs on :5173 and proxies /api to FastAPI.
const backend = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
    },
  },
});
