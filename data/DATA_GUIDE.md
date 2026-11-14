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

## Gaps
No solid-material ignition data, no liquid fuels, no CO/H2/CH4 fire products, no gravity other than microgravity. Source links, download dates and licenses are not yet recorded (see README.md).
