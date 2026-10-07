import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    // ngrok / Cloudflare tunnels change hostname; Telegram Mini App opens via that host
    allowedHosts: true,
    proxy: {
      // In Docker Compose web service, set VITE_PROXY_TARGET=http://api:8000
      "/api": process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
      "/media": process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
      "/health": process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
    },
  },
});
