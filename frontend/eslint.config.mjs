import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  // Old generated copy of ../fire-dashboard, in case one is still on disk.
  { ignores: [".next/**", "public/fire-dashboard/**"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
