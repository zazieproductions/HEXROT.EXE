import path from "path";
import { fileURLToPath } from "url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vite.dev/config/
export default defineConfig({
  // Relative base: vite-plugin-singlefile forces "./" so the single-file build
  // works under any subpath (e.g. the /HEXROT.EXE/ GitHub Pages project site).
  // Keep asset references relative and never hard-code an absolute base here;
  // a CLI --base flag is overridden by the plugin and has no effect.
  base: "./",
  plugins: [react(), tailwindcss(), viteSingleFile()],
  // The dev preview is served through a proxied host, so accept any Host header.
  server: { host: "0.0.0.0", allowedHosts: true },
  preview: { host: "0.0.0.0", allowedHosts: true },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
