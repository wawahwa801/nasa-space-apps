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

## LLM analysis API

The backend includes a provider-neutral framework in `backend/llm/` that takes quantitative or qualitative data, builds a prompt, and sends it to a configurable LLM provider. Until a real provider is added, the built-in `mock` provider returns canned output so the full pipeline can run offline.

```text
backend/llm/
  config.py            LLM settings read from environment variables
  input_processing.py  validates data and computes summary statistics
  prompts.py           system prompt and prompt templates
  service.py           validate -> build prompt -> call provider
  providers/
    base.py            LLMProvider interface, request/response types, errors
    mock.py            offline provider for development and tests
    template.py        starting point for a real provider
    __init__.py        provider registry
```

### Endpoints

- `GET /api/llm/status` returns the active provider, model, and registered providers.
- `POST /api/analyze` accepts JSON:

```json
{
  "data": [{"site": "A", "temp": 20}, {"site": "B", "temp": 31}],
  "data_type": "auto",
  "instructions": "Which site is hotter, and by how much?",
  "context": "Daily maximum temperatures in Celsius."
}
```

`data` may be a string or list of strings (qualitative), or a list of numbers, an object of named number lists, or a list of row objects (quantitative). `data_type` is `auto`, `quantitative`, or `qualitative`. `instructions` and `context` are optional.

The response contains `output` (the model's text), `provider`, `model`, `usage`, and `input` (the detected data type and computed statistics). Invalid input returns `400`. Provider failures return `503` when retrying may help and `502` otherwise.

### Configuration

Copy `backend/.env.example` to `backend/.env` and set `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY`. Do not commit `.env`.

### Adding a provider

1. Copy `backend/llm/providers/template.py` to a new file and implement `generate()`.
2. Add the provider's SDK to `backend/requirements.txt`.
3. Register the class in `backend/llm/providers/__init__.py`.
4. Set `LLM_PROVIDER` to the provider's `name` in `backend/.env`.

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

## Next steps

- Add dashboard views and interactive visualizations in `frontend/app/`.
- Add API integrations and application endpoints in `backend/app.py`.
- Add model training code and document its data, configuration, and outputs before connecting it to the API.
- Keep secrets in environment variables; do not commit credentials or private data.

## Flame-model experiments

See [ml/README.md](ml/README.md) for separate BASS-II PMMA and NASA FLEX methanol experiments. The simplified local page at `http://127.0.0.1:5050` has one experiment selector, relevant physical controls and two 256×256 comparison images. Models use independent whole-run splits and explicit baselines; neither has demonstrated a meaningful accuracy win. The page also includes 274 FLEX and 8 FLEX-2 conditions rows and original CSV downloads. The previous four-source prototype is preserved in `ml/LEGACY.md`.
