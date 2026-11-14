import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  // Generated copy of ../fire-dashboard (see scripts/sync-fire-dashboard.mjs).
  { ignores: [".next/**", "public/fire-dashboard/**"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
