# Feature-to-image flame CNN

The current prototype takes **five numeric features** and predicts a 64×64 RGB flame image. It uses a small feature encoder plus a convolutional decoder (144,155 parameters). It does not require a source image at inference. The earlier next-frame model is retained in `flame.py` for comparison.

## Start the test interface

From the repository root (tested with Python 3.14 on macOS CPU):

```bash
python3 -m venv ml/.venv
source ml/.venv/bin/activate
pip install -r ml/requirements.txt
python ml/fetch_bass.py
python ml/conditional.py prepare
python ml/conditional.py train --epochs 250
python ml/lab.py
```

Open **http://127.0.0.1:5050**. If the data/checkpoint already exist, only the final command is needed. Restart the server after retraining. The lab runs separately from the team's Next.js dashboard and Flask backend.

Choose a documented trial preset or change the sliders. Every prediction is computed by `conditional.pt`; the browser does not draw a procedural flame. The nearest recorded evidence image is retrieved separately and is never fed into the CNN. A novel feature combination has no corresponding measured ground truth just because it is within the slider bounds.

| Model input | Training range | Meaning |
| --- | --- | --- |
| Film thickness | 0.1–0.3 mm | Explicit micron dimensions in the source table |
| Fan display | 46.5–62 | Instrument display reading; **not m/s** |
| Air display | 2–5 | Instrument display reading; **not m/s** |
| Initial CO₂ | 0.43–0.51% by volume | Trial-level initial measurement, not a per-frame sensor reading |
| Video time | 15–34.5 s | Time from start of video, not ignition |

Initial oxygen is 22.2%, film width is 2 cm, and flow restrictor is 2 across this sample; their effects cannot be learned here. Pressure, calibrated airflow, gravity variation, temperature, humidity, and fuel categories remain unsupported. The table explicitly identifies PMMA for B1/B4 but does not name the polymer in every selected film description. Preserve those original descriptions; confirm material comparability before expanding training.

## Architecture and training

`conditional.py` encodes the five normalized scalars through linear layers (5 → 64 → 32×8×8), then three transposed convolutions decode to 16×16, 32×32, and 64×64 RGB output. Sigmoid bounds the image to [0,1]. The network learns from experimental images, not manually specified flame shapes.

Only training trials determine normalization ranges. B1, B4, B5, and B12 provide 160 training frames; the entire B3 trial provides 40 held-out frames. Frames are sampled every 0.5 s from 15 to 34.5 s. A fixed normalized ROI (x 5–95%, y 22–95%) removes upper telemetry; aspect-preserving padding fits the ROI to 64×64. Background dominates these videos, so the loss uses pixel MSE weighted by `1 + 100 × target maximum RGB intensity`. This emphasizes observed luminous pixels; it does not supply physical heat-flux labels.

The 250-epoch run (seed 42, CPU) gave held-out pixel MSE **0.005215**, versus **0.001571** for the mean training image. The model responds to all five features but **does not outperform that baseline**. Correlated settings from only four trials cannot isolate causal effects. Treat generated images as illustrative and avoid interpreting them as safety predictions, calibrated flame geometry, or heat flux. This is a feature-conditioned generator prototype, not the complete physics/CNN coupling in the Planning document.

Artifacts (ignored by Git):

- `ml/data/conditional.npz`: feature vectors, image targets, trial IDs.
- `ml/data/conditional-manifest.json`: exact CSV rows, source videos, hashes, timestamps, and original material descriptions.
- `ml/artifacts/conditional.pt`: weights, architecture ID, training-only normalization, feature specification, metrics.
- `ml/artifacts/conditional-metrics.json`: held-out error, baseline, and per-feature sensitivity probes.
- `ml/artifacts/conditional-comparison.png`: first B3 prediction / recorded target.

The five source videos and CSV total about 51 MB. `fetch_bass.py` downloads only selected unrestricted files (15 MB per-file cap) from the [public BASS-II catalog](https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-25). The catalog reports CC0-1.0. It uses NASA's public download endpoint to resolve temporary URLs; those URLs are not stored as provenance. The earlier `/studies/PSI-25` metadata request was the wrong catalog route, which explains the initial access failure. The other requested datasets have not been added to this model.

## API

`GET /api/info` reports supported features, ranges, defaults, training metrics, source trials and unsupported parameters.

```bash
curl 'http://127.0.0.1:5050/api/predict?thickness=0.2&fan=59&air=5&co2=0.43&time=20'
```

`GET /api/predict` returns a PNG data URL in `prediction`, a separately retrieved `reference`, its trial/conditions, and a limitations message. All inputs must be finite and within training ranges; unsupported parameters return HTTP 400. Bounds do not guarantee a supported joint combination. There is no source-image argument.

## Scale toward the Planning document

1. Acquire many independent trials spanning oxygen, calibrated airflow, pressure, geometry and verified fuel categories. Join images to documented measurements and preserve missing fields instead of filling them in.
2. Confirm comparable BASS-II/SAFFIRE/SoFIE camera views, timing, units, material descriptions and targets before combining them. Keep SPICE jet flames a separate domain. Inspect PSI-62 for actual calibrated temperature/soot measurements before using it for richer supervision.
3. Expand the experiment manifest and split entire trials/conditions into training, validation and untouched test sets. Nearby frames and camera views from one trial must stay together.
4. Update the feature specification and normalization, stream frames with a Dataset/DataLoader, and increase data diversity before increasing model size. Use a GPU for larger runs. Add domain/camera controls to avoid learning experimental setup as a shortcut.
5. Compare held-out flame-region errors and geometry against retrieval and mean-image baselines. Use the Planning document's feature-based retrieval approach while generation quality remains limited. Display source conditions and out-of-range/uncertain cases.
6. Add calibrated heat-flux targets and simulation-state inputs before coupling CNN output to a physics spread solver. RGB brightness is not heat flux. Keep retrieved evidence, illustrative generated images, and physics-based spread estimates distinct.

Data and physical-label work is tracked in [issue #4](https://github.com/wawahwa801/nasa-space-apps/issues/4).

## Earlier image-input baseline

`flame.py` still supports `prepare`, `train`, and `predict` for the residual next-frame CNN. It uses separate `tiny.pt` weights. Those weights are incompatible with the conditional decoder and are not used by the current lab. Historical B1/B3 residual MSE was 0.0006166 versus persistence 0.0006226 on a different frame-preparation pipeline; it is not directly comparable to the conditional model's held-out score.
