import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server on :5173; the backend API runs separately on :8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
});
