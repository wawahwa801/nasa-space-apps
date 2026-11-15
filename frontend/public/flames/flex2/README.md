# FLEX-2 retrieval evidence

This derivative bundle contains 100 prepared colour-image targets from NASA FLEX-2 / PSI-68 across decane, heptane, isooctane, n-octane and toluene. Each target summarizes four selected RGB frames, not four independent experiments. The expanded source subset and audit were prepared in PR #30: https://github.com/wawahwa801/nasa-space-apps/pull/30 .

Source: https://psi.nasa.gov/physci/repo/data/investigations/PSI-68
NASA PSI license: CC0-1.0.

`index.json` records exact test-point IDs, original camera archive/member names and member SHA256, archive versions, fuel categories, measured pre-ignition chamber pressure/temperature, exported PNG hashes, source preparation and display alignment. The image width is 256 pixels; centring translates the detected luminous region without rescaling or recolouring. Weak source signals, saturated highlights, reflections and approximate alignment remain.

The dashboard matches fuel exactly and ranks pressure/temperature differences using the expanded subset's training ranges. All 100 recorded targets are searchable; no CNN, inference server or network data source is needed after these local assets load. Retrieval is experimental evidence, not a causal physical prediction. Per-run oxygen and initial droplet-size labels are not available in this bundle. Source-member hashes are verified during export; obsolete unchanged images from a prior export are removed using that export's index.

Rebuild after preparing verified source data, from the repository root:

```bash
python ml/export_flex2_retrieval.py --data /path/to/flex2-study
node frontend/scripts/check-feature-retrieval.mjs
```

Preparation and source-data acquisition are documented in `ml/FLEX2.md`. Commit the regenerated index and image assets together. No signed download URLs or private data are included.
