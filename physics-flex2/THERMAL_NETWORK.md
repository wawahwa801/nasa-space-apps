# Scaled equivalent-droplet room scenarios

This is a dimensioned thermal-network sensitivity study, not calibrated spacecraft
fire prediction. The CNN predicts a luminous flame mask. Its equivalent-area size,
multiplied by a user-supplied image scale, is treated as an **equivalent droplet
proxy**, not a measured liquid-droplet diameter. Actual droplet diameter and its
physical calibration remain missing evidence (issue #81).

## Droplet coupling and time units

For proxy diameter d (mm) and assumed K (mm²/s), the idealized D² law gives a raw
lifetime tau_d = d²/K seconds. An explicit assumed aggregation multiplier S (default
600, adjustable 60–3600) gives the nominal room-release lifetime tau = S tau_d.
The three sensitivity profiles multiply tau by 0.5, 1 and 2. No empirical similarity
law establishes these multipliers for room fires; they are adjustable assumptions.

A 1.05 mm proxy at K=0.8 has tau_d=1.378 s and nominal scaled lifetime 826.875 s.
This calculation is exported and shown in the UI; changing the CNN-derived size,
image scale, K or aggregation multiplier changes the actual solver output.

D² implies a relative volume F(t)=max(0,1-t/tau)^(3/2). Per-step release is the
finite difference E_initial [F(t)-F(t+1)] kJ over a 1-second step, multiplied by a
bounded startup ramp min(1,((age+0.5)/ramp_time)²). Ramp time is the smaller of the
profile's 150/300/600-second parameter and 30% of scaled lifetime. Finite fuel
energy is enforced. Unconsumed fuel after the scaled release ends is retained and
the room is labeled extinguished; a curve ending does not claim complete burnout.

Every fueled room has an assumed 30 MJ/m² floor fuel load. The D² shape distributes
that energy in time. This is an assumed aggregate-source construction, not an
assertion that many droplets or arbitrary solid materials obey isolated-droplet
combustion. HRR is derived from this construction, not independently measured.

Simulation time uses actual modeled seconds (1-second integration and 5-second
output frames). Playback defaults to **30×**, so one real second displays 30
simulated seconds. Speed affects presentation only. The clock shows minutes and
seconds plus total simulated seconds; it does not relabel display frames as time.

## Room and hallway effects

Room width/length/height affect effective heat capacity; floor area also changes
assumed fuel energy. Air density is fixed at 1.2 kg/m³, specific heat at
1 kJ/(kg K), and an assumed inertia multiplier represents unresolved linings.
Open corridors receive a bounded HRR share split by corridor width, delayed by
ceil(length/assumed velocity), and attenuated by exp(-length/20 m). Closed doors
transfer zero. Heat loss uses a 1200-second timescale and an effective radiative
loss with emissivity 0.15 to ambient 22 °C. New ignitions are synchronous.

The simple default is six 5×5×2.7 m rooms, five 6 m long / 1.2 m wide corridors,
and a 20-minute horizon. The compact editor opens beside the map. Basic controls
are room width/length, ignition, hallway length and doors. Name/position/add/remove/
connect/fuel/height and scaling settings are grouped under disclosure sections.
Deck coordinates are schematic; numeric lengths are the solver's physical inputs.

## Sensitivity ranges and limits

Earlier/nominal/later profiles vary assumed ignition threshold (140/180/240 °C),
inertia (1.5/2/3), transfer (0.60/0.50/0.35), velocity (0.80/0.50/0.25 m/s), and
scaled burn duration (0.5/1/2× nominal). The UI reports min/max temperature and
ignition-time envelopes across these three profiles. If any profile does not
ignite within the horizon, the upper ignition bound is null and displayed as
censored. Unreached does not mean safe. These are selected assumption envelopes,
not comprehensive bounds or calibrated 95% confidence/credible intervals.

There is no resolved gas stratification, pressure-driven ventilation, oxygen
depletion, smoke, surface ignition, wall conduction or radiative ignition. K and
scale are not learned cabin parameters. Calibration needs matched compartment-
scale measurements and independent evaluation (issue #81; #46 remains open).

## Scientific context

The isolated-droplet D² law and its approximations are described by NASA. It is
not generally valid for interacting droplets, and no direct transfer to room
fire times is established by these references:

- NASA classical droplet theory: https://ntrs.nasa.gov/citations/19890010934
- NASA interacting arrays and departures from D²: https://ntrs.nasa.gov/citations/19990054030
- NASA Saffire full-scale/scaling motivation: https://ntrs.nasa.gov/citations/20180005168
- NIST compartment geometry, specified HRR and validation context: https://www.nist.gov/publications/cfast-consolidated-model-fire-growth-and-smoke-transport-version-6-technical-reference

This implementation is not CFAST/FDS and does not inherit their validation.
References motivate the assumptions/limits, not the selected scale or accuracy.
