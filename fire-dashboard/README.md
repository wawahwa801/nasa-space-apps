# Fire safety dashboard (prototype)

A standalone page that takes quantitative and qualitative fire safety inputs
(cabin conditions, atmosphere, nearby fuels) and compares them with NASA
microgravity fire experiment data from the repository's `data/` folder.

It is separate from the Next.js app in `frontend/` and the CNN work in `ml/`:
plain HTML, CSS and JavaScript, with no dependencies and no build step.

> Prototype for exploration only. It is not a certified safety assessment.

## Open it

Open `fire-dashboard/index.html` in a browser. No server is needed, and nothing
is sent over the network. Click **Load example** to see a filled-in dashboard.

## Using it

- **Units:** pressure (kPa, psia, atm), temperature (°C, K, °F), gas concentrations
  (ppm, %) and distances (m, cm, ft) can be entered in any listed unit. Switching the
  unit converts the value already entered.
- **Help and checks:** click a field to see what it is used for. Values outside a
  sensible range (for example O₂ above 100%) are marked and ignored until corrected.
- **Progress:** each section heading shows how many of its fields are filled.
- **From result to input:** click an item in the assessment to jump to the input behind it.
- **Saving:** inputs save automatically in the browser. **Export** downloads them as
  JSON (in kPa, °C, ppm and m) and **Import** loads such a file again.
- **On a phone:** a bar at the bottom shows the issue count and jumps between inputs and results.

## What it shows

- **Summary tiles:** issue count and highest severity, O₂ %, O₂ partial pressure, internal pressure.
- **Assessment:** rule-based flags (oxygen enrichment, flammable gases against their
  flammability limits, CO and CO₂ against NIOSH limits, leaks, distance to ignition
  sources, open fuel storage, monitoring status, microgravity), each with a severity, icon and explanation.
- **Gas levels:** H₂ and CH₄ as a share of their lower flammability limits; CO and CO₂ against exposure limits.
- **ACME ignition tests:** your O₂ % and pressure plotted against 195 ACME test points,
  coloured by whether they ignited, with the closest tests highlighted in the table view.
- **Saffire-I sample 2:** O₂, CO₂, pressure and plume temperature during a large-scale burn,
  with your values as reference lines.
- **Related NASA tests:** SAME-R tests for your material; SPICE and ACME tests for your fuel.
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
