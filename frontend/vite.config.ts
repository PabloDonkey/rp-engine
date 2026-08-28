import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { playwright } from "@vitest/browser-playwright";
// From `vitest/config`, not `vite`: it is the same `defineConfig` widened to accept the
// `test` block below. Importing it from `vite` type-errors on that block.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5174,
    proxy: {
      "/admin": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  // Named so the first test run on a clean checkout does not discover these mid-run and
  // reload, which Vitest warns is a source of flaky runs. `pinia` joined the list with S031,
  // the first test to build a store: discovering it mid-run drops the active Pinia and every
  // test in the file fails with "getActivePinia() was called but there was no active Pinia".
  optimizeDeps: {
    include: ["zod", "pinia"],
  },
  // Components are tested in a real browser, not in a simulated DOM. The form controls
  // this panel needs carry real focus, real selection and real file inputs, and a
  // simulated DOM only pretends to have those. There is no continuous integration (CI)
  // setup in this repository, so these tests run on a developer machine.
  test: {
    browser: {
      enabled: true,
      headless: true,
      provider: playwright(),
      instances: [{ browser: "chromium" }],
    },
    include: ["src/**/*.test.ts"],
  },
});
