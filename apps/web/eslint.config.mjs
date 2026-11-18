import { fileURLToPath } from "node:url";

import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextCoreWebVitals,
  ...nextTypeScript,
  { settings: { next: { rootDir: fileURLToPath(new URL(".", import.meta.url)) } } },
  globalIgnores([".next/**", "next-env.d.ts"]),
]);
