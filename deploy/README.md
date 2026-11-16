# Vercel deployment

The connected `nasa-space-apps` project uses repository root `.` and the Services
framework preset. Keep those settings; `vercel.json` defines three services:

- Frontend: Next.js, including traced NASA comparison assets from fire-dashboard.
- Backend: Flask via backend/wsgi.py; set LLM provider secrets in Vercel environment settings.
- ML: CPU PyTorch container via deploy/ml.Dockerfile, with published checkpoints,
  prepared references, and the illustrative physics layer bundled together.

Frontend runtime routes read the generated BACKEND_URL and ML_URL service bindings.
Do not configure these as localhost or NEXT_PUBLIC variables. `/api/*` routes to
Flask directly; `/hybrid/*` and `/insight-api/*` proxy from frontend functions.
Binding URLs are runtime-only and therefore are not embedded by next.config rewrites.

Local use remains supported: backend port 5000, hybrid service port 5055, frontend
port 3000. Optional BACKEND_URL and ML_URL override local services.

Push the task branch to create a connected Vercel preview. Verify `/api/health`,
`/nasa-dashboard/index.html`, `/hybrid/runs`, one `/hybrid/compare` query from a
recorded state, and `/hybrid/simulate` before production promotion. The ML image
build installs CPU wheels and can take longer than the frontend. Container image
build and cold-start inference must be verified on Vercel; a local frontend build
alone does not establish deployment success. No datasets are acquired or models
trained during startup. Inference uses the committed snapshot checksums.
