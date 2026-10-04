import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// No React plugin: tests need the automatic JSX runtime, which esbuild picks up from
// tsconfig's `jsx: react-jsx`. Fast Refresh is a dev-server concern Vitest has no use for,
// and dropping the plugin keeps a second copy of Vite out of the tree.
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
