# Tiny flame CNN

This is the first image-processing experiment toward the Google Doc's local flame surrogate. It learns to predict the next 64×64 RGB video frame with a three-layer CNN (1,827 parameters). It does **not** predict heat flux, ignition probability, environmental effects, or validated fire spread. The physics baseline and CNN/physics coupling in the document remain future work.

## Data status

The requested sources are [BASS-II PSI-25](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25), [SAFFIRE-I PSI-98](https://psi.nasa.gov/physci/repo/data/investigations/PSI-98), [tomography PSI-62](https://psi.nasa.gov/physci/repo/data/investigations/PSI-62), and [SPICE PSI-107](https://psi.nasa.gov/physci/repo/data/investigations/PSI-107).

No raw files from these four datasets have been downloaded. The PSI-25 catalog request returned a permission error; the PSI pages render through JavaScript and other requests were intermittent. This is an access gap, not proof that the datasets are unavailable. Obtain files through the portal's legitimate access process; do not bypass permissions.

For an executable pipeline demonstration only, `prepare` downloads one low-resolution **SAFFIRE-V** public NASA media video, ID `GRC-2021-CN-00008`, found through the [NASA Image and Video Library API](https://images-api.nasa.gov/search?q=Saffire&media_type=video). This is neither SAFFIRE-I nor a raw PSI training sample. It may contain edited footage, titles, and overlays. Inspect `first-frame.png` and the source video before interpreting results. The download is capped at 30 MiB; defaults extract only 80 frames, spaced 0.25 s apart. Source URL, video SHA-256, timestamps, and image dimensions are saved alongside each run. Data and checkpoints stay outside Git.

## Train and run

Run from the repository root. Tested environment: Python 3.14 on macOS, CPU. Dependencies are pinned to the versions used for the demonstration.

```bash
python3 -m venv ml/.venv
source ml/.venv/bin/activate
pip install -r ml/requirements.txt
python ml/flame.py prepare
python ml/flame.py train --epochs 10
python ml/flame.py predict ml/data/saffire-v-demo/first-frame.png
```

Outputs in `ml/artifacts/`:

- `tiny.pt`: model weights, loaded by the prediction command.
- `metrics.json`: pixel MSE, persistence baseline MSE, sample counts, seed, evaluation scope.
- `comparison.png`: input / CNN prediction / actual next frame, left to right.
- `prediction.png`: prediction for the supplied image. For this demo the horizon is 0.25 s; use the same preprocessing and sampling interval at inference.

Lower MSE is better; a model worse than simply copying the current frame is not useful yet. Dark backgrounds and static overlays can dominate this metric, so also inspect flame-region errors. The default uses a chronological 75/25 split with no shared frame across the boundary. Both portions are from the same video: this is a smoke test, **not an independent experimental evaluation**.

## Import real experiment videos

```bash
python ml/flame.py prepare --video /path/to/raw-trial-A.mp4 --run-id bass25-trial-A --source https://psi.nasa.gov/physci/repo/data/investigations/PSI-25 --start 2 --frames 120 --interval 0.25
python ml/flame.py prepare --video /path/to/raw-trial-B.mp4 --run-id bass25-trial-B --source https://psi.nasa.gov/physci/repo/data/investigations/PSI-25 --frames 120
python ml/flame.py train --run-id bass25-trial-A --val-run bass25-trial-B --epochs 30
```

Use genuinely different experimental trials, not clips renamed from the same trial. Record camera calibration, orientation, frame timing, material, oxygen, pressure, airflow, gravity, units, and reuse terms separately; the tiny script records only video provenance and does not consume environmental conditions. Unknown values must stay unknown. Avoid mixing physically different experiments into one undifferentiated training set.

## Scale toward the model in the document

1. Acquire raw BASS-II/SAFFIRE-I trials first, with matched conditions and outcomes. Inspect PSI-62 for actual calibrated temperature/soot targets before using it. Treat SPICE jet flames as a separate domain from solid fuels. Review each source's reuse terms.
2. Create a per-trial manifest and split complete trials into training, validation, and untouched test sets **before** extracting frames. Hold out materials and flow/oxygen conditions to measure generalization. Keep adjacent frames and duplicate views together.
3. Crop consistent flame regions, remove overlays, preserve aspect ratio, and align sensor timestamps. Add manually reviewed masks or measured flame geometry. For heat flux, require calibrated heat-flux labels or a defensible physical conversion; brightness is not heat flux.
4. Replace the one-frame input with recent frames and spatial simulation state. Encode measured conditions/fuel properties in a separate branch or spatial channels; predict flame masks/fields and calibrated flux only where labeled. Compare against persistence and the document's physics-only baseline.
5. Replace this in-memory loader with a streaming Dataset/DataLoader over many trial shards, add configurable paths/checkpoints, and train on a GPU with mixed precision. Increase data diversity before model size. The current command supports one training run and one validation run; it is intentionally not a bulk-training engine.
6. Measure per-trial errors, held-out condition performance, uncertainty, and out-of-range inputs. Couple validated flux to a physics solver with consistent units and energy accounting, then connect inference to Flask/dashboard. More epochs or a larger network alone cannot provide missing physical labels.

The dashboard should retain the document's exploratory framing until independent validation supports stronger claims.

## Recorded smoke-test result

On the downloaded 80-frame sample, 10 epochs trained on 59 pairs and evaluated on 19 same-video pairs. CNN pixel MSE was **0.02738**, versus **0.002934** for persistence. The CNN performed worse than persistence, so this checkpoint demonstrates the pipeline only and should not be used for simulation. Source SHA-256: `5b92c74d633f816070ec893d9b06c6448f545c48b97b47a61d3dee1c25d01417`.

Raw-data acquisition and target-label decisions are tracked in [issue #4](https://github.com/wawahwa801/nasa-space-apps/issues/4).
