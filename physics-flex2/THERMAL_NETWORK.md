# Dimensioned room-scenario model

This is a thermal-network sensitivity study, not a calibrated compartment fire
or spacecraft safety model. It replaces the main dashboard's use of the FLEX-2
D² liquid-droplet lifetime as the lifetime of a whole room. The original droplet
and legacy graph experiments remain available in their standalone prototype.

## Dimensions and explicit assumptions

Room width/length/height (m) affect effective heat capacity. Fuel energy is an
assumed 30 MJ per square metre of floor area. Air density is fixed at 1.2 kg/m³
and specific heat at 1 kJ/(kg K); a thermal inertia multiplier represents
unresolved contents/linings. This is not a measurement of actual wall properties.

Each ignited room has specified heat release Q = min(1000, 20 + 1000(t/tg)²) kW,
limited by remaining assumed fuel energy. Source ignition is imposed at time zero.
An open hallway receives a bounded fraction of HRR split by hallway width, delayed
by ceil(length/assumed transport speed), attenuated by exp(-length/20 m).
Closed doors transfer zero in this model; leakage/door failure is not modeled.

Room temperature uses an explicit 1-second heat-capacity update with a 1200-second
cooling timescale plus effective radiative loss (emissivity 0.15) to ambient 22 °C.
This single mean temperature is used for an assumed ignition threshold; real
material surface ignition, stratification, oxygen, pressure-driven ventilation,
smoke and microgravity flow are not resolved. New ignitions are synchronous.

The default 16-module schematic now has room widths 4–6 m, lengths 5–6 m, height
2.7 m, hallway lengths 4–10 m and widths 1.2 m. It runs for 20 minutes. The default
nominal scenario reaches some adjacent rooms after roughly 12 minutes; that is a
result of these assumptions, not a validated fire-spread time or a minimum delay.
Some rooms are not reached before the horizon. Faster real events remain possible.

The CNN mask/diameter is retained as visual provenance only. It supplies no
calibrated heat release, fuel load, room growth rate or ignition boundary.
Changing the image's assumed mm/pixel conversion does not alter cabin timing.

## Sensitivity ranges

Three deterministic profiles vary t² growth time, ignition threshold, effective
thermal inertia, transfer fraction and corridor transport speed together:

| Profile | tg (s) | Threshold (°C) | Inertia | Fraction | Speed (m/s) |
|---|---:|---:|---:|---:|---:|
| Earlier spread | 150 | 140 | 1.5 | 0.60 | 0.80 |
| Nominal | 300 | 180 | 2.0 | 0.50 | 0.50 |
| Later spread | 600 | 240 | 3.0 | 0.35 | 0.25 |

The UI reports min/max temperature across these profiles and ignition-time ranges.
A null latest time means at least one profile never ignited within the horizon;
it must be displayed as censored, not as a bounded interval or proof of safety.
These are selected scenario envelopes, not all possible parameter extremes, not
95% confidence/credible intervals, and not calibrated image-model uncertainty.
No probability coverage is asserted. Calibration needs matched compartment-scale
HRR, material/ventilation, wall/thermal and ignition data; see issues #46/#55.

## Scientific context

NIST CFAST uses user-specified heat release and distinguishes model assumptions,
geometry, ventilation, sensitivity and validation. We use the t² HRR *form* as
scenario input only; we do not implement CFAST's two-zone equations or inherit its
validation. Numeric defaults above are explicit illustrative choices.

- NIST CFAST technical reference: https://www.nist.gov/publications/cfast-consolidated-model-fire-growth-and-smoke-transport-version-6-technical-reference
- NIST user guide, specified t² fires: https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.1041r1.pdf
- NASA Saffire full-scale motivation and scaling limitations: https://ntrs.nasa.gov/citations/20180005168

The NASA work emphasizes that small-scale flames and spacecraft fire interactions
do not scale linearly. These sources motivate the design/limitations; they do not
validate this implementation or its numeric scenario settings.
