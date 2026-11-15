# Fire safety dashboard (prototype)

A standalone page that takes quantitative and qualitative fire safety inputs
(cabin conditions, atmosphere, nearby fuels) and compares them with NASA
microgravity fire experiment data from the repository's `data/` folder.

It is plain HTML, CSS and JavaScript, with no dependencies and no build step.
It can be opened on its own or viewed inside the Next.js app in `frontend/`.

> Prototype for exploration only. It is not a certified safety assessment.

## Open it

Open `fire-dashboard/index.html` in a browser. No server is needed, and nothing
is sent over the network unless you click **Generate insight** (below). Click
**Load example** to see a filled-in dashboard.

## Using it

- **Units:** pressure (kPa, psia, atm), temperature (°C, K, °F), gas concentrations
  (% or ppm, including O₂ and N₂) and distances (m, cm, ft) can be entered in any listed unit. Switching the
  unit converts the value already entered.
- **Help and checks:** click a field to see what it is used for. Values outside a
  sensible range (for example O₂ above 100%) are marked and ignored until corrected.
- **Progress:** each section heading shows how many of its fields are filled.
- **Test data:** **Load example** has three scenarios (`EXAMPLE_INPUTS` in `js/parameters.js`): an
  ISS-like cabin, an exploration habitat at 8.2 psia with 34% O₂, and degraded monitoring with fuel
  and oxidizer leaks. **Play demo** has three live-monitoring demos (`DEMOS` in `js/monitoring.js`):
  smouldering turning into flames, smouldering with no flame, and an oxygen and hydrogen leak. The
  same demos are in `data/sample-readings/*.csv` for testing **Import readings CSV**; regenerate them
  with `node fire-dashboard/scripts/make_sample_readings.cjs`. All of these are synthetic.
- **Hide and collapse sections:** click a section title to collapse it, or use **Sections** above the
  results to hide sections entirely (**Expand all**, **Collapse all**, **Show all** and **Reset view** are
  there too). Results are grouped into *Current conditions* and *Compared with NASA experiments*; the
  Saffire, related-tests and data-set sections start collapsed. The view is remembered in this browser.
- **From result to input:** click an item in the assessment to jump to the input behind it.
- **Saving:** inputs save automatically in the browser. **Export** downloads them as
  JSON (in kPa, °C, ppm and m) and **Import** loads such a file again.
- **On a phone:** a bar at the bottom shows the issue count and jumps between inputs and results.

## What it shows

- **Safety insight (AI):** on request, the current report (inputs, assessment, smoke status
  and live monitoring, built by `buildReport` in `js/app.js`) is sent to the backend's
  `POST /api/safety-insights`, which asks OpenRouter's Dots3-Note Preview model
  (`dots-studio/dots-3-note-preview:free`) for a plain-language reading: headline, concerns,
  next checks and data gaps. It needs the Next.js dev server (which proxies `/api` to Flask)
  and the backend running with `backend/.env` set to:

  ```
  LLM_PROVIDER=openrouter
  LLM_MODEL=dots-studio/dots-3-note-preview:free
  LLM_API_KEY=<your OpenRouter key>
  LLM_MAX_OUTPUT_TOKENS=6000
  LLM_TIMEOUT_SECONDS=150
  ```

  Without a key the backend's offline mock answers instead. The prompt is in
  `backend/llm/safety_insights.py`. The AI text explains the report; the rule-based
  assessment remains the dashboard's result.

- **Live monitoring:** readings taken over time (default every 5 minutes) are compared to detect a
  fire starting or smoke building up: CO rising for several intervals without heat (possible
  smouldering), CO and CO₂ rising together as O₂ falls (combustion signature), fast heating with
  combustion gases (possible flaming fire), flammable gas accumulating, O₂ rising, CO/CO₂ above NIOSH
  limits with a time-to-limit projection, and missed readings. Readings come from **Record reading**
  (the current inputs), a CSV import (a time column plus gas/temperature columns), the accelerated
  demo, or `FireDashboard.addReading({...})` for a sensor feed. Detection logic is in
  `js/monitoring.js`; its rise thresholds (`THRESHOLDS.monitoring` in `js/parameters.js`) are
  placeholders to tune with real sensor data, and the demo sequence is synthetic.
- **Summary tiles:** issue count and highest severity, O₂ %, O₂ partial pressure, internal pressure.
- **Assessment:** rule-based flags (oxygen enrichment, flammable gases against their
  flammability limits, CO and CO₂ against NIOSH limits, leaks, distance to ignition
  sources, open fuel storage, monitoring status, microgravity), each with a severity, icon and explanation.
