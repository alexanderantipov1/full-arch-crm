import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    exclude: ["**/node_modules/**", "**/tests/e2e/**"],
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./"),
      // ``server-only`` is a Next.js sentinel that throws at import-time when
      // bundled into a client component. In vitest we exercise the server-side
      // helpers directly, so alias it to an empty stub. Production builds keep
      // the real package — only the test environment bypasses the guard.
      "server-only": resolve(__dirname, "./tests/__stubs__/server-only.ts"),
    },
  },
});
