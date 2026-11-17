# Automated Historical Sensor Stress Pipeline

**Phase:** P2.2 — Automated Historical Sensor Stress Validation  
**Branch:** `main-phase2`  
**Frozen detector:** `structural_engine/isolated_break_detector_v1/`  
**Detector math:** unchanged; no tuning or edits are performed by this pipeline.

## What it does

1. Discovers and downloads the official World Bank Pink Sheet monthly workbook.
2. Queries World Bank GEM (Data API source 15) for a small, declared set of monthly indicators. Annual or non-monthly records are not relabelled as monthly data.
3. Retrieves five geographically separated USGS ComCat belts from 1980 through 2024, retaining the exact GeoJSON responses and query parameters.
4. Builds monthly commodity log-return series and earthquake inter-event interval series without filling gaps.
5. Applies G0 and then runs the three frozen detector modes: `fast`, `markov_cusum`, and `consensus`.
6. Estimates empirical null alarm rates using the Politis–Romano Stationary Bootstrap on eligible sequences. The bootstrap result is a conditional sequence-level null diagnostic, not a substitute for a domain-specific earthquake point-process null.
7. Measures structural alarms per decade and matches detector events to a predeclared historical macro-shock anchor contract. A positive lead means the detector event was available before the anchor date; a post-anchor detection is a lag, not a warning.
8. Emits an Arabic report, a JSON manifest, SHA-256 inventory, and raw source snapshots.

## Quality gates

- Commodity monthly series: more than 500 contiguous positive monthly prices in the 1980–2024 window, more than 500 log-return observations, valid chronology, and non-degenerate robust scale.
- Seismic inter-event series: at least 87 consecutive event intervals, valid time ordering, and non-degenerate robust scale.
- Monthly seismic counts are retained as a secondary representation; they are not substituted for inter-event intervals.
- No missing-value imputation, interpolation, or artificial extension is permitted.
- Failed sources and rejected series remain visible in the report with explicit reasons.

## Historical shock anchors

The contract at `shock_event_contract.json` fixes four external anchor dates before the detector is run:

- 2008-09-15 — Lehman Brothers bankruptcy / global financial-crisis anchor.
- 2014-06-01 — start-of-decline anchor for the 2014 oil-price shock.
- 2020-03-11 — WHO pandemic characterization anchor.
- 2022-02-24 — start-of-war anchor for the 2022 commodity-supply shock.

These are global calendar anchors, not assertions that every commodity or seismic belt experienced its own shock on that exact date. The report distinguishes pre-anchor lead, same-window detection, and post-anchor lag, and does not claim causal attribution.

## Reproducibility

Run from repository root:

```bash
python -m pip install -r real_data_stress_pipeline/requirements.txt
python -m unittest discover -s real_data_stress_pipeline/tests -v
python -m real_data_stress_pipeline.run_pipeline
```

Configuration is available through environment variables:

- `STRESS_BOOTSTRAP_REPLICATES` (default 99)
- `STRESS_BOOTSTRAP_MEAN_BLOCK_MONTHS` (default 12)
- `STRESS_MIN_COMMODITY_POINTS` (default 501)
- `STRESS_USGS_MIN_MAGNITUDE` (default 4.5)

Raw files are written to `artifacts/real_data_stress/raw/`; they are not committed as source code. GitHub Actions uploads raw responses, report, manifest, and SHA-256 inventory as a versioned artifact. The generated Arabic report is also committed at repository root.

## Interpretation limits

The bootstrap asks how often the frozen detector alarms on stationary-block-resampled versions of each observed sequence. It does not prove that the original sequence is stationary, does not remove every possible historical regime effect, and does not establish a causal mechanism. For earthquake catalogs, event-time interval resampling is only a conditional diagnostic; a defensible seismic null additionally requires point-process/declustering review, catalog-completeness analysis, and sensitivity across magnitude thresholds.

The detector's `CONFIRMED` status remains internal to its own rules. A detected break is not automatically a validated historical shock, an early warning, a forecast, or a probability of future events.