- **Gas levels:** H₂ and CH₄ as a share of their lower flammability limits; CO and CO₂ against exposure limits.
- **Air composition:** a donut of N₂, O₂, trace gases (CO₂, H₂, CH₄, CO, listed individually) and the
  unaccounted remainder, switchable between % and ppm.
- **ACME ignition tests:** your O₂ % and pressure plotted against 195 ACME test points,
  coloured by whether they ignited, with the closest tests highlighted in the table view.
- **Saffire-I sample 2:** O₂, CO₂, pressure and plume temperature during a large-scale burn,
  with your values as reference lines.
- **BASS-II solid materials:** 129 ISS burn tests plotted by starting O₂, one row per material, with
  your O₂ as a reference line; CO/CO₂ rises during burns and the earlier BASS run counts.
- **Smoke and soot hazards:** an overall smoke-hazard level from your CO and CO₂ readings (NIOSH limits),
  smoke-detection status and your material; what the material's or fuel's smoke can contain (general
  combustion chemistry from its composition, kept in `SMOKE_PRODUCTS` in `js/parameters.js`, not measured
  data); and measured CO rises during BASS-II burns, by material.
- **Related NASA tests:** SAME-R and BASS tests for your material; SPICE and ACME tests for your fuel.
- **Data sets:** the four built-in data sets, plus any CSV you add.

## Inputs

Inputs are grouped into four sections: environment, atmospheric composition,
nearby fuels (gases) and combustible materials (solids). Every input is either a
number or a pick from a fixed list. Only inputs that feed an assessment rule or a
comparison with the NASA data are included; users cannot add their own.

The fuel and material lists are generated from the data sets, so each option has
matching NASA tests: fuels from ACME and SPICE, materials from SAME-R.

## Changing parameters and adding data sets

- **Parameters:** edit `js/parameters.js`. Only add a parameter when the dashboard has
  data or a rule that uses it. Assessment thresholds are in the same file under
  `THRESHOLDS`; replace them with the limits that apply to your vehicle or facility.
- **A data set for one person:** use **Add CSV data set** on the page. It is saved in
  that browser only.
- **New built-in data:** put the file in `data/`, extend
  `scripts/build_reference_data.py` to read it, and rebuild (below).

## Embedded in the Next.js app

The same files also appear as the "NASA data comparison" section of the Next.js
page in `frontend/`, where the flame simulation's **Parameters panel is the only
place to enter values**:

- O₂, pressure, temperature, CO₂ and gravity are shared with the flame simulation
  (CO₂ % is converted to ppm; gravity below 0.05 g counts as microgravity).
- The other inputs here appear in the Parameters panel as extra sections
  (`frontend/components/nasa-parameter-fields.jsx`), built from `js/parameters.js`,
  so parameters stay defined in one place.
- The dashboard runs in a shadow root (`frontend/components/fire-safety-comparison.jsx`)
  with `FireDashboard.mount(shadowRoot, { externalInputs: true, ... })`: its own form is
  hidden, values arrive through `FireDashboard.setInputs(values)` in base units, and the
  `ember` theme (`data-theme="ember"`) matches the flame simulation's look.
- The results layout follows the space it is given (container queries), so it also
  fits between the Parameters and chat panels.

The standalone page still has its own form and calls `mount(document)` automatically.

The Next.js app serves this folder directly at `/nasa-dashboard/` (see
`frontend/app/nasa-dashboard/[...path]/route.js`), so edits here show up on reload
with no copy step.

## Rebuilding the reference data

`data/reference-data.js` is generated from the files in `data/`. After a data file
changes, run from the repository root:

```sh
python fire-dashboard/scripts/build_reference_data.py
```

It uses only the Python standard library (it reads `.xlsx` files directly).

## Files

| Path | Purpose |
|---|---|
| `index.html`, `styles.css` | Page layout and styles (light and dark mode) |
| `js/parameters.js` | Input fields (fuel/material lists built from the data), assessment thresholds, example input |
| `js/app.js` | Form, assessment rules, dashboard rendering, user data sets |
| `js/charts.js` | SVG scatter and line charts with hover tooltips |
| `data/reference-data.js` | Generated summary of the NASA data (do not edit by hand) |
| `scripts/build_reference_data.py` | Builds `data/reference-data.js` from `../data/` |

## Not done yet

- No connection to the LLM analysis API (`backend/llm`). The **Export JSON** button
  produces the inputs and assessment in a form that could be sent to it later.
- No physics or CNN model output; the ACME comparison is empirical only.
