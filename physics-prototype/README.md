# Physics-only surface fire-spread prototype

Run independently of the dashboard and CNN with Python 3.9 or newer:

```sh
cd physics-prototype
python3 acquire.py
python3 server.py --port 8010
```

Open http://localhost:8010. No packages, training, CNN checkpoints, cloud services or model servers are required. Downloaded PDFs are included; the 22 MiB sensor workbook stays local and can be reproduced using `acquire.py`. Files are capped at 32 MiB and checked against recorded SHA-256 hashes.

## Demo workflow

Choose a source patch, toggle fuel/inert patches, edit source and material assumptions, then run. Play or scrub time; hover or keyboard-focus a patch for its low/base/high ignition times. Export includes the scenario, full time histories, assumptions and energy diagnostics. The JSON editor supports up to 100 uniquely positioned patches with independently specified material properties. Unknown properties must be supplied as explicit assumptions; no experimental property lookup is implied.

The default scenario has 24 identical 10 cm square patches. All thermal and combustion values are illustrative assumptions. Under the default losses, only the heated source patch ignites during 180 seconds. To demonstrate a lower-loss assumed environment, set convection h to 2 W/(m² K) and emissivity to 0.3: neighboring patches ignite in all three source-power cases. These values demonstrate sensitivity, not a fit to NASA results. The ±20% power cases are not confidence intervals and higher power need not always produce earlier ignition because fuel burns out sooner.

## Equations and boundaries

Each patch is a lumped solid with heat capacity `C = area * thickness * density * cp`:

`C dT/dt = external source + captured combustion + sum(Gij*(Tj-Ti)) - h*A*(T-Ta) - emissivity*sigma*A*(T^4-Ta^4)`.

Conductive links connect adjacent integer grid positions, use harmonic-mean conductivity and a conservative pairwise flux. Radiative combustion allocation uses a **user-assumed inverse-grid-distance kernel**, normalized so total absorbed energy is at most the captured fraction of released energy; the remainder escapes. This is not a geometric radiation/view-factor solver. Grid spacing follows the square-patch area assumption; unequal patches are approximate and should not be interpreted as resolved cabin geometry.

Fuel ignites when its temperature reaches the configured threshold and prescribed oxygen exceeds an assumed cutoff. Burning releases fixed configured power until its finite fuel energy is exhausted. There is no thermal extinction, pyrolysis kinetics, char evolution, oxygen depletion, smoke, gas-phase combustion, pressure law, or solved velocity field. Oxygen and cabin temperature are fixed boundary conditions. Forced ventilation is represented only by an editable h; there is no automatic airflow-speed conversion or Earth-to-microgravity interpolation. The source is an external heater: ignition time refers to material ignition, not spontaneous appearance of a fire.

The explicit solver uses adaptive substeps bounded by thermal conductances and radiative-loss derivatives, a maximum step of 0.1 seconds, a computation-budget guard and a 2000 K model-limit rejection. Frames are sampled at roughly one-second intervals; ignition times are stored at the integration timestep. Sensitivity cases vary external-source and burning powers by factors 0.8, 1, 1.2 while preserving finite fuel energy.

## Evidence and acquisition limits

`references/manifest.json` records public URLs, UTC download dates, sizes, hashes and reuse-status caveats. The two planning PDFs and NASA SAFFIRE presentation were downloaded directly. `data/experiments.json` normalizes catalog-level geometry, material composition and flow with missing outcomes explicitly null. No imagery brightness is converted into heat flux.

The PSI-98 portal did not expose a readable raw download listing in this environment. A separately downloaded, commit-pinned team mirror of the SAFFIRE-I sensor workbook is audited by `audit_data.py`. `data/workbook-audit.json` lists its sheets and unresolved channel/geometry/unit mappings. It is not used to calibrate the solver. The quoted 0.2 m/s ventilation condition is metadata; the demo does not derive h from it. No BASS raw trial, matched heat-flux/ignition dataset, independent held-out evaluation or experimental error estimate has been acquired. A certified or operational astronaut safety predictor requires substantial additional measurements and validation.

## Local API

- `GET /api/example`: fully specified assumed demo scenario.
- `POST /api/validate`: scenario JSON → `{valid:true}` or HTTP 400 with an error.
- `POST /api/simulate`: same JSON → three cases with frames, patch ignition times (null means not ignited during duration), remaining fuel, energy diagnostics and assumptions.

The example defines all required fields and SI units. Results are deterministic. Server binds to localhost, caps request bodies at 200 kB, and has no persistent uploads or external calls. This development server is not a public deployment endpoint.

## Verification

```sh
python3 -m unittest -v
python3 acquire.py
python3 -m py_compile model.py server.py acquire.py audit_data.py
node --check web/app.js
```

Nine tests cover conservation, equilibrium, analytic heater response, finite fuel, oxygen cutoff, timestep convergence, material sensitivity, invalid inputs and sensitivity cases. Chrome checks passed for editing, runs, playback, JSON rejection, mobile overflow and runtime errors. No comparison to measured spread times is claimed. GitHub issue creation for the acquisition/calibration gap returned integration 403; tracking synchronization remains pending. CNN and frontend files are untouched.
