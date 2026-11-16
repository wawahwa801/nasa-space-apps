# One Linux container: Next.js publicly on 8080, Flask internally on 5000.
FROM node:24-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY fire-dashboard/ /app/fire-dashboard/
ENV NEXT_TELEMETRY_DISABLED=1 BACKEND_URL=http://127.0.0.1:5000
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 \
    NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 \
    BACKEND_URL=http://127.0.0.1:5000 MODEL_CACHE_DIR=/app/backend/.model-cache
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
COPY backend/requirements.txt backend/requirements-inference.txt /tmp/
# Install CPU wheels first; avoid downloading CUDA libraries on EC2.
RUN pip install --no-cache-dir 'torch>=2.8,<3' --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /tmp/requirements-inference.txt
COPY backend/ /app/backend/
COPY ml/*.py /app/ml/
COPY physics-flex2/*.py /app/physics-flex2/
COPY --from=frontend-build /app/frontend/ /app/frontend/
COPY --from=frontend-build /app/fire-dashboard/ /app/fire-dashboard/
COPY deploy/run_fullstack.py /app/deploy/run_fullstack.py
COPY deploy/rds-ca-bundle.pem /app/deploy/rds-ca-bundle.pem
RUN useradd --create-home --uid 10001 pyroclast \
    && mkdir -p /app/backend/.model-cache \
    && chown -R pyroclast:pyroclast /app/backend/.model-cache /app/frontend/.next
USER pyroclast
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=8)"
CMD ["python", "/app/deploy/run_fullstack.py"]
