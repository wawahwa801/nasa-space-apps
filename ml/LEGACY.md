> Historical experiment. Raw-file availability notes based on release-change metadata are not exhaustive; use the full public file-browser listing to discover older assets. The active BASS/FLEX experiments and interface are documented in README.md.

# Four-source condition-to-image CNN prototype

The current lab uses **600 image–feature pairs, about 150 from each of four sources**, and predicts a **256×256 RGB typical flame appearance**. No video time, brightness slider, instrument display reading or source image enters the model. Timestamps remain in provenance only.

| Source | Pairs | Included evidence | Validation |
| --- | --- | --- | --- |
| [BASS-II / PSI-25](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25) | 150 | 25 frames each from B1, B3, B4, B5, B12, B16 | Entire B3 held out (25 pairs) |
| [SAFFIRE-I / PSI-98](https://psi.nasa.gov/physci/repo/data/investigations/PSI-98) | 150 | S1C1 actual fabric-burn images | No independent held-out burn |
| [SAFFIRE-III / PSI-100](https://psi.nasa.gov/physci/repo/data/investigations/PSI-100) | 150 | S1C1 actual fabric-burn images | No independent held-out burn |
| [SPICE / PSI-107](https://psi.nasa.gov/physci/repo/data/investigations/PSI-107) | 150 | 75 frames each from two documented fuel phases in GMT062 trial 99 | Both phases stay in training; they are one experiment |

SAFFIRE-III supplies another accessible solid-fuel source. PSI-62 currently exposed metadata without raw flame targets in the inspected catalog; SoFIE public montages did not provide 150 matched raw examples. SPICE remains a separate gas-jet domain. Combining four sources does not make their cameras, scales or fuel physics interchangeable. Each record preserves its source, trial/phase, original conditions and material description.

## Run locally

Use the isolated CNN checkout so other tasks can switch branches without disrupting the server. From a checkout containing this code, with Python 3.14 (tested on macOS CPU):

```bash
python3 -m venv ml/.venv
source ml/.venv/bin/activate
pip install -r ml/requirements.txt
python ml/multisource_data.py fetch
python ml/multisource_data.py prepare
python ml/multi_model.py --epochs 200
python ml/lab.py
```

Open **http://127.0.0.1:5050**. If the prepared data and `multi.pt` already exist, run only the last command. Restart after retraining. The server loads its template/model/data at startup and continues serving if unrelated files later change.

Downloads are capped at 120 MB per file, restricted files are rejected, and only a selected subset is acquired. The catalog reports CC0 for these PSI sources. The selected raw data total roughly 250 MB, mostly SAFFIRE image archives; data and weights stay outside Git. Exploratory downloads from development are not required by `fetch`.

## Physical inputs and missing values

The numeric schema includes documented oxygen lower/upper bounds, airflow (m/s), pressure (kPa), sample thickness (mm), width/length (cm), initial CO₂ (%), nozzle diameter (mm), and fuel-flow lower/upper bounds (sccm). A material category and investigation/domain identifier are also encoded. Numeric values are accompanied by explicit known/missing masks. Computational zeros behind a missing mask are not claimed measurements.

- BASS supplies initial oxygen, thickness, width and initial CO₂. Fan/air display values are **not** treated as calibrated airflow. Some films lack an explicit polymer name; they remain “Unspecified film.” B16's table sample ID is 150m while its video uses 150; it is joined by the documented B16 trial ID, retaining the original row.
- SAFFIRE-I supplies SIBAL fabric dimensions, 20 cm/s airflow and a documented 21.5–21.7% O₂ interval. The interval is retained, not replaced by an invented exact oxygen value.
- SAFFIRE-III supplies SIBAL fabric dimensions and 30 cm/s airflow. Its table does not report oxygen or pressure; those stay missing.
- SPICE uses the original `Spice Flight Test Data II modified.xls` workbook. Zero-based rows 295/297 (Excel rows 296/298) document the high-fuel phase; row 296 (Excel row 297) documents the lower-fuel phase. Pressure is converted from Pa to kPa and calibrated air rate from cm/s to m/s. These are nominal documented phase conditions, not a reconstructed per-frame sensor stream. The clip clock and fuel/air display were inspected over the selected segments.

Select a source and documented trial/phase in the interface. Only known values appear. Values with no variation in that source's training sample are read-only. New combinations within the bounds remain illustrative; this small dataset cannot isolate causal effects. Temperature, humidity and variable gravity remain unsupported. Pressure is documented only at a single setting in SPICE, so pressure effects cannot be learned here.

## Sampling and image clarity

Sampling increases from 4 to **6 fps**, and target resolution is now **256×256** (four times the pixels of the previous 128×128 targets). Frame rate controls temporal density; pixel resolution controls image detail. Higher sampling does not create new independent experiments or turn the still-image decoder into a video forecaster.

BASS videos use 25 unique source frames per trial from 15 s, at 6 fps. SPICE uses 75 unique frames each from offsets 15 s and 40 s in the same readable GMT62_11.41 clip, at 6 fps. Other inspected SPICE clips failed decoding and are excluded.

SAFFIRE JPEG filenames contain source timestamps at approximately native video cadence. Preparation requests a 6 fps sampling grid within the inspected S1C1 part1 archives, rejects duplicate members, green camera-illumination shots and frames without a minimum luminous red region, then keeps 150 qualified frames per source. Rejection creates timing gaps; these are not synthesized into a continuous 6 fps sequence. F1 streams are pre-test flow visualization and are excluded.

SAFFIRE targets and evidence use the same fixed low-light display transform `clip((RGB - 3) * 6, 0, 255)` and an explicit camera ROI. This enhances visibility; it is not radiometric or heat-flux calibration. BASS/SPICE crops remove upper telemetry. Aspect-preserving padding fits every selected image to 256×256. Camera orientation/scale differences remain.

Without time or simulation state, different moments from the same conditions share a feature vector. The decoder therefore estimates typical appearance and can blur changing flames. Accurate phase-specific generation would require a documented state/phase input or a temporal model; timestamps are not secretly reintroduced.

## Model and measured result

`multi_model.py` encodes normalized numeric features, missing masks, source and material indicators through two linear layers, then five convolutional upsampling layers generate RGB output. There are **147,819 parameters**. Only training records determine scaling and material categories. Weighted pixel MSE emphasizes observed luminous regions. The earlier `conditional.py`/`flame.py` scripts are historical baselines and are not used by the current lab.

The earlier 128-pixel, 200-epoch CPU run (seed 42) used **575 training pairs + 25 held-out BASS-B3 pairs**. Held-out MSE was **0.0092805** versus **0.0009329** for the BASS training mean-image baseline. The CNN is worse than that baseline. No independent accuracy claim can be made for the other three domains in this sample. This is an acquisition/conditioning/interface prototype, not a validated fire predictor or a complete physics/CNN spread simulation.

## Artifacts and provenance

- `ml/data/multi-images.npz`: 600 target images.
- `ml/data/multi-manifest.json`: source counts, experiment-level physical labels, explicit nulls, original rows/workbook references, image locations, timestamps, display transforms and source file hashes.
- `ml/data/multi-pairs.csv`: readable image-index-to-feature joins. Blank cells mean missing measurements. Video time appears only as provenance.
- `ml/artifacts/multi.pt`: architecture ID, weights, normalization, material categories and metrics.
- `ml/artifacts/multi-metrics.json`: counts, split, resolution, cadence target and per-source validation availability/results.

`GET /api/info` reports sources, known feature ranges, experiments and metrics. `GET /api/predict?source=PSI-25&run=BASS-B1` returns a generated PNG and a separately retrieved same-source/material evidence frame. Unsupported, missing, nonfinite and out-of-range inputs are rejected. `time` and image inputs are rejected.

## Improve the actual model

Acquire more independent, comparable trials spanning the requested conditions, verify material identities, and hold out entire burns in every source. Add pressure/temperature/gravity variation only where matched labels exist. Compare against retrieval and source-specific mean-image baselines using flame-region and geometry metrics. Calibrate camera scale/intensity before treating images as physical fields. Heat flux requires measured labels, not RGB brightness. Stream larger data with a DataLoader and GPU once this baseline is useful. Track remaining work in [issue #4](https://github.com/wawahwa801/nasa-space-apps/issues/4).

## 256-pixel update

Targets are regenerated from the selected raw images at 256×256 and the CNN has a fifth learned upsampling stage. The checkpoint architecture ID is `multi-source-conditions-v2-256`; old 128-pixel checkpoints are incompatible. Training and serving reject mismatched target/checkpoint dimensions.

The 200-epoch 256-pixel run retained 575 training and 25 held-out pairs. BASS-B3 MSE was **0.0103019**, versus **0.0009303** for the source mean-image baseline. Higher resolution increases spatial detail but does not resolve the model's accuracy limitations. Sampling remains 6 fps and time remains excluded from model inputs.
