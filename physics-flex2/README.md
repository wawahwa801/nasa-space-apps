# FLEX-2 droplet physics baseline

A standalone, dependency-free prototype, separate from the CNN and cabin spread demo.

```sh
python3 physics-flex2/app.py
# Open http://127.0.0.1:5054
python3 -m unittest discover -s physics-flex2 -v
```

Select one of 99 independently identified FLEX-2 runs from the existing checked-in frontend index. Seven source-conflicted fuel records are visible but cannot be simulated; E183L11 is excluded as a placeholder. Fuel, pre-ignition chamber pressure/temperature, source identifiers, original split, fiber setting and igniter-power metadata are retained. No raw NASA download, Torch, training or cloud service is required.

Supply a **liquid droplet** diameter from the CNN image, plus mm per pixel in that image's coordinate system and a calibration description. Resizing/cropping changes the applicable scale. A luminous-flame diameter is not a droplet diameter. The current CNN does not independently resolve/calibrate the liquid droplet: this is a manual integration boundary, not an automatic detector. Model-derived observations are labeled as such.

The initial 100 px × 0.03 mm/px = 3 mm and K=0.8 mm²/s are illustrative defaults, not NASA run measurements. The user-requested 22% O2 / 78% N2 is an explicit **scenario assumption**. Recorded composition remains unchanged in provenance; the ten currently source-matched heptane runs report 21/79, not 22/78. They cannot be relabeled to fit this model.

## Physics and limits

We use `D²(t) = max(0, D_observed² - K*t)` after the supplied observation during established burning. This enforces nonnegative diameter and monotonically decreasing volume for positive K. Relative volume assumes a sphere and constant density. Formal zero-diameter time `D_observed²/K` is an idealized extrapolation, **not a flame-extinction or safety prediction**. Time zero is the observation, not automatically ignition or the selected RGB target's stage.

This quasi-steady approximation does not solve ignition transients, radiation-driven extinction, cool-flame transitions, gas chemistry, oxygen depletion, fiber heat conduction, or convection. No flame-temperature/heat-flux/fire-spread claims. Pressure, temperature and fuel identify the experiment; in assumed-K mode they do not automatically change K. The measured mode retrieves K by fuel/fiber and normalized pressure/temperature distance, rather than inventing pressure/temperature power laws. Igniter stage, power, on-time, configuration and camera covariates are not learned by this small baseline; unavailable values remain missing. Camera covariates belong to the measurement/calibration pipeline.

Reference: [NASA FLEX requirements](https://www1.grc.nasa.gov/wp-content/uploads/FLEX_EIRD_v4.pdf) discusses the D²/K lifetime approximation and a representative 0.8 mm²/s value for certain methanol/heptane conditions. That value is not a calibrated universal FLEX-2 coefficient. [NASA's FLEX results](https://ntrs.nasa.gov/api/citations/20150023456/downloads/20150023456.pdf) document diameter histories and distinguish burning/extinction stages. [FLEX-2 measurement study](https://doi.org/10.1109/TPAMI.2022.3170926) describes backlit diameter extraction and soot-related measurement limits. Source data: [PSI-68](https://psi.nasa.gov/physci/repo/data/investigations/PSI-68).

## Fit measured histories when available

There is **no real physical training result shipped here**: the current bundle lacks verified diameter histories and exact-run spatial calibration. `measurements-template.csv` intentionally contains only a header. Supply at least three unique timestamps per run, authoritative mm diameters, measured gas composition, and source/calibration references. Select a quasi-steady interval; inspect residuals for a poor D² approximation. These CSV fields are asserted by the data supplier, not independently authenticated by the fitter.

```sh
python3 physics-flex2/app.py --fit /path/to/measurements.csv --output /tmp/flex2-physics-fit.json
python3 physics-flex2/app.py --model /tmp/flex2-physics-fit.json
```

The fitter rejects generated targets, disputed/unknown IDs, nonpositive regression slopes, duplicate timestamps and compositions other than measured 22/78. It estimates K per run via least-squares on measured D² versus time. Only original train-split runs enter the reference model and pressure/temperature normalization. Validation/test trajectories use training references only, matching fuel and fiber; missing coverage is reported. Inference excludes its own run. Reports include per-run D² residuals, held-out diameter RMSE, measurement/source-index hashes and selected reference provenance. A held-out trajectory starts at its first measured diameter: it evaluates subsequent regression, not prediction of initial diameter. No checkpoint tuning or claim of calibrated uncertainty; no held-out coverage means no generalization evidence.

## API

`GET /api/runs` returns source records and model mode. `POST /api/predict` accepts:

```json
{"run_id":"A184D09","observation":{"diameter_px":100,"mm_per_pixel":0.03,"calibration_source":"illustrative only; replace with calibrated scale","image_kind":"cnn_estimate"},"k_mm2_s":0.8,"duration_s":30}
```

Result includes trajectory, recorded conditions, gas assumption, reference/run-range status and warnings; downloadable from the UI. Server binds only to localhost. Units: mm, mm²/s, kPa, °C, seconds. `image_kind` can also be `measured_backlit`; inputs are supplied observations, not an image-upload or segmentation service.
