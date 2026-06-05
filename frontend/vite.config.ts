import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
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
          // Heavy libs only — never split other React wrappers here (causes circular chunks).
          if (id.includes("recharts")) return "vendor-recharts";
          if (id.includes("@fullcalendar")) return "vendor-fullcalendar";
          if (id.includes("react-pdf") || id.includes("pdfjs")) return "vendor-pdf";
          if (id.includes("exceljs")) return "vendor-exceljs";
        },
      },
    },
  },
}));
