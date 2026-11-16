# S3-backed animated hybrid

The browser calls `/hybrid/*` on Next.js. Next.js forwards these requests to
`BACKEND_URL/api/hybrid/*`. Flask queries `model_registry.models` for the latest
ready `flex2-hybrid` model, downloads its private S3 package, checks its SHA-256,
and runs inference on the server. Model weights never go to the browser.
There is no fallback to the standalone service on port 5055.

## Prepare the backend

Use Python 3.11 or later and install the inference dependencies:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-inference.txt
```

Set the existing `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` in
`backend/.env`, plus:

```dotenv
HYBRID_MODEL_NAME=flex2-hybrid
HYBRID_S3_BUCKET=pyroclast-ai-204898220304-us-west-2-an
HYBRID_S3_PREFIX=models/flex2-hybrid/
AWS_REGION=us-west-2
```

Use a database login with SELECT access to the registry. Use your normal AWS
credential chain locally and an EC2 instance role with `s3:GetObject` access to
the hybrid prefix in production. Keep the bucket private. Do not put database
passwords or AWS credentials in frontend environment variables.

## Publish a new version

The hybrid requires the geometry checkpoint, reference dataset, and baseline
CNN. The earlier feature-only `models/flex2/v1/selected.pt` is insufficient.
Build a complete package from the checked-in model snapshot:

```sh
backend/.venv/bin/python backend/package_hybrid.py --out /tmp/hybrid-new.zip
```

The command prints a SHA-256 and content-addressed S3 key. Upload to that key
in the configured bucket; keep previously published keys immutable. Verify a
fresh download against the printed SHA-256 before registering it. Register a
new version as ready only after a successful prediction with that package.
Use `database/register_hybrid_demo.sql` for the first verified demo publication.
Execute that file as the database administrator in DBeaver, connected to
`pyroclast`; the runtime reader cannot insert rows. Commit the transaction.
For later versions use distinct versions, keys and checksums, with actual
training completion times when available.

## Run and test

From the repository root:

```sh
backend/.venv/bin/python backend/app.py
curl -f http://127.0.0.1:5000/api/models/latest?model_name=flex2-hybrid
curl -f http://127.0.0.1:5000/api/hybrid/runs
cd frontend
npm install
BACKEND_URL=http://127.0.0.1:5000 npm run dev
```

Open localhost:3000. The flame automatically cycles cached predictions and the
Room simulation uses the same model version. Responses include `model.source`
equal to `s3`. Requests after loading the controls send `X-Model-ID` so an
animation cannot mix versions during a publication. Reload to select a newer
ready version. No ready row, missing AWS access, or a checksum failure returns
503; fix the server configuration rather than starting the old local predictor.
The first request includes download and model warm-up and can take longer.

```sh
backend/.venv/bin/python -m pytest backend/tests
node --test frontend/scripts/test-service-proxy.mjs
cd frontend
npm run lint
npm run build
```

For EC2 start with one Gunicorn worker and two threads from `backend`:
`gunicorn --workers 1 --threads 2 --timeout 180 'app:create_app()'`.
Each worker maintains its own model cache and serializes inference. Disk cache
defaults to `backend/.model-cache`; ensure that directory is writable and has
room for packages. The runtime retains two loaded versions. Removing ready
status also stops pinned requests for that version. Select the worker count
after measuring available memory and prediction latency.

On Windows PowerShell replace `backend/.venv/bin/python` with
`backend/.venv/Scripts/python.exe`, use `$env:BACKEND_URL='http://127.0.0.1:5000'`
before `npm run dev`, and use a new path under `$env:TEMP` for the ZIP. Use a
production Linux EC2 environment for the Gunicorn command.
