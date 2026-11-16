# Data guide (for agents)

Quick reference for the files in `data/`. Column indexes are 0-based.
`fire-dashboard/scripts/build_reference_data.py` already parses all four.

## PSI-159 ACME Chamber Calculator (.xlsx)
ISS combustion chamber, 2021-03-09 to 2021-10-21. Sheet `EventData`, header rows 2–4, data from row 5.
- Col 0 `OP`: `TP` = test point (use these), also `Vent`, `Cabin Air`, etc.
- Col 1 `Ignite`: Yes/No as-run decision. Col 2 `TPID`. Col 12/13 start/end time (GMT).
- Col 18/19 chamber pressure start/end (psia, ×6.894757 → kPa). Col 23 fuel type (e.g. "Butane / Nitrogen (30/70)").
- Cols 28–35 temperatures (mostly blank). Col 37 burn fraction.
- Cols 75–85 `Finish Mixture (Percent)` as fractions: O2, He, CO2, N2, H2O, ethylene, methane, propane, butane, ethane, H2.
- 195 TP rows, 129 ignited. Fuels are gases only.

## Saffire-I Sample 2 Sensor Data (.xlsx, 23 MB)
Large-scale flame spread test, 2016-06-14. Sheet `Calibrated Data` (other sheets are charts). Row 1 names, row 2 units, data rows 3–20002 (~30 Hz, ~658 s). Rows after 20002 are a separate radiometer block; skip them.
- Col 0 elapsed s, 1 epoch ms, 5 CO2 %, 6 O2 %, 7–8 anemometer cm/s, 9 pressure psia,
  22 humidity %, 23 inlet temp °C, 24–29 plume TC1–6 °C, 30–35 sample TC7–12 °C.
- O2 barely changes (22.3–22.4 %); plume peaks ~94 °C. No CO data.
- Stream-parse it (iterparse); it is too large to load whole.

## PSI-107 SPICE (.csv)
Smoke Point In Co-flow Experiment: laminar gas-jet flames.
Columns: GMT date (day of year), ignition/flame-off times (some use `.` separators), Fuel (ethylene, propane, methane, propylene, "50 % Propylene"…), Nozzle (mm), Fuel Rate (sccm, mg/s), Air Rate (cm/s).
Test conditions only; no measured smoke points. Duplicate rows exist.

## PSI-101 SAME-R (.csv)
Smoke Aerosol Measurement Experiment – Reflight: smoke from heated materials.
Columns: Sample Type (Kapton, Silicone, Lampwick, Pyrell, Teflon), test # ("a" suffix = aged-smoke reading of the same test), description, date, inlet velocity (cm/s), Rt/R0 (heater resistance ratio, higher = hotter), durations and aging times (s).
Test conditions only; no particle-size results.

## BASS-II Test Matrix by PI Final (.xlsx)
Burning and Suppression of Solids II, ISS, 2014–2016. Six sheets, one per PI (Bhattacharjee, Ferkul, Miller, Olson, Fernandez-Pello, T'ien), identical 16 columns, header in row 1, ~129 tests.
- Col 0 date (Excel serial), 1 GMT day, 2 test no. (e.g. B1, O3a), 3 sample no., 4 material (free text: PMMA films/rods/slabs/spheres, "clear"/"black" rod = PMMA, SIBAL fabric, Nomex, candle).
- 5 flow restrictor, 6 fan display and 7 air display: free-text sequences ("10, 5, 3", "5 down to ext"), not clean numbers.
- 10/11 calibrated O₂ % start/end, 12/13 CO₂ % start/end, 14/15 CO ppm start/end (some cells "none", ">500", "OR", "over").
- No outcome column: ignition/extinction only appears in free-text notes. Starting O₂ 13.6–22.2%; CO rose up to ~575 ppm in one burn.

## PSI-26_Experimental table_BASS (.csv)
BASS (first experiment), ISS, 2012–2013. Columns: Date (a few typos, e.g. 6/29/`12, 5/15/2103), GMT, As Run Test #, Test #, Sample #, Fuel Sample Material (free text; may include "wake ign" or "opposed flow"). "SOOT Cleaning" rows have no test number. No atmosphere or flow conditions.

The build script groups both files' materials into categories (PMMA, SIBAL fabric, Nomex, Ultem, wax).

## ochmo-tb-003-habitable-atmosphere (.pdf, 21 pages)
NASA-STD-3001 Technical Brief, Rev A (2023): crew-health limits, not experiment data. Not parsed by the build script; values are transcribed into `THRESHOLDS.habitable` in `fire-dashboard/js/parameters.js`. Used: total pressure 34.5 < P ≤ 103 kPa for indefinite exposure [V2 6006]; ebullism at 6.27 kPa; supplemental O₂ may not suffice below 130 mmHg (17.3 kPa); at least 30 % inert diluent gas [V2 6002]; PIO₂ = (Pb − 47 mmHg) × FiO₂ with normoxia 149, exploration minimum 127 and absolute minimum 122 mmHg (1-hour average) [V2 6003]; pressure changes > 1 psi at most 13.5 psi/min [V2 6007]. Table 6.2-1 is an image (not transcribed). No humidity, temperature or CO₂ limits (CO₂ is in OCHMO-TB-004).

## Gaps
No liquid fuels, no gravity other than microgravity, and no recorded ignition/extinction outcomes for solids (BASS-II gives the O₂ levels flames were studied at). CO/CO₂ during fires come only from BASS-II chamber readings. BASS-II is PSI-25 (CC0-1.0); the PSI-26/BASS record and license still need checking (see README.md).
