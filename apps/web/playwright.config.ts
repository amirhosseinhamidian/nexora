import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: "http://127.0.0.1:3000" },
  webServer: {
    command: "pnpm exec next build && pnpm exec next start --hostname 127.0.0.1",
    reuseExistingServer: false,
    url: "http://127.0.0.1:3000/fa",
  },
});
