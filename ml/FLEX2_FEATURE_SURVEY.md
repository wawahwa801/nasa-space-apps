# Bounded FLEX-2 feature survey

This follow-up to [#18](https://github.com/wawahwa801/nasa-space-apps/issues/18) inspects **48 additional run records**, excluded from the published 100-run library: four evenly spaced IDs from each of 12 prespecified campaigns. The selection spans ten catalogued fuel/formulation labels and five catalog families (quiescent, surrogate fuel, imposed flow, binary arrays, condensed phase). It is a diversity sample, not a random population estimate.

The pass stopped at that cap. It acquired **318 small metadata files (15,256,231 bytes)** from a maximum of 336 lookups; 18 files were missing, ambiguous or restricted. No image archives or new image targets were downloaded. Existing catalog/summary metadata were also consulted. All available sampled files have resource IDs, versions and checked SHA256 hashes in `reports/flex2-feature-sample.json`.

**Significance here means a defensible candidate with recorded variation or documented physical relevance. No predictive feature-importance, statistical-significance, or causal test was performed.** Outcomes and newly qualified flame images were not collected, so improved model accuracy is not claimed.

## Existing inputs and additional candidates

| Feature family | Evidence in the additional 48 | Assessment |
| --- | --- | --- |
| Fuel identity and blend formulation — already used for five pure fuels | All 48 catalog labels; ten formulations, including heptane–toluene, decane–propylbenzene and propanol–glycerol blends | Retain fuel. Extend verified blend identities as categorical labels; mixture mass/volume basis and disputed chemical identities must be resolved before treating name ratios as numeric composition. |
| Chamber pressure — already used | 37 unit-verified pre-ignition joins, **51.41–305.64 kPa** | Strong candidate to retain and evaluate across a broad range. No pressure value is inferred from `N/A` unit headers. |
| Chamber temperature — already used | 37 unit-verified joins, **23.01–27.23 °C** | Retain as measured context; narrow variation and campaign correlation limit independent temperature-effect claims. Chamber temperature is not flame temperature. |
| Support fiber usage | 44 exact settings joins: **five Yes / 39 No** | Useful apparatus/configuration candidate for an explicit ablation or separate groups. A recorded usage parameter is not independent visual confirmation of deployment. |
| Igniter power setting | 44 exact settings joins; six values, **8.03–21.07 W** | Test as a procedure covariate, especially for early-stage imagery. Commanded wattage is not measured heat transferred to the droplet or flame power. |
| Igniter on-time | 44 verified event summaries; 16 values, **0.8–6.0 s** | Test alongside power and burn-stage alignment. Their product is a possible nominal-energy feature, not an independently measured delivered energy. |
| Time since igniter-on / burn-stage proxy | 44 verified event joins; igniter-on to retraction **1.205–6.423 s** | High-priority alignment check. Applying the current 4.15-second post-retraction stage would produce **5.355–10.573 s after igniter-on**. These are hypothetical sample times, not newly downloaded targets or measured flame onset. |
| Experiment family / droplet arrangement | Five catalog families, including eight binary-array and four imposed-flow records | Keep an explicit configuration/grouping field; validate compatibility before pooling these physics into a single-droplet predictor. Actual droplet count, spacing and flow still require matched measurements. |
| Camera shutter and gain | Raw settings in 46 records: six shutter positions (**1/4 to 1/725 s**), four gains (**−3 to 9 dB**) | Acquisition/appearance covariates to audit, normalize or stratify. Auto modes and stale/status fields mean these are not certified frame-level effective exposures. |
| Camera zoom, red/blue gains and aperture setting | 46 raw records: 14 zoom codes, six red-gain codes, nine blue-gain codes and two aperture-gain codes | Important image-scale/colour confound candidates. Device codes have no verified physical calibration here; do not present them as physical flame controls. |
| Exposure and white-balance mode | 31 descriptive Auto/Full Auto values and 15 `0.0` codes | Semantics remain incomplete. Two raw encodings do not establish two real modes. Resolve codes before model conditioning. |
| Pressure/temperature stability | 37 pre-ignition windows; temporal standard deviations **0.0069–0.0308 kPa** and **0.0068–0.0315 °C** | Primarily small quality indicators; not established independent combustion controls or calibrated sensor uncertainties. |
| Campaign / acquisition day | Prespecified campaign labels and event timestamps | Evaluation groups for held-out campaigns/days. Avoid a date slider or learning acquisition identity as a physical cause. |

The currently published 100 targets independently show **5.343–11.122 seconds since recorded igniter-on** at the median selected frame timestamp. Thus fixed time after retraction does not imply fixed time since igniter-on even in the existing library. This observation motivates checking stage alignment before increasing model complexity; it does not prove that stage explains current image error.

## Important physical factors still lacking sufficiently matched labels

The official [PSI-68 investigation](https://psi.nasa.gov/physci/repo/data/investigations/PSI-68) names ambient composition, initial droplet size, relative motion and array spacing among the experimental factors. The downloaded eight-row experimental summary lists possible conditions: diameter **1.5–5 mm**, O₂ fractions **0.17, 0.21, 0.25, 0.30**, O₂/N₂ or O₂/He, pressures **0.5–3 atm**, and flow **0.1–5 cm/s**. The catalog narrative describes a broader O₂ range of 0.1–0.4. Both are study-level descriptions, not exact per-run labels or a verified Cartesian grid of experiments.

The physical feature candidates with high priority but incomplete joins are:

1. **Oxygen mole fraction.** Two additional heptane IDs in this sample (`E066C04`, `E087C04`) match the [published exact-ID list](https://doi.org/10.1080/00102202.2025.2595114). Both are again reported at 21% O₂ / 79% N₂. With the earlier ten matches, this is twelve matched records across the 148 inspected IDs, all at the same reported mixture. It is not a measurement of label availability across the full dataset, and some additional runs were excluded from the current image library for image/source checks. No varying exact-run oxygen labels were recovered here.
2. **Diluent identity and gas fractions** (e.g. N₂ versus He). Listed by the study; their different properties are relevant to modelling, but no new varied exact-run mixture labels were established in these files.
3. **Initial droplet diameter.** A physical size input needs calibrated backlit measurement at a deployment-aware initial stage. The earlier ten-run backlit pilot and [measurement-method paper](https://doi.org/10.1109/TPAMI.2022.3170926) support feasibility, not an automatically verified mm label for this sample.
4. **Relative flow / droplet translation velocity and acceleration.** Imposed-flow campaigns exist. Raw nozzle/device-speed values in `N/A` units do not supply calibrated cm/s or m/s and are not assigned physical units here.
5. **Droplet spacing and array geometry.** Relevant specifically to binary-array experiments. Calibrated spacing/separation and successful deployment are not supplied by the campaign name or unscaled motor positions.

Seven of the earlier 100 and at least one additional sampled record (`E159F06`) are covered by the catalog/paper fuel disagreement tracked in [#33](https://github.com/wawahwa801/nasa-space-apps/issues/33). Catalog labels are retained as claims of that source, not independent chemical verification. Conflicting paper-derived labels are withheld.

## Fields not promoted to independent model controls

- Camera focus mode is Auto in all 46 available records; illumination and soot-sampler usage are No in all 44 valid settings rows. These supplied no useful variation in this sample.
- All sampled campaigns are labelled Reduced Gravity. No measured gravity variation was established, so the sample does not support learning a gravity response.
- Programmed burn-to-completion duration varies from 12–120 seconds, but it is a procedure/scheduling parameter rather than measured flame lifetime. Actual extinction/burn duration and image-derived flame brightness/area should not be fed back as inputs to predict those same outcomes.
- Dispenser totals, needle/igniter positions, motor moves and nozzle settings have device-dependent or `N/A` units. They may help diagnose procedures; they are not substituted for calibrated droplet size, separation, fuel volume or flow.
- Raw mode-code variation and broad numeric spread are not evidence that a feature improves held-out prediction. Temperature, power, camera settings and campaign can be strongly confounded.

## Practical order of work

Keep **fuel, pressure and measured temperature**. First test **stage/time alignment, fiber usage, igniter power and on-time** with training-only reference selection and whole-run/campaign holdouts. Audit camera covariates in parallel so an apparent flame response is not merely camera response. Resolve exact-run **diameter, oxygen, gas composition and relative flow** before introducing those physical sliders. The fixed 48-record cap was sufficient to expose the coverage/variation and main missing joins; no full-dataset scan is needed to support this shortlist.

## Reproduce

```bash
python ml/flex2_feature_sample.py fetch
python ml/flex2_feature_sample.py audit
python -m unittest discover -s ml -p 'test_flex2_feature_sample.py' -v
```

The selector excludes the existing 100 run IDs and chooses four IDs per prespecified category. The fetch command is capped at seven small metadata files per run and never fetches image archives. Raw caches remain ignored; the tracked JSON contains field variation, checked file hashes/versions, missingness and all 48 run records. The CSV is a compact per-run table. This research pass does not modify training data, checkpoints or dashboard controls.
