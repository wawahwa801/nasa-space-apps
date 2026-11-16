FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
COPY ml/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 && pip install --no-cache-dir -r /tmp/requirements.txt gunicorn
COPY ml /app/ml
COPY physics-flex2 /app/physics-flex2
COPY frontend/public/flames/flex2 /app/frontend/public/flames/flex2
WORKDIR /app/ml
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 1 --timeout 180 deployment:app"]
