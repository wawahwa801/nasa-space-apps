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

## Flame-model experiments

See [ml/README.md](ml/README.md) for separate BASS-II PMMA and NASA FLEX methanol experiments. The simplified local page at `http://127.0.0.1:5050` has one experiment selector, relevant physical controls and two 256×256 comparison images. Models use independent whole-run splits and explicit baselines; neither has demonstrated a meaningful accuracy win. The page also includes 274 FLEX and 8 FLEX-2 conditions rows and original CSV downloads. The previous four-source prototype is preserved in `ml/LEGACY.md`.
