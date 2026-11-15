# FLEX-2 live flame lab

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
