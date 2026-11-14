# Project

A starter project for an interactive dashboard with a Next.js frontend and Flask API. The app can grow to include model training and external API integrations.

## Project structure

```text
frontend/   Next.js dashboard
backend/    Flask API
```

## Requirements

- Node.js 20 or newer
- Python 3.10 or newer

## Run locally

Start the backend in one terminal:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The API runs at `http://localhost:5000`.

Start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The dashboard calls the Flask health endpoint at `http://localhost:5000/api/health`.

## Next steps

- Add dashboard views and interactive visualizations in `frontend/app/`.
- Add API integrations and application endpoints in `backend/app.py`.
- Add model training code and document its data, configuration, and outputs before connecting it to the API.
- Keep secrets in environment variables; do not commit credentials or private data.

## Feature-to-image CNN experiment

See [ml/README.md](ml/README.md) to acquire 150 image–feature pairs each from BASS-II, SAFFIRE-I, SAFFIRE-III and SPICE, train the condition-only CNN, and run the local lab at `http://127.0.0.1:5050`. The current sample uses 600 pairs, 128×128 targets and a 6 fps sampling target. Time is provenance only. Physical measurements are used where documented; missing features remain unknown. Predictions are illustrative and do not yet outperform the held-out mean-image baseline.
