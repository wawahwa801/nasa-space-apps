# Focused BASS-II and FLEX flame experiments

**Active comparison: [FLEX-2 live retrieval and CNN](FLEX2.md)** at http://127.0.0.1:5051/flex2/. It uses real RGB spherical-flame data with a CNN/Retrieval switch and slider updates while dragging. The SPICE page remains available separately.

The frozen 100-run FLEX-2 retrieval library and trained CNN are included in Git. After installing `ml/requirements.txt`, run `python ml/verify_flex2_models.py` and `python ml/flex2_lab.py`; NASA acquisition and retraining are optional. See the published-snapshot instructions and limitations in [FLEX2.md](FLEX2.md).

**New: [SPICE retrieval and feature-to-image CNN](SPICE.md).** Run `python ml/spice_lab.py` for the standalone comparison at http://127.0.0.1:5051/spice/. Its matched data and trained checkpoint must be prepared first; commands and evaluation are in the linked guide. When those artifacts exist, restarting `ml/lab.py` also mounts it at `/spice/` on port 5050.

The local page now has one experiment selector, the relevant physical inputs, a CNN image, a nearest-training-trial image and an optional mask view. Detailed scores and NASA conditions are collapsed below. Two separately trained models avoid pooling solid PMMA films with liquid methanol droplets. Both produce 256×256 images and remain experimental.

| Experiment | Independent targets | Train / validation / test | Source frames used |
| --- | --- | --- | --- |
| BASS-II, documented PMMA | 12 | 8 / 2 / 2 whole trials | 120 selected frames |
| FLEX, methanol, camera B | 8 | 4 / 2 / 2 whole runs | 119 mid-burn frames + 120 post-reported-burn baseline frames |

Each target summarizes one experiment. The selected frames are not counted as independent environmental conditions. Neither model takes a source image or video time at inference.

## Setup and run

Use a dedicated checkout so other tasks can switch branches without disturbing the server. From the repository root (Python 3.14 tested, macOS CPU):

```bash
python3 -m venv ml/.venv
source ml/.venv/bin/activate
pip install -r ml/requirements.txt
python ml/fetch_bass.py
python ml/bass_study.py fetch
python ml/bass_study.py prepare
python ml/bass_train.py --epochs 400
python ml/flex_data.py
python ml/flex_images.py fetch
python ml/flex_images.py prepare
python ml/flex_train.py --epochs 400
python ml/flex_data.py
python ml/lab.py
```

Open **http://127.0.0.1:5050**. If the current artifacts already exist, only the final command is needed. Stop any previous server on that port first; restart after retraining. The template, models and data are held in memory after startup.

The previous four-source model is preserved in [LEGACY.md](LEGACY.md), `multi_model.py`, `legacy_lab.py` and `templates/legacy.html`. It uses separate artifacts and is not the current page. Run `python ml/legacy_lab.py` after stopping the active server if you need the old interface.

## BASS-II: comparable material and standardized targets

[PSI-25 BASS-II](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25) supplies original material, geometry and initial oxygen labels. The experiment uses only explicitly documented PMMA and uniquely matched primary-view videos. It attempted 15 trials; B14, B18 and B20 failed decoding and were excluded with reasons. Ambiguous B15 and missing-primary-view B17 were not candidates.

A fixed rule searches the early video for a five-second window with low luminous-area variation. Ten 2-fps snapshots define that window; this is a visually stable-stage proxy, **not proof of physically steady conditions**. A fixed camera ROI, aspect-preserving padding, color-based mask and translation-only registration produce a representative target. Relative pixel extent is retained; camera scale is not physically calibrated. Glowing fuel and imperfect masks remain limitations requiring manual review.

Inputs are **initial oxygen (% by volume), film thickness (mm), and film width (cm)**. Initial oxygen is trial-level, not a synchronized per-frame measurement. Calibrated airflow, pressure, temperature, humidity and gravity variation are not invented or supplied as fake constants.

Frozen splits before fitting:

- Train: B1, B2, B4, B6, B8, B16, B21, B22.
- Validation: B9, B10. B20 had been assigned here but its video failed decoding.
- Test: B11, B19.

## FLEX: real raw-image joins

The release-change metadata initially appeared to list conditions only. That was not a complete inventory: NASA's full public `/geode-py/ws/files/v2` browser listing exposes the older raw assets. The FLEX ingestion now uses that full listing and matches exact `FLEX Identifier` values to named camera-B archives.

