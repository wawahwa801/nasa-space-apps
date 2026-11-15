# data

Source data for the fire safety dashboard.

## Scope

- Contains only fire safety data from NASA. Do not add data from other sources.
- Data sets are supplied by the project team.

## Data sets

| File | Experiment | Contents |
|---|---|---|
| `PSI-159_Raw Data_Final ACME Chamber Calculator - 2021-03-09 to 2021-10-21.xlsx` | ACME (Advanced Combustion via Microgravity Experiments) chamber, ISS | As-run test points: gas additions, chamber mixture, pressure, temperatures, and whether each test ignited |
| `Saffire-I Sample 2 Sensor Data Complete TM graphs.xlsx` | Saffire-I, sample 2 | Calibrated sensor log (~32 readings/s): O₂, CO₂, pressure, humidity, flow, plume and sample temperatures |
| `PSI-107_Experimental table_Spice.csv` | SPICE (Smoke Point In Co-flow Experiment) | Gas-jet flame runs: fuel, nozzle diameter, fuel and air flow rates |
| `PSI-101_Experimental table_SAME-R.csv` | SAME-R (Smoke Aerosol Measurement Experiment – Reflight) | Smoke tests: material, flow, heater ratio, aging times |

## Sources, citation, and reuse

| File | NASA PSI source | Reuse terms |
|---|---|---|
| `PSI-159_Raw Data_Final ACME Chamber Calculator - 2021-03-09 to 2021-10-21.xlsx` | [PSI-159: ACME CFI-G](https://psi.nasa.gov/physci/repo/data/investigations/PSI-159) | CC0-1.0 |
| `Saffire-I Sample 2 Sensor Data Complete TM graphs.xlsx` | [PSI-98: SAFFIRE-I](https://psi.nasa.gov/physci/repo/data/investigations/PSI-98) ([DOI](https://doi.org/10.60555/0t15-1z43)) | CC0-1.0 |
| `PSI-107_Experimental table_Spice.csv` | [PSI-107: SPICE](https://psi.nasa.gov/physci/repo/data/investigations/PSI-107) ([DOI](https://doi.org/10.60555/9kbh-e962)) | CC0-1.0 |
| `PSI-101_Experimental table_SAME-R.csv` | [PSI-101: SAME-R](https://psi.nasa.gov/physci/repo/data/investigations/PSI-101) ([DOI](https://doi.org/10.60555/2np7-jv14)) | CC0-1.0 |

The PSI investigation records list the licenses above. NASA asks users to cite
PSI data using the investigation DOI where available. The files first appear in
this repository in the 2026-11-14 data commit; the original download dates were
not recorded, so that commit date is not presented as a download date. Source
metadata was checked on 2026-11-14. See [NASA's PSI citation guidance](https://psi.nasa.gov/physci/repo)
and [NASA's science data license guidance](https://science.data.nasa.gov/about/license).

`fire-dashboard/scripts/build_reference_data.py` turns these files into the
dashboard's reference data.

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
