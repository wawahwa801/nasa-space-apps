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

## Spaceship room graph

Open **http://127.0.0.1:5054/spaceship** using the same launcher. Sixteen square modules form a fictional orbital-station graph with a seven-module docking spine, command/crew/engineering/science branches and two bypass loops (17 passages). Choose **Fire starts in**, or enable **Pick start on map** and click any fueled module. The selected source is marked SOURCE and time resets to zero. Click a room normally to inspect it; toggle its fuel flag or click passage connectors to open/close them. Scrub elapsed time, play/pause at 1–8×, restart, or export the full scenario/history. Pan the scrollable map on small screens; zoom in/out or use **Fit map** for an overview. Controls cover observed droplet size/scale, K, transfer fraction, ignition threshold, cooling and duration. Conditions are selected from recorded runs; unvalidated pressure/temperature/fuel effects are not invented.

The droplet engine supplies the decreasing relative-volume curve for each fueled room. One initial droplet-equivalent proxy unit per room is consumed according to that curve. At each step a configured fraction of consumed proxy is divided equally among open neighbors. Closed passages transfer none. An unignited fueled room accumulates proxy with exponential decay; crossing the assumed threshold ignites it at the end of that step. Its burn starts contributing in the next step. Transfers are simultaneous, so iteration order cannot propagate across an entire graph in one timestep. Transferred proxy is bounded by consumed proxy times the transfer fraction, including shares lost to inert/already-burning rooms. Empty rooms do not burn or relay proxy, but open connections to them still receive a share of transfer.

The numerical step is at most 0.1 s; displayed states sample every five steps (normally 0.5 s). The time slider scrubs a fixed computed history, so backward scrubbing is deterministic. Parameter/topology changes invalidate and replace that history and reset elapsed time. In-flight responses cannot overwrite a newer scenario. All rooms share the selected droplet engine conditions and K; room-specific real materials are not represented.

**This is an illustrative graph spread rule, not a calibrated spacecraft fire simulation.** Rooms are graph nodes, with no physical dimensions. The proxy is not joules, heat flux or room temperature. Cabin ignition thresholds and coupling cannot be learned from the available FLEX-2 droplets. No smoke transport, compartment radiation, oxygen depletion, suppression or ventilation field is solved. Validate a separate cabin model with matched solid-fuel spread measurements before interpreting displayed times as physical predictions. Tracked in issue #55, related to scope #25 and physical calibration #52.

API: `GET /api/rooms/example` returns the editable scenario. `POST /api/rooms/simulate` takes this scenario (at most 16 rooms/120 unique undirected edges, duration ≤180 s) and returns frames, ignition times, burn-model provenance and finite-budget diagnostics. The API retains fitted-model support from `--model`; the graph's transfer/ignition parameters remain assumptions even with a fitted droplet coefficient.

## Custom environment in the main dashboard

Open **Room simulation → Edit environment** to show the compact editor beside
the map (stacked above it on smaller screens). Select a room on the map or from
the dropdown, rename it, change integer X/Y grid coordinates (0–9), toggle fuel,
and set ignition. Occupied positions are rejected. Up to 16 rooms are supported;
removing a room also removes/reindexes its hallways and adjusts ignition.
Choose a destination and **Connect rooms**, then toggle a hallway open/closed or
remove it. **Reset station layout** restores the default graph.

Edits clear prior simulation and explanation results; press **Simulate** again.
Layouts are held for the current page session. Grid distance does not change the
transfer coefficient: open graph connections determine spread in this illustrative
solver. The live CNN remains conditioned on the model controls, not room geometry.

Playback uses continuous elapsed time, speed 0.5–8×, pause/resume, restart, and
explicit time scrubbing. Closed hallways use dashed lines on the map.

The ML service exposes `GET /api/environment` for the default layout and accepts
`environment: {rooms, edges}` on `POST /api/simulate`. Layout validation runs before
inference. Frontend and ML service must be deployed together for this feature.
