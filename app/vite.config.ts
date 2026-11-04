import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// In dev (`npm run dev` on the laptop), API calls are proxied to the Pi so the app behaves
// exactly as when the Pi serves it. Point PI_URL at the Pi's Tailscale name.
const PI_URL = process.env.PI_URL ?? "http://piano-pi:8000";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Piano Companion",
        short_name: "Piano",
        description: "Practice companion running on the Raspberry Pi",
        display: "fullscreen",
        orientation: "any",
        background_color: "#14161a",
        theme_color: "#14161a",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
      },
      workbox: {
        // Never cache API responses or recordings; the app shell is enough offline.
        navigateFallbackDenylist: [/^\/api/],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
      },
    }),
  ],
  server: {
    proxy: { "/api": { target: PI_URL, ws: true, changeOrigin: true } },
  },
  test: { environment: "node" },
});
