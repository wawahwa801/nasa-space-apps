// Serves the NASA comparison dashboard straight from ../fire-dashboard, so
// there is no copy step to forget (a missing copy gave "HTTP 404").
// Only the files the dashboard needs are served: index.html, styles.css,
// js/ and data/. Paths outside those are rejected.

import { readFile, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

// The dev/build commands run in frontend/; fall back to the repo root.
const ROOT = [path.join(process.cwd(), "..", "fire-dashboard"), path.join(process.cwd(), "fire-dashboard")]
  .find((dir) => existsSync(path.join(dir, "index.html")));

const ALLOWED = /^(index\.html|styles\.css|js\/[\w.-]+\.js|data\/[\w ./-]+\.(js|csv|json))$/;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};

export async function GET(_request, { params }) {
  const parts = (await params).path || [];
  const rel = parts.join("/");
  if (!ROOT) {
    return new Response("fire-dashboard folder not found next to frontend/", { status: 500 });
  }
  if (!ALLOWED.test(rel) || parts.some((p) => p === ".." || p.startsWith("."))) {
    return new Response("Not found", { status: 404 });
  }
  const file = path.resolve(ROOT, rel);
  if (!file.startsWith(path.resolve(ROOT) + path.sep)) {
    return new Response("Not found", { status: 404 });
  }
  try {
    if (!(await stat(file)).isFile()) throw new Error("not a file");
    const body = await readFile(file);
    return new Response(body, {
      headers: {
        "Content-Type": TYPES[path.extname(file)] || "application/octet-stream",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
