# FLEX-2 live flame lab

The exact-run missing-input investigation is documented in [FLEX2_INPUTS.md](FLEX2_INPUTS.md), with a 100-row provenance table, partial published gas-condition matches, backlit-camera pilot and unresolved source conflicts. These audit labels have not been added to the inference schema.

## 100-run retrieval expansion

Issue [#17](https://github.com/wawahwa801/nasa-space-apps/issues/17) expands the bounded testing library to **100 independent test points**, each represented by four timestamp-selected RGB frames. This is source verification and basic image screening, not certification of 100 steady physical states. Independent runs can share measured conditions; exact pressure/temperature-pair coverage is reported separately. The 24-target results below describe the earlier prototype and do not measure the expanded library.

The final selection has **60 training / 20 validation / 20 test runs**, from 247 candidate archives: 41 fail acquisition/metadata checks, 65 fail the stronger visibility screen, and 41 usable runs remain outside the bounded selection. Counts by fuel are 25 decane, 10 heptane, 16 isooctane, 25 n-octane and 24 toluene. Each selected run has a distinct measured pressure/temperature pair within its fuel, although small sensor differences do not establish physically distinct operating regimes.

The expanded CPU benchmark completed 100 epochs in 203.5 seconds and selected epoch 60. On 20 held-out runs, RGB MAE is **0.0862 CNN / 0.0821 same-fuel training mean / 0.1100 training-only retrieval**; foreground MAE is **0.1648 / 0.1659 / 0.2964**. CNN RGB error is lower than retrieval but higher than the mean baseline. These image errors, weak masks and incomplete labels do not establish physical accuracy or a causal response. The architecture-version string remains `flex2-rgb-v2`; dataset hash, counts and the separate report filename identify this expanded run.

From an isolated checkout and the ML Python environment:

```bash
python ml/flex2_data.py fetch --runs-per-fuel 100
python ml/flex2_data.py prepare --target-runs 100
python ml/flex2_audit.py
python ml/flex2_model.py --epochs 100
python -m unittest discover -s ml -p 'test_flex2.py' -v
python ml/flex2_lab.py
```

`--runs-per-fuel` retains its historical name but limits candidates **per campaign category**. The expanded allowlist covers quiescent decane and single-droplet surrogate-fuel campaigns for heptane, n-octane, isooctane and toluene. Binary arrays and imposed-flow campaigns are excluded. Camera format, run identity, explicit telemetry units, pre-ignition timing, source member checksums and visible connected colour signal must pass. `NA` telemetry units are not guessed. Repeated identical inventory nodes are deduplicated; conflicting archive identities fail acquisition. Cached frame/metadata hashes are checked before reuse.

Preparation requires at least 400 connected colour-mask pixels in the fixed ROI, increased from 100 after montage inspection found near-empty accepted targets. This is a basic visibility screen; remaining highlights, reflections, saturation and weak segmentation are not calibrated away. Preparation refuses to replace the existing library if fewer than 100 usable independent runs remain. It allocates fuel quotas round-robin, then selects evenly spaced pressure-sorted runs within each fuel. At least six runs per retained fuel and whole-run train/validation/test splits remain required. Accepted runs outside this bounded selection are distinguished from failed acquisition/image checks in the exclusions. The testing page derives its fuels, ranges and count from the rebuilt artifacts. Retrain the CNN after preparation because the server rejects a checkpoint for a different dataset. Models and source images stay local/ignored; reproduce them with the commands above.

`ml/reports/flex2-100-data.json` records accepted run IDs, source resource versions, selected member hashes, split membership and exclusions. `flex2-100-audit.json` reports per-fuel ranges, distinct measured feature pairs, camera-setting distributions, pre-ignition stability, sensor spread and image quality indicators. Run `flex2_audit.py` after every dataset rebuild. The retrained benchmark is saved separately as `flex2-rgb-100-v1.json`; compare CNN against training-only retrieval and same-fuel means on this dataset, not against the earlier five-test-run scores.

Additional pipeline features supported by these records:

- **Pre-ignition sensor stability and inter-channel spread:** available quality flags. Channel spread can reflect sensor location or offsets and is not a calibrated uncertainty estimate.
- **Camera zoom, exposure, gain and white balance:** audited nuisance covariates for stratified evaluation or an explicitly tested ablation. Auto settings and command/status fields need interpretation before using them as image-conditioning controls.
- **Campaign and acquisition date:** useful for grouped holdouts to detect acquisition confounding. Existing whole-run splits alone cannot establish generalization across campaigns.
- **Weak-mask area and saturation:** target-quality diagnostics only; using target-derived values as inference inputs would leak the answer.

All 100 selected records contain the audited raw camera fields, but 20 encode exposure and white-balance modes as `0.0` rather than descriptive values. Field presence does not establish verified semantics; preserve these codes and resolve the camera schema before promoting them to model features.

Oxygen fraction, initial droplet diameter, ambient gas composition and airflow are still absent from the verified inference schema. Their exact-run joins remain tracked in [#18](https://github.com/wawahwa801/nasa-space-apps/issues/18). Camera calibration, reflections, weak masks and manual quality review remain in [#19](https://github.com/wawahwa801/nasa-space-apps/issues/19). More records do not establish causal input effects or CNN accuracy.

The active page now uses **NASA FLEX-2 (PSI-68)** RGB spherical-droplet-flame images. Switch **CNN / Retrieval** without leaving the page. Sliders update on `input` events while dragging: retrieval searches a preloaded library locally, while the CNN sends at most one request at a time, retaining only the newest pending inputs. Completed intermediate predictions remain visible during continuous dragging. Captions show the conditions actually displayed. The previous SPICE page remains accessible through the dataset navigation.

## Prepare, train and run

From a dedicated repository checkout, with [the Python environment](README.md) activated:

```bash
python ml/flex2_data.py fetch --runs-per-fuel 16
python ml/flex2_data.py prepare
python ml/flex2_model.py --epochs 250
python ml/flex2_lab.py
```

Open **http://127.0.0.1:5051/flex2/**. Existing local data and checkpoint allow skipping preparation/training. Stop an older server on port 5051 before starting; restart after training or template changes. `python ml/spice_lab.py` also makes FLEX-2 the default when its checkpoint exists. Both launchers retain SPICE navigation when its artifacts exist. The older BASS/FLEX lab mounts `/flex2/` on port 5050 when those artifacts exist at startup. Models, source frames and raw telemetry remain local/ignored; tracked source audits and reports support review.

## What the inputs actually mean

- **Fuel:** Decane or Heptane, from NASA's full-file-tree subcategory for the exact archive.
- **Chamber pressure (kPa):** mean of channels PT16/PT17/PT28/PT29 in the five seconds strictly before ignition, converted from PSIA with 6.894757293 kPa/PSIA.
- **Chamber temperature (°C):** mean of TM1/TM2/TM3/TM4 over that same pre-ignition window.

These are measured environmental inputs, not flame temperature or heat flux. The public eight-row experimental summary gives ranges and possible mixtures; it does **not** supply per-run oxygen, initial droplet diameter or airflow. Those labels have not been invented or inferred from range combinations. Temperature varies over a narrow range and can correlate with acquisition conditions; an image response to its slider is not a validated causal effect. Missing droplet size and oxygen make this an incomplete predictor.

## Real colour data and preprocessing

The [NASA PSI-68 file inventory](https://psi.nasa.gov/physci/repo/data/investigations/PSI-68) exposes per-test-point camera ZIPs, event records, chamber telemetry and camera settings. Acquisition joins exact test-point IDs. RGB24 settings and 640×480 RGB BMP members identify the colour-camera D stream. This is distinct from the monochrome camera-B stream used in the earlier FLEX/PSI-69 prototype.

Selection is spread across 16 candidate runs per fuel before image inspection. HTTP range reads retrieve metadata and four source members per archive; whole hundreds-of-MB/GB camera archives are not downloaded. Restricted/ambiguous resources, missing timestamps, wrong camera formats and insufficient visible colour signal are excluded with reasons. Selected members have ZIP CRC verification plus cached SHA256 checks; **whole-archive hashes are not claimed** for range reads. Source resource IDs, versions, camera settings, frame clocks, event clocks and original telemetry files are retained. The full inventory is cached separately from release-change metadata.

Initial quality checking found immediate post-igniter samples dominated by flares. The final fixed stage is **4.0/4.1/4.2/4.3 seconds after recorded igniter retraction**, summarized with a per-channel median. This is a repeatable stage proxy, not proof of steady conditions or a common burn fraction. Fixed crop x160:480/y100:420, display transform `clip((RGB-3)*2)`, Gaussian 3×3 sigma .6, and resize to 256 preserve image-relative scale and source colours. No artificial colourization, per-flame resizing or generated training data is used. Saturated highlights, camera noise, hardware reflections and some distorted flames remain; weak HSV masks can include these artifacts. The minimum connected colour-signal threshold excludes point-like residuals, not every failed ignition.

The prepared manifest records the actual final counts and exclusions; adjacent frames are **not independent examples**. One target summarizes one test point. Native camera resolution, not displayed dimensions or padding, limits detail.

The final subset has **24 targets (96 selected RGB frames)**: 10 decane and 14 heptane runs, split into 14 training / 5 validation / 5 test targets. Thirty-two runs were attempted; one camera format was rejected and seven lacked sufficient connected colour signal in the fixed later ROI. This is a bounded prototype, not the full FLEX-2 dataset.

## CNN, retrieval and evaluation

A separate 1,076,404-parameter feature-conditioned CNN predicts the full 256×256 RGB image and an auxiliary weak mask. It does not reuse SPICE weights or SPICE's horizontal strip geometry. Foreground-balanced and multiscale losses address background domination. Time, source images and test-point identifiers are not inference inputs.

Whole-test-point hash splits within fuel keep all frames of a run together. Only training data set normalization. Validation selects a checkpoint and early stopping waits 50 epochs; the test set is evaluated afterward. The final report is `ml/reports/flex2-rgb-v2.json`; the source audit is `ml/reports/flex2-data-v2.json`. The early-stage trial was superseded after image-quality inspection; its metrics are not compared as an accuracy improvement because its targets differ. The final model remains experimental even when pixels change with inputs.

Retrieval matches fuel exactly and ranks normalized pressure/temperature distance. The default library includes all recorded targets, including held-out examples; enable **Retrieve training images only** for a restricted comparison. Reported retrieval benchmarks always use training targets only. Retrieval can stay unchanged between recorded conditions and does not synthesize a continuous physical transition. Neither model predicts arbitrary oxygen/diameter conditions, temperature fields, heat flux or fire spread.

The page starts in **Retrieval** to show recorded colour flames immediately; the **CNN** button selects generated estimates. The final CPU run took **29.8 seconds**, completed 70 epochs and selected epoch 20. On five test runs, CNN RGB MAE was **0.0759** versus **0.0383** for the same-fuel training mean and **0.0374** for training-only retrieval; foreground MAE was **0.2632 / 0.2016 / 0.2259**, respectively. The CNN is worse than those baselines on these errors. It produces blurred or distorted colours/shapes and severe artifacts outside training ranges. Slider sensitivity demonstrates that inputs reach the model; it does not demonstrate predictive accuracy. Missing physical labels and camera variation remain substantive blockers to that accuracy.

Preview alignment uses an integer translation to put the detected luminous-region bounding-box centre in the middle of the display. Smoothed intensity and component filtering reduce camera noise/reflection influence. This is approximate display alignment, not calibrated segmentation; empty/weak detections retain their position. No scaling or recolouring is applied. Background at an image edge can be clipped as it moves off-canvas. Training targets, checkpoints and reported unaligned benchmark scores remain unchanged, so the display does not imply a new accuracy result.

In the saved model's within-training-range sweeps at fixed median remaining inputs, higher decane pressure produces a brighter, larger diffuse prediction. Temperature produces smaller changes in colour/shape. Heptane pressure varies over only about 1.2 kPa in training and barely changes the prediction. These are empirical model responses, not isolated causal effects or a reliable monotonic law. Chamber temperature is not flame temperature; arbitrary red/blue colour rules have not been programmed into the interface.

## Verify

```bash
python -m unittest discover -s ml -p 'test_flex2.py' -v
```

The suite verifies actual source member hashes, pre-ignition-only telemetry, fuel joins, whole-run splits, mode-specific responses, numeric/unknown-field rejection, PNG dimensions and pressure sensitivity. Data-dependent checks skip without local data/checkpoint. Existing SPICE tests remain applicable. The optional `check_flex2_ui.cjs` uses Playwright against the running lab to verify updates during continuous dragging, latest-input convergence, immediate local retrieval, mode/fuel switching and mobile overflow. Install Playwright separately for this optional development check; it is not an application dependency.

Remaining work is tracked in GitHub issue #4: matched per-run oxygen/droplet-size labels, camera/exposure and physical spatial calibration, stronger target/mask review, more independent conditions and evaluation across acquisition days. The interface and learned sensitivity are functional prototypes, not established physical accuracy.