[FLEX / PSI-69](https://psi.nasa.gov/physci/repo/data/investigations/PSI-69) contributes eight selected methanol runs:

- Train: C06M101, C07M101, C07M201, C05M301.
- Validation: C05M101, C06M201.
- Test: C05M201, C06M401.

Inputs are **initial oxygen (% mole fraction), pressure (kPa), initial CO₂ (% mole fraction), and initial droplet diameter (mm)**. Pressure is converted from source mmHg using approximately 0.133322 kPa/mmHg; fractions are multiplied by 100. Original rows and units remain available. Methanol is fixed; other fuels and helium mixtures are not silently mixed in.

The native TIFFs are **16-bit monochrome flame-camera data**. Direct ordinary RGB conversion would clip their intensities. Preparation retains the raw counts, joins TIFF members to the archive timestamp table, and selects frames 25–65% through the reported burn duration relative to `Test GMT`. Treating that timestamp as burn start is an explicit alignment proxy needing verification. It uses timestamp-selected frames after the reported burn as a camera baseline; these are not certified dark frames and are not guaranteed free of residual/cool-flame signal.

Targets use mean signal minus a median camera baseline, Gaussian smoothing, a fixed 100-count weak-mask threshold, small-component filtering, translation registration and a fixed 2000-count display scale. The result is a **normalized monochrome flame-signal image**, not an RGB color, temperature or heat-flux prediction. Exposure/response calibration and weak-mask review remain necessary. C06M101 has timestamp gaps and only seven qualifying mid-burn frames; the other runs supply 16 each. Actual counts are retained without duplicated frames.

Archive acquisition uses bounded HTTP Range requests through NASA's public download URLs rather than downloading every large ZIP. Servers must honor ranges; each individual range is capped at 16 MB and each remote archive session at 60 MB. Needed members are CRC-checked by `zipfile`, SHA-256 recorded and verified on cached reads. Source resource IDs, archive versions and timestamps are retained. Full-archive SHA-256 is not claimed for ranged reads. A locally cached whole archive may be reused. Hardware-view camera D was inspected and excluded; its images are not mislabeled as flames.

## Model selection and results

The small residual CNN begins at the training mean image, then learns condition-dependent RGB corrections and a mask using bilinear upsampling and convolutions. Separate PMMA and methanol checkpoints have their own input normalization and targets. Only training trials define scaling and initialization.

The two objectives (`rgb-focused`, `shape-assisted`) and checkpoint selection rule were declared before inspecting test results. Selection uses validation RGB MSE; test results are computed after selection. No test-set model tuning was performed. Future model development needs an additional untouched test set or nested evaluation, rather than repeated optimization against these reported tests.

| Experiment / test metric | CNN | Mean-image baseline |
| --- | --- | --- |
| BASS RGB MSE | 0.0027612 | 0.0027619 |
| BASS weak-mask IoU | 0.434 | 0.378 |
| FLEX RGB MSE | 0.0015738 | 0.0015856 |
| FLEX weak-mask IoU | 0.662 | 0.728 |

BASS's pixel gain is about 0.03%; FLEX's is about 0.75%. BASS area/height errors are worse, and FLEX mask overlap is worse. These are **not meaningful, validated accuracy wins** on just two test runs per domain and weak image-derived labels. Neither model is qualified for promotion as a physical predictor. The page exposes them as inspectable experiments, with recorded evidence and explicit limitations. Scores cannot be compared directly with the historical four-source model because the target construction differs.

Selected candidates: BASS `shape-assisted` at epoch 120; FLEX `shape-assisted` at epoch 40, each from predeclared 400-epoch candidate runs. Detailed validation/test/baseline scores are in [reports/bass-stage-v1.json](reports/bass-stage-v1.json) and [reports/flex-methanol-v1.json](reports/flex-methanol-v1.json).

## FLEX conditions browser

The folded NASA section includes **274 FLEX rows** and **8 FLEX-2 rows**, with search and original CSV downloads. Counts are source rows, not a claim of 282 independently image-labeled experiments. Only the eight verified FLEX methanol runs above enter this image experiment. [FLEX-2 / PSI-68](https://psi.nasa.gov/physci/repo/data/investigations/PSI-68) remains conditions-only in this prototype; its raw images have not been selected or trained here.

Original column names, units, values, source URLs, hashes and licenses are preserved. FLEX's source CSV uses Windows-1252, handled explicitly. FLEX pressure columns use mmHg; FLEX-2 uses atm. The browser preserves those original units. PSI catalogs report CC0.

## Artifacts and API

Legacy BASS-II/FLEX generated data and weights remain outside Git; the published FLEX-2 runtime pair is the explicit exception described above:

- `ml/data/bass-study/`: acquisition inventory, preparation/exclusion manifest, standardized `prepared.npz` and QA montage.
- `ml/data/flex/conditions.json`: both original conditions releases and matched-image availability.
- `ml/data/flex/full-file-tree.json`: complete public file-browser inventory used for source discovery.
- `ml/data/flex/study/`: run/member selections, cached original TIFFs/timestamps, source hashes, preprocessing parameters, prepared targets and QA montage.
- `ml/artifacts/bass-study/selected.pt` and `ml/artifacts/flex-study/selected.pt`: separate validation-selected models and reports.
- `ml/reports/`: tracked review copies of both reports.

`GET /api/info?domain=bass` or `?domain=flex` reports that model's features, actual sample counts and scores. `GET /api/predict?domain=flex` runs its documented defaults and returns CNN RGB/mask PNGs plus the nearest **training** target and actual conditions. Extra, nonfinite or out-of-range fields are rejected; time and image inputs are unsupported. `/api/flex` returns original conditions metadata and selected image-training scope; `/api/flex/csv/PSI-69` and `/api/flex/csv/PSI-68` serve the original CSV bytes.

Next work is manual stage/mask review, camera/exposure calibration, synchronized conditions and more comparable independent trials. Bigger images or more adjacent frames alone cannot supply those labels. Track remaining work in [issue #4](https://github.com/wawahwa801/nasa-space-apps/issues/4).
