import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Match the application's TypeScript alias when rendering server pages in tests.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});
