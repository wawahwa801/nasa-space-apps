# data

Source data for the fire safety dashboard.

## Scope

- Contains only fire safety and crew habitability data from NASA. Do not add data from other sources.
- Data sets are supplied by the project team.

## Data sets

| File | Experiment | Contents |
|---|---|---|
| `PSI-159_Raw Data_Final ACME Chamber Calculator - 2021-03-09 to 2021-10-21.xlsx` | ACME (Advanced Combustion via Microgravity Experiments) chamber, ISS | As-run test points: gas additions, chamber mixture, pressure, temperatures, and whether each test ignited |
| `Saffire-I Sample 2 Sensor Data Complete TM graphs.xlsx` | Saffire-I, sample 2 | Calibrated sensor log (~32 readings/s): O₂, CO₂, pressure, humidity, flow, plume and sample temperatures |
| `PSI-107_Experimental table_Spice.csv` | SPICE (Smoke Point In Co-flow Experiment) | Gas-jet flame runs: fuel, nozzle diameter, fuel and air flow rates |
| `PSI-101_Experimental table_SAME-R.csv` | SAME-R (Smoke Aerosol Measurement Experiment – Reflight) | Smoke tests: material, flow, heater ratio, aging times |
| `BASS-II Test Matrix by PI Final.xlsx` | BASS-II (Burning and Suppression of Solids II), ISS, 2014–2016 | One sheet per principal investigator: sample material, calibrated chamber O₂ at start/end, CO₂ (%) and CO (ppm) before/after, air-flow display notes |
| `PSI-26_Experimental table_BASS.csv` | BASS (Burning and Suppression of Solids), ISS, 2012–2013 | As-run test log: date, test and sample numbers, sample material (no atmosphere or flow data) |
| `ochmo-tb-003-habitable-atmosphere.pdf` | NASA-STD-3001 Technical Brief OCHMO-TB-003 *Habitable Atmosphere*, Rev A (11/30/2023) | Crew-health limits for cabin air: total pressure range, inspired O₂ (PIO₂) limits, minimum inert diluent gas, rate of pressure change, ebullism pressure, and the related NASA-STD-3001 requirement text (not experiment data) |

## Sources, citation, and reuse

| File | NASA PSI source | Reuse terms |
|---|---|---|
| `PSI-159_Raw Data_Final ACME Chamber Calculator - 2021-03-09 to 2021-10-21.xlsx` | [PSI-159: ACME CFI-G](https://psi.nasa.gov/physci/repo/data/investigations/PSI-159) | CC0-1.0 |
| `Saffire-I Sample 2 Sensor Data Complete TM graphs.xlsx` | [PSI-98: SAFFIRE-I](https://psi.nasa.gov/physci/repo/data/investigations/PSI-98) ([DOI](https://doi.org/10.60555/0t15-1z43)) | CC0-1.0 |
| `PSI-107_Experimental table_Spice.csv` | [PSI-107: SPICE](https://psi.nasa.gov/physci/repo/data/investigations/PSI-107) ([DOI](https://doi.org/10.60555/9kbh-e962)) | CC0-1.0 |
| `PSI-101_Experimental table_SAME-R.csv` | [PSI-101: SAME-R](https://psi.nasa.gov/physci/repo/data/investigations/PSI-101) ([DOI](https://doi.org/10.60555/2np7-jv14)) | CC0-1.0 |
| `BASS-II Test Matrix by PI Final.xlsx` | [PSI-25: BASS-II](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25) ([DOI](https://doi.org/10.60555/4qc4-de67)) | CC0-1.0 |
| `PSI-26_Experimental table_BASS.csv` | [PSI-26: BASS](https://psi.nasa.gov/physci/repo/data/investigations/PSI-26) (record not yet checked) | Not yet checked |

The PSI investigation records list the licenses above. The two BASS files were added on
2026-11-15. The BASS-II source (PSI-25, DOI, CC0-1.0) is as identified in the independent review of
PR #35/#38; the PSI-26/BASS record and reuse terms still need checking. In the BASS-II workbook,
one T'ien test (T9) carries a 2018 date although its GMT day matches 2014 tests; dates are
kept as recorded. NASA asks users to cite
PSI data using the investigation DOI where available. The files first appear in
this repository in the 2026-11-14 data commit; the original download dates were
not recorded, so that commit date is not presented as a download date. Source
metadata was checked on 2026-11-14. See [NASA's PSI citation guidance](https://psi.nasa.gov/physci/repo)
and [NASA's science data license guidance](https://science.data.nasa.gov/about/license).

`fire-dashboard/scripts/build_reference_data.py` turns these files into the
dashboard's reference data.

### Habitable atmosphere technical brief

| File | NASA source | Reuse terms |
|---|---|---|
| `ochmo-tb-003-habitable-atmosphere.pdf` | NASA Office of the Chief Health & Medical Officer, [OCHMO-TB-003 Habitable Atmosphere](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-003-habitable-atmosphere.pdf) | NASA material (generally not copyrighted in the US); some figures are credited to third parties and keep their own terms (not checked) |

Supplied by Cody and added on 2026-11-15 (downloaded that day). Its SHA-256 (`a53c44ae…77163`)
matched the copy at the NASA link above when checked on 2026-11-16 UTC. The brief is for reference
only and does not supersede program requirements. It is not read by the build script: the limits the
dashboard uses are transcribed into `THRESHOLDS.habitable` in `fire-dashboard/js/parameters.js`, each
with its NASA-STD-3001 requirement number. Table 6.2-1 (PIO₂ exposure ranges, including any
hyperoxia limits) is an image in the PDF and was not transcribed; humidity, temperature and CO₂
limits are not in this brief.

## How this data will be used

The dashboard skeleton (its layout, metrics and charts) will be designed once,
from the data sets stored here. It will not be regenerated each time a user
submits input, because rebuilding it per request would be too slow and costly.
User input will fill the existing skeleton instead.

A prototype dashboard built from this data is in `fire-dashboard/`.

## When adding a data set

When adding a data set, record for each file:

- NASA source (mission, experiment or data portal) and a link to it
- Date downloaded
- License or usage terms
- Short description of its contents, units and columns
