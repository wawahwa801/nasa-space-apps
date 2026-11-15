# SPICE feature retrieval and image CNN

Two prototypes use the same exactly matched NASA still-image/condition pairs. Retrieval returns a real recorded image. The conditional CNN predicts RGB pixels from fuel category, nozzle diameter (mm), fuel flow (sccm), and air co-flow (cm/s). No source image, time, row number, or experiment ID enters the CNN.

## Run

From the repository root, using the environment in [README.md](README.md):

```bash
python ml/spice_data.py fetch
python ml/spice_data.py prepare
python ml/spice_model.py --epochs 250
python ml/spice_lab.py
```

Open **http://127.0.0.1:5051/spice/**. Existing prepared data/checkpoints let you skip the first three commands. Restart the server after retraining. The BASS/FLEX lab also mounts `/spice/` on port 5050 when the SPICE artifacts exist at startup. Source files, generated pairs and checkpoints are ignored by git; acquisition and training are reproducible from these commands. The downloads total approximately 220 MB and are capped per file at 160 MB. Training uses the local CPU; the saved report records elapsed time, actual completed epochs, and the validation-selected checkpoint.

Choose a fuel, nozzle and flow values, or select a recorded condition. The CNN output changes continuously with its numerical inputs. Retrieval changes when another recorded example becomes closest. “Search training images only” excludes validation/test references; the default catalog includes all matched stills. Retrieved conditions and original NASA image links are shown explicitly. Selecting a test example does not supply its image to the CNN.

## Matched subset

The [NASA PSI-107 catalog](https://psi.nasa.gov/physci/repo/data/investigations/PSI-107) provides the public CC0-1.0 data. Its *SPICE Image Organization Guide* identifies workbook column AD as the Nikon exchange image ID, with corresponding conditions on that row. The prototype reads *Spice Flight Test Data II modified.xls* and joins exact IDs to unmodified JPEG members from GMT 045, 048, 052, 055 and 062 archives. Edited `SCALE` image variants are not substituted. Source and member hashes, original rows, excluded-row reasons and joins are retained in `ml/data/spice-study/manifest.json`.

The resulting subset has **92 images across 44 ignition/condition groups**: 64 training, 12 validation, 16 test images. Fuels are ethylene (20), propane (16), 75% propylene (22) and 50% propylene (34). Fuel mixtures remain separate categories, not an invented continuous composition measurement. Methane has fewer than four usable groups after filtering and is excluded from this prototype. Other archive days and fuels are not claimed as covered.

The tracked acquisition audit is `ml/reports/spice-data-v1.json`: selected image IDs, workbook rows, input values, groups, splits, source/member hashes and exclusion reasons. The generated local manifest additionally preserves complete original workbook rows.

Select one source-labeled −5 EV bracket per row and reject images explicitly flagged saturated in any RGB channel. Blank saturation flags mean unknown, not certified unsaturated. Equal bracket labels do not establish identical exposure or radiometric response. Source camera settings remain in the manifest; camera/view changes, exposure and burn-stage confounding still need review.

All accepted source images are 3008×2000. A fixed camera ROI `[150, 680, 2950, 1100]` removes much of the hardware/reflections, then aspect-preserving padding creates 256×256 targets. There is no per-flame size normalization, artificial colour or synthesized data. Images retain their horizontal camera orientation. This ROI can omit faint signal or flame portions; inspect `montage.jpg` and original stills. HSV largest-component masks provide weak training supervision, not measured flame boundaries. The black padding occupies most of each square; meaningful content lies in a narrow horizontal strip.

## CNN and honest comparison

The model is an approximately one-million-parameter feature MLP and convolutional decoder, with feature conditioning at each upsampling stage. It learns a 64×256 image band at native width, then adds the known black padding to return 256×256. Padding is not extra flame resolution. It predicts the full flame RGB field, rather than a correction restricted around a mean image. An auxiliary weak-mask head and foreground-balanced, multiscale image losses keep the small flame from being overwhelmed by the black background. These choices provide capacity; they do not guarantee physical accuracy.

Splits group whole ignition intervals using day and ignition clock. Exact duplicate feature conditions are joined into the same group, even across ignitions, before splitting. Seeded hash ordering splits within each fuel. Only training data define normalization. The best checkpoint minimizes validation global RGB MAE plus half the flame-region MAE; early stopping waits 50 epochs without improvement. Test images are evaluated after selection. No test-result tuning or physical calibration is claimed.

`ml/artifacts/spice-study/report.json` records training/validation/test errors, comparisons against a same-fuel training mean and **training-only** retrieval, group/ID splits, elapsed training time, and per-feature prediction sensitivity. `*-comparison.jpg` shows recorded / CNN / training-only retrieval side by side. The tracked report is `ml/reports/spice-conditional-v1.json`. MAE/MSE use RGB values scaled to [0,1]; mask IoU is an image-derived proxy. Nearby conditions in distinct groups can still be similar, so this is a small interpolation-oriented benchmark, not proof of generalization to new camera days or fuels.

Retrieval matches fuel exactly, prefers an exact recorded nozzle if available, then ranks normalized numerical feature distance. Its distance is not a probability or confidence interval. A training-only search may have no matching nozzle and returns the nearest available nozzle explicitly. The CNN can receive unseen combinations even within individual recorded ranges; it cannot predict unsupported fuels, arbitrary oxygen/pressure variation, calibrated temperature, heat flux or fire spread.

The initial CPU run took **110.7 seconds**, completed 125 epochs and selected epoch 75 by validation. On 16 test stills from seven held-out groups, flame-region MAE was **0.1606** for the CNN, **0.3870** for the same-fuel training mean and **0.3678** for training-only retrieval. Overall RGB MAE was **0.00494** for the CNN, essentially tied with retrieval (**0.00493**), and weak-mask IoU was only **0.3165**. These small-subset metrics do not establish physical accuracy; visible shape distortions remain. Reported feature sweeps changed predicted pixels for every varying numerical feature within each supported fuel. Sweeps are sensitivity checks, not validated causal effects, and may include unobserved combinations.

## Verification and scaling

```bash
python -m unittest discover -s ml -p 'test_spice.py' -v
```

Checks cover grouped splits, image-ID/feature joins, selected member hashes, retrieval identity/filtering, checkpoint/dataset consistency, API input rejection and PNG output. Data-dependent checks skip when local artifacts are absent; download/preparation/training are required for the full suite.

To scale: add more explicitly linked source days, standardize/record camera settings and spatial scale, manually inspect crops/masks, and reserve whole acquisition days for a stronger evaluation. Increase distinct fuel/flow/nozzle conditions and repeats before adding adjacent frames. Broader features require actual varying, synchronized measurements. Keep retrieval as a baseline and judge foreground/shape errors alongside visual quality before increasing model size.
