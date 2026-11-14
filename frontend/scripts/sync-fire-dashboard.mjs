// Copies the standalone fire safety dashboard (../fire-dashboard) into
// public/fire-dashboard so Next.js can serve it. fire-dashboard/ stays the
// single source; public/fire-dashboard is generated and git-ignored.
// Runs automatically before `npm run dev` and `npm run build`.

import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(frontend, "..", "fire-dashboard");
const target = join(frontend, "public", "fire-dashboard");
const parts = ["index.html", "styles.css", "js", "data"];

for (const part of parts) {
  if (!existsSync(join(source, part))) {
    console.error(`Missing ${join(source, part)}`);
    process.exit(1);
  }
}

rmSync(target, { recursive: true, force: true });
for (const part of parts) {
  cpSync(join(source, part), join(target, part), { recursive: true });
}
console.log(`Synced fire-dashboard -> ${target}`);
