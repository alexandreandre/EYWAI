import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(() => ({
  server: {
    host: "::",
    port: 8080,
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  optimizeDeps: {
    include: ["exceljs"],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          // Keep React ecosystem in a single chunk (must run before other React-based vendors).
          if (
            /node_modules\/(react|react-dom|react-router|scheduler)\//.test(id)
          ) {
            return "vendor-react";
          }
          // clsx sert aux boutons dès le premier écran ET à recharts : rangé avec
          // React, il ne fait plus précharger recharts par index.html.
          if (/node_modules\/clsx\//.test(id)) return "vendor-react";
          // Heavy libs only — never split other React wrappers here (causes circular chunks).
          if (id.includes("recharts")) return "vendor-recharts";
          // Pas de chunk forcé pour exceljs ni pour le lecteur PDF : chargés à la
          // demande (import dynamique), Rollup les isole seul. Forcés ici, ils
          // embarquaient des aides partagées et index.html les préchargeait dès
          // l'écran de connexion (1,4 Mo, audit R2 geste 1).
        },
      },
    },
  },
}));
