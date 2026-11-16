# Project

A starter project for an interactive dashboard with a Next.js frontend and Flask API. The app can grow to include model training and external API integrations.

## Project structure

```text
frontend/        Next.js dashboard (Pyroclast workspace + NASA data comparison)
fire-dashboard/  NASA data comparison dashboard (standalone page, also embedded in frontend/)
data/            NASA fire experiment data sets
backend/         Flask API
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
npm ci
npm run dev
```

`npm ci` installs the exact versions in `package-lock.json`. Use `npm install` only when changing dependencies, then commit the updated lockfile and run `npm audit`. The `overrides` in `package.json` patch `postcss` (bundled with Next.js 15) and `minimatch` (ESLint tooling) against published advisories until upstream releases include the fixes.

### Windows (PowerShell)

The commands above are for macOS and Linux. On Windows, use three PowerShell terminals, starting from the repository root in each.

Backend (port 5000):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Hybrid model service (port 5055; needed for the hybrid Simulate controls, see [below](#hybrid-image--illustrative-room-simulation)):

```powershell
python -m venv .venv-ml
.venv-ml\Scripts\python -m pip install -r ml\requirements.txt
.venv-ml\Scripts\python ml\dashboard_simulation.py
```

Frontend (port 3000):

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

- These commands call the virtual environment's `python` directly and use `npm.cmd`, so they work even when PowerShell blocks scripts ("running scripts is disabled on this system"). To use `.venv\Scripts\activate` and plain `npm` instead, run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once.
- `Failed to proxy http://127.0.0.1:5055/api/runs ... ECONNREFUSED` in the frontend terminal means the hybrid model service is not running. Check its own terminal for the error.
- Clone with Git rather than downloading a ZIP, so `git pull` keeps your copy current.

Open `http://localhost:3000`. The NASA-comparison view works with the frontend alone. The separate Flask API provides `http://localhost:5000/api/health` and the analysis endpoints below.

The page has the Pyroclast flame simulation and, below it, the NASA data comparison from
`fire-dashboard/` (rendered in an isolated shadow root). The two take separate inputs:

- **Parameters** (left panel): the flame model's conditions. The live selected image updates as you edit;
  **Simulate** passes the same conditions and equivalent diameter into the room solver.
  Binary apparatus flags, missingness flags and camera codes remain at recorded preset
  values and are omitted from the controls. Image-scale and K assumptions are collapsed.
- **NASA comparison parameters** (collapsible, under "NASA data comparison"): air quality
  (O₂, pressure, temperature, humidity, CO₂, gravity) and the NASA-only inputs (fuels,
  materials, leaks, monitoring). They change the comparison, assessment, gas levels, charts
  and live monitoring, not the flame.
- **Room fire spread** opens below the main preview when you press **Simulate**.
  Edit the environment beside the map, choose ignition, toggle doors and control playback
  in the same workspace. There is no separate room page.
- **AI insights** is a collapsible header at the bottom of the simulation page.
  Its Summary, Applied parameters and Assumptions & uncertainty headers organize
  the explanation and the last applied scenario.
- The selected CNN image is stationary at rest. Hover or keyboard focus prepares and
  plays a cached nearby-condition sweep; leaving restores the selected prediction.
  Reduced-motion users keep a stationary image. These alternatives are sensitivity
  illustrations, not elapsed-time frames or calibrated uncertainty.

Unit pickers on the air-quality sliders switch O₂/CO₂ between % and ppm, pressure between
kPa, psia and atm, and temperature between °C, K and °F.
The app serves `fire-dashboard/` directly at `/nasa-dashboard/`, so there is no copy or
sync step; edit `fire-dashboard/` and reload.

The **Compare CNN & reference** button reveals the feature-only CNN and retrieved source images for the selected prediction. The standalone feature-retrieval component is retained in source, but has no separate dashboard tab.

The images and provenance are in `frontend/public/flames/flex2/`. After acquiring and preparing FLEX-2 data as described in [ml/FLEX2.md](ml/FLEX2.md), regenerate them with `python ml/export_flex2_retrieval.py --data /path/to/flex2-study`. Verify the bundled image hashes and joins using `node frontend/scripts/check-feature-retrieval.mjs`.

The bundled 100-run source subset was prepared by the expansion in [PR #30](https://github.com/wawahwa801/nasa-space-apps/pull/30). Until that acquisition workflow merges, use its verified prepared dataset to reproduce this expanded bundle; the older lab instructions prepare a smaller subset. The frontend itself already includes the complete exported bundle and needs no source-data download.

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

The dashboard's Feature retrieval tab displays real recorded FLEX-2 images. The separate [FLEX-2 lab](ml/FLEX2.md) at `http://127.0.0.1:5051/flex2/` also provides an experimental CNN comparison; its CNN currently performs worse than mean/retrieval baselines. See [ml/README.md](ml/README.md) for the older BASS-II PMMA and FLEX methanol experiments at port 5050, and [ml/SPICE.md](ml/SPICE.md) for the separate SPICE prototype. These are bounded image experiments, not validated physical fire forecasts. The previous four-source prototype is preserved in `ml/LEGACY.md`.

## Hybrid image → illustrative room simulation

On the dashboard integration branch, install `ml/requirements.txt` in a Python
environment and run `python ml/dashboard_simulation.py` from the repository root.
Start the Next.js frontend normally (`cd frontend && npm ci && npm run dev`).
Next.js proxies `/hybrid/*` to the local model service on port 5055.
Open the Parameters panel, choose a recorded state and edit the hybrid controls,
then press **Simulate**. The service uses the published geometry model with its
retrieved-texture compositor and sends the mask's equivalent-area diameter to
the room solver with the explicitly assumed mm/pixel scale and burn coefficient.
The result includes the actual applied controls, model note and size conversion.
The central view shows the predicted image and starts room playback; changing
hybrid inputs invalidates the previous result. Play/pause and time scrubbing are
available below the room graph. Original atmosphere controls serve the NASA
comparison and are not inputs to this illustrative room solver.

This uses a flame-size proxy, not a measured liquid-droplet diameter. Room
transfer, scale and burn coefficient are illustrative assumptions. The solver
does not calculate ventilation or oxygen effects. The model fitted all runs and
has no held-out accuracy claim. This integration needs independent review before
merging into main.

Check the actual model-to-physics boundary with:
`python -m unittest discover -s ml -p test_dashboard_simulation.py`.
