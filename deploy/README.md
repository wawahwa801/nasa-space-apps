# Vercel deployment

The connected `nasa-space-apps` project uses repository root `.` and the Services
framework preset. Keep those settings; `vercel.json` defines three services:

- Frontend: Next.js, including traced NASA comparison assets from fire-dashboard.
- Backend: Flask via backend/wsgi.py; set LLM provider secrets in Vercel environment settings.
- ML: CPU PyTorch container via deploy/ml.Dockerfile, with published checkpoints,
  prepared references, and the illustrative physics layer bundled together.

The S3 hybrid integration now sends `/hybrid/*` through BACKEND_URL to
`/api/hybrid/*`. Configure BACKEND_URL to a backend with the inference
dependencies, DB_* settings, and private S3 access described in
[HYBRID_DEPLOYMENT.md](../backend/HYBRID_DEPLOYMENT.md). The previous lightweight
Flask service alone is insufficient for these routes. An EC2 backend can serve
both the existing API and hybrid inference; ML_URL is no longer used by the
frontend hybrid proxy. The legacy ML service remains in vercel.json for separate
standalone use; this change does not deploy or remove existing services.

Frontend runtime routes read BACKEND_URL at request time.
Do not configure these as localhost or NEXT_PUBLIC variables. `/api/*` routes to
Flask directly; `/hybrid/*` and `/insight-api/*` proxy from frontend functions.
Binding URLs are runtime-only and therefore are not embedded by next.config rewrites.

Local use: inference-enabled backend port 5000 and frontend port 3000.
BACKEND_URL overrides the backend address. Port 5055 is no longer a frontend
fallback.

Push the task branch to create a connected Vercel preview. Verify `/api/health`,
`/nasa-dashboard/index.html`, `/hybrid/runs`, one `/hybrid/compare` query from a
recorded state, and `/hybrid/simulate` before production promotion. The ML image
build installs CPU wheels and can take longer than the frontend. Container image
build and cold-start inference must be verified on Vercel; a local frontend build
alone does not establish deployment success. No datasets are acquired or models
trained during startup. Inference uses the committed snapshot checksums.
