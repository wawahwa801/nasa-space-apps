import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";
import globals from "globals";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  // Old generated copy of ../fire-dashboard, in case one is still on disk.
  { ignores: [".next/**", "public/fire-dashboard/**"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  // next/typescript turns off no-undef (TypeScript covers it), but this app is
  // plain JS/JSX. Without it, a reference to a removed variable (e.g.
  // setAppliedHybrid) passed lint and build and only crashed at runtime.
  {
    files: ["**/*.{js,jsx,mjs}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { "no-undef": "error" },
  },
];

export default config;
