import { defineConfig } from "astro/config";
import react from "@astrojs/react";

export default defineConfig({
  integrations: [react()],
  output: "static",
  site: "https://geo-industrial-atlas.pages.dev",
  build: { inlineStylesheets: "auto" },
  vite: { build: { chunkSizeWarningLimit: 1200 } },
});
