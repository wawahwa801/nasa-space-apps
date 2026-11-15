# FLEX-2 input-label investigation

This is a source audit for [issue #18](https://github.com/wawahwa801/nasa-space-apps/issues/18). It preserves the existing 100-run retrieval/CNN artifacts. No investigator or other person was contacted.

## Results

| Input or record | Coverage in the 100-run library | Interpretation |
| --- | --- | --- |
| Oxygen and nitrogen mole fraction | 10 runs | Exact heptane run IDs matched to a published 21% O₂ / 79% N₂ experimental condition; not new sensor measurements |
| Initial droplet diameter in mm | 0 verified labels | Backlit acquisition works; exact-run spatial calibration and validated post-deployment initial-size measurement remain missing |
| Calibrated airflow in m/s | 0 verified labels | Nozzle fields have `N/A` units and are not a calibrated velocity |
| Fiber usage flag | 99 source-joined settings | Four `Yes`, 95 `No`; apparatus setting, not a measured combustion output |
| Igniter power setting in watts | 99 source-joined settings | Commanded setting, not flame power or a calibrated delivered-power measurement |
| Test-point / backlit-camera settings | 100 files each | One test-point settings file is rejected because its embedded run ID is `0` |
| Comments / event-log DOCX | 92 / 3 files | 97 event-log DOCX and eight comments files were unavailable or ambiguous in the inventory |

The source audit checks hashes for 395 available files: 100 existing event summaries plus 295 newly inspected settings/comments/log records. It records 105 missing/ambiguous/restricted lookups rather than presenting them as searched documents. The three available DOCX logs (`A109D04`, `A109D07`, `A109D10`) contain screenshots, not searchable paragraphs. Their embedded PNGs were visually inspected: they show igniter parameters, timing and image counts, without the missing gas/diameter/velocity labels. Automatic OCR returned no recognized text and is not used as evidence.

`E183L11` has a test-point settings row of placeholders (embedded ID `0`, fiber code `0`, power `0`). Its settings are excluded from the feature table despite the matching filename. Other independent source records for that run are not silently discarded.

## Published gas-condition join

[Vang & Shaw (2025)](https://doi.org/10.1080/00102202.2025.2595114), experimental-conditions section (PDF page 3), lists the exact heptane identifiers and reports 21% oxygen / 79% nitrogen. All ten selected heptane IDs match both the run identifiers and the NASA fuel category. These are reported experimental conditions with no per-run uncertainty supplied. Other gases are not filled with inferred zeroes.

All ten matched rows have the same reported mixture and fuel, so they do not support training an oxygen-response control. Ninety rows retain missing oxygen/nitrogen labels. `ml/reports/flex2-input-evidence.json` holds the reviewed run lists, source locations and distinctions between reported conditions and measurements.

The same paper calls several E135F/E156F/E159F IDs n-decane, while the PSI inventory places them under n-octane. Seven are in the current library. This unresolved primary-source disagreement is tracked in [issue #33](https://github.com/wawahwa801/nasa-space-apps/issues/33). Both claims are retained in the audit; additional labels from that conflicting list are withheld. The model/dashboard fuel values are not silently relabelled. The existing library's source verification does not independently establish chemical identity.

## Backlit diameter feasibility

`ml/flex2_backlit.py` uses bounded HTTP ZIP ranges to recover three frames at 1.0, 0.5 and 0.1 seconds before the recorded igniter-on event from two runs per fuel. All ten pilots succeeded: 30 original 1024×1024 grayscale TIFFs, with exact camera-A member clocks, ZIP CRC verification, resource IDs/versions, frame hashes and timestamp-file hashes recorded. Three NASA science/engineering PDFs were also acquired and their source hashes recorded.

These timestamps are a feasibility sample, not a validated relaxed-droplet stage. Visual inspection of A184D09 shows an attached liquid bridge in a sampled pre-ignition frame. Its event summary places needle retraction only about 0.12 seconds before igniter-on. A valid initial-size measurement needs deployment-aware frame selection, enough relaxation, reliable segmentation and spatial calibration. Pixel counts or a generic approximate field width must not silently become a verified initial diameter.

[Rasul et al.](https://doi.org/10.1109/TPAMI.2022.3170926), section 1.2, describes backlit FLEX-2 imagery and an approximate field size. [Liu et al.](https://doi.org/10.1016/j.combustflame.2016.05.013), section 3.1, describes the liquid-bridge deployment sequence. Neither inspected source supplies the exact-run calibration and initial-size join needed here. The NASA science/engineering PDFs describe experiment requirements rather than providing that join. Radiometer/LCTF calibration archive names do not establish a spatial calibration for the backlit camera.

## Reproduce and inspect

From a dedicated checkout with the 100-run dataset prepared as described in [FLEX2.md](FLEX2.md):

```bash
python ml/flex2_inputs.py fetch
python ml/flex2_backlit.py
python ml/flex2_inputs.py audit
python -m unittest discover -s ml -p 'test_flex2_inputs.py' -v
```

Source downloads remain local/ignored. The existing Python environment/dependencies suffice; no OCR or PDF-extraction dependency is required by these commands. The source-cache JSON retains original text and missing lookups. The audit exports:

- `ml/reports/flex2-inputs.csv`: one row per run; units in field names, missing measurements blank, source/status columns, uncertainty blank when unsupplied.
- `ml/reports/flex2-input-coverage.json`: hashes, versions, availability, per-row provenance, conflicts, pilot frames and limitations.
- `ml/reports/flex2-input-evidence.json`: reviewed publication assertions and reference locations.

The supported next step is to resolve the flagged source conflicts and obtain verified calibration/deployment-aware diameter measurements. No new inference sliders or retraining are justified by these partial, mostly constant gas labels alone. The CSV and audit make verified apparatus settings available for explicit future ablations without inventing missing physical labels.
