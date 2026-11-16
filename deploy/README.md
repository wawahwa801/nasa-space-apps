# Vercel deployment

The connected `nasa-space-apps` project uses repository root `.` and the Services
framework preset. Keep those settings; `vercel.json` defines three services:

- Frontend: Next.js, including traced NASA comparison assets from fire-dashboard.
- Backend: Flask via backend/wsgi.py; set LLM provider secrets in Vercel environment settings.
- ML: CPU PyTorch container via deploy/ml.Dockerfile, with published checkpoints,
  prepared references, and the illustrative physics layer bundled together.

Frontend runtime routes read the generated BACKEND_URL and ML_URL service bindings.
Do not configure these as localhost or NEXT_PUBLIC variables. `/api/*` routes to
Flask directly (including the AI insight endpoints `/api/analyze` and
`/api/safety-insights`); `/hybrid/*` proxies from a frontend function.
Binding URLs are runtime-only and therefore are not embedded by next.config rewrites.

## AI insights key (never in the repository)

The OpenRouter key lives only in the backend service's environment. The browser calls
`/api/analyze` and `/api/safety-insights` on the same site; Flask adds the key when it
calls the provider, so the key never reaches the page or GitHub.

1. In Vercel: Project → Settings → Environment Variables, add for **Production** and
   **Preview**:
   - `LLM_PROVIDER` = `openrouter`
   - `LLM_MODEL` = e.g. `dots-studio/dots-3-note-preview:free`
   - `LLM_API_KEY` = your OpenRouter key, marked **Sensitive**
2. Redeploy (environment changes apply to new deployments only).
3. Check `https://<your-site>/api/llm/status`: it should show `"provider": "openrouter"`
   and `"configured": true`. It never shows the key.

Public-site protection is on by default on Vercel: the two endpoints only answer
requests whose Origin/Referer is the same site (or listed in `LLM_ALLOWED_ORIGINS`,
e.g. a custom domain), and each client IP is limited to 6 requests per minute and 100
per day, with 30 per minute per server instance (`LLM_RATE_LIMIT_PER_MINUTE`,
`LLM_RATE_LIMIT_PER_DAY`, `LLM_GLOBAL_LIMIT_PER_MINUTE`). The counters live in memory
per serverless instance, so for a hard ceiling also add a Vercel Firewall rate-limit
rule for `/api/analyze` and `/api/safety-insights`, and set a spending limit on the
OpenRouter key. If a key is ever exposed, revoke it in OpenRouter and set a new one
in Vercel.

Local use remains supported: backend port 5000, hybrid service port 5055, frontend
port 3000. Optional BACKEND_URL and ML_URL override local services.

Push the task branch to create a connected Vercel preview. Verify `/api/health`,
`/nasa-dashboard/index.html`, `/hybrid/runs`, one `/hybrid/compare` query from a
recorded state, and `/hybrid/simulate` before production promotion. The ML image
build installs CPU wheels and can take longer than the frontend. Container image
build and cold-start inference must be verified on Vercel; a local frontend build
alone does not establish deployment success. No datasets are acquired or models
trained during startup. Inference uses the committed snapshot checksums.
