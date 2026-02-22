import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: process.env.VITE_BASE_PATH || "/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          const seg = id.split("node_modules/")[1] || "";
          const pkg = seg.startsWith("@") ? seg.split("/").slice(0, 2).join("/") : seg.split("/")[0];
          if (pkg === "react" || pkg === "react-dom" || pkg === "react-router-dom" || pkg === "scheduler") return "vendor-react";
          if (pkg === "antd" || pkg === "@ant-design/icons" || pkg === "@ant-design/icons-svg" || pkg.startsWith("@rc-component/"))
            return "vendor-antd";
          if (pkg.startsWith("@tanstack")) return "vendor-query";
          if (pkg === "zustand") return "vendor-state";
          return;
        },
      },
    },
  },
});
