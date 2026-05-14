import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./client/src"),
      "@shared": path.resolve(__dirname, "./shared"),
    },
  },
  test: {
    environment: "node",
    include: ["server/**/*.test.ts", "shared/**/*.test.ts", "test/**/*.test.ts"],
    exclude: ["node_modules", "dist", "build"],
    globals: false,
    // Dummy values that satisfy module-load-time guards (e.g. server/db.ts
    // throws if DATABASE_URL is unset). Pool() is lazy — it won't actually
    // connect to this URL unless a test issues a query.
    env: {
      DATABASE_URL: "postgres://test:test@localhost:5432/test",
      SESSION_SECRET: "test-session-secret-not-for-production",
      ANTHROPIC_API_KEY: "test-anthropic-key",
      AI_INTEGRATIONS_OPENAI_API_KEY: "test-openai-key",
      OPENAI_API_KEY: "test-openai-key",
      NODE_ENV: "test",
    },
  },
});
